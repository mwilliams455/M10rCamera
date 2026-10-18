#!/usr/bin/env python3
"""Assemble the exact delivered sources over the pinned public PhotonCamera base."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import tarfile
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def relative(value):
    path = Path(value)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Unsafe manifest path: ' + value)
    return path

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--base-archive', type=Path)
    parser.add_argument('--apk', type=Path, help='Delivered COLOURCACHE3H APK, verified before native payload extraction')
    parser.add_argument('--output', type=Path, default=ROOT / 'PhotonCamera')
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    for entry in manifest['overlay']:
        path = ROOT / 'overlay' / relative(entry['path'])
        if digest(path) != entry['sha256']:
            raise ValueError('Overlay hash mismatch: ' + entry['path'])
    if args.verify_only:
        print('Verified', len(manifest['overlay']), 'overlay files')
        return
    if args.output.exists():
        raise FileExistsError('Output already exists; choose a new --output directory')
    if args.apk and digest(args.apk) != manifest['apkSha256']:
        raise ValueError('APK hash mismatch; expected the delivered COLOURCACHE3H test APK')
    with tempfile.TemporaryDirectory(prefix='m10r-checkpoint-') as temporary:
        temporary = Path(temporary)
        archive = args.base_archive
        if archive is None:
            archive = temporary / 'base.tar.gz'
            url = 'https://codeload.github.com/' + manifest['baseRepository'] + '/tar.gz/' + manifest['baseCommit']
            with urllib.request.urlopen(url, timeout=60) as response, archive.open('wb') as output:
                shutil.copyfileobj(response, output)
        if digest(archive) != manifest['baseArchiveSha256']:
            raise ValueError('Pinned base archive hash mismatch')
        with tarfile.open(archive) as source:
            source.extractall(temporary / 'base', filter='data')
        base = next((temporary / 'base').iterdir())
        for entry in manifest['overlay']:
            target = base / relative(entry['path'])
            expected = entry['baseSha256']
            if expected is not None and (not target.is_file() or digest(target) != expected):
                raise ValueError('Base file mismatch: ' + entry['path'])
            if expected is None and target.exists():
                raise ValueError('New overlay file unexpectedly exists: ' + entry['path'])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / 'overlay' / relative(entry['path']), target)
        for entry in manifest['assembledSourceFiles']:
            if digest(base / relative(entry['path'])) != entry['sha256']:
                raise ValueError('Assembled source mismatch: ' + entry['path'])
        if args.apk:
            with zipfile.ZipFile(args.apk) as apk:
                for entry in manifest['nativeLibraries']:
                    path = relative(entry['path'])
                    content = apk.read('lib/' + path.as_posix())
                    if hashlib.sha256(content).hexdigest() != entry['sha256']:
                        raise ValueError('Native library hash mismatch: ' + str(path))
                    target = base / 'app/src/main/jniLibs' / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(content)
        shutil.copytree(base, args.output)
    print('Verified', len(manifest['assembledSourceFiles']), 'source files in', args.output)
    if args.apk:
        print('Extracted and verified', len(manifest['nativeLibraries']), 'native libraries')
    else:
        print('Source-only assembly; pass --apk to include the verified native runtime for an APK build')

if __name__ == '__main__':
    main()
