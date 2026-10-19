#!/usr/bin/env python3
"""Post-edit validation: exact production Java table bytes and entire integer input domain.

This accepts normal source changes to M10RToneDg1A but requires its embedded
MEDIUM and DG payloads to remain byte-identical to 4A. It validates the newly
generated LOW/HIGH payloads against independent frozen SHA-256s and firmware
extractions, then checks every supported tone input using the existing Q15 model.
The settings/default-selection and asynchronous preview lifecycle need separate
application integration tests; this data test makes no claim to execute them.
"""
from __future__ import annotations
import base64
import gzip
import hashlib
import json
from pathlib import Path
import re
import struct

ROOT = Path(__file__).resolve().parent
JAVA = ROOT.parent / "PhotonCamera/app/src/main/java/com/particlesdevs/photoncamera/m10r"
EXPECTED = {
    "low": "136b69127e73cc43c28c0aa7b511f1f3e9b29be139f4d491422f2eb574a49fb0",
    "medium": "2fd6ca209f290c75aa96976b3d7692e55c41a55c0017a063aba9808da3b41a00",
    "high": "0a764cf29d35cd4a4eb7f816e5d128bccaef81b4d5eca991d9b80ab207bd0101",
}
DG_SHA = "9e65de24d52271be0783f4e2728f20f482c0ba43b63159b75033b4a4fc75457d"

def sha(data):
    return hashlib.sha256(data).hexdigest()

def decode(text, regex):
    match = re.search(regex, text, re.S)
    assert match is not None, "Missing expected embedded table"
    encoded = "".join(re.findall(r'"([A-Za-z0-9+/=]+)"', match.group(1)))
    compressed = base64.b64decode(encoded, validate=True)
    return gzip.decompress(compressed), compressed

def evaluate(x, table):
    bounded = max(0, min(20479, x))
    return (bounded * table[bounded >> 1]) >> 15

def main():
    main_path = JAVA / "M10RToneDg1A.java"
    new_path = JAVA / "M10RContrastTables4B.java"
    main_text = main_path.read_text()
    new_text = new_path.read_text()
    blobs = {}
    blobs["medium"], _ = decode(main_text, r"String\[\]\s+TONE_B64\s*=\s*\{(.*?)\};")
    dg_blob, _ = decode(main_text, r"String\[\]\s+DG_B64\s*=\s*\{(.*?)\};")
    assert len(dg_blob) == 65536 and sha(dg_blob) == DG_SHA
    assert dg_blob == (ROOT / "dg_expanded_u16le.bin").read_bytes()
    dg = struct.unpack("<32768H", dg_blob)
    for mode in ("low", "high"):
        pattern = r"class\s+" + mode.capitalize() + r"Holder\s*\{\s*private\s+static\s+final\s+String\[\]\s+B64\s*=\s*\{(.*?)\};"
        blobs[mode], compressed = decode(new_text, pattern)
        assert compressed[:10] == bytes.fromhex("1f8b08000000000002ff"), "Non-deterministic gzip header"
    details = {}
    for mode in ("low", "medium", "high"):
        blob = blobs[mode]
        reference = (ROOT / ("tone_" + mode + "_q15.u32le")).read_bytes()
        assert len(blob) == 40960 and sha(blob) == EXPECTED[mode]
        assert blob == reference
        table = struct.unpack("<10240I", blob)
        original = struct.unpack("<10240I", reference)
        ys = [evaluate(x, table) for x in range(20480)]
        reference_ys = [evaluate(x, original) for x in range(20480)]
        assert ys == reference_ys
        assert all(a <= b for a, b in zip(ys, ys[1:]))
        assert all(0 <= y <= 32767 for y in ys)
        scalar = [dg[y] for y in ys]
        assert all(a <= b for a, b in zip(scalar, scalar[1:]))
        for x in (-2147483648, -1, 20480, 2147483647):
            assert evaluate(x, table) == evaluate(x, original)
        if mode == "low":
            assert all(v == 32768 for v in table)
            assert ys == list(range(20480))
        details[mode] = {
            "sha256": sha(blob), "bytes": len(blob), "entries": len(table),
            "entire_lut_domain_equal_to_firmware_model": True,
            "integer_inputs_compared": len(ys), "boundary_inputs_compared": 4,
            "tone_nondecreasing": True, "tone_then_dg_nondecreasing": True,
            "dg_input_clamps": 0,
        }
    report = {
        "format": "m10r-contrast4b-app-tables-verification-v1", "status": "PASS",
        "sources": {
            str(main_path): sha(main_path.read_bytes()),
            str(new_path): sha(new_path.read_bytes()),
        },
        "tables": details, "medium_payload_byte_identical_to_4a": True,
        "differential_gamma_payload_byte_identical_to_4a": True,
        "differential_gamma_sha256": sha(dg_blob),
        "compression_header_deterministic": True,
        "input_domains": {"normalized_app": [0, 16383], "whole_lut": [0, 20479]},
        "full_asic_parity_claimed": False,
        "settings_default_runtime_executed": False,
        "scope": "Exact embedded asset identity and existing scalar model; application selection/lifecycle belongs to integration regression.",
    }
    (ROOT / "app_tables_verification.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
