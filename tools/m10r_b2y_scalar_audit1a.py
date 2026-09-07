#!/usr/bin/env python3
"""Cross-check the Java reference with Python integer arithmetic and DG deltas.

Reports exact observational ambiguities of the *candidate scalar model*.
Agreement between two software implementations is not Leica hardware parity.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
import subprocess
import tempfile
from pathlib import Path

from m10r_b2y_nonlinear_oracle import load_assets

ROUNDINGS = ("trunc", "half_up", "ties_even")
CLAMPS = ("none", "input14", "each14", "final14")


def q15(sample, gain, mode):
    # Integer division and remainder, independently of the Java bit shifts.
    q, r = divmod(sample * gain, 32768)
    if mode == "half_up":
        q += r >= 16384
    elif mode == "ties_even":
        q += r > 16384 or (r == 16384 and q % 2 == 1)
    return q


def comparison(a, b):
    different = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
    return {"coordinates": len(a), "differences": len(different),
            "max_abs_delta": max(abs(x-y) for x, y in zip(a, b)),
            "first_examples": [{"x": i, "a": a[i], "b": b[i]} for i in different[:8]]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("assets", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--ecj-jar", type=Path, help="optional Eclipse compiler when host has only a JRE")
    args = ap.parse_args()
    a = load_assets(args.assets)
    # Reconstruct independently at every address from firmware coarse/fine bytes.
    anchors = struct.unpack('<2048H', (args.assets/'dg_fl_u16le.bin').read_bytes())
    diffs = (args.assets/'dg_main_u8.bin').read_bytes()
    direct = [anchors[x//16] + sum(diffs[(x//16)*16+1:(x//16)*16+x%16+1]) for x in range(32768)]
    assert tuple(direct) == a.dg

    def tone(x, rounding):
        return q15(x, a.tone[x//2], rounding)

    def candidate(x, order, rounding, clamps):
        v = min(x, 16383) if clamps == "input14" else x
        operations = ((lambda v: tone(v, rounding)), (lambda v: a.dg[v]))
        if order == "dg-tone": operations = tuple(reversed(operations))
        for f in operations:
            v = f(v)
            if clamps == "each14": v = min(v, 16383)
        return min(v, 16383) if clamps == "final14" else v

    expected = list(a.dg)
    tones, curves = {}, {}
    for r in ROUNDINGS:
        tones[r] = [tone(x, r) for x in range(20480)]
        expected.extend(tones[r])
        for order in ("tone-dg", "dg-tone"):
            for clamp in CLAMPS:
                values = [candidate(x, order, r, clamp) for x in range(20480)]
                curves[r, order, clamp] = values
                expected.extend(values)
        for sample in (0, 1, 127, 1024, 16383, 32767):
            for coordinate in (0, 1, 4095, 8192, 14710, 20479):
                expected.append(q15(sample, a.tone[coordinate//2], r))
        for gain in (0, 1, 16384, 32768, 65535):
            for sample in (0, 1, 2, 3, 16383, 32767):
                expected.append(q15(sample, gain, r))
    expected_raw = struct.pack('<' + str(len(expected)) + 'H', *expected)
    root = Path(__file__).resolve().parents[1]
    pkg = Path('com/particlesdevs/photoncamera/m10r')
    with tempfile.TemporaryDirectory(prefix='m10r-scalar-audit-') as td:
        compiler = ['java', '-jar', str(args.ecj_jar.resolve())] if args.ecj_jar else ['javac']
        subprocess.run([*compiler, '--release', '8', '-d', td,
                        str(root/'reference/android'/pkg/'M10RB2YScalarOracle.java'),
                        str(root/'tests/java'/pkg/'B2YScalarProbe.java')], check=True)
        actual = subprocess.check_output(['java', '-cp', td,
                'com.particlesdevs.photoncamera.m10r.B2YScalarProbe', str(args.assets.resolve())])
    if actual != expected_raw:
        raise AssertionError("Java/Python scalar mismatch")
    tr, hu, te = [curves[r, 'tone-dg', 'none'] for r in ROUNDINGS]
    first = next(i for i, v in enumerate(a.dg) if v == 16383)
    starts = {r: next(i for i, v in enumerate(curves[r, 'tone-dg', 'none']) if v == 16383) for r in ROUNDINGS}
    assert first == 14800 and set(starts.values()) == {14710}
    report = {
        "schema": "m10r.b2y.scalar_audit1a.v1",
        "scope": "exact assets + explicit candidate arithmetic; no hardware pixel-parity claim",
        "java_release": 8, "java_python_u16_values_equal": len(expected),
        "compiler": "Eclipse ECJ " + args.ecj_jar.name if args.ecj_jar else "javac",
        "java_python_stream_sha256": hashlib.sha256(actual).hexdigest(),
        "dg_coarse_fine_exact_coordinates": len(direct),
        "dg_first_saturation_coordinate": first,
        "medium_dg_first_saturation_coordinate": starts,
        "rounding_tone_trunc_vs_half_up": comparison(tones['trunc'], tones['half_up']),
        "rounding_after_dg_trunc_vs_half_up": comparison(tr, hu),
        "rounding_tone_half_up_vs_ties_even": comparison(tones['half_up'], tones['ties_even']),
        "rounding_after_dg_half_up_vs_ties_even": comparison(hu, te),
        "tone_product_exact_halfway_coordinates": [x for x in range(20480) if (x*a.tone[x//2]) % 32768 == 16384],
        "clamp_ambiguity_tone_dg": {
            r: {c: comparison(curves[r,'tone-dg','none'], curves[r,'tone-dg',c]) for c in CLAMPS[1:]}
            for r in ROUNDINGS},
        "sample_codes_truncate": [{"coordinate": x, "medium": tones['trunc'][x], "dg": tr[x]}
            for x in [0,1,16,64,128,256,512,1024,2048,2949,4096,8192,12288,14709,14710,14800,16383,20479]],
        "open": ["tone signal and independently DG signal", "physical order", "real input coordinate scaling",
                 "true multiplier rounding", "pixel clamp sequencing", "whether DG output needs another transfer"],
    }
    assert all(v['differences'] == 0 for cases in report['clamp_ambiguity_tone_dg'].values() for v in cases.values())
    assert report['rounding_after_dg_half_up_vs_ties_even']['differences'] == 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ['java_python_u16_values_equal','java_python_stream_sha256',
          'dg_first_saturation_coordinate','medium_dg_first_saturation_coordinate','rounding_after_dg_trunc_vs_half_up']}, indent=2))


if __name__ == '__main__':
    main()
