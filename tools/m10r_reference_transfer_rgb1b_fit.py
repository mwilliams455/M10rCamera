#!/usr/bin/env python3
"""Score RGB1B full-RGB domain-placement candidates against a same-capture Leica M10-R JPEG.

No exposure, affine, gamma, tone-power, white-balance or colour fit is performed.
All five renders share one DNG decode, one CA9/ColorSpec path, the exact recovered
MEDIUM->DG assets and one geometry. Only nonlinear-domain placement differs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
import rawpy

from m10r_reference_order_fit import alignment_search, metadata_status
from m10r_reference_transfer_rgb_fit import crop_to_reference, metrics

MODES = (
    "linear_luma_linear_gain_oetf",
    "linear_luma_linear_gain_identity",
    "linear_luma_encoded_gain_identity",
    "encoded_luma_linear_gain_oetf",
    "encoded_luma_encoded_gain_identity",
)


def load_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        return np.asarray(im.convert("RGB"), dtype=np.uint8)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jpg", type=Path, required=True)
    ap.add_argument("--dng", type=Path, required=True)
    ap.add_argument("--ll-oetf", type=Path, required=True)
    ap.add_argument("--ll-identity", type=Path, required=True)
    ap.add_argument("--le-identity", type=Path, required=True)
    ap.add_argument("--el-oetf", type=Path, required=True)
    ap.add_argument("--ee-identity", type=Path, required=True)
    ap.add_argument("--sample", required=True)
    ap.add_argument("--metadata-json", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    with Image.open(args.jpg) as im:
        jpg = np.asarray(ImageOps.exif_transpose(im).convert("RGB"), dtype=np.uint8)

    renders = {
        MODES[0]: load_rgb(args.ll_oetf),
        MODES[1]: load_rgb(args.ll_identity),
        MODES[2]: load_rgb(args.le_identity),
        MODES[3]: load_rgb(args.el_oetf),
        MODES[4]: load_rgb(args.ee_identity),
    }
    shapes = {x.shape for x in renders.values()}
    if len(shapes) != 1:
        raise RuntimeError(f"RGB1B renderer geometries differ: {shapes}")

    with rawpy.imread(str(args.dng)) as r:
        rgb = r.postprocess(use_camera_wb=True, no_auto_bright=True, gamma=(1, 1),
                            output_bps=16, output_color=rawpy.ColorSpace.raw)
        white = float(r.white_level)
        raw_flip = int(r.sizes.flip)
    proxy = rgb[..., 1].astype(np.float32) * (white / 65535.0)
    del rgb
    oriented, scores = alignment_search(proxy, jpg)
    score, rot_k, dx, dy = scores[0]
    raw_h, raw_w = oriented.shape
    jpg_h, jpg_w = jpg.shape[:2]

    cropped = {}
    for name, render in renders.items():
        cropped[name] = crop_to_reference(render, rot_k, dx, dy, raw_w, raw_h, jpg_w, jpg_h)
    cropped_shapes = {x.shape for x in cropped.values()}
    if len(cropped_shapes) != 1:
        raise RuntimeError(f"RGB1B crop geometries differ: {cropped_shapes}")

    h, w = next(iter(cropped.values())).shape[:2]
    ref = np.asarray(Image.fromarray(jpg).resize((w, h), Image.Resampling.LANCZOS), dtype=np.uint8)
    if h > 12 and w > 12:
        ref = ref[3:-3, 3:-3]
        cropped = {k: v[3:-3, 3:-3] for k, v in cropped.items()}

    result = {
        "sample": args.sample,
        "metadata": metadata_status(args.metadata_json),
        "fit_freedom": "NONE: no gamma/exposure/affine/WB/colour/tone fit",
        "upstream": "RENDER_PARITY1A C: WhiteLevel clamp + CA9 neutral clip + frozen Leica ColorSpec",
        "nonlinear": "exact recovered MEDIUM -> Differential Gamma; shared gain; fixed 14-bit 0..16383 coordinate mapping",
        "encoded_domain": "bounded standard sRGB code values derived from linear sRGB before MEDIUM->DG/gain placement",
        "modes": {
            MODES[0]: "linear luma -> MEDIUM/DG -> gain linear RGB -> sRGB OETF (RGB1A ON)",
            MODES[1]: "linear luma -> MEDIUM/DG -> gain linear RGB -> identity (RGB1A OFF control)",
            MODES[2]: "linear luma -> MEDIUM/DG -> gain bounded encoded sRGB -> identity",
            MODES[3]: "bounded encoded-sRGB luma -> MEDIUM/DG -> gain linear RGB -> sRGB OETF",
            MODES[4]: "bounded encoded-sRGB luma -> MEDIUM/DG -> gain bounded encoded sRGB -> identity",
        },
        "alignment": {
            "score": float(score), "rot90_k": int(rot_k), "dx": int(dx), "dy": int(dy),
            "rawpy_flip": raw_flip, "raw_oriented": [raw_w, raw_h], "jpeg": [jpg_w, jpg_h],
            "comparison": [int(ref.shape[1]), int(ref.shape[0])],
        },
        "metrics": {name: metrics(cand, ref) for name, cand in cropped.items()},
    }
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
