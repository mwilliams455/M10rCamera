#!/usr/bin/env python3
"""Reproduce the independent 4B native-test resource from exact local inputs.

No raster is generated or modified. DNG inputs are 64 sparse RGGB quad samples,
averaging the greens only to form representative renderer inputs, not AMaZE replay.
"""
from __future__ import annotations
import base64
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent / "PhotonCamera"
WORKSPACE = ROOT.parent.parent
DNG = WORKSPACE / "upload/02-60819.dng"
SIDECAR = WORKSPACE / "upload/IMG_20261019_195120_M10R_CAPTURE1B.json"
OUTPUT = PROJECT / "app/src/test/resources/contrast4b/native_probe4a.json"
DNG_SHA = "7c845978bef32c94f908e09893ade83412f961064e1a4c18fb209b4701c80838"
SIDECAR_SHA = "b66588ac8338b6a8934544c1064c4208cc875803abe0d8a3a769d44b17d86d07"
TONE_SHA = "2fd6ca209f290c75aa96976b3d7692e55c41a55c0017a063aba9808da3b41a00"
DG_SHA = "9e65de24d52271be0783f4e2728f20f482c0ba43b63159b75033b4a4fc75457d"

def sha(data):
    return hashlib.sha256(data).hexdigest()

def encode(data):
    output = io.BytesIO()
    with gzip.GzipFile(fileobj=output, mode="wb", filename="", compresslevel=9, mtime=0) as stream:
        stream.write(data)
    return base64.b64encode(output.getvalue()).decode("ascii")

def main():
    data = DNG.read_bytes()
    assert sha(data) == DNG_SHA
    assert sha(SIDECAR.read_bytes()) == SIDECAR_SHA
    assert data[:4] == b"II\x2a\x00"
    offset = struct.unpack_from("<I", data, 4)[0]
    n = struct.unpack_from("<H", data, offset)[0]
    tags = {}
    sizes = {1:1, 2:1, 3:2, 4:4, 5:8, 7:1, 9:4, 10:8, 11:4, 12:8}
    for i in range(n):
        p = offset + 2 + 12 * i
        tag, kind, count = struct.unpack_from("<HHI", data, p)
        length = sizes[kind] * count
        start = p + 8 if length <= 4 else struct.unpack_from("<I", data, p + 8)[0]
        blob = data[start:start + length]
        if kind in (1, 7):
            value = list(blob)
        elif kind in (3, 4, 9):
            value = list(struct.unpack("<" + {3:"H", 4:"I", 9:"i"}[kind] * count, blob))
        elif kind in (5, 10):
            values = struct.unpack("<" + ("I" if kind == 5 else "i") * count * 2, blob)
            value = [values[j*2] / values[j*2+1] for j in range(count)]
        else:
            continue
        tags[tag] = value
    for tag, expected in {
        256:[4096], 257:[3072], 258:[16], 259:[1], 262:[32803],
        273:[4881], 277:[1], 278:[3072], 279:[25165824], 284:[1],
        33421:[2,2], 33422:[0,1,1,2], 50713:[2,2],
        50714:[64,64,64,64], 50717:[1023], 50829:[0,0,3072,4096],
    }.items():
        assert tags.get(tag) == expected, ("Unexpected DNG layout", tag, tags.get(tag))
    samples = []
    def raw(x, y):
        return struct.unpack_from("<H", data, 4881 + 2 * (y * 4096 + x))[0]
    def corrected(value):
        return max(0, min(959, value - 64))
    def round_ratio(numerator, denominator):
        return (2 * numerator + denominator) // (2 * denominator)
    for gy in range(8):
        y = ((2 * gy + 1) * 3072 // 16) & ~1
        for gx in range(8):
            x = ((2 * gx + 1) * 4096 // 16) & ~1
            r, g0, g1, b = raw(x,y), raw(x+1,y), raw(x,y+1), raw(x+1,y+1)
            rgb = [
                round_ratio(corrected(r) * 65535, 959),
                round_ratio((corrected(g0) + corrected(g1)) * 65535, 1918),
                round_ratio(corrected(b) * 65535, 959),
            ]
            samples.append({"x":x, "y":y, "rggb":[r,g0,g1,b], "rgbU16":rgb})
    medium = (ROOT / "tone_medium_q15.u32le").read_bytes()
    dg = (ROOT / "dg_expanded_u16le.bin").read_bytes()
    assert sha(medium) == TONE_SHA and sha(dg) == DG_SHA
    golden = PROJECT / "app/src/test/resources/sourcewhite3n/guardoff3l_colour_baseline.json"
    cpp = PROJECT / "app/src/main/cpp/m10rRender.cpp"
    wrapper = PROJECT / "app/src/main/cpp/m10rExposure1B.cpp"
    host = ROOT.parent / "verification/shadow-build"
    result = {
        "format":"m10r-contrast4b-native-probe-v1",
        "mediumSha256":TONE_SHA, "dgSha256":DG_SHA,
        "mediumU32leGzipBase64":encode(medium),
        "dgU16leGzipBase64":encode(dg),
        "existingGoldenResource":"/sourcewhite3n/guardoff3l_colour_baseline.json",
        "existingGoldenSha256":sha(golden.read_bytes()),
        "baselineScope":"Unchanged 4A MEDIUM/DG assets and inherited native pixel arithmetic; no 3I optimization or full-RAW demosaic assertion.",
        "nativeRendererSourceSha256":sha(cpp.read_bytes()),
        "nativeExposureWrapperSourceSha256":sha(wrapper.read_bytes()),
        "hostJni": {
            "wrapperSha256":sha((host / "libdngCreator.so").read_bytes()),
            "rendererSha256":sha((host / "libdngCreator3n.so").read_bytes()),
            "export":"Java_com_particlesdevs_photoncamera_m10r_M10RExposureNative1B_nativeRender",
            "forwardsTo":"Java_com_particlesdevs_photoncamera_m10r_M10RNativeRenderer_nativeProcessTile",
        },
        "sparseDng": {
            "filename":DNG.name, "sha256":DNG_SHA, "sidecarSha256":SIDECAR_SHA,
            "width":4096, "height":3072, "pattern":"RGGB",
            "stripOffset":4881, "black":64, "white":1023,
            "inverseScale":1.0, "sampleCount":len(samples),
            "sampling":"Centers of a fixed 8x8 grid, aligned to even CFA coordinates.",
            "normalization":"Clamp each black-subtracted code to 0..959; average the two corrected greens; scale RGB to 0..65535 with nearest half-up rounding.",
            "demosaicParityClaimed":False,
            "samples":samples,
        },
    }
    encoded = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if sys.argv[1:] == ["--check"]:
        assert OUTPUT.read_bytes() == encoded
    elif not sys.argv[1:]:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_bytes(encoded)
    else:
        raise SystemExit("usage: prepare_native_probe_fixture4b.py [--check]")
    print(json.dumps({"status":"PASS", "path":str(OUTPUT), "bytes":len(encoded),
                      "sha256":sha(encoded), "sampleCount":len(samples),
                      "existingGoldenSha256":result["existingGoldenSha256"]}, indent=2))

if __name__ == "__main__":
    main()
