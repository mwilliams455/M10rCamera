#!/usr/bin/env python3
"""Verify exact M10-R contrast assets against B2Y and current embedded assets.

Writes only into this script's directory. This is a table/operator comparison,
not a claim that the complete Leica ASIC pipeline has been reconstructed.
"""
from __future__ import annotations
import base64
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

sys.dont_write_bytecode = True
import m10r_b2y_assets as extractor

ROOT = Path(__file__).resolve().parent
EXPECTED = {
    "low": "136b69127e73cc43c28c0aa7b511f1f3e9b29be139f4d491422f2eb574a49fb0",
    "medium": "2fd6ca209f290c75aa96976b3d7692e55c41a55c0017a063aba9808da3b41a00",
    "high": "0a764cf29d35cd4a4eb7f816e5d128bccaef81b4d5eca991d9b80ab207bd0101",
}
DG_SHA = "9e65de24d52271be0783f4e2728f20f482c0ba43b63159b75033b4a4fc75457d"
NAMES = tuple(EXPECTED)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def inflate_java(text, name):
    match = re.search(r"String\[\]\s+" + name + r"_B64\s*=\s*\{(.*?)\};", text, re.S)
    if match is None:
        raise AssertionError("Missing original embedded array: " + name)
    encoded = "".join(re.findall(r'"([A-Za-z0-9+/=]+)"', match.group(1)))
    return gzip.decompress(base64.b64decode(encoded, validate=True))

def tone(x, table):
    xx = max(0, min(20479, x))
    return (xx * table[xx >> 1]) >> 15

def stats(values):
    steps = [b - a for a, b in zip(values, values[1:])]
    return {
        "min": min(values), "max": max(values),
        "first": values[0], "last": values[-1],
        "downward_steps": sum(x < 0 for x in steps),
        "plateau_steps": sum(x == 0 for x in steps),
        "minimum_step": min(steps), "maximum_step": max(steps),
    }

def diff_stats(a, b):
    delta = [y - x for x, y in zip(a, b)]
    maximum = max(abs(d) for d in delta)
    at = [i for i, d in enumerate(delta) if abs(d) == maximum]
    return {
        "different_inputs": sum(d != 0 for d in delta),
        "higher_inputs": sum(d > 0 for d in delta),
        "lower_inputs": sum(d < 0 for d in delta),
        "minimum_delta": min(delta), "maximum_delta": max(delta),
        "mean_signed_delta": sum(delta) / len(delta),
        "maximum_absolute_delta": maximum,
        "first_maximum_absolute_delta_input": at[0],
        "last_maximum_absolute_delta_input": at[-1],
    }

def main():
    provenance = json.loads((ROOT / "provenance.json").read_text())
    source = Path(provenance["source_b2y_section"]).read_bytes()
    assert sha(source) == provenance["source_b2y_sha256"]
    records = extractor.parse_records(source)
    banks0 = extractor.occurrences(records, 0x19)
    banks1 = extractor.occurrences(records, 0x1A)
    assert len(banks0) >= 3 and len(banks1) >= 3

    java_path = Path(provenance["comparison_java"])
    java_bytes = java_path.read_bytes()
    assert sha(java_bytes) == provenance["comparison_java_sha256"], "Baseline source changed"
    java_text = java_bytes.decode("utf-8")
    original_tone = inflate_java(java_text, "TONE")
    original_dg = inflate_java(java_text, "DG")
    assert sha(original_tone) == EXPECTED["medium"]
    assert sha(original_dg) == DG_SHA

    tables, table_details = {}, {}
    for i, name in enumerate(NAMES):
        filename = "tone_" + name + "_q15.u32le"
        blob = (ROOT / filename).read_bytes()
        assert len(blob) == 40960
        assert sha(blob) == EXPECTED[name]
        assert blob == extractor.active_blob(source, banks0[i], 40960, name + " bank0")
        bank1 = extractor.active_blob(source, banks1[i], 40960, name + " bank1")
        assert blob == bank1, name + " TBL0/TBL1 differ"
        values = struct.unpack("<10240I", blob)
        tables[name] = values
        table_details[name] = {
            "file": filename, "bytes": len(blob), "sha256": sha(blob),
            "gain_min_q15": min(values), "gain_max_q15": max(values),
            "gain_min": min(values) / 32768, "gain_max": max(values) / 32768,
            "table_entries": len(values), "unique_gains": len(set(values)),
            "tbl0_record_index": banks0[i].index, "tbl0_payload_offset": banks0[i].payload_offset,
            "tbl1_record_index": banks1[i].index, "tbl1_payload_offset": banks1[i].payload_offset,
            "tbl0_equals_tbl1": True,
        }
    assert all(v == 32768 for v in tables["low"])
    assert (ROOT / "tone_medium_q15.u32le").read_bytes() == original_tone
    dg_bytes = (ROOT / "dg_expanded_u16le.bin").read_bytes()
    assert sha(dg_bytes) == DG_SHA and dg_bytes == original_dg
    dg = struct.unpack("<32768H", dg_bytes)

    tone_curves = {name: [tone(x, tables[name]) for x in range(20480)] for name in NAMES}
    scalar_curves = {
        name: [dg[max(0, min(32767, y))] for y in tone_curves[name]] for name in NAMES
    }
    assert tone_curves["low"] == list(range(20480))
    domains = {}
    for name, end in [("current_app_normalized_input", 16383), ("complete_tone_lut_domain", 20479)]:
        n = end + 1
        domains[name] = {
            "input_first": 0, "input_last": end, "input_count": n,
            "tone_outputs": {m: stats(tone_curves[m][:n]) for m in NAMES},
            "tone_then_dg_scalar_outputs": {m: stats(scalar_curves[m][:n]) for m in NAMES},
            "tone_then_dg_scalar_differences": {
                b + "_minus_" + a: diff_stats(scalar_curves[a][:n], scalar_curves[b][:n])
                for a, b in [("low", "medium"), ("medium", "high"), ("low", "high")]
            },
            "dg_input_clamps": {
                m: sum(y < 0 or y > 32767 for y in tone_curves[m][:n]) for m in NAMES
            },
        }

    headers = ["input_x", "input_fraction_of_16383", "within_current_app_input"]
    for name in NAMES:
        headers += [name + "_gain_q15", name + "_tone_x", name + "_tone_then_dg_x"]
    def row(x):
        out = [x, x / 16383, x <= 16383]
        for name in NAMES:
            out += [tables[name][x >> 1], tone_curves[name][x], scalar_curves[name][x]]
        return out
    sample_x = [0, 1, 2, 64, 164, 410, 819, 1638, 2949, 4096, 5898, 8192,
                12287, 14745, 15564, 16383, 16384, 18432, 20479]
    for filename, xs in [
        ("tone_curve_samples.csv", sample_x),
        ("tone_curve_full_domain.csv", range(20480)),
    ]:
        with (ROOT / filename).open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(headers)
            writer.writerows(row(x) for x in xs)

    source_files = []
    for entry in provenance["sources"]:
        data = (ROOT / entry["path"]).read_bytes()
        source_files.append(dict(entry, bytes=len(data), sha256=sha(data)))
    verification = {
        "format": "m10r-contrast-assets-verification-v1", "status": "PASS",
        "source_b2y": {
            "path": provenance["source_b2y_section"], "bytes": len(source),
            "sha256": sha(source), "record_count": len(records),
        },
        "comparison_java": {
            "path": str(java_path), "sha256": sha(java_bytes),
            "embedded_medium_bytes_identical": True,
            "embedded_dg_bytes_identical": True,
        },
        "tables": table_details,
        "differential_gamma": {"bytes": len(dg_bytes), "sha256": sha(dg_bytes)},
        "operator": {
            "tone": "xx=clamp(x,0,20479); y=(xx*table[xx>>1])>>15",
            "tone_then_dg_scalar_model": "dg[clamp(tone(x),0,32767)]",
            "application": "Exact existing scalar integer operators, before colour matrices, gamut, ToneCal and detail.",
            "current_app_input": "toInputLuma normalizes/clamps working luma to 0..16383",
            "low_is_identity_at_tone_stage": True,
            "low_bypasses_differential_gamma": False,
            "complete_asic_parity_claimed": False,
        },
        "domains": domains,
        "sample_rows": [dict(zip(headers, row(x))) for x in sample_x],
        "source_files": source_files,
    }
    (ROOT / "verification.json").write_text(json.dumps(verification, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "status": verification["status"], "tables": table_details,
        "original_medium_identical": True, "original_dg_identical": True,
        "domains": domains,
        "samples": [
            {"x": x, "low": scalar_curves["low"][x], "medium": scalar_curves["medium"][x],
             "high": scalar_curves["high"][x]} for x in [164, 819, 1638, 2949, 4096, 8192, 12287, 16383, 20479]
        ],
    }, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
