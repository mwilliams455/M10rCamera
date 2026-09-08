#!/usr/bin/env python3
"""Score RGB1A OETF ON/OFF renders against a same-capture Leica M10-R JPEG.

No exposure, affine, gamma, tone-power, white-balance or colour fit is performed.
Geometry is recovered with the already-used RAW/JPEG alignment oracle; the two
candidate images share exactly the same geometry and upstream rendering.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
import rawpy

from m10r_reference_order_fit import alignment_search, metadata_status


def encoded_luma(rgb: np.ndarray) -> np.ndarray:
    x = rgb.astype(np.float64)
    return 0.2126*x[..., 0] + 0.7152*x[..., 1] + 0.0722*x[..., 2]


def hsv_hs(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x = rgb.astype(np.float64) / 255.0
    mx = x.max(axis=-1); mn = x.min(axis=-1); d = mx - mn
    s = np.where(mx > 1e-12, d / mx, 0.0)
    h = np.zeros_like(mx)
    nz = d > 1e-12
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    mr = nz & (mx == r); mg = nz & (mx == g); mb = nz & (mx == b)
    h[mr] = np.mod((g[mr] - b[mr]) / d[mr], 6.0)
    h[mg] = (b[mg] - r[mg]) / d[mg] + 2.0
    h[mb] = (r[mb] - g[mb]) / d[mb] + 4.0
    return h * 60.0, s, mx


def srgb_eotf(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def lab_d65(rgb: np.ndarray) -> np.ndarray:
    l = srgb_eotf(rgb.astype(np.float64) / 255.0)
    xyz = l @ np.array([[0.4124564, 0.3575761, 0.1804375],
                        [0.2126729, 0.7151522, 0.0721750],
                        [0.0193339, 0.1191920, 0.9503041]], dtype=np.float64).T
    xyz /= np.array([0.95047, 1.0, 1.08883])
    delta = 6.0 / 29.0
    def f(t):
        return np.where(t > delta**3, np.cbrt(t), t/(3*delta**2) + 4.0/29.0)
    fx, fy, fz = f(xyz[..., 0]), f(xyz[..., 1]), f(xyz[..., 2])
    return np.stack([116*fy-16, 500*(fx-fy), 200*(fy-fz)], axis=-1)


def masked_error(cand: np.ndarray, ref: np.ndarray, mask: np.ndarray) -> dict:
    if not np.any(mask):
        return {"pixels": 0, "rgb_rmse": None, "rgb_mae": None,
                "luma_rmse": None, "luma_mae": None}
    d = cand[mask].astype(np.float64) - ref[mask].astype(np.float64)
    cy, ry = encoded_luma(cand)[mask], encoded_luma(ref)[mask]
    return {
        "pixels": int(mask.sum()),
        "rgb_rmse": float(np.sqrt(np.mean(d*d))),
        "rgb_mae": float(np.mean(np.abs(d))),
        "luma_rmse": float(np.sqrt(np.mean((cy-ry)**2))),
        "luma_mae": float(np.mean(np.abs(cy-ry))),
    }


def patch_errors(cand: np.ndarray, ref: np.ndarray, block: int = 20) -> dict:
    h, w = ref.shape[:2]
    neutral, colourful = [], []
    for y in range(block, h-block+1, block):
        for x in range(block, w-block+1, block):
            rb = ref[y-block:y, x-block:x].reshape(-1, 3).mean(0)
            cb = cand[y-block:y, x-block:x].reshape(-1, 3).mean(0)
            mx, mn = float(rb.max()), float(rb.min())
            sat = (mx-mn)/mx if mx > 1e-9 else 0.0
            lum = 0.2126*rb[0] + 0.7152*rb[1] + 0.0722*rb[2]
            err = float(np.linalg.norm(cb-rb))
            if 8 < lum < 247 and sat <= 0.08:
                neutral.append(err)
            if 16 < lum < 240 and 0.18 <= sat <= 0.65:
                colourful.append(err)
    def rec(v):
        return {"count": len(v), "rgb_euclidean_mean": float(np.mean(v)) if v else None,
                "rgb_euclidean_median": float(np.median(v)) if v else None}
    return {"neutral": rec(neutral), "moderately_colourful": rec(colourful), "block": block}


def metrics(cand: np.ndarray, ref: np.ndarray) -> dict:
    d = cand.astype(np.float64) - ref.astype(np.float64)
    cy, ry = encoded_luma(cand), encoded_luma(ref)
    per = {}
    for i, name in enumerate("RGB"):
        q = d[..., i]
        per[name] = {"bias": float(q.mean()), "rmse": float(np.sqrt(np.mean(q*q))),
                     "mae": float(np.mean(np.abs(q)))}

    rh, rs, rv = hsv_hs(ref); ch, cs, cv = hsv_hs(cand)
    hm = (rs >= 0.12) & (rv >= 0.08) & (rv <= 0.98)
    hd = np.abs(ch-rh); hd = np.minimum(hd, 360.0-hd)
    sm = (rv >= 0.05) & (rv <= 0.99)

    de = np.linalg.norm(lab_d65(cand) - lab_d65(ref), axis=-1)
    refmax = ref.max(axis=-1); refmin = ref.min(axis=-1)
    masks = {
        "shadow": ry < 64.0,
        "midtone": (ry >= 64.0) & (ry < 192.0),
        "highlight": ry >= 192.0,
        "neutral_pixels": (refmax-refmin) <= 12,
        "colourful_pixels": ((refmax-refmin) >= 32) & (ry >= 20) & (ry <= 235),
    }
    clipping = {}
    for i, name in enumerate("RGB"):
        clipping[name] = {
            "candidate_255": int((cand[..., i] == 255).sum()),
            "reference_255": int((ref[..., i] == 255).sum()),
            "candidate_255_reference_below_250": int(((cand[..., i] == 255) & (ref[..., i] < 250)).sum()),
            "candidate_0_reference_above_5": int(((cand[..., i] == 0) & (ref[..., i] > 5)).sum()),
        }
    return {
        "encoded_rgb_rmse": float(np.sqrt(np.mean(d*d))),
        "encoded_rgb_mae": float(np.mean(np.abs(d))),
        "luma_rmse": float(np.sqrt(np.mean((cy-ry)**2))),
        "luma_mae": float(np.mean(np.abs(cy-ry))),
        "per_channel": per,
        "color_residual_rgb_euclidean_mean": float(np.linalg.norm(d, axis=-1).mean()),
        "hue_error_deg_mean": float(hd[hm].mean()) if hm.any() else None,
        "hue_error_deg_median": float(np.median(hd[hm])) if hm.any() else None,
        "saturation_error_abs_mean": float(np.abs(cs-rs)[sm].mean()) if sm.any() else None,
        "saturation_error_abs_median": float(np.median(np.abs(cs-rs)[sm])) if sm.any() else None,
        "delta_e76_mean": float(de.mean()),
        "delta_e76_median": float(np.median(de)),
        "delta_e76_p90": float(np.percentile(de, 90)),
        "bins": {k: masked_error(cand, ref, v) for k, v in masks.items()},
        "patches": patch_errors(cand, ref),
        "highlight_channel_clipping": clipping,
    }


def crop_to_reference(render: np.ndarray, rot_k: int, dx: int, dy: int,
                      raw_w: int, raw_h: int, jpg_w: int, jpg_h: int) -> np.ndarray:
    r = np.rot90(render, rot_k)
    rh, rw = r.shape[:2]
    sx, sy = rw / raw_w, rh / raw_h
    x0 = int(round(dx*sx)); y0 = int(round(dy*sy))
    x1 = int(round((dx+jpg_w)*sx)); y1 = int(round((dy+jpg_h)*sy))
    x0=max(0,min(rw-1,x0)); y0=max(0,min(rh-1,y0)); x1=max(x0+1,min(rw,x1)); y1=max(y0+1,min(rh,y1))
    return r[y0:y1, x0:x1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jpg", type=Path, required=True)
    ap.add_argument("--dng", type=Path, required=True)
    ap.add_argument("--on", type=Path, required=True)
    ap.add_argument("--off", type=Path, required=True)
    ap.add_argument("--sample", required=True)
    ap.add_argument("--metadata-json", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    with Image.open(args.jpg) as im:
        jpg = np.asarray(ImageOps.exif_transpose(im).convert("RGB"), dtype=np.uint8)
    with Image.open(args.on) as im: on = np.asarray(im.convert("RGB"), dtype=np.uint8)
    with Image.open(args.off) as im: off = np.asarray(im.convert("RGB"), dtype=np.uint8)
    if on.shape != off.shape: raise RuntimeError("ON/OFF renderer geometry differs")

    with rawpy.imread(str(args.dng)) as r:
        rgb = r.postprocess(use_camera_wb=True, no_auto_bright=True, gamma=(1,1),
                            output_bps=16, output_color=rawpy.ColorSpace.raw)
        white = float(r.white_level); raw_flip = int(r.sizes.flip)
    proxy = rgb[..., 1].astype(np.float32) * (white / 65535.0)
    del rgb
    oriented, scores = alignment_search(proxy, jpg)
    score, rot_k, dx, dy = scores[0]
    raw_h, raw_w = oriented.shape
    jpg_h, jpg_w = jpg.shape[:2]

    on = crop_to_reference(on, rot_k, dx, dy, raw_w, raw_h, jpg_w, jpg_h)
    off = crop_to_reference(off, rot_k, dx, dy, raw_w, raw_h, jpg_w, jpg_h)
    if on.shape != off.shape: raise RuntimeError("ON/OFF crop geometry differs")
    h, w = on.shape[:2]
    ref = np.asarray(Image.fromarray(jpg).resize((w, h), Image.Resampling.LANCZOS), dtype=np.uint8)
    # Trim a small edge where resize/crop phase is least reliable.
    if h > 12 and w > 12:
        on, off, ref = on[3:-3,3:-3], off[3:-3,3:-3], ref[3:-3,3:-3]

    result = {
        "sample": args.sample,
        "metadata": metadata_status(args.metadata_json),
        "fit_freedom": "NONE: no gamma/exposure/affine/WB/colour/tone fit",
        "upstream": "RENDER_PARITY1A C: WhiteLevel clamp + CA9 neutral clip + frozen Leica ColorSpec + TONEDG1B luma MEDIUM->DG shared RGB gain",
        "transfer_on": "standard_sRGB_OETF",
        "transfer_off": "identity_mapping",
        "alignment": {"score": float(score), "rot90_k": int(rot_k), "dx": int(dx), "dy": int(dy),
                      "rawpy_flip": raw_flip, "raw_oriented": [raw_w, raw_h], "jpeg": [jpg_w, jpg_h],
                      "comparison": [int(ref.shape[1]), int(ref.shape[0])]},
        "metrics": {"oetf_on": metrics(on, ref), "oetf_off": metrics(off, ref)},
    }
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
