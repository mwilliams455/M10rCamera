package com.m10r.diagnostic;

import java.util.Locale;

/**
 * v0.5.3 controlled highlight-boundary experiment.
 *
 * Together with frozen v0.5.1 (headroom/no neutral clip) and unchanged v0.5.2
 * (WhiteLevel clamp + neutral clip), these two modes complete a 2x2 isolation:
 *   A headroom + no neutral clip   = v0.5.1
 *   B WhiteLevel clamp only        = WHITELEVEL_CLAMP_ONLY
 *   C headroom + neutral clip only = HEADROOM_NEUTRAL_CLIP_ONLY
 *   D WhiteLevel clamp + neutral   = v0.5.2
 *
 * This is diagnostic variable isolation only. It does not claim the exact Leica
 * 11-bit B2Y front-end arithmetic or stage ordering.
 */
public final class M10RHighlightFactorialRenderer {
    private M10RHighlightFactorialRenderer() {}

    public enum Mode {
        WHITELEVEL_CLAMP_ONLY,
        HEADROOM_NEUTRAL_CLIP_ONLY
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
            String policy = mode == Mode.WHITELEVEL_CLAMP_ONLY
                    ? "WhiteLevel clamp only; no CA9 neutral-domain clip"
                    : "positive headroom preserved; CA9 neutral-domain clip only";
            return String.format(Locale.US,
                    "v0.5.3 FACTORIAL %s: %dx%d from CFA stride=%d, CFA=%s\n" +
                    "Candidate only; variable-isolation diagnostic, NOT firmware-parity claimed.\n" +
                    "Policy: %s -> unchanged v0.5.1 ColorSpec.\n" +
                    "CA9 gains: [%d, %d, %d]\n" +
                    "Camera RGB >1 counts before optional neutral clip: R=%d G=%d B=%d\n" +
                    "Neutral-domain clip counts: R=%d G=%d B=%d\n" +
                    "Linear sRGB <0 counts: R=%d G=%d B=%d\n" +
                    "Linear sRGB >1 counts: R=%d G=%d B=%d",
                    mode.name(), width, height, sourceStride, cfaPattern.name(), policy,
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
        boolean preserveHeadroom = mode == Mode.HEADROOM_NEUTRAL_CLIP_ONLY;

        for (int oy = 0; oy < outHeight; oy++) {
            int sy = Math.min(oy * stride, raw.height - 1);
            for (int ox = 0; ox < outWidth; ox++) {
                int sx = Math.min(ox * stride, raw.width - 1);
                double[] camera = {
                        interpolate(raw.samples, raw.width, raw.height, sx, sy,
                                SensorPreviewCore.Channel.R, cfa, info.blackLevel, info.whiteLevel,
                                preserveHeadroom),
                        interpolate(raw.samples, raw.width, raw.height, sx, sy,
                                SensorPreviewCore.Channel.G, cfa, info.blackLevel, info.whiteLevel,
                                preserveHeadroom),
                        interpolate(raw.samples, raw.width, raw.height, sx, sy,
                                SensorPreviewCore.Channel.B, cfa, info.blackLevel, info.whiteLevel,
                                preserveHeadroom)
                };
                for (int c = 0; c < 3; c++) {
                    if (camera[c] > 1.0) cameraAboveOne[c]++;
                }

                double[] colorInput = camera;
                if (mode == Mode.HEADROOM_NEUTRAL_CLIP_ONLY) {
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
