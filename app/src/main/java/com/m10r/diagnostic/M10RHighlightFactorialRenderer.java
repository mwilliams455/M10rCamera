package com.m10r.diagnostic;

import java.util.Locale;

/**
 * RENDER_PARITY1A controlled 2x2 highlight-boundary experiment.
 *
 * Canonical matrix (authoritative for this experiment):
 *   A_BASELINE      = RAW headroom OFF, CA9 neutral clip OFF
 *   B_HEADROOM      = RAW headroom ON,  CA9 neutral clip OFF
 *   C_CA9_CLIP      = RAW headroom OFF, CA9 neutral clip ON
 *   D_HEADROOM_CA9  = RAW headroom ON,  CA9 neutral clip ON
 *
 * Only these two switches vary. CFA, demosaic, DNG black/white metadata,
 * NeutralToXY/ColorSpec, output matrix and display encoding are unchanged.
 * Legacy v0.5.3 enum names are retained as aliases so the existing diagnostic
 * activity remains source-compatible while callers migrate to the canonical
 * A/B/C/D names.
 */
public final class M10RHighlightFactorialRenderer {
    private M10RHighlightFactorialRenderer() {}

    public enum Mode {
        A_BASELINE(false, false),
        B_HEADROOM(true, false),
        C_CA9_CLIP(false, true),
        D_HEADROOM_CA9(true, true),

        /** @deprecated use A_BASELINE */
        @Deprecated WHITELEVEL_CLAMP_ONLY(false, false),
        /** @deprecated use D_HEADROOM_CA9 */
        @Deprecated HEADROOM_NEUTRAL_CLIP_ONLY(true, true);

        public final boolean retainRawHeadroom;
        public final boolean applyCa9NeutralClip;

        Mode(boolean retainRawHeadroom, boolean applyCa9NeutralClip) {
            this.retainRawHeadroom = retainRawHeadroom;
            this.applyCa9NeutralClip = applyCa9NeutralClip;
        }
    }

    public static final class Result {
        public final Mode mode;
        public final int width;
        public final int height;
        public final int sourceStride;
        public final int[] argb;
        public final SensorPreviewCore.CfaPattern cfaPattern;
        public final int[] ca9Gains;
        public final long[] cameraAboveOneCounts;
        public final long[] neutralClipCounts;
        public final long[] linearBelowZeroCounts;
        public final long[] linearAboveOneCounts;

        Result(Mode mode, int width, int height, int sourceStride, int[] argb,
               SensorPreviewCore.CfaPattern cfaPattern, int[] ca9Gains,
               long[] cameraAboveOneCounts, long[] neutralClipCounts,
               long[] linearBelowZeroCounts, long[] linearAboveOneCounts) {
            this.mode = mode;
            this.width = width;
            this.height = height;
            this.sourceStride = sourceStride;
            this.argb = argb;
            this.cfaPattern = cfaPattern;
            this.ca9Gains = ca9Gains;
            this.cameraAboveOneCounts = cameraAboveOneCounts;
            this.neutralClipCounts = neutralClipCounts;
            this.linearBelowZeroCounts = linearBelowZeroCounts;
            this.linearAboveOneCounts = linearAboveOneCounts;
        }

        public String diagnosticSummary() {
            return String.format(Locale.US,
                    "RENDER_PARITY1A %s: %dx%d from CFA stride=%d, CFA=%s\n" +
                    "Candidate only; controlled 2x2 variable isolation, NOT firmware-parity claimed.\n" +
                    "RAW headroom: %s; CA9 neutral clip: %s; ColorSpec unchanged.\n" +
                    "CA9 gains: [%d, %d, %d]\n" +
                    "Camera RGB >1 counts: R=%d G=%d B=%d\n" +
                    "Neutral-domain clip counts: R=%d G=%d B=%d\n" +
                    "Linear sRGB <0 counts: R=%d G=%d B=%d\n" +
                    "Linear sRGB >1 counts: R=%d G=%d B=%d",
                    mode.name(), width, height, sourceStride, cfaPattern.name(),
                    mode.retainRawHeadroom ? "ON" : "OFF",
                    mode.applyCa9NeutralClip ? "ON" : "OFF",
                    ca9Gains[0], ca9Gains[1], ca9Gains[2],
                    cameraAboveOneCounts[0], cameraAboveOneCounts[1], cameraAboveOneCounts[2],
                    neutralClipCounts[0], neutralClipCounts[1], neutralClipCounts[2],
                    linearBelowZeroCounts[0], linearBelowZeroCounts[1], linearBelowZeroCounts[2],
                    linearAboveOneCounts[0], linearAboveOneCounts[1], linearAboveOneCounts[2]);
        }
    }

    public static Result render(DngRawDecoder.RawImage raw, DngMetadataReader.DngInfo info, Mode mode) {
        return render(raw, info, mode, SensorPreviewCore.DEFAULT_MAX_DIMENSION);
    }

    static Result render(DngRawDecoder.RawImage raw, DngMetadataReader.DngInfo info,
                         Mode mode, int maxDimension) {
        if (raw == null || info == null || mode == null) {
            throw new IllegalArgumentException("raw/info/mode must not be null");
        }
        if (raw.width != info.width || raw.height != info.height) {
            throw new IllegalArgumentException("decoded RAW dimensions do not match DNG metadata");
        }
        if (info.colorMatrix1 == null || info.colorMatrix2 == null) {
            throw new IllegalArgumentException("ColorMatrix1/2 are required");
        }
        if (info.asShotNeutral == null || info.asShotNeutral.length != 3) {
            throw new IllegalArgumentException("AsShotNeutral is required");
        }
        if (maxDimension <= 0) throw new IllegalArgumentException("maxDimension must be > 0");

        M10RReferenceColorCore.CalibrationTemperatures temperatures =
                M10RReferenceColorCore.referenceTemperaturesForIlluminants(
                        info.calibrationIlluminant1, info.calibrationIlluminant2);
        M10RReferenceColorCore.WhiteSolution white = M10RReferenceColorCore.solveNeutralToXy(
                info.asShotNeutral, info.colorMatrix1, info.colorMatrix2,
                temperatures.t1, temperatures.t2);
        int[] gains = M10RColorSpecCore.recoverCa9Gains(info.asShotNeutral);
        SensorPreviewCore.CfaPattern cfa = SensorPreviewCore.CfaPattern.fromDng(
                info.cfaRepeatPatternDim, info.cfaPattern);

        int stride = Math.max(1, ceilDiv(Math.max(raw.width, raw.height), maxDimension));
        int outWidth = ceilDiv(raw.width, stride);
        int outHeight = ceilDiv(raw.height, stride);
        int[] argb = new int[Math.multiplyExact(outWidth, outHeight)];
        long[] cameraAboveOne = new long[3];
        long[] neutralClips = new long[3];
        long[] belowZero = new long[3];
        long[] aboveOne = new long[3];

        for (int oy = 0; oy < outHeight; oy++) {
            int sy = Math.min(oy * stride, raw.height - 1);
            for (int ox = 0; ox < outWidth; ox++) {
                int sx = Math.min(ox * stride, raw.width - 1);
                double[] camera = {
                        interpolate(raw.samples, raw.width, raw.height, sx, sy,
                                SensorPreviewCore.Channel.R, cfa, info.blackLevel, info.whiteLevel,
                                mode.retainRawHeadroom),
                        interpolate(raw.samples, raw.width, raw.height, sx, sy,
                                SensorPreviewCore.Channel.G, cfa, info.blackLevel, info.whiteLevel,
                                mode.retainRawHeadroom),
                        interpolate(raw.samples, raw.width, raw.height, sx, sy,
                                SensorPreviewCore.Channel.B, cfa, info.blackLevel, info.whiteLevel,
                                mode.retainRawHeadroom)
                };
                for (int c = 0; c < 3; c++) {
                    if (camera[c] > 1.0) cameraAboveOne[c]++;
                }

                double[] colorInput = camera;
                if (mode.applyCa9NeutralClip) {
                    for (int c = 0; c < 3; c++) {
                        if (camera[c] * gains[c] / M10RColorSpecCore.ASN_SCALE > 1.0) {
                            neutralClips[c]++;
                        }
                    }
                    colorInput = M10RNeutralClipReferenceRenderer.applyCa9NeutralSaturation(camera, gains);
                }

                double[] srgbLinear = M10RColorSpecCore.matVecMul(white.cameraToSrgbLinear, colorInput);
                for (int c = 0; c < 3; c++) {
                    if (srgbLinear[c] < 0.0) belowZero[c]++;
                    if (srgbLinear[c] > 1.0) aboveOne[c]++;
                }
                int r8 = SensorPreviewCore.toSrgb8(srgbLinear[0]);
                int g8 = SensorPreviewCore.toSrgb8(srgbLinear[1]);
                int b8 = SensorPreviewCore.toSrgb8(srgbLinear[2]);
                argb[oy * outWidth + ox] = 0xff000000 | (r8 << 16) | (g8 << 8) | b8;
            }
        }

        return new Result(mode, outWidth, outHeight, stride, argb, cfa, gains,
                cameraAboveOne, neutralClips, belowZero, aboveOne);
    }

    private static double interpolate(short[] samples, int width, int height,
                                      int x, int y, SensorPreviewCore.Channel wanted,
                                      SensorPreviewCore.CfaPattern cfa,
                                      double[] black, double[] white,
                                      boolean preserveHeadroom) {
        if (cfa.channelAt(x, y) == wanted) {
            return normalize(samples[y * width + x] & 0xffff, x, y, black, white,
                    preserveHeadroom);
        }
        double sum = 0.0;
        int count = 0;
        for (int dy = -1; dy <= 1; dy++) {
            int yy = y + dy;
            if (yy < 0 || yy >= height) continue;
            for (int dx = -1; dx <= 1; dx++) {
                int xx = x + dx;
                if (xx < 0 || xx >= width || (dx == 0 && dy == 0)) continue;
                if (cfa.channelAt(xx, yy) != wanted) continue;
                sum += normalize(samples[yy * width + xx] & 0xffff, xx, yy,
                        black, white, preserveHeadroom);
                count++;
            }
        }
        if (count == 0) throw new IllegalStateException("no Bayer neighbour for " + wanted);
        return sum / count;
    }

    static double normalize(int sample, int x, int y, double[] black, double[] white,
                            boolean preserveHeadroom) {
        if (preserveHeadroom) {
            return M10RLinearReferenceRenderer.normalizedLinear(sample, x, y, black, white);
        }
        return SensorPreviewCore.normalized(sample, x, y, black, white);
    }

    private static int ceilDiv(int a, int b) {
        return (a + b - 1) / b;
    }
}
