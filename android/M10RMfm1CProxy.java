package com.particlesdevs.photoncamera.m10r;

/**
 * MFM1C live-preview -> RAW-proxy luminance transform.
 *
 * The current meter already converts SurfaceTexture sRGB code values to
 * approximate linear Rec.709 luminance. Real-device paired live/RAW evidence
 * shows that the preview pipeline still lifts/compresses dark regions relative
 * to normalized pre-shading RAW. MFM1C applies one monotonic nonlinear
 * de-compression before the unchanged MFM1B spatial decision.
 *
 * This exponent is an empirical phone-domain proxy, not a recovered Leica
 * firmware constant. It affects metering only; renderer pixels are untouched.
 */
public final class M10RMfm1CProxy {
    public static final double EXPONENT = 1.90;

    private M10RMfm1CProxy() {}

    public static double[] transform(double[] linearPreviewGrid) {
        if (linearPreviewGrid == null) return null;
        double[] out = new double[linearPreviewGrid.length];
        for (int i = 0; i < linearPreviewGrid.length; i++) {
            double v = linearPreviewGrid[i];
            if (!Double.isFinite(v) || v < 0.0) {
                out[i] = Double.NaN;
                continue;
            }
            // SurfaceTexture-derived linear Y is nominally 0..1. Clamp only the
            // representational overshoot; no spatial/local manipulation is used.
            v = Math.max(0.0, Math.min(1.0, v));
            out[i] = Math.pow(v, EXPONENT);
        }
        return out;
    }
}
