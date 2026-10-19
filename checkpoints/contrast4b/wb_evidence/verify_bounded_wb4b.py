#!/usr/bin/env python3
"""Verify bounded WB evidence consistency without private captures or full firmware.

The original byte-to-source claims are documented in the source review. This
portable check verifies preserved inline records, derived scalar values, and the
complete 132-byte calibration record reconstructed from the declared words.
"""
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import hashlib
import json
import re
import struct

ROOT = Path(__file__).resolve().parent


def s16(value):
    return (value + 32768) % 65536 - 32768


def divide_zero(value, denominator):
    result = abs(value) // denominator
    return -result if value < 0 else result


def ir_to_p34(value):
    if value < 0:
        return value
    if value < 260:
        numerator = (value - 160) * 46
    elif value < 360:
        numerator = value * 42
    elif value < 600:
        numerator = value * 34
    elif value < 1000:
        numerator = value * 30
    else:
        numerator = value * 21
    return s16(divide_zero(numerator, 10))


def main():
    scalar = json.loads((ROOT / "observed_wb_scalar_inputs4b.json").read_text())
    for case in scalar["cases"]:
        fields = case["observed_source_fields"]
        for key, tag in (("F_plus_0x96_IR", 6), ("F_plus_0x98_ExtBv", 17)):
            field = fields[key]
            raw = bytes.fromhex(field["descriptor_hex"])
            assert len(raw) == 12
            assert struct.unpack_from("<HHI", raw) == (tag, 8, 1)
            assert struct.unpack_from("<h", raw, 8)[0] == field["value"]
            assert raw[10:].hex() == field["ignored_padding_hex"]
        ir, ext = fields["F_plus_0x96_IR"]["value"], fields["F_plus_0x98_ExtBv"]["value"]
        derived = case["derived_using_IMG_30_22_23_34_packet_contract"]
        assert derived["P_plus_0x34"] == ir_to_p34(ir)
        assert derived["P_plus_0x36"] == ext
        assert derived["s16_P36_minus_P34"] == s16(ext - ir_to_p34(ir))
        assert derived["is_observed_runtime_packet"] is False
        assert case["exif_identity"]["software"] == "10.20.27.20"
    target = json.loads((ROOT / "target_cm_source_identity4b.json").read_text())
    chunks = []
    renderer = (ROOT.parent / "overlay/app/src/main/java/com/particlesdevs/"
                "photoncamera/m10r/M10RNativeRenderer.java").read_text()
    for record in target["records"]:
        values = record["coefficient_words_s32"]
        exponent = record["scale_exponent_word"]
        tail = record["trailing_word_at_record_plus_0x28"]
        chunks.append(struct.pack("<11i", *values, exponent, tail))
        exact = [Decimal(value) / Decimal(2 ** exponent) for value in values]
        rounded = [float(value.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP))
                   for value in exact]
        assert rounded == record["renderer_literals"]
        match = re.search(record["renderer_symbol"] + r"\s*=\s*\{([^}]+)\}", renderer)
        assert match is not None
        current = [float(part.strip()) for part in match[1].split(",") if part.strip()]
        assert current == rounded
    chunks.append(struct.pack("<11i", *target["third_record_raw_words"]))
    reconstructed = b"".join(chunks)
    assert len(reconstructed) == 132
    assert hashlib.sha256(reconstructed).hexdigest() == target["extracted_sha256"]
    assert hashlib.md5(reconstructed).hexdigest() == target["section_metadata"]["toc_md5"]
    print(json.dumps({
        "status": "PASS", "scalarFixtures": len(scalar["cases"]),
        "targetCoefficientLiterals": 18,
        "reconstructedCalibrationRecordBytes": len(reconstructed),
        "calibrationSha256": target["extracted_sha256"],
        "currentRendererCoefficientsMatch": True,
        "originalPrivateImageBytesRechecked": False,
        "originalFirmwareExecuted": False,
        "photographicWbPromoted": False,
    }, indent=2))


if __name__ == "__main__":
    main()
