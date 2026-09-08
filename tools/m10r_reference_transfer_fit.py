#!/usr/bin/env python3
"""Empirically discriminate fixed post-TONE->DG transfer candidates on M10-R JPEG/DNG pairs.

This reuses the same-capture, metadata-gated Photography Blog corpus and the
same neutral/low-texture patch strategy as m10r_reference_order_fit.py.
Unlike the older order fit, this tool does NOT fit an arbitrary output gamma.
It fits only nuisance input scale plus output affine terms around fixed transfer
candidates so a free gamma cannot hide transfer ownership.

This is empirical photographic evidence, not direct CA9/B2Y hardware proof.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
import rawpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m10r_b2y_nonlinear_oracle as oracle
from m10r_reference_order_fit import alignment_search, metadata_status


def srgb_oetf(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1.0 / 2.4) - 0.055)


def srgb_eotf(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.04045, x / 12.92, np.power((x + 0.055) / 1.055, 2.4))


def apply_transfer(name: str, x: np.ndarray) -> np.ndarray:
    if name == "identity":
        return np.clip(x, 0.0, 1.0)
    if name == "srgb_oetf":
        return srgb_oetf(x)
    if name == "gamma22_oetf":
        return np.power(np.clip(x, 0.0, 1.0), 1.0 / 2.2)
    if name == "srgb_eotf":
        return srgb_eotf(x)
    if name == "gamma22_eotf":
        return np.power(np.clip(x, 0.0, 1.0), 2.2)
    raise ValueError(name)


def fit_transfer(curve: np.ndarray, G: np.ndarray, J: np.ndarray, transfer: str) -> dict:
    idx = np.arange(len(G)); train = (idx % 2) == 0; test = ~train
    scales = np.linspace(0.35, 3.0, 266)
    best = None
    for sc in scales:
        xi = np.clip(np.rint(G * sc), 0, oracle.TONE_COORD_MAX).astype(np.int32)
        yy = curve[xi] / 16383.0
        z = apply_transfer(transfer, yy)
        A = np.column_stack([np.ones(train.sum()), z[train]])
        coef = np.linalg.lstsq(A, J[train], rcond=None)[0]
        pred = coef[0] + coef[1] * z
        tr = float(np.sqrt(np.mean((pred[train] - J[train]) ** 2)))
        te = float(np.sqrt(np.mean((pred[test] - J[test]) ** 2))) if test.any() else tr
        if best is None or te < best[0]:
            best = (te, tr, sc, float(coef[0]), float(coef[1]), pred, xi)
    te, tr, sc, b0, b1, pred, xi = best
    mae = float(np.mean(np.abs(pred[test] - J[test]))) if test.any() else float(np.mean(np.abs(pred - J)))
    return {
        "test_rmse": te, "train_rmse": tr, "test_mae": mae,
        "raw_scale": float(sc), "b0": b0, "b1": b1,
        "x_min": int(xi.min()), "x_max": int(xi.max()),
    }


def extract_patches(jpg: Path, dng: Path):
    with Image.open(jpg) as im:
        jim = ImageOps.exif_transpose(im).convert("RGB")
        jpg_u8 = np.asarray(jim, dtype=np.uint8)
    jh, jw = jpg_u8.shape[:2]

    with rawpy.imread(str(dng)) as r:
        rgb = r.postprocess(use_camera_wb=True, no_auto_bright=True, gamma=(1, 1),
                            output_bps=16, output_color=rawpy.ColorSpace.raw)
        white = float(r.white_level)
        pattern = None if r.raw_pattern is None else r.raw_pattern.copy()
        desc = bytes(r.color_desc) if r.color_desc is not None else b""
        raw_flip = int(r.sizes.flip)
    raw_proxy = rgb[:, :, 1].astype(np.float32) * (white / 65535.0)
    del rgb

    oriented_proxy, scores = alignment_search(raw_proxy, jpg_u8)
    best_score, rot_k, dx, dy = scores[0]
    rh, rw = oriented_proxy.shape
    rcrop = oriented_proxy[dy:dy+jh, dx:dx+jw]

    block = 64; step = 128; margin = 128
    patches = []
    for y in range(margin, jh-margin-block+1, step):
        for x in range(margin, jw-margin-block+1, step):
            jb = jpg_u8[y:y+block, x:x+block].astype(np.float32)
            meanrgb = jb.reshape(-1, 3).mean(0)
            chroma = float(meanrgb.max() - meanrgb.min())
            jlum = 0.2126*jb[:, :, 0] + 0.7152*jb[:, :, 1] + 0.0722*jb[:, :, 2]
            texture = float(jlum.std())
            gv = rcrop[y:y+block, x:x+block]
            patches.append((float(gv.mean()), float(gv.std()), float(jlum.mean()), texture, chroma))

    thresholds = [(10, 8), (16, 10), (24, 14), (32, 18)]
    chosen = []; threshold = None
    for cmax, tmax in thresholds:
        chosen = [p for p in patches if p[4] <= cmax and p[3] <= tmax and p[0] > 50 and 2 < p[2] < 253]
        if len(chosen) >= 40:
            threshold = (cmax, tmax); break
    if not chosen:
        chosen = patches; threshold = (None, None)
    chosen.sort(key=lambda p: (p[3], p[4]))
    G = np.array([p[0] for p in chosen], dtype=np.float64)
    J = np.array([p[2] for p in chosen], dtype=np.float64)
    mask = (G < white * 0.985) & (J > 4) & (J < 250)
    G = G[mask]; J = J[mask]

    info = {
        "dimensions": {"raw_oriented": [rw, rh], "jpeg_oriented": [jw, jh], "difference": [rw-jw, rh-jh]},
        "alignment": {"score": best_score, "rot90_k": rot_k, "dx": dx, "dy": dy, "rawpy_flip": raw_flip},
        "raw": {"white_level": white,
                "pattern": None if pattern is None else pattern.tolist(),
                "color_desc": desc.decode("ascii", "replace"),
                "proxy": "rawpy linear camera-space green normalized by white_level/65535"},
        "patches": {"total": len(patches), "chosen": len(chosen), "fit": int(len(G)),
                    "threshold_chroma_texture": list(threshold),
                    "rawG_range": [float(G.min()), float(G.max())] if len(G) else None,
                    "jpgY_range": [float(J.min()), float(J.max())] if len(J) else None},
    }
    return G, J, info


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jpg", type=Path, required=True)
    ap.add_argument("--dng", type=Path, required=True)
    ap.add_argument("--assets", type=Path, required=True)
    ap.add_argument("--sample", required=True)
    ap.add_argument("--metadata-json", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    meta = metadata_status(args.metadata_json)
    G, J, info = extract_patches(args.jpg, args.dng)
    result = {"sample": args.sample, "metadata": meta, **info, "fits": {}, "deltas": {}}
    if len(G) < 20:
        result["error"] = "insufficient neutral patches"
    else:
        assets = oracle.load_assets(args.assets, "medium")
        transfers = ("identity", "srgb_oetf", "gamma22_oetf", "srgb_eotf", "gamma22_eotf")
        for rounding in ("trunc", "nearest"):
            curve = np.asarray(oracle.evaluate_curve(assets, order="tone-dg", rounding=rounding,
                                                     clamp_policy="none"), dtype=np.float64)
            for transfer in transfers:
                result["fits"][f"{rounding}|{transfer}"] = fit_transfer(curve, G, J, transfer)
            base = result["fits"][f"{rounding}|identity"]["test_rmse"]
            result["deltas"][rounding] = {
                transfer: result["fits"][f"{rounding}|{transfer}"]["test_rmse"] - base
                for transfer in transfers if transfer != "identity"
            }
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
