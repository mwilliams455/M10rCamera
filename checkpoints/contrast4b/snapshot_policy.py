"""Shared source-snapshot policy for checkpoint generation and reconstruction."""
from pathlib import Path, PurePosixPath
import os

EXCLUDED_DIRECTORIES = {
    ".git", ".gradle", ".idea", ".cxx", ".externalNativeBuild", ".kotlin",
    "__pycache__", ".pytest_cache", "build", "captures", "upload", "sidecars",
}
EXCLUDED_PREFIXES = (
    "app/src/main/cpp/ncnn",
    "app/src/main/jniLibs",
    "key", "keys", "deps",
)
EXCLUDED_FILENAMES = {
    ".DS_Store", "local.properties", "signing.properties", "keystore.properties",
}
EXCLUDED_SUFFIXES = {
    ".so", ".a", ".o", ".class", ".dex", ".apk", ".apks", ".aab",
    ".jks", ".keystore", ".hprof", ".pyc", ".pyo",
    ".dng", ".nef", ".cr2", ".cr3", ".arw", ".raf",
}


def relative(value):
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "\\" in value:
        raise ValueError("Unsafe checkpoint path: " + value)
    return Path(*path.parts)


def excluded_directory(value):
    path = PurePosixPath(value)
    if any(part in EXCLUDED_DIRECTORIES for part in path.parts):
        return True
    return any(value == prefix or value.startswith(prefix + "/")
               for prefix in EXCLUDED_PREFIXES)


def included(value):
    path = PurePosixPath(value)
    if excluded_directory(value):
        return False
    if path.name in EXCLUDED_FILENAMES or path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    if "_m10r_capture1b" in path.name.lower() or path.name.startswith("hs_err_pid"):
        return False
    return True


def source_files(root):
    """Yield regular included files without traversing excluded trees."""
    root = Path(root)
    for current, directories, files in os.walk(root):
        parent = Path(current).relative_to(root)
        directories[:] = sorted(
            name for name in directories
            if not excluded_directory((parent / name).as_posix()))
        for name in sorted(files):
            path = Path(current) / name
            rel = path.relative_to(root).as_posix()
            if not included(rel):
                continue
            if path.is_symlink():
                raise ValueError("Included source symlink requires explicit handling: " + rel)
            if path.is_file():
                yield rel, path
