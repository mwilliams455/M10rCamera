package com.m10r.diagnostic;

import java.util.Locale;

/**
 * v0.5.2 experimental highlight-boundary diagnostic.
 *
 * This deliberately keeps the v0.5.1 ColorSpec transform unchanged, but tests one candidate
 * pre-ColorSpec saturation policy in the recovered CA9 neutral/gain domain. It is NOT yet claimed
 * as Leica firmware parity. The purpose is to determine whether the cyan/magenta highlight
 * excursions are caused by sensor-channel clipping before CC0.
 */
public final class M10RNeutralClipReferenceRenderer {
    private M10RNeutralClipReferenceRenderer() {}

    public static final class Result {
        public final int width;
        public final int height;
        public final int sourceStride;
        public final int[] argb;
        public final SensorPreviewCore.CfaPattern cfaPattern;
        public final M10RReferenceColorCore.WhiteSolution whiteSolution;
        public final int[] ca9Gains;
        public final double[] firmwareNeutral;
        public final long[] neutralDomainClipCounts;
        public final long[] linearBelowZeroCounts;
        public final long[] linearAboveOneCounts;

        Result(int width, int height, int sourceStride, int[] argb,
               SensorPreviewCore.CfaPattern cfaPattern,
               M10RReferenceColorCore.WhiteSolution whiteSolution,
               int[] ca9Gains, double[] firmwareNeutral,
               long[] neutralDomainClipCounts,
               long[] linearBelowZeroCounts,
               long[] linearAboveOneCounts) {
            this.width = width;
            this.height = height;
            this.sourceStride = sourceStride;
            this.argb = argb;
            this.cfaPattern = cfaPattern;
            this.whiteSolution = whiteSolution;
            this.ca9Gains = ca9Gains;
            this.firmwareNeutral = firmwareNeutral;
            this.neutralDomainClipCounts = neutralDomainClipCounts;
            this.linearBelowZeroCounts = linearBelowZeroCounts;
            this.linearAboveOneCounts = linearAboveOneCounts;
        }

        public String diagnosticSummary() {
            return String.format(Locale.US,
                    "v0.5.2 EXPERIMENTAL CA9 NEUTRAL-CLIP IMAGE: %dx%d from CFA stride=%d, CFA=%s\n" +
                    "Candidate only; NOT firmware-parity claimed.\n" +
                    "CA9 gains: [%d, %d, %d]\n" +
                    "Quantized firmware neutral: [%.9f, %.9f, %.9f]\n" +
                    "Policy: DNG WhiteLevel clamp -> demosaic -> CA9 gain domain -> clip each balanced channel at 1 -> return to camera domain -> unchanged v0.5.1 ColorSpec.\n" +
                    "Neutral-domain clip counts: R=%d G=%d B=%d\n" +
                    "Linear sRGB <0 counts after candidate: R=%d G=%d B=%d\n" +
                    "Linear sRGB >1 counts after candidate: R=%d G=%d B=%d",
                    width, height, sourceStride, cfaPattern.name(),
                    ca9Gains[0], ca9Gains[1], ca9Gains[2],
                    firmwareNeutral[0], firmwareNeutral[1], firmwareNeutral[2],
                    neutralDomainClipCounts[0], neutralDomainClipCounts[1], neutralDomainClipCounts[2],
                    linearBelowZeroCounts[0], linearBelowZeroCounts[1], linearBelowZeroCounts[2],
                    linearAboveOneCounts[0], linearAboveOneCounts[1], linearAboveOneCounts[2]);
        }
    }

    public static Result render(DngRawDecoder.RawImage raw, DngMetadataReader.DngInfo info) {
        return render(raw, info, SensorPreviewCore.DEFAULT_MAX_DIMENSION);
    }

    static Result render(DngRawDecoder.RawImage raw, DngMetadataReader.DngInfo info, int maxDimension) {
        if (raw == null || info == null) throw new IllegalArgumentException("raw/info must not be null");
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
        double[] firmwareNeutral = M10RColorSpecCore.gainsToFirmwareNeutral(gains);
        SensorPreviewCore.CfaPattern cfa = SensorPreviewCore.CfaPattern.fromDng(
                info.cfaRepeatPatternDim, info.cfaPattern);

        int stride = Math.max(1, ceilDiv(Math.max(raw.width, raw.height), maxDimension));
        int outWidth = ceilDiv(raw.width, stride);
        int outHeight = ceilDiv(raw.height, stride);
        int[] argb = new int[Math.multiplyExact(outWidth, outHeight)];
        long[] clipped = new long[3];
        long[] belowZero = new long[3];
        long[] aboveOne = new long[3];

        for (int oy = 0; oy < outHeight; oy++) {
            int sy = Math.min(oy * stride, raw.height - 1);
            for (int ox = 0; ox < outWidth; ox++) {
                int sx = Math.min(ox * stride, raw.width - 1);
                double[] camera = {
                        interpolate(raw.samples, raw.width, raw.height, sx, sy,
                                SensorPreviewCore.Channel.R, cfa, info.blackLevel, info.whiteLevel),
                        interpolate(raw.samples, raw.width, raw.height, sx, sy,
                                SensorPreviewCore.Channel.G, cfa, info.blackLevel, info.whiteLevel),
                        interpolate(raw.samples, raw.width, raw.height, sx, sy,
                                SensorPreviewCore.Channel.B, cfa, info.blackLevel, info.whiteLevel)
                };

                double[] guarded = applyCa9NeutralSaturation(camera, gains, clipped);
                double[] srgbLinear = M10RColorSpecCore.matVecMul(white.cameraToSrgbLinear, guarded);
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

        return new Result(outWidth, outHeight, stride, argb, cfa, white,
                gains, firmwareNeutral, clipped, belowZero, aboveOne);
    }

    static double[] applyCa9NeutralSaturation(double[] camera, int[] gains) {
        return applyCa9NeutralSaturation(camera, gains, null);
    }

    private static double[] applyCa9NeutralSaturation(double[] camera, int[] gains, long[] clipCounts) {
        if (camera == null || camera.length != 3 || gains == null || gains.length != 3) {
            throw new IllegalArgumentException("camera/gains must have three channels");
        }
        double[] out = new double[3];
        for (int c = 0; c < 3; c++) {
            if (!(gains[c] > 0)) throw new IllegalArgumentException("CA9 gains must be positive");
            double balanced = camera[c] * gains[c] / M10RColorSpecCore.ASN_SCALE;
            if (balanced > 1.0) {
                balanced = 1.0;
                if (clipCounts != null) clipCounts[c]++;
            }
            if (balanced < 0.0) balanced = 0.0;
            out[c] = balanced * M10RColorSpecCore.ASN_SCALE / gains[c];
        }
        return out;
    }

    private static double interpolate(short[] samples, int width, int height,
                                      int x, int y, SensorPreviewCore.Channel wanted,
                                      SensorPreviewCore.CfaPattern cfa,
                                      double[] black, double[] white) {
        if (cfa.channelAt(x, y) == wanted) {
            return SensorPreviewCore.normalized(samples[y * width + x] & 0xffff, x, y, black, white);
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
                sum += SensorPreviewCore.normalized(samples[yy * width + xx] & 0xffff,
                        xx, yy, black, white);
                count++;
            }
        }
        if (count == 0) throw new IllegalStateException("no Bayer neighbour for " + wanted);
        return sum / count;
    }

    private static int ceilDiv(int a, int b) {
        return (a + b - 1) / b;
    }
}
