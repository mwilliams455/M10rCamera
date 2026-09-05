package com.m10r.diagnostic;

import java.util.Locale;

/** Bounded v0.5 image renderer for the proven Leica linear ColorSpec stage only. */
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

        Result(int width, int height, int sourceStride, int[] argb,
               SensorPreviewCore.CfaPattern cfaPattern,
               M10RReferenceColorCore.WhiteSolution whiteSolution,
               String temperatureProvenance) {
            this.width = width;
            this.height = height;
            this.sourceStride = sourceStride;
            this.argb = argb;
            this.cfaPattern = cfaPattern;
            this.whiteSolution = whiteSolution;
            this.temperatureProvenance = temperatureProvenance;
        }

        public String diagnosticSummary() {
            return String.format(Locale.US,
                    "v0.5 LINEAR IMAGE: %dx%d from CFA stride=%d, CFA=%s\n%s",
                    width, height, sourceStride, cfaPattern.name(),
                    whiteSolution.diagnosticSummary(temperatureProvenance));
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
            throw new IllegalArgumentException("ColorMatrix1/2 are required for v0.5 Leica linear reference");
        }
        if (info.asShotNeutral == null || info.asShotNeutral.length != 3) {
            throw new IllegalArgumentException("AsShotNeutral is required for v0.5 Leica linear reference");
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
                double[] srgbLinear = M10RColorSpecCore.matVecMul(white.cameraToSrgbLinear, camera);
                int r8 = SensorPreviewCore.toSrgb8(srgbLinear[0]);
                int g8 = SensorPreviewCore.toSrgb8(srgbLinear[1]);
                int b8 = SensorPreviewCore.toSrgb8(srgbLinear[2]);
                argb[oy * outWidth + ox] = 0xff000000 | (r8 << 16) | (g8 << 8) | b8;
            }
        }

        return new Result(outWidth, outHeight, stride, argb, cfa, white, temperatures.provenance);
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
