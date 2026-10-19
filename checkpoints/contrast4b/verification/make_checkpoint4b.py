#!/usr/bin/env python3
"""Create a rerunnable CONTRAST4B source checkpoint; never modify the application.

The overlay is computed against the exact public PhotonCamera archive. Supply
the final delivered APK to bind its 31 native-library hashes after source freeze.
Without --apk the generated manifest explicitly remains an unbound scaffold.
"""
from pathlib import Path
import argparse
import base64
import hashlib
import importlib.util
import json
import re
import shutil
import sys
import tarfile
import tempfile
import zipfile

sys.dont_write_bytecode = True
WORK = Path(__file__).resolve().parents[1]
TEMPLATE = WORK if (WORK / "snapshot_policy.py").is_file() else WORK / "checkpoint4b"
BASE_REPOSITORY = "eszdman/PhotonCamera"
BASE_COMMIT = "4ee108e169496f429c0afa0cc33e57bb6b2ec724"
BASE_ARCHIVE_SHA256 = "cc19cd95990b6125d7cc6711f1805db3d52b499e2ee490d98de15d184c5cd76b"
BASE_ARCHIVE_BYTES = 78659423
VERSION_NAME = "1.48-m10r-contrast4b-test"
VERSION_CODE = 29007
FORMAT_SOURCE_COMMIT = "c060686a4a9538fc612808f32386219c01da63c5"
EXPECTED_NATIVE_COUNT = 31

CONTRAST_FILES = (
    "manifest.json", "provenance.json", "verification.json", "java_generation.json",
    "app_tables_verification.json", "INTEGRATION_NOTES.md", "tone_curve_samples.csv",
    "generate_contrast_java.py", "verify_app_contrast4b.py",
    "prepare_native_probe_fixture4b.py",
    "verify_contrast_assets.py", "m10r_b2y_assets.py",
    "tone_low_q15.u32le", "tone_medium_q15.u32le", "tone_high_q15.u32le",
    "dg_expanded_u16le.bin", "dg_main_u8.bin", "dg_fl_u16le.bin",
    "evidence/M10R_v192_TONE_Q15_GAIN_MODEL_FROZEN.md",
    "evidence/M10R_v198_CONTRAST_ENUM_TONE_SELECTION_FROZEN.md",
    "evidence/M10R_v206_DEFAULT_STILL_CONTRAST_MEDIUM_FROZEN.md",
    "evidence/M10R_v207_b2y_asset_extractor_validation.txt",
    "evidence/M10R_v214_TONE_DUAL_BANK_SELECTION_FROZEN.md",
)
WB_FILES = (
    "WB12MP_INPUT_BOUNDARIES4B.txt",
    "observed_wb_scalar_inputs4b.json",
    "target_cm_source_identity4b.json",
)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=False) + "\n")


def load_policy(template):
    spec = importlib.util.spec_from_file_location(
        "contrast4b_snapshot_policy", template / "snapshot_policy.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_inventory(project, policy):
    result = {}
    for name, path in policy.source_files(project):
        result[name] = {"path": name, "sha256": digest(path), "bytes": path.stat().st_size}
    return result


def upstream_inventory(archive, policy):
    result = {}
    prefix = None
    with tarfile.open(archive) as source:
        for member in source:
            parts = member.name.split("/", 1)
            if prefix is None:
                prefix = parts[0]
            if parts[0] != prefix:
                raise ValueError("Unexpected multiple upstream archive roots")
            if len(parts) != 2 or not parts[1] or not policy.included(parts[1]):
                continue
            name = parts[1]
            policy.relative(name)
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError("Included upstream source is not a regular file: " + name)
            if name in result:
                raise ValueError("Duplicate upstream source path: " + name)
            with source.extractfile(member) as stream:
                value = hashlib.file_digest(stream, "sha256").hexdigest()
            result[name] = {"path": name, "sha256": value, "bytes": member.size}
    return result


def copy(source, destination):
    if not source.is_file() or source.is_symlink():
        raise ValueError("Missing regular checkpoint input: " + str(source))
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def export_evidence(source, destination, aliases, records, record_root):
    """Normalize environment path labels in exported text, retaining input identity."""
    copy(source, destination)
    original = destination.read_bytes()
    exported = original
    if source.suffix.lower() in (".json", ".txt", ".md", ".xml", ".csv"):
        text = original.decode("utf-8")
        for absolute, label in sorted(aliases.items(), key=lambda item: -len(item[0])):
            text = text.replace(absolute, label)
        text = re.sub(r"/workspace/scratch/[A-Za-z0-9_-]+", "<retained-workspace>", text)
        text = re.sub(r"/(?:home|Users)/[^/\s\"'<>]+", "<user-home>", text)
        text = text.replace("/root/", "<user-home>/")
        exported = text.encode("utf-8")
        destination.write_bytes(exported)
    records.append({
        "path": destination.relative_to(record_root).as_posix(),
        "sourceFilename": source.name,
        "originalSha256": sha(original), "originalBytes": len(original),
        "exportedSha256": sha(exported), "exportedBytes": len(exported),
        "environmentPathsNormalized": original != exported,
    })


def git_blob_sha(data):
    header = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.sha1(header + data).hexdigest()


def make_upload_plan(checkpoint, base_tree, destination, prefix, policy):
    """Write local connector payloads only; this function has no network operations."""
    if destination == checkpoint or destination.is_relative_to(checkpoint):
        raise ValueError("Upload plan must remain outside the checkpoint")
    policy.relative(prefix)
    tree = json.loads(base_tree.read_text())
    if tree.get("truncated"):
        raise ValueError("Known GitHub base tree is truncated")
    known_entries = [item for item in tree["tree"] if item["type"] == "blob"]
    known = {item["sha"] for item in known_entries}
    files, entries, unique = [], [], {}
    local_path_findings = []
    for source in sorted(checkpoint.rglob("*")):
        if not source.is_file():
            continue
        if source.is_symlink():
            raise ValueError("Checkpoint contains a symlink: " + str(source))
        name = source.relative_to(checkpoint).as_posix()
        if "__pycache__" in source.parts or source.suffix.lower() in (".pyc", ".pyo"):
            raise ValueError("Checkpoint contains untracked Python cache: " + name)
        data = source.read_bytes()
        blob = git_blob_sha(data)
        try:
            content = data.decode("utf-8")
            is_text = "\0" not in content
        except UnicodeDecodeError:
            content, is_text = None, False
        kind = "reused" if blob in known else ("new_utf8" if is_text else "new_binary")
        path = prefix.rstrip("/") + "/" + name
        item = {"path": path, "sourcePath": name, "mode": "100644", "type": "blob",
                "gitBlobSha1": blob, "sha256": sha(data), "bytes": len(data), "kind": kind}
        files.append(item)
        entry = {"path": path, "mode": "100644", "type": "blob"}
        if kind == "new_utf8":
            entry["content"] = content
        else:
            entry["sha"] = blob
        entries.append(entry)
        if blob not in unique:
            unique[blob] = dict(item, paths=[path])
            if kind == "new_binary":
                unique[blob].update(encoding="base64", content=base64.b64encode(data).decode("ascii"))
        else:
            unique[blob]["paths"].append(path)
        # Do not alter application source to hide an accidental environment dependency.
        # Exported evidence has already had path labels normalized above.
        if kind == "new_utf8":
            pattern = r"/(?:workspace/scratch/[^/\s\"'<>]+|home/[^/\s\"'<>]+|Users/[^/\s\"'<>]+|root)/(?=[A-Za-z0-9_.-])"
            for match in re.finditer(pattern, content):
                local_path_findings.append({"path": name, "offset": match.start()})
            if re.search(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----", content):
                raise ValueError("Checkpoint contains private-key material: " + name)
    if local_path_findings:
        raise ValueError("New checkpoint text contains machine-specific environment paths: "
                         + json.dumps(local_path_findings))

    def stats(items):
        return {"count": len(items), "bytes": sum(item["bytes"] for item in items),
                "maxBytes": max((item["bytes"] for item in items), default=0)}

    summary = {
        "files": stats(files), "uniqueBlobs": stats(list(unique.values())),
        "knownBaseBlobFiles": len(known_entries), "knownBaseUniqueBlobs": len(known),
        "byFileKind": {kind: stats([item for item in files if item["kind"] == kind])
                       for kind in ("reused", "new_utf8", "new_binary")},
        "byUniqueBlobKind": {
            kind: stats([item for item in unique.values() if item["kind"] == kind])
            for kind in ("reused", "new_utf8", "new_binary")},
        "newBinaryOver1MB": [{"sha": item["gitBlobSha1"], "bytes": item["bytes"],
                              "paths": item["paths"]} for item in unique.values()
                             if item["kind"] == "new_binary" and item["bytes"] > 1000000],
        "newEnvironmentPathFindings": local_path_findings,
    }
    plan = {
        "format": "m10r-contrast4b-local-upload-plan-v1",
        "scope": "Read-only local Git blob comparison; no GitHub objects or refs created",
        "checkpointDirectory": str(checkpoint), "destinationPrefix": prefix,
        "knownTreeResponseSha": tree.get("sha"), "knownTreeFileSha256": digest(base_tree),
        "checkpointManifestSha256": digest(checkpoint / "manifest.json"),
        "summary": summary, "files": files,
        "createTreeEntries": entries,
        "newBinaryBlobs": [item for item in unique.values() if item["kind"] == "new_binary"],
        "uploadOrder": [
            "Create each newBinaryBlobs payload using encoding=base64 and verify returned SHA1.",
            "Create a tree using createTreeEntries over the intended existing repository base tree.",
            "New UTF-8 files carry content; reused files and created binary blobs carry SHA1.",
            "Only the separately authorized uploader may create commits or update refs.",
        ],
    }
    write_json(destination, plan)
    return summary


def apk_inventory(path, policy):
    result = []
    seen = set()
    with zipfile.ZipFile(path) as source:
        for info in source.infolist():
            if not info.filename.startswith("lib/") or not info.filename.endswith(".so"):
                continue
            name = info.filename[4:]
            rel = policy.relative(name)
            if len(rel.parts) != 2 or rel.parts[0] not in ("arm64-v8a", "armeabi-v7a"):
                raise ValueError("Unexpected native payload path: " + name)
            if name in seen:
                raise ValueError("Duplicate APK native payload: " + name)
            seen.add(name)
            data = source.read(info)
            result.append({"path": name, "sha256": sha(data), "bytes": len(data)})
    if len(result) != EXPECTED_NATIVE_COUNT:
        raise ValueError("Expected 31 native libraries; found " + str(len(result)))
    return sorted(result, key=lambda item: item["path"])


def source_version(project):
    text = (project / "app/build.gradle").read_text()
    name = re.search(r"\bversionName\s+['\"]([^'\"]+)['\"]", text)
    code = re.search(r"\bversionCode\s+(\d+)", text)
    if name is None or code is None or (name[1], int(code[1])) != (VERSION_NAME, VERSION_CODE):
        raise ValueError("Application is not the expected CONTRAST4B version")
    if "m10rDetail3D" not in text:
        raise ValueError("Missing explicit DETAIL3D Gradle property")


def build_config_evidence(project, explicit, apk_supplied):
    path = explicit or (
        project / "app/build/generated/source/buildConfig/debug/"
        "com/particlesdevs/photoncamera/BuildConfig.java")
    if not path.is_file():
        if explicit:
            raise FileNotFoundError(path)
        return None
    text = path.read_text()
    fields = {}
    for key, expression in (
            ("M10R_DETAIL3D", r"\bM10R_DETAIL3D\s*=\s*(true|false)\s*;"),
            ("M10R_WBSELECTOR3Y", r"\bM10R_WBSELECTOR3Y\s*=\s*(true|false)\s*;"),
            ("VERSION_CODE", r"\bVERSION_CODE\s*=\s*(\d+)\s*;"),
            ("VERSION_NAME", r'\bVERSION_NAME\s*=\s*"([^"]+)"\s*;')):
        match = re.search(expression, text)
        if match is None:
            raise ValueError("Missing compiled BuildConfig field: " + key)
        value = match[1]
        fields[key] = value == "true" if value in ("true", "false") else (
            int(value) if key == "VERSION_CODE" else value)
    if apk_supplied and (
            fields["VERSION_NAME"] != VERSION_NAME or fields["VERSION_CODE"] != VERSION_CODE
            or fields["M10R_DETAIL3D"] is not True or fields["M10R_WBSELECTOR3Y"] is not True):
        raise ValueError("Compiled BuildConfig does not match the delivered checkpoint properties")
    return {
        "sha256": digest(path), "fields": fields,
        "scope": "Recorded generated source; APK internals are validated by the separate packaging review.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=WORK / "PhotonCamera")
    parser.add_argument("--base-archive", type=Path, default=WORK / "deps/photoncamera_4ee108e.tar.gz")
    parser.add_argument("--output", type=Path, default=WORK / "checkpoint4b")
    parser.add_argument("--template-dir", type=Path, default=TEMPLATE)
    parser.add_argument("--contrast-assets", type=Path, default=WORK / "contrast_assets")
    parser.add_argument("--wb-evidence", type=Path,
                        default=WORK.parent / "analysis_wb12mp_inputs4b")
    parser.add_argument("--apk", type=Path)
    parser.add_argument("--build-config", type=Path)
    parser.add_argument("--result-file", type=Path, action="append", default=[])
    parser.add_argument("--verification-script", type=Path, action="append", default=[])
    parser.add_argument("--report-file", type=Path)
    parser.add_argument("--github-base-tree", type=Path,
                        default=WORK / "verification/github_base_tree4b.json")
    parser.add_argument("--upload-plan", type=Path,
                        help="External local upload plan; defaults beside the checkpoint")
    parser.add_argument("--github-prefix", default="checkpoints/contrast4b")
    args = parser.parse_args()
    project, output = args.project.resolve(), args.output.resolve()
    if project == output or output.is_relative_to(project):
        raise ValueError("Checkpoint output must be outside the application project")
    if not project.is_dir():
        raise FileNotFoundError(project)
    source_version(project)
    archive = args.base_archive.resolve()
    if archive.stat().st_size != BASE_ARCHIVE_BYTES or digest(archive) != BASE_ARCHIVE_SHA256:
        raise ValueError("Pinned public PhotonCamera archive size/hash mismatch")
    policy = load_policy(args.template_dir)
    base = upstream_inventory(archive, policy)
    current = source_inventory(project, policy)
    native = apk_inventory(args.apk, policy) if args.apk else []
    apk_hash = digest(args.apk) if args.apk else None
    compiled = build_config_evidence(project, args.build_config, bool(args.apk))
    overlay = []
    removed = []
    for name in sorted(current):
        original = base.get(name)
        if original is None or original["sha256"] != current[name]["sha256"]:
            overlay.append({
                "path": name,
                "baseSha256": original["sha256"] if original else None,
                "sha256": current[name]["sha256"], "bytes": current[name]["bytes"],
            })
    for name in sorted(set(base) - set(current)):
        removed.append({
            "path": name, "baseSha256": base[name]["sha256"], "bytes": base[name]["bytes"],
        })
    assembled = [current[name] for name in sorted(current)]
    inventory_hash = sha(json.dumps(
        assembled, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    output.parent.mkdir(parents=True, exist_ok=True)
    aliases = {
        str(project): "PhotonCamera",
        str(args.contrast_assets.resolve()): "contrast_assets",
        str(args.wb_evidence.resolve()): "wb_evidence",
        str((WORK / "verification").resolve()): "verification",
    }
    evidence_exports = []

    with tempfile.TemporaryDirectory(prefix="checkpoint4b-stage-", dir=output.parent) as temporary:
        stage = Path(temporary)
        for name in ("prepare_project.py", "snapshot_policy.py", "README.md", ".gitignore"):
            copy(args.template_dir / name, stage / name)
        for item in overlay:
            source = project / policy.relative(item["path"])
            copy(source, stage / "overlay" / policy.relative(item["path"]))
            if digest(stage / "overlay" / item["path"]) != item["sha256"]:
                raise ValueError("Source changed during copy: " + item["path"])
        for name in CONTRAST_FILES:
            export_evidence(args.contrast_assets / name, stage / "contrast_assets" / name,
                            aliases, evidence_exports, stage)
        for name in WB_FILES:
            export_evidence(args.wb_evidence / name, stage / "wb_evidence" / name,
                            aliases, evidence_exports, stage)
        copy(args.template_dir / "wb_evidence/verify_bounded_wb4b.py",
             stage / "wb_evidence/verify_bounded_wb4b.py")
        copy(Path(__file__).resolve(), stage / "verification/make_checkpoint4b.py")
        for name in ("test-agent.gradle", "shadow-tests.gradle"):
            source = WORK / "verification" / name
            if source.is_file():
                copy(source, stage / "verification" / name)
        script_names = {"make_checkpoint4b.py"}
        for path in args.verification_script:
            if path.name in script_names or path.suffix.lower() != ".py":
                raise ValueError("Invalid or duplicate verification helper: " + path.name)
            script_names.add(path.name)
            export_evidence(path, stage / "verification" / path.name, aliases, evidence_exports, stage)
        result_names = set()
        for path in args.result_file:
            if path.name in result_names or "_m10r_capture1b" in path.name.lower():
                raise ValueError("Duplicate or private-capture result filename: " + path.name)
            if path.suffix.lower() not in (".json", ".txt", ".md", ".xml", ".csv"):
                raise ValueError("Result files must be text evidence: " + path.name)
            result_names.add(path.name)
            export_evidence(path, stage / "results" / path.name, aliases, evidence_exports, stage)
        if compiled is not None:
            write_json(stage / "results/compiled_build_config.json", compiled)
        status = "source_and_delivered_apk_bound" if args.apk else "source_scaffold_apk_pending"
        snapshot = {
            "revision": "CONTRAST4B", "status": "PASS",
            "scope": "Stable source inventory, exact base diff and optional delivered native payload identity",
            "snapshotStatus": status, "baseArchiveSha256": BASE_ARCHIVE_SHA256,
            "baseSourceFiles": len(base), "overlayFiles": len(overlay),
            "removedSourceFiles": len(removed), "assembledSourceFiles": len(assembled),
            "assembledSourceInventorySha256": inventory_hash,
            "nativeLibraries": len(native), "apkSha256": apk_hash,
            "requiredBuildProperties": {"m10rDetail3D": "true"},
            "androidTestsExecutedByThisGenerator": False,
            "phoneValidationExecutedByThisGenerator": False,
        }
        write_json(stage / "results/source_snapshot.json", snapshot)
        if args.report_file:
            export_evidence(args.report_file, stage / "REPORT.txt", aliases, evidence_exports, stage)
        else:
            (stage / "REPORT.txt").write_text(
                "M10-R CONTRAST4B reproducible source checkpoint\n"
                "Version: " + VERSION_NAME + " / " + str(VERSION_CODE) + "\n"
                "Snapshot status: " + status + "\n"
                "Assembled source/resource/test files: " + str(len(assembled)) + "\n"
                "Changed or added files: " + str(len(overlay)) + "\n"
                "Removed upstream source files: " + str(len(removed)) + "\n"
                "Required build property: -Pm10rDetail3D=true\n"
                "Delivered native-library hashes: " + str(len(native)) + "\n\n"
                "The generator verified source/base identity and source stability. "
                "It did not run Android tests or physical-phone validation.\n"
                "Recorded table verification, source provenance and optional final validation "
                "records retain their own scopes under contrast_assets/ and results/.\n"
                "WB source observations remain bounded evidence; they do not change "
                "photographic WB authority or resolve phone statistics calibration.\n"
            )
        write_json(stage / "results/evidence_exports.json", {
            "scope": "Hashes before and after normalizing environment path labels in exported evidence; application overlay bytes are unchanged",
            "records": evidence_exports,
        })
        if current != source_inventory(project, policy):
            raise ValueError("Application source changed during snapshot; rerun after source freeze")
        auxiliary = []
        for path in sorted(stage.rglob("*")):
            if not path.is_file():
                continue
            name = path.relative_to(stage).as_posix()
            if name.startswith("overlay/"):
                continue
            if path.suffix.lower() in (".so", ".apk", ".jks", ".keystore", ".dng"):
                raise ValueError("Forbidden binary/private checkpoint artifact: " + name)
            auxiliary.append({"path": name, "sha256": digest(path), "bytes": path.stat().st_size})
        manifest = {
            "revision": "CONTRAST4B", "versionName": VERSION_NAME, "versionCode": VERSION_CODE,
            "snapshotStatus": status,
            "baseRepository": BASE_REPOSITORY, "baseCommit": BASE_COMMIT,
            "baseArchiveSha256": BASE_ARCHIVE_SHA256, "baseArchiveBytes": BASE_ARCHIVE_BYTES,
            "checkpointFormatSourceCommit": FORMAT_SOURCE_COMMIT,
            "buildProperties": {"m10rDetail3D": "true"},
            "apkSha256": apk_hash,
            "apkBytes": args.apk.stat().st_size if args.apk else None,
            "overlay": overlay, "removedSourceFiles": removed,
            "assembledSourceFiles": assembled,
            "assembledSourceInventorySha256": inventory_hash,
            "nativeLibraries": native,
            "nativeStrategy": "extract the 31 hash-verified libraries from the delivered CONTRAST4B APK",
            "checkpointFiles": auxiliary,
            "excludedFromSnapshot": [
                "build outputs and local state",
                "unused app/src/main/cpp/ncnn static toolchain payloads",
                "native binaries; restored only from the hash-verified delivered APK",
                "private photographs and full M10R_CAPTURE1B sidecars",
                "signing material",
                "full firmware; only bounded table/metadata evidence is included",
            ],
        }
        write_json(stage / "manifest.json", manifest)
        # Replace only generator-owned checkpoint content. Source/APK inputs stay read-only.
        output.mkdir(parents=True, exist_ok=True)
        for name in ("overlay", "contrast_assets", "wb_evidence", "results", "verification"):
            destination = output / name
            if destination.exists():
                shutil.rmtree(destination)
            source = stage / name
            if source.is_dir():
                shutil.copytree(source, destination)
        for name in ("prepare_project.py", "snapshot_policy.py", "README.md",
                     ".gitignore", "REPORT.txt", "manifest.json"):
            shutil.copyfile(stage / name, output / name)
    print(json.dumps({
        "status": "PASS", "output": str(output), "snapshotStatus": status,
        "overlayFiles": len(overlay), "removedSourceFiles": len(removed),
        "assembledSourceFiles": len(assembled), "nativeLibraries": len(native),
        "assembledSourceInventorySha256": inventory_hash,
    }, indent=2))
    if args.github_base_tree.is_file():
        plan_path = (args.upload_plan or output.parent / (output.name + "_upload_plan.json")).resolve()
        summary = make_upload_plan(output, args.github_base_tree, plan_path,
                                   args.github_prefix, policy)
        print(json.dumps({"uploadPlan": str(plan_path), "summary": summary}, indent=2))
    elif args.upload_plan:
        raise FileNotFoundError(args.github_base_tree)


if __name__ == "__main__":
    main()
