#!/usr/bin/env python3
"""Empirically rank the frozen M10-R DG/tone order candidates on a same-capture JPG/DNG pair.

This is deliberately an empirical discriminator, not hardware proof. It uses
low-chroma/low-texture patches and an oriented linear camera-space green proxy,
then fits only nuisance scale + output-transfer parameters around the exact
firmware nonlinear assets.
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


def corr(a: np.ndarray, b: np.ndarray) -> float:
    aa = a.ravel().astype(np.float64)
    bb = b.ravel().astype(np.float64)
    aa -= aa.mean(); bb -= bb.mean()
    den = np.linalg.norm(aa) * np.linalg.norm(bb)
    return float(np.dot(aa, bb) / den) if den else -1.0


def metadata_status(meta_path: Path | None) -> dict:
    if meta_path is None:
        return {"provided": False, "identity_supported": None, "default_jpeg_controls": None}
    ex = json.loads(meta_path.read_text())
    by = {Path(x["SourceFile"]).suffix.lower(): x for x in ex}
    j = by.get(".jpg", {}); d = by.get(".dng", {})
    identity_keys = ["Make", "Model", "SerialNumber", "ImageUniqueID", "DateTimeOriginal",
                     "ExposureTime", "FNumber", "ISO", "FocalLength", "ExposureCompensation"]
    comparisons = {k: (k in j and k in d and j[k] == d[k]) for k in identity_keys}
    required = ["Make", "Model", "SerialNumber", "ImageUniqueID", "DateTimeOriginal",
                "ExposureTime", "ISO", "FocalLength"]
    identity = all(comparisons[k] for k in required)
    defaults = all(j.get(k) == 0 for k in ("Contrast", "Saturation", "Sharpness"))
    return {
        "provided": True,
        "identity_supported": identity,
        "default_jpeg_controls": defaults,
        "comparisons": comparisons,
        "jpg": {k: j.get(k) for k in identity_keys + ["Contrast", "Saturation", "Sharpness", "WhiteBalance"]},
        "dng": {k: d.get(k) for k in identity_keys},
    }


def fit_candidate(curve: np.ndarray, G: np.ndarray, J: np.ndarray) -> dict:
    idx = np.arange(len(G)); train = (idx % 2) == 0; test = ~train
    scales = np.linspace(0.35, 3.0, 266)
    gammas = np.linspace(0.55, 1.8, 126)
    best = None
    for sc in scales:
        xi = np.clip(np.rint(G * sc), 0, oracle.TONE_COORD_MAX).astype(np.int32)
        yy = curve[xi] / 16383.0
        for gm in gammas:
            z = np.power(np.clip(yy, 0, 1), gm)
            A = np.column_stack([np.ones(train.sum()), z[train]])
            coef = np.linalg.lstsq(A, J[train], rcond=None)[0]
            pred = coef[0] + coef[1] * z
            tr = float(np.sqrt(np.mean((pred[train] - J[train]) ** 2)))
            te = float(np.sqrt(np.mean((pred[test] - J[test]) ** 2))) if test.any() else tr
            if best is None or te < best[0]:
                best = (te, tr, sc, gm, float(coef[0]), float(coef[1]), pred, xi)
    te, tr, sc, gm, b0, b1, pred, xi = best
    mae = float(np.mean(np.abs(pred[test] - J[test]))) if test.any() else float(np.mean(np.abs(pred - J)))
    return {"test_rmse": te, "train_rmse": tr, "test_mae": mae, "raw_scale": float(sc),
            "output_gamma": float(gm), "b0": b0, "b1": b1,
            "x_min": int(xi.min()), "x_max": int(xi.max())}


def alignment_search(raw_proxy: np.ndarray, jpg_u8: np.ndarray) -> tuple[np.ndarray, list[tuple[float,int,int,int]]]:
    """Return best oriented raw proxy and scored (score,k,dx,dy) candidates.

    k is np.rot90 count. We permit only near-full-frame geometries so arbitrary
    rotations/crops cannot win by chance.
    """
    jh, jw = jpg_u8.shape[:2]
    jf = jpg_u8.astype(np.float32) / 255.0
    jpgg = np.log1p((0.2126 * jf[:, :, 0] + 0.7152 * jf[:, :, 1] + 0.0722 * jf[:, :, 2]) * 8.0)
    del jf
    stride = 16
    j = jpgg[64:jh-64:stride, 64:jw-64:stride]
    jx = np.diff(j, axis=1); jy = np.diff(j, axis=0)
    all_scores: list[tuple[float,int,int,int]] = []
    oriented: dict[int,np.ndarray] = {}
    for k in range(4):
        rp = np.rot90(raw_proxy, k)
        rh, rw = rp.shape
        if rw < jw or rh < jh or rw-jw > 96 or rh-jh > 96:
            continue
        oriented[k] = rp
        rawg = np.log1p(rp.astype(np.float32) / 256.0)
        for dy in range(rh-jh+1):
            for dx in range(rw-jw+1):
                rr = rawg[dy+64:dy+jh-64:stride, dx+64:dx+jw-64:stride]
                if rr.shape != j.shape:
                    continue
                s = (corr(np.diff(rr, axis=1), jx) + corr(np.diff(rr, axis=0), jy)) / 2
                all_scores.append((s, k, dx, dy))
    all_scores.sort(reverse=True)
    if not all_scores:
        raise RuntimeError(f"no geometry-compatible raw/JPEG orientation: raw={raw_proxy.shape[::-1]} jpeg={(jw,jh)}")
    best_k = all_scores[0][1]
    return oriented[best_k], all_scores


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
    with Image.open(args.jpg) as im:
        jim = ImageOps.exif_transpose(im).convert("RGB")
        jpg_u8 = np.asarray(jim, dtype=np.uint8)
    jh, jw = jpg_u8.shape[:2]

    with rawpy.imread(str(args.dng)) as r:
        # Camera-space RGB, camera WB, no auto-brightening, linear 16-bit output.
        # Green is normalized back into approximate native raw-code units so the
        # fitted input scale remains comparable across captures/orientations.
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

    result = {
        "sample": args.sample,
        "metadata": meta,
        "dimensions": {"raw_oriented": [rw, rh], "jpeg_oriented": [jw, jh], "difference": [rw-jw, rh-jh]},
        "alignment": {"score": best_score, "rot90_k": rot_k, "dx": dx, "dy": dy,
                      "rawpy_flip": raw_flip,
                      "top5": [{"score": s, "rot90_k": k, "dx": x, "dy": y} for s, k, x, y in scores[:5]]},
        "raw": {"white_level": white,
                "pattern": None if pattern is None else pattern.tolist(),
                "color_desc": desc.decode("ascii", "replace"),
                "proxy": "rawpy linear camera-space green, normalized by white_level/65535"},
        "patches": {"total": len(patches), "chosen": len(chosen), "fit": int(len(G)),
                    "threshold_chroma_texture": list(threshold),
                    "rawG_range": [float(G.min()), float(G.max())] if len(G) else None,
                    "jpgY_range": [float(J.min()), float(J.max())] if len(J) else None},
        "fits": {},
    }
    if len(G) >= 20:
        assets = oracle.load_assets(args.assets, "medium")
        for order in ("dg-tone", "tone-dg"):
            for rounding in ("trunc", "nearest"):
                curve = np.asarray(oracle.evaluate_curve(assets, order=order, rounding=rounding,
                                                         clamp_policy="none"), dtype=np.float64)
                result["fits"][f"{order}|{rounding}"] = fit_candidate(curve, G, J)
        result["deltas"] = {}
        for rnd in ("trunc", "nearest"):
            a = result["fits"][f"dg-tone|{rnd}"]["test_rmse"]
            b = result["fits"][f"tone-dg|{rnd}"]["test_rmse"]
            result["deltas"][rnd] = a - b
    else:
        result["error"] = "insufficient neutral patches"

    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
