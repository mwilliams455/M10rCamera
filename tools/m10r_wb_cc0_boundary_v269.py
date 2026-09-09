#!/usr/bin/env python3
"""M10-R v2.69 WB <-> CC0 finite-precision boundary discriminator.

Research-only.  This tool does NOT alter the Android renderer and deliberately
requires an explicit firmware-derived CC0 matrix.  It never substitutes an
Adobe/rawpy colour matrix for Leica ColorSpec state.

Evidence used here
------------------
PROVEN:
* rendered-CC scaleCode is 0..3;
* signed coefficient code range is -2048..+2047;
* decoded coefficient denominator is 2**(9-scaleCode);
* firmware SelectScale tests scale codes in increasing order and accepts the
  first code whose rounded coefficients fit the signed range;
* 0x40012940 + Thumb 0x400133D0 implement nearest / ties-away-from-zero for
  finite rendered-CC coefficient encoding.

STRONG / empirical first-parity:
* WB is tested in native-CFA domain, following v0.59;
* CA9 gains are represented as Q8 integer gains recovered from AsShotNeutral.

OPEN and therefore parameterised:
* WB product rounding (trunc or nearest);
* physical WB clamp (none, 15000, or 16383 are candidates, not Leica truth);
* exact CC matrix MAC/output arithmetic.  Sfull below uses decoded float matrix
  multiplication and is explicitly NON-BIT-EXACT.

Layers
------
F0    floating algebraic control: CC0 @ WB versus (CC0 @ WB) collapse.
W1    native-CFA Q8 WB finite precision only; CC0 remains floating.
C1    floating WB with separately quantised CC0 versus independently quantised
      collapsed (CC0 @ WB) matrix.  This is the strongest exact discriminator.
Sfull native-CFA integer WB + candidate clamp + quantised CC0, but decoded-float
      matrix MAC/output pending firmware closure.

For a genuine JPEG/DNG pair, alignment and low-texture held-out scoring reuse
the v2.20/v0.59 project approach.  The JPEG fit is a nuisance downstream model;
it is not a claim that this tool reproduces Leica's complete output pipeline.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
from PIL import Image, ImageOps
import rawpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m10r_reference_order_fit import alignment_search
from m10r_wb_headroom_fit_v058 import fit_eval, load_meta, q8_from_asn
from m10r_wb_bayer_headroom_v059 import orient_libraw, pattern_letters

UNITY_Q8 = 256
CC_MIN = -2048
CC_MAX = 2047
SCALE_CODES = (0, 1, 2, 3)
CANDIDATE_CLAMPS = {"none": None, "15000": 15000, "16383": 16383}


def parse_floats(text: str, n: int, what: str) -> np.ndarray:
    vals = [float(x) for x in re.split(r"[\s,;]+", text.strip()) if x]
    if len(vals) != n or not np.all(np.isfinite(vals)):
        raise ValueError(f"{what} must contain exactly {n} finite numbers")
    return np.asarray(vals, dtype=np.float64)


def parse_matrix3(text: str) -> np.ndarray:
    return parse_floats(text, 9, "CC0").reshape(3, 3)


def round_ties_away(x: np.ndarray | float) -> np.ndarray:
    """PROVEN finite rendered-CC rounding: nearest, exact ties away from zero."""
    a = np.asarray(x, dtype=np.float64)
    if not np.all(np.isfinite(a)):
        raise ValueError("cannot quantise non-finite rendered-CC coefficient")
    return np.copysign(np.floor(np.abs(a) + 0.5), a).astype(np.int64)


def quantize_cc_first_fit(matrix: np.ndarray) -> dict:
    """PROVEN rendered-CC first-fit scale search for the recovered 0..3 range."""
    m = np.asarray(matrix, dtype=np.float64).reshape(3, 3)
    for sc in SCALE_CODES:
        den = 1 << (9 - sc)
        q = round_ties_away(m * float(den))
        if int(q.min()) >= CC_MIN and int(q.max()) <= CC_MAX:
            return {
                "scale_code": sc,
                "denominator": den,
                "q": q,
                "decoded": q.astype(np.float64) / float(den),
            }
    raise OverflowError("matrix cannot be represented by recovered rendered-CC scaleCode 0..3")


def wb_diag(gains_q8: np.ndarray) -> np.ndarray:
    return np.diag(np.asarray(gains_q8, dtype=np.float64) / float(UNITY_Q8))


def gain_lut_for_rawpy(gains_rgb: np.ndarray, color_desc: bytes | str) -> np.ndarray:
    desc = color_desc.decode("ascii", "replace") if isinstance(color_desc, bytes) else str(color_desc)
    lut = np.empty(len(desc), dtype=np.uint64)
    for i, c in enumerate(desc.upper()):
        if c == "R":
            lut[i] = int(gains_rgb[0])
        elif c == "G":
            lut[i] = int(gains_rgb[1])
        elif c == "B":
            lut[i] = int(gains_rgb[2])
        else:
            raise RuntimeError(f"unsupported rawpy colour descriptor {c!r} in {desc!r}")
    return lut


def black_lut_for_rawpy(black: Iterable[float], color_desc: bytes | str) -> np.ndarray:
    b = list(float(x) for x in black)
    if not b:
        b = [0.0]
    desc = color_desc.decode("ascii", "replace") if isinstance(color_desc, bytes) else str(color_desc)
    out = np.empty(len(desc), dtype=np.float64)
    for i in range(len(desc)):
        out[i] = b[min(i, len(b) - 1)]
    return out


def apply_wb_cfa_wide(mosaic_signal: np.ndarray, colors: np.ndarray, lut: np.ndarray,
                      rounding: str, clamp_mode: str) -> np.ndarray:
    """Apply v0.59-style Q8 WB without an accidental uint16 boundary.

    v0.59 used uint32 product and uint16 output after an explicit ceiling.
    Here the product is uint64 and the result remains float64/uint64 until the
    requested candidate clamp.  `none` therefore means genuinely no software
    ceiling at this stage.
    """
    x = np.asarray(mosaic_signal, dtype=np.float64)
    if np.any(x < 0):
        raise ValueError("mosaic_signal must already be black-subtracted/non-negative")
    xi = np.rint(x).astype(np.uint64)
    p = xi * lut[colors]
    if rounding == "trunc":
        v = p >> 8
    elif rounding == "nearest":
        v = (p + 128) >> 8
    else:
        raise ValueError(f"unsupported WB rounding {rounding}")
    ceiling = CANDIDATE_CLAMPS.get(clamp_mode)
    if clamp_mode not in CANDIDATE_CLAMPS:
        raise ValueError(f"unsupported clamp mode {clamp_mode}")
    if ceiling is not None:
        v = np.minimum(v, np.uint64(ceiling))
    return v.astype(np.float64)


def _conv_same(a: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    return cv2.filter2D(a.astype(np.float64), cv2.CV_64F, kernel, borderType=cv2.BORDER_REFLECT_101)


def demosaic_linear_proxy(mosaic: np.ndarray, colors: np.ndarray, color_desc: bytes | str) -> np.ndarray:
    """Wide-precision deterministic linear demosaic used identically by candidates.

    This is a proxy, not Leica demosaic.  Sparse R/G/B planes are normalised by
    identically filtered support masks, which avoids uint16 clipping and keeps
    channel-scalar multiplication linear away from explicit WB quantisation.
    """
    desc = color_desc.decode("ascii", "replace") if isinstance(color_desc, bytes) else str(color_desc)
    kernel = np.asarray([[1.0, 2.0, 1.0], [2.0, 4.0, 2.0], [1.0, 2.0, 1.0]], dtype=np.float64)
    out = []
    for letter in "RGB":
        ids = [i for i, c in enumerate(desc.upper()) if c == letter]
        if not ids:
            raise RuntimeError(f"missing {letter} in rawpy color_desc {desc!r}")
        mask = np.isin(colors, ids).astype(np.float64)
        num = _conv_same(np.asarray(mosaic, dtype=np.float64) * mask, kernel)
        den = _conv_same(mask, kernel)
        plane = np.divide(num, den, out=np.zeros_like(num), where=den > 1.0e-12)
        out.append(plane)
    return np.stack(out, axis=2)


def patch_positions(jpg: np.ndarray, margin: int = 96, block: int = 48, step: int = 72):
    h, w = jpg.shape[:2]
    pos = []
    for y0 in range(margin, h - margin - block + 1, step):
        for x0 in range(margin, w - margin - block + 1, step):
            jb = jpg[y0:y0 + block, x0:x0 + block].astype(np.float64) / 255.0
            lum = 0.2126 * jb[:, :, 0] + 0.7152 * jb[:, :, 1] + 0.0722 * jb[:, :, 2]
            if float(lum.std()) <= 0.12:
                pos.append((y0, x0, jb.reshape(-1, 3).mean(0)))
    return pos


def patch_means(rgb: np.ndarray, positions, block: int = 48) -> np.ndarray:
    return np.asarray([
        rgb[y:y + block, x:x + block].reshape(-1, 3).mean(0)
        for y, x, _ in positions
    ], dtype=np.float64)


def apply_matrix(vectors: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    # vectors are row vectors; firmware algebra is expressed as column vectors.
    return np.asarray(vectors, dtype=np.float64) @ np.asarray(matrix, dtype=np.float64).T


def residual_stats(a: np.ndarray, b: np.ndarray, signal: np.ndarray, headroom: np.ndarray) -> dict:
    d = np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64)
    l2 = np.linalg.norm(d, axis=1)
    maxabs = np.max(np.abs(d), axis=1)
    out = {
        "count": int(len(d)),
        "rmse": float(np.sqrt(np.mean(d * d))) if len(d) else None,
        "mae": float(np.mean(np.abs(d))) if len(d) else None,
        "max_abs": float(np.max(np.abs(d))) if len(d) else None,
        "l2_median": float(np.median(l2)) if len(d) else None,
        "l2_p95": float(np.percentile(l2, 95)) if len(d) else None,
        "per_channel_mean": np.mean(d, axis=0).tolist() if len(d) else None,
    }
    bins = []
    if len(d) >= 4:
        qs = np.quantile(signal, [0.0, 0.25, 0.5, 0.75, 1.0])
        for i in range(4):
            mask = (signal >= qs[i]) & ((signal <= qs[i + 1]) if i == 3 else (signal < qs[i + 1]))
            if mask.any():
                bins.append({"q": i, "signal_range": [float(qs[i]), float(qs[i + 1])],
                             "count": int(mask.sum()), "l2_mean": float(l2[mask].mean()),
                             "max_abs_mean": float(maxabs[mask].mean()),
                             "headroom_mean": float(headroom[mask].mean())})
    out["signal_quartiles"] = bins
    if len(d) > 1 and np.std(headroom) > 1.0e-12:
        out["corr_l2_headroom"] = float(np.corrcoef(l2, headroom)[0, 1])
    else:
        out["corr_l2_headroom"] = None
    return out


def fit_if_possible(x: np.ndarray, jmean: np.ndarray, train: np.ndarray, test: np.ndarray,
                    scale: float) -> dict | None:
    if int(train.sum()) < 24 or int(test.sum()) < 10:
        return None
    return fit_eval(np.asarray(x, dtype=np.float64) / float(scale), jmean, train, test)


def self_test() -> dict:
    tie_in = np.asarray([-2.5, -1.5, -0.5, -0.49, 0.49, 0.5, 1.5, 2.5])
    tie_out = round_ties_away(tie_in)
    expected = np.asarray([-3, -2, -1, 0, 0, 1, 2, 3])
    if not np.array_equal(tie_out, expected):
        raise AssertionError((tie_out, expected))

    # A matrix that fits scale 0 must select scale 0; large-but-representable
    # coefficients force a later scale.
    q0 = quantize_cc_first_fit(np.eye(3))
    if q0["scale_code"] != 0 or q0["denominator"] != 512:
        raise AssertionError(q0)
    q2 = quantize_cc_first_fit(np.diag([6.0, 1.0, 1.0]))
    if q2["scale_code"] != 1:  # 6*512 overflows; 6*256 fits.
        raise AssertionError(q2)

    cc0 = np.asarray([[1.173, -0.121, -0.052], [-0.087, 1.109, -0.022], [0.011, -0.137, 1.126]])
    gains = np.asarray([477, 256, 391])
    wb = wb_diag(gains)
    x = np.asarray([[100.0, 200.0, 300.0], [1234.5, 2048.25, 4095.75], [9000.0, 7000.0, 5000.0]])
    f0a = apply_matrix(apply_matrix(x, wb), cc0)
    f0b = apply_matrix(x, cc0 @ wb)
    f0err = float(np.max(np.abs(f0a - f0b)))
    if f0err > 1.0e-9:
        raise AssertionError(f"F0 algebra failed: {f0err}")

    sep = quantize_cc_first_fit(cc0)
    col = quantize_cc_first_fit(cc0 @ wb)
    c1a = apply_matrix(apply_matrix(x, wb), sep["decoded"])
    c1b = apply_matrix(x, col["decoded"])
    c1err = float(np.max(np.abs(c1a - c1b)))
    if c1err <= 0.0:
        raise AssertionError("C1 synthetic probe unexpectedly has zero finite-precision residual")

    return {
        "status": "PASS",
        "rounding": "PROVEN nearest/ties-away",
        "scale_search": "PROVEN increasing first-fit over recovered scaleCode 0..3",
        "ties": {str(float(k)): int(v) for k, v in zip(tie_in, tie_out)},
        "identity_scale_code": int(q0["scale_code"]),
        "forced_later_scale_code": int(q2["scale_code"]),
        "f0_max_abs": f0err,
        "c1_synthetic_max_abs": c1err,
        "sfull": "NON-BIT-EXACT: exact CC MAC/output arithmetic remains OPEN",
    }


def analyze_scene(args) -> dict:
    cc0 = parse_matrix3(args.cc0)
    with Image.open(args.jpg) as im:
        jpg = np.asarray(ImageOps.exif_transpose(im).convert("RGB"), dtype=np.uint8)
    jh, jw = jpg.shape[:2]

    meta, asn = load_meta(args.metadata_json)
    with rawpy.imread(str(args.dng)) as r:
        mosaic = r.raw_image_visible.copy().astype(np.float64)
        colors = r.raw_colors_visible.copy()
        raw_pattern = None if r.raw_pattern is None else r.raw_pattern.copy()
        color_desc = bytes(r.color_desc)
        raw_wb = np.asarray(r.camera_whitebalance, dtype=np.float64)
        white = float(r.white_level)
        black = np.asarray(r.black_level_per_channel, dtype=np.float64)
        raw_flip = int(r.sizes.flip)

    if raw_pattern is None:
        raise RuntimeError("DNG has no 2x2 raw_pattern")
    pattern = pattern_letters(raw_pattern, color_desc)
    black_lut = black_lut_for_rawpy(black, color_desc)
    signal = np.maximum(mosaic - black_lut[colors], 0.0)
    gains_q8, gain_source = q8_from_asn(asn, raw_wb)
    if args.wb_gains:
        gains_q8 = np.rint(parse_floats(args.wb_gains, 3, "WB gains")).astype(np.int64)
        gain_source = "explicit --wb-gains Q8"
    wb = wb_diag(gains_q8)

    base_rgb = demosaic_linear_proxy(signal, colors, color_desc)
    oriented_base = orient_libraw(base_rgb, raw_flip)
    _, scores = alignment_search(oriented_base[:, :, 1], jpg)
    best_score, k, dx, dy = scores[0]
    base_crop = np.rot90(oriented_base, k)[dy:dy + jh, dx:dx + jw]
    if base_crop.shape[:2] != (jh, jw):
        raise RuntimeError(f"aligned base crop {base_crop.shape[:2]} != JPEG {(jh, jw)}")

    positions = patch_positions(jpg)
    if not positions:
        raise RuntimeError("no usable low-texture patches")
    jmean = np.asarray([p[2] for p in positions], dtype=np.float64)
    base_vec = patch_means(base_crop, positions)
    float_wb_vec = apply_matrix(base_vec, wb)
    pre_max = np.max(float_wb_vec, axis=1)
    signal_level = np.mean(base_vec, axis=1)
    headroom = white - pre_max
    train = (pre_max < white * 0.72) & (jmean.max(1) < 0.92) & (jmean.mean(1) > 0.02)
    test = (pre_max > white * 0.92) & (jmean.mean(1) > 0.04) & (jmean.min(1) < 0.995)

    # F0: mathematical control.  Must collapse to numerical noise.
    f0_sep = apply_matrix(float_wb_vec, cc0)
    collapsed_float = cc0 @ wb
    f0_col = apply_matrix(base_vec, collapsed_float)

    # C1: exact recovered rendered-CC finite precision, separate vs collapsed.
    q_cc0 = quantize_cc_first_fit(cc0)
    q_collapsed = quantize_cc_first_fit(collapsed_float)
    c1_sep = apply_matrix(float_wb_vec, q_cc0["decoded"])
    c1_col = apply_matrix(base_vec, q_collapsed["decoded"])

    result = {
        "version": "v269",
        "sample": args.sample,
        "research_only": True,
        "explicit_cc0_required": True,
        "metadata": meta,
        "raw": {"white_level": white, "black_level_per_channel": black.tolist(),
                "pattern_letters": pattern, "raw_flip": raw_flip,
                "demosaic": "wide-precision deterministic linear proxy; NOT Leica demosaic"},
        "wb": {"gain_q8_rgb": gains_q8.tolist(), "gain_source": gain_source,
               "gain_float_rgb": (gains_q8.astype(np.float64) / UNITY_Q8).tolist(),
               "asymmetry_max_over_min": float(np.max(gains_q8) / np.min(gains_q8))},
        "cc0": {"input": cc0.tolist(),
                "separate": {"scale_code": int(q_cc0["scale_code"]), "denominator": int(q_cc0["denominator"]),
                             "q": q_cc0["q"].tolist(), "decoded": q_cc0["decoded"].tolist()},
                "collapsed": {"float": collapsed_float.tolist(),
                              "scale_code": int(q_collapsed["scale_code"]), "denominator": int(q_collapsed["denominator"]),
                              "q": q_collapsed["q"].tolist(), "decoded": q_collapsed["decoded"].tolist()},
                "scale_code_transition": bool(q_cc0["scale_code"] != q_collapsed["scale_code"])},
        "alignment": {"score": float(best_score), "rot90_k": int(k), "dx": int(dx), "dy": int(dy)},
        "patches": {"usable": len(positions), "train": int(train.sum()), "test": int(test.sum()),
                    "signal_range": [float(signal_level.min()), float(signal_level.max())],
                    "headroom_range": [float(headroom.min()), float(headroom.max())]},
        "F0": {"status": "control", "residual": residual_stats(f0_sep, f0_col, signal_level, headroom)},
        "C1": {"status": "exact CC encoding / matrix-order discriminator",
               "residual": residual_stats(c1_sep, c1_col, signal_level, headroom),
               "separate_fit": fit_if_possible(c1_sep, jmean, train, test, white),
               "collapsed_fit": fit_if_possible(c1_col, jmean, train, test, white)},
        "W1": {},
        "Sfull": {},
        "limitations": [
            "CC0 was supplied explicitly; no Adobe/rawpy matrix substituted for firmware ColorSpec state.",
            "WB rounding/clamps below are candidates; 15000/16383 are not proven physical Leica WB clamps.",
            "Demosaic is a wide-precision linear proxy used identically across candidates, not Leica demosaic.",
            "Sfull uses decoded float matrix multiplication; exact CC MAC/output arithmetic remains OPEN.",
            "JPEG scoring fits a nuisance downstream quadratic on held-out patches and is empirical parity evidence only.",
        ],
    }

    lut = gain_lut_for_rawpy(gains_q8, color_desc)
    for rounding in args.wb_rounding:
        for clamp_mode in args.clamp:
            wb_mosaic = apply_wb_cfa_wide(signal, colors, lut, rounding, clamp_mode)
            wb_rgb = demosaic_linear_proxy(wb_mosaic, colors, color_desc)
            wb_oriented = orient_libraw(wb_rgb, raw_flip)
            wb_crop = np.rot90(wb_oriented, k)[dy:dy + jh, dx:dx + jw]
            wb_vec = patch_means(wb_crop, positions)

            key = f"{rounding}|{clamp_mode}"
            w1_sep = apply_matrix(wb_vec, cc0)
            result["W1"][key] = {
                "status": "candidate native-CFA Q8 WB finite precision; CC0 floating",
                "clamp_is_proven": False if clamp_mode != "none" else None,
                "residual_vs_float_WB": residual_stats(w1_sep, f0_sep, signal_level, headroom),
                "fit": fit_if_possible(w1_sep, jmean, train, test, white),
            }

            s_sep = apply_matrix(wb_vec, q_cc0["decoded"])
            result["Sfull"][key] = {
                "status": "PROVISIONAL / NON-BIT-EXACT CC MAC",
                "cc_mac_mode": "decoded-float-matrix",
                "residual_vs_collapsed": residual_stats(s_sep, c1_col, signal_level, headroom),
                "fit": fit_if_possible(s_sep, jmean, train, test, white),
            }

    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--jpg", type=Path)
    ap.add_argument("--dng", type=Path)
    ap.add_argument("--metadata-json", type=Path)
    ap.add_argument("--sample", default="sample")
    ap.add_argument("--cc0", help="explicit row-major 3x3 firmware-derived CC0; nine comma/space-separated floats")
    ap.add_argument("--wb-gains", help="optional explicit Q8 R,G,B gains; default derives first-parity gains from DNG ASN")
    ap.add_argument("--wb-rounding", nargs="+", choices=["trunc", "nearest"], default=["trunc", "nearest"])
    ap.add_argument("--clamp", nargs="+", choices=list(CANDIDATE_CLAMPS), default=["none", "15000", "16383"])
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    if args.self_test:
        result = self_test()
    else:
        required = {"--jpg": args.jpg, "--dng": args.dng, "--metadata-json": args.metadata_json,
                    "--cc0": args.cc0, "--out": args.out}
        missing = [k for k, v in required.items() if v is None]
        if missing:
            ap.error("scene mode requires " + ", ".join(missing))
        result = analyze_scene(args)

    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
