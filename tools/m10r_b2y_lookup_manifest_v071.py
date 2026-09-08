#!/usr/bin/env python3
"""v0.71 corrected runner for the v0.70 lookup/record audit.

The B2Y calibration extraction is an auxiliary file emitted by m10r_sections,
not a sections.csv row. Reuse the v0.70 evidence functions but locate that file
directly. This distinction is itself tooling-only and carries no firmware
semantic conclusion.
"""
from pathlib import Path
import csv
import importlib.util
import sys


def load_v070(repo_root: Path):
    p = repo_root / "tools" / "m10r_b2y_lookup_manifest_v070.py"
    spec = importlib.util.spec_from_file_location("m10r_b2y_lookup_manifest_v070_runtime", p)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load v070 probe")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: m10r_b2y_lookup_manifest_v071.py <sections_dir> <repo_root>")
    sections = Path(sys.argv[1])
    repo_root = Path(sys.argv[2])
    mod = load_v070(repo_root)
    rows = list(csv.DictReader((sections / "sections.csv").open()))
    img_row = next((r for r in rows if r["name"] == "IMG-System"), None)
    if img_row is None:
        raise SystemExit("IMG-System section missing")
    candidates = sorted(sections.glob("*data_calib_B2Y*.bin*"))
    if not candidates:
        raise SystemExit("extracted data_calib_B2Y auxiliary file missing")
    # Prefer the exact established filename if present; otherwise require a unique candidate.
    exact = sections / "074_IMG_Calibration_Data_data_calib_B2Y.bin.bin"
    if exact.exists():
        b2y = exact
    elif len(candidates) == 1:
        b2y = candidates[0]
    else:
        raise SystemExit("ambiguous data_calib_B2Y candidates: " + ",".join(str(p) for p in candidates))
    img = (sections / img_row["file"]).read_bytes()
    print(f"V071_B2Y_AUXILIARY_FILE={b2y}")
    mod.trace_lookup(img)
    mod.record_manifest(repo_root, b2y)
    print("\nOVERALL_VERDICT=LOOKUP_CODE_AND_RECORD_MANIFEST_RECORDED_WITHOUT_FORCED_MAPPING")


if __name__ == "__main__":
    main()
