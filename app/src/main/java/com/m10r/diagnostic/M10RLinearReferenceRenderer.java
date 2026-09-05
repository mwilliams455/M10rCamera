package com.m10r.diagnostic;

import java.util.Locale;

/**
 * Bounded v0.5.1 image renderer for the proven Leica linear ColorSpec stage only.
 *
 * v0.4 deliberately clamps normalized sensor values to [0,1] for its display sanity preview.
 * This linear reference must not reuse that display clamp: genuine M10-R compression-7 samples
 * can extend above the DNG WhiteLevel (15000) to the 14-bit code maximum (16383). v0.5.1 keeps
 * that positive headroom through demosaic and ColorSpec, then clamps only at the final 8-bit
 * diagnostic display conversion.
 */
public final class M10RLinearReferenceRenderer {
    private M10RLinearReferenceRenderer() {}

    public static final class Result {
        public final int width;
        public final int height;
        public final int sourceStride;
        public final int[] argb;
        public final SensorPreviewCore.CfaPattern cfaPattern;
        public final M10RReferenceColorCore.WhiteSolution whiteSolution;
        public final String temperatureProvenance;
        public final double[] cameraMin;
        public final double[] cameraMax;
        public final long[] cameraAboveOne;
        public final double[] outputMin;
        public final double[] outputMax;
        public final long[] outputBelowZero;
        public final long[] outputAboveOne;

        Result(int width, int height, int sourceStride, int[] argb,
               SensorPreviewCore.CfaPattern cfaPattern,
               M10RReferenceColorCore.WhiteSolution whiteSolution,
               String temperatureProvenance,
               double[] cameraMin, double[] cameraMax, long[] cameraAboveOne,
               double[] outputMin, double[] outputMax,
               long[] outputBelowZero, long[] outputAboveOne) {
            this.width = width;
            this.height = height;
            this.sourceStride = sourceStride;
            this.argb = argb;
            this.cfaPattern = cfaPattern;
            this.whiteSolution = whiteSolution;
            this.temperatureProvenance = temperatureProvenance;
            this.cameraMin = cameraMin;
            this.cameraMax = cameraMax;
            this.cameraAboveOne = cameraAboveOne;
            this.outputMin = outputMin;
            this.outputMax = outputMax;
            this.outputBelowZero = outputBelowZero;
            this.outputAboveOne = outputAboveOne;
        }

        public String diagnosticSummary() {
            return String.format(Locale.US,
                    "v0.5.1 LINEAR IMAGE: %dx%d from CFA stride=%d, CFA=%s\n%s\n" +
                    "HEADROOM POLICY: positive CFA values above DNG WhiteLevel are preserved through demosaic + ColorSpec; clamp occurs only for the 8-bit diagnostic display.\n" +
                    "Camera RGB pre-ColorSpec min/max: R=%.6f/%.6f G=%.6f/%.6f B=%.6f/%.6f\n" +
                    "Camera RGB >1 counts: R=%d G=%d B=%d\n" +
                    "Linear sRGB pre-display min/max: R=%.6f/%.6f G=%.6f/%.6f B=%.6f/%.6f\n" +
                    "Linear sRGB <0 counts: R=%d G=%d B=%d\n" +
                    "Linear sRGB >1 counts: R=%d G=%d B=%d",
                    width, height, sourceStride, cfaPattern.name(),
                    whiteSolution.diagnosticSummary(temperatureProvenance),
                    cameraMin[0], cameraMax[0], cameraMin[1], cameraMax[1],
                    cameraMin[2], cameraMax[2],
                    cameraAboveOne[0], cameraAboveOne[1], cameraAboveOne[2],
                    outputMin[0], outputMax[0], outputMin[1], outputMax[1],
                    outputMin[2], outputMax[2],
                    outputBelowZero[0], outputBelowZero[1], outputBelowZero[2],
                    outputAboveOne[0], outputAboveOne[1], outputAboveOne[2]);
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
            throw new IllegalArgumentException("ColorMatrix1/2 are required for v0.5.1 Leica linear reference");
        }
        if (info.asShotNeutral == null || info.asShotNeutral.length != 3) {
            throw new IllegalArgumentException("AsShotNeutral is required for v0.5.1 Leica linear reference");
        }
        if (maxDimension <= 0) throw new IllegalArgumentException("maxDimension must be > 0");

        M10RReferenceColorCore.CalibrationTemperatures temperatures =
                M10RReferenceColorCore.referenceTemperaturesForIlluminants(
                        info.calibrationIlluminant1, info.calibrationIlluminant2);
        M10RReferenceColorCore.WhiteSolution white = M10RReferenceColorCore.solveNeutralToXy(
                info.asShotNeutral, info.colorMatrix1, info.colorMatrix2,
                temperatures.t1, temperatures.t2);

        SensorPreviewCore.CfaPattern cfa = SensorPreviewCore.CfaPattern.fromDng(
                info.cfaRepeatPatternDim, info.cfaPattern);
        int stride = Math.max(1, ceilDiv(Math.max(raw.width, raw.height), maxDimension));
        int outWidth = ceilDiv(raw.width, stride);
        int outHeight = ceilDiv(raw.height, stride);
        int[] argb = new int[Math.multiplyExact(outWidth, outHeight)];

        double[] cameraMin = {Double.POSITIVE_INFINITY, Double.POSITIVE_INFINITY, Double.POSITIVE_INFINITY};
        double[] cameraMax = {Double.NEGATIVE_INFINITY, Double.NEGATIVE_INFINITY, Double.NEGATIVE_INFINITY};
        long[] cameraAboveOne = new long[3];
        double[] outputMin = {Double.POSITIVE_INFINITY, Double.POSITIVE_INFINITY, Double.POSITIVE_INFINITY};
        double[] outputMax = {Double.NEGATIVE_INFINITY, Double.NEGATIVE_INFINITY, Double.NEGATIVE_INFINITY};
        long[] outputBelowZero = new long[3];
        long[] outputAboveOne = new long[3];

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
                track(camera, cameraMin, cameraMax, null, cameraAboveOne);

                double[] srgbLinear = M10RColorSpecCore.matVecMul(white.cameraToSrgbLinear, camera);
                track(srgbLinear, outputMin, outputMax, outputBelowZero, outputAboveOne);

                int r8 = SensorPreviewCore.toSrgb8(srgbLinear[0]);
                int g8 = SensorPreviewCore.toSrgb8(srgbLinear[1]);
                int b8 = SensorPreviewCore.toSrgb8(srgbLinear[2]);
                argb[oy * outWidth + ox] = 0xff000000 | (r8 << 16) | (g8 << 8) | b8;
            }
        }

        return new Result(outWidth, outHeight, stride, argb, cfa, white, temperatures.provenance,
                cameraMin, cameraMax, cameraAboveOne,
                outputMin, outputMax, outputBelowZero, outputAboveOne);
    }

    private static void track(double[] v, double[] min, double[] max,
                              long[] belowZero, long[] aboveOne) {
        for (int c = 0; c < 3; c++) {
            if (v[c] < min[c]) min[c] = v[c];
            if (v[c] > max[c]) max[c] = v[c];
            if (belowZero != null && v[c] < 0.0) belowZero[c]++;
            if (aboveOne != null && v[c] > 1.0) aboveOne[c]++;
        }
    }

    private static double interpolate(short[] samples, int width, int height,
                                      int x, int y, SensorPreviewCore.Channel wanted,
                                      SensorPreviewCore.CfaPattern cfa,
                                      double[] black, double[] white) {
        if (cfa.channelAt(x, y) == wanted) {
            return normalizedLinear(samples[y * width + x] & 0xffff, x, y, black, white);
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
                sum += normalizedLinear(samples[yy * width + xx] & 0xffff,
                        xx, yy, black, white);
                count++;
            }
        }
        if (count == 0) throw new IllegalStateException("no Bayer neighbour for " + wanted);
        return sum / count;
    }

    /**
     * Linear ColorSpec normalization. Negative values are floored at black, but positive values
     * above DNG WhiteLevel are intentionally retained as headroom instead of display-clamped.
     */
    static double normalizedLinear(int sample, int x, int y, double[] black, double[] white) {
        double lo = levelAt(black, x, y, "BlackLevel");
        double hi = levelAt(white, x, y, "WhiteLevel");
        if (!(hi > lo)) throw new IllegalArgumentException("WhiteLevel must be greater than BlackLevel");
        double v = (sample - lo) / (hi - lo);
        return v <= 0.0 ? 0.0 : v;
    }

    private static double levelAt(double[] levels, int x, int y, String name) {
        if (levels == null || (levels.length != 1 && levels.length != 4)) {
            throw new IllegalArgumentException(name + " must be scalar or one value per 2x2 Bayer site");
        }
        double value = levels.length == 1 ? levels[0] : levels[((y & 1) << 1) | (x & 1)];
        if (!Double.isFinite(value)) throw new IllegalArgumentException(name + " contains non-finite data");
        return value;
    }

    private static int ceilDiv(int a, int b) {
        return (a + b - 1) / b;
    }
}
