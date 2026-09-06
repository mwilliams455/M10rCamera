#!/usr/bin/env python3
"""M10-R v0.59 Bayer-domain direct-WB headroom discriminator.

This removes the principal approximation in v0.58: WB is applied to the native
CFA mosaic before demosaic.  The CFA samples come from rawpy's decoded visible
mosaic; the project's independent v2.42 work remains the pixel-exact Leica SOF3
validation baseline.  One deterministic OpenCV Bayer demosaic is then held
identical for every candidate.

This is still an empirical parity discriminator, not proof of the hidden B2Y
multiplier, demosaic, rounding, clipping, or physical stage order.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps
import rawpy

from m10r_wb_headroom_fit_v058 import load_meta, q8_from_asn, fit_eval

UNITY_Q8 = 256
B2Y_14BIT_MAX = 16383


def pattern_letters(raw_pattern: np.ndarray, color_desc) -> str:
    if raw_pattern is None or raw_pattern.shape != (2, 2):
        raise RuntimeError(f"unsupported CFA pattern {raw_pattern!r}")
    if isinstance(color_desc, bytes):
        desc = color_desc.decode("ascii", "replace")
    else:
        desc = str(color_desc)
    return "".join(desc[int(i)].upper() for i in raw_pattern.reshape(-1))


def cv_code(pattern: str) -> int:
    table = {
        "RGGB": cv2.COLOR_BayerRG2RGB,
        "BGGR": cv2.COLOR_BayerBG2RGB,
        "GRBG": cv2.COLOR_BayerGR2RGB,
        "GBRG": cv2.COLOR_BayerGB2RGB,
    }
    if pattern not in table:
        raise RuntimeError(f"unsupported Bayer pattern {pattern}")
    return table[pattern]


def orient_libraw(arr: np.ndarray, flip: int) -> np.ndarray:
    """Apply LibRaw/dcraw orientation codes used by rawpy sizes.flip.

    The M10-R public fixtures encountered here use 0 and 6.  Keep explicit
    support for the standard dcraw 3/5/6 rotations and reject anything else so
    orientation can never be silently guessed.
    """
    if flip == 0:
        return arr
    if flip == 3:
        return np.rot90(arr, 2)
    if flip == 5:
        return np.rot90(arr, 1)  # 90 degrees CCW
    if flip == 6:
        return np.rot90(arr, 3)  # 90 degrees CW
    raise RuntimeError(f"unsupported rawpy/LibRaw flip code {flip}")


def load_v058_alignment(path: Path, sample: str) -> dict:
    obj = json.loads(path.read_text())
    rows = obj.get("samples", obj if isinstance(obj, list) else [])
    for r in rows:
        if str(r.get("sample")) == str(sample):
            return r["alignment"]
    raise RuntimeError(f"sample {sample} alignment absent from {path}")


def gain_lut_for_rawpy(gains_rgb: np.ndarray, color_desc) -> np.ndarray:
    if isinstance(color_desc, bytes):
        desc = color_desc.decode("ascii", "replace")
    else:
        desc = str(color_desc)
    lut = np.empty(len(desc), dtype=np.uint32)
    for i, c in enumerate(desc.upper()):
        if c == "R": lut[i] = int(gains_rgb[0])
        elif c == "G": lut[i] = int(gains_rgb[1])
        elif c == "B": lut[i] = int(gains_rgb[2])
        else: raise RuntimeError(f"unsupported rawpy color_desc entry {c!r} in {desc!r}")
    return lut


def apply_wb_cfa(mosaic: np.ndarray, colors: np.ndarray, lut: np.ndarray,
                 rounding: str, ceiling: int) -> np.ndarray:
    out = np.empty(mosaic.shape, dtype=np.uint16)
    strip = 256
    for y in range(0, mosaic.shape[0], strip):
        ys = slice(y, min(y + strip, mosaic.shape[0]))
        p = mosaic[ys].astype(np.uint32) * lut[colors[ys]]
        if rounding == "trunc":
            v = p >> 8
        elif rounding == "nearest":
            v = (p + 128) >> 8
        else:
            raise ValueError(rounding)
        out[ys] = np.minimum(v, np.uint32(ceiling)).astype(np.uint16)
    return out


def patch_positions(jpg: np.ndarray, margin=96, block=48, step=72):
    h, w = jpg.shape[:2]
    pos = []
    for y0 in range(margin, h-margin-block+1, step):
        for x0 in range(margin, w-margin-block+1, step):
            jb = jpg[y0:y0+block, x0:x0+block].astype(np.float64)/255.0
            lum = 0.2126*jb[:,:,0] + 0.7152*jb[:,:,1] + 0.0722*jb[:,:,2]
            if float(lum.std()) <= 0.12:
                pos.append((y0, x0, jb.reshape(-1,3).mean(0)))
    return pos


def preclip_patch_metric(mosaic_crop: np.ndarray, color_crop: np.ndarray,
                         lut: np.ndarray, y0: int, x0: int, block: int) -> tuple[float,float]:
    m = mosaic_crop[y0:y0+block, x0:x0+block].astype(np.uint32)
    c = color_crop[y0:y0+block, x0:x0+block]
    vals = (m * lut[c]).astype(np.float64) / UNITY_Q8
    return float(np.percentile(vals, 95.0)), float(vals.mean())


def candidate_patch_rgb(mosaic: np.ndarray, colors: np.ndarray, lut: np.ndarray,
                        rounding: str, ceiling: int, code: int, raw_flip: int,
                        k: int, dx: int, dy: int, jh: int, jw: int,
                        positions, block: int) -> np.ndarray:
    wb = apply_wb_cfa(mosaic, colors, lut, rounding, ceiling)
    rgb = cv2.cvtColor(wb, code)
    del wb
    # rawpy postprocess (used by v0.58) presents the LibRaw orientation already
    # applied. Reproduce that transform before reusing v0.58's residual rot/crop.
    rgb = orient_libraw(rgb, raw_flip)
    rgb = np.rot90(rgb, k)
    crop = rgb[dy:dy+jh, dx:dx+jw, :]
    if crop.shape[:2] != (jh, jw):
        raise RuntimeError(f"candidate crop mismatch {crop.shape[:2]} vs {(jh,jw)}")
    return np.asarray([
        crop[y0:y0+block, x0:x0+block].reshape(-1,3).mean(0) / float(ceiling)
        for y0, x0, _ in positions
    ], dtype=np.float64)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jpg", type=Path, required=True)
    ap.add_argument("--dng", type=Path, required=True)
    ap.add_argument("--metadata-json", type=Path, required=True)
    ap.add_argument("--v058-json", type=Path, required=True)
    ap.add_argument("--sample", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    meta, asn = load_meta(args.metadata_json)
    align = load_v058_alignment(args.v058_json, args.sample)
    k, dx, dy = int(align["rot90_k"]), int(align["dx"]), int(align["dy"])

    with Image.open(args.jpg) as im:
        jpg = np.asarray(ImageOps.exif_transpose(im).convert("RGB"), dtype=np.uint8)
    jh, jw = jpg.shape[:2]

    with rawpy.imread(str(args.dng)) as r:
        mosaic = r.raw_image_visible.copy()
        colors = r.raw_colors_visible.copy()
        raw_pattern = None if r.raw_pattern is None else r.raw_pattern.copy()
        color_desc = bytes(r.color_desc)
        raw_wb = np.asarray(r.camera_whitebalance, dtype=np.float64)
        white = int(r.white_level)
        black = [float(x) for x in r.black_level_per_channel]
        sizes = {"raw_width":int(r.sizes.raw_width), "raw_height":int(r.sizes.raw_height),
                 "width":int(r.sizes.width), "height":int(r.sizes.height),
                 "top_margin":int(r.sizes.top_margin), "left_margin":int(r.sizes.left_margin),
                 "flip":int(r.sizes.flip)}

    raw_flip = sizes["flip"]
    pattern = pattern_letters(raw_pattern, color_desc)
    code = cv_code(pattern)
    gains, gain_source = q8_from_asn(asn, raw_wb)
    lut = gain_lut_for_rawpy(gains, color_desc)

    schema_ok = (mosaic.shape == (5208, 7872) and pattern == "GBRG" and
                 white == 15000 and max(abs(x) for x in black) == 0.0)

    oriented_m = np.rot90(orient_libraw(mosaic, raw_flip), k)
    oriented_c = np.rot90(orient_libraw(colors, raw_flip), k)
    mcrop = oriented_m[dy:dy+jh, dx:dx+jw]
    ccrop = oriented_c[dy:dy+jh, dx:dx+jw]
    if mcrop.shape != (jh, jw):
        raise RuntimeError(f"native CFA crop mismatch {mcrop.shape} vs {(jh,jw)} after flip={raw_flip}; v0.58 geometry not transferable")

    block = 48
    positions = patch_positions(jpg, block=block)
    if not positions:
        raise RuntimeError("no usable patches")
    jmean = np.asarray([p[2] for p in positions], dtype=np.float64)
    metrics = np.asarray([
        preclip_patch_metric(mcrop, ccrop, lut, y0, x0, block)
        for y0, x0, _ in positions
    ], dtype=np.float64)
    q95, pmean = metrics[:,0], metrics[:,1]

    train = (q95 < white*0.72) & (jmean.max(1) < 0.92) & (jmean.mean(1) > 0.02)
    test = (q95 > white*0.92) & (jmean.mean(1) > 0.04) & (jmean.min(1) < 0.995)

    result = {
        "sample": args.sample,
        "metadata": meta,
        "alignment": {**align, "native_cfa_libraw_flip_applied":raw_flip},
        "raw": {"shape":list(mosaic.shape), "sizes":sizes, "white_level":white,
                "black_level_per_channel":black, "raw_pattern_indices":raw_pattern.tolist(),
                "color_desc":color_desc.decode("ascii","replace"), "pattern_letters":pattern,
                "schema_matches_pixel_exact_fixture":schema_ok,
                "cfa_source":"rawpy raw_image_visible; independent project v2.42 Leica SOF3 decoder is the pixel-exact validation baseline",
                "demosaic_proxy":"OpenCV bilinear-family Bayer conversion, identical for all candidates",
                "b2y_14bit_max":B2Y_14BIT_MAX},
        "wb": {"asn":asn, "rawpy_camera_whitebalance":raw_wb.tolist(),
               "gain_q8_rgb":gains.tolist(), "gain_source":gain_source,
               "unity_code":256, "known_driver_limit_exclusive":2048},
        "patches": {"usable":len(positions), "train":int(train.sum()), "test":int(test.sum()),
                    "preclip_q95_range":[float(q95.min()),float(q95.max())],
                    "preclip_mean_range":[float(pmean.min()),float(pmean.max())]},
        "fits": {}
    }

    if not schema_ok:
        result["error"] = "public DNG does not match established M10-R CFA schema"
    elif train.sum() < 24 or test.sum() < 10:
        result["error"] = "insufficient train/test highlight patches"
    else:
        for cname, ceiling in (("dng_white",white),("b2y_14bit",B2Y_14BIT_MAX)):
            for rounding in ("trunc","nearest"):
                x = candidate_patch_rgb(mosaic, colors, lut, rounding, ceiling, code,
                                        raw_flip, k, dx, dy, jh, jw, positions, block)
                result["fits"][f"{cname}|{rounding}"] = fit_eval(x, jmean, train, test)
        for rounding in ("trunc","nearest"):
            a=result["fits"][f"dng_white|{rounding}"]["rgb_rmse"]
            b=result["fits"][f"b2y_14bit|{rounding}"]["rgb_rmse"]
            result.setdefault("headroom_delta",{})[rounding]=a-b
        for cname in ("dng_white","b2y_14bit"):
            t=result["fits"][f"{cname}|trunc"]["rgb_rmse"]
            n=result["fits"][f"{cname}|nearest"]["rgb_rmse"]
            result.setdefault("rounding_delta",{})[cname]=n-t

    args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
