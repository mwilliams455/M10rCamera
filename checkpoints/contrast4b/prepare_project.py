#!/usr/bin/env python3
"""Reconstruct CONTRAST4B from a pinned public base and the complete source overlay."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import tarfile
import tempfile
import urllib.request
import zipfile

from snapshot_policy import relative, source_files

ROOT = Path(__file__).resolve().parent


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def entries_by_path(entries, label):
    result = {}
    for entry in entries:
        path = entry["path"]
        relative(path)
        if path in result:
            raise ValueError("Duplicate " + label + " path: " + path)
        result[path] = entry
    return result


def verify_file(root, entry, label):
    path = root / relative(entry["path"])
    if not path.is_file() or path.is_symlink():
        raise ValueError(label + " missing regular file: " + entry["path"])
    if path.stat().st_size != entry["bytes"] or digest(path) != entry["sha256"]:
        raise ValueError(label + " hash/size mismatch: " + entry["path"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true",
                        help="Verify committed overlay and evidence without downloading anything")
    parser.add_argument("--require-apk-manifest", action="store_true",
                        help="Require a finalized delivered-APK/native hash manifest")
    parser.add_argument("--base-archive", type=Path)
    parser.add_argument("--apk", type=Path,
                        help="Delivered CONTRAST4B APK; verified before native extraction")
    parser.add_argument("--output", type=Path, default=ROOT / "PhotonCamera")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "manifest.json").read_text())
    if (manifest["revision"], manifest["versionName"], manifest["versionCode"]) != (
            "CONTRAST4B", "1.48-m10r-contrast4b-test", 29007):
        raise ValueError("Unexpected checkpoint identity")
    overlays = entries_by_path(manifest["overlay"], "overlay")
    assembled = entries_by_path(manifest["assembledSourceFiles"], "assembled source")
    removed = entries_by_path(manifest.get("removedSourceFiles", []), "removed source")
    auxiliary = entries_by_path(manifest.get("checkpointFiles", []), "checkpoint")
    natives = entries_by_path(manifest["nativeLibraries"], "native library")
    for entry in overlays.values():
        verify_file(ROOT / "overlay", entry, "Overlay")
    for entry in auxiliary.values():
        verify_file(ROOT, entry, "Checkpoint")
    if set(overlays) & set(removed):
        raise ValueError("A source path cannot be both overlaid and removed")
    if args.require_apk_manifest and (
            not manifest.get("apkSha256") or len(natives) != 31):
        raise ValueError("Checkpoint still awaits the delivered APK's 31 native-library hashes")
    if args.verify_only:
        print(json.dumps({
            "status": "PASS", "revision": manifest["revision"],
            "overlayFiles": len(overlays), "checkpointFiles": len(auxiliary),
            "snapshotStatus": manifest["snapshotStatus"],
            "apkManifestPresent": bool(manifest.get("apkSha256")),
        }, indent=2))
        return
    if args.output.exists():
        raise FileExistsError("Output exists; choose a new --output directory")
    if args.apk:
        if not manifest.get("apkSha256"):
            raise ValueError("Manifest has not been bound to the delivered APK yet")
        if digest(args.apk) != manifest["apkSha256"]:
            raise ValueError("APK hash mismatch; use the exact delivered CONTRAST4B APK")
        if len(natives) != 31:
            raise ValueError("Expected 31 delivered native libraries")

    with tempfile.TemporaryDirectory(prefix="m10r-contrast4b-") as temporary:
        temporary = Path(temporary)
        archive = args.base_archive
        if archive is None:
            archive = temporary / "base.tar.gz"
            url = ("https://codeload.github.com/" + manifest["baseRepository"]
                   + "/tar.gz/" + manifest["baseCommit"])
            with urllib.request.urlopen(url, timeout=60) as response, archive.open("wb") as output:
                shutil.copyfileobj(response, output)
        if digest(archive) != manifest["baseArchiveSha256"]:
            raise ValueError("Pinned PhotonCamera base archive hash mismatch")
        extraction = temporary / "base"
        with tarfile.open(archive) as source:
            source.extractall(extraction, filter="data")
        roots = list(extraction.iterdir())
        if len(roots) != 1 or not roots[0].is_dir():
            raise ValueError("Unexpected upstream archive root layout")
        base = roots[0]
        for entry in removed.values():
            target = base / relative(entry["path"])
            if not target.is_file() or digest(target) != entry["baseSha256"]:
                raise ValueError("Removed base file mismatch: " + entry["path"])
            target.unlink()
        for entry in overlays.values():
            target = base / relative(entry["path"])
            expected = entry["baseSha256"]
            if expected is not None:
                if not target.is_file() or digest(target) != expected:
                    raise ValueError("Base source hash mismatch: " + entry["path"])
            elif target.exists():
                raise ValueError("New overlay file unexpectedly exists in base: " + entry["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / "overlay" / relative(entry["path"]), target)
        actual_paths = {name for name, _ in source_files(base)}
        if actual_paths != set(assembled):
            raise ValueError("Assembled source inventory mismatch: " + json.dumps({
                "missing": sorted(set(assembled) - actual_paths),
                "extra": sorted(actual_paths - set(assembled)),
            }))
        for entry in assembled.values():
            verify_file(base, entry, "Assembled source")
        if args.apk:
            with zipfile.ZipFile(args.apk) as apk:
                actual_natives = {
                    info.filename[4:] for info in apk.infolist()
                    if info.filename.startswith("lib/") and info.filename.endswith(".so")
                }
                if actual_natives != set(natives):
                    raise ValueError("APK native-library inventory mismatch")
                for entry in natives.values():
                    content = apk.read("lib/" + entry["path"])
                    if len(content) != entry["bytes"] or (
                            hashlib.sha256(content).hexdigest() != entry["sha256"]):
                        raise ValueError("Native payload mismatch: " + entry["path"])
                    target = base / "app/src/main/jniLibs" / relative(entry["path"])
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(content)
        shutil.copytree(base, args.output)
    print(json.dumps({
        "status": "PASS", "output": str(args.output),
        "assembledSourceFiles": len(assembled),
        "nativeLibrariesExtracted": len(natives) if args.apk else 0,
        "buildProperties": manifest["buildProperties"],
    }, indent=2))
    if not args.apk:
        print("Source-only assembly. Supply --apk for the verified native runtime needed by an APK build.")


if __name__ == "__main__":
    main()
