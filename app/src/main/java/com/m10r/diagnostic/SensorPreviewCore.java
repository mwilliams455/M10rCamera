package com.m10r.diagnostic;

import java.util.Locale;

/**
 * v0.4 sensor-sanity preview only.
 *
 * This class deliberately sits downstream of the frozen pixel-exact SOF3 decoder. It resolves
 * the DNG CFA pattern, applies DNG black/white normalization, performs a deterministic bilinear
 * demosaic, applies diagnostic AsShotNeutral white balance, and encodes the bounded preview to
 * sRGB. It does not apply Leica ColorMatrix/CA9/CC0/tone/DG/CC1 rendering.
 */
public final class SensorPreviewCore {
    private SensorPreviewCore() {}

    public static final int DEFAULT_MAX_DIMENSION = 1600;

    enum Channel { R, G, B }

    public enum CfaPattern {
        RGGB(new Channel[] { Channel.R, Channel.G, Channel.G, Channel.B }),
        GRBG(new Channel[] { Channel.G, Channel.R, Channel.B, Channel.G }),
        GBRG(new Channel[] { Channel.G, Channel.B, Channel.R, Channel.G }),
        BGGR(new Channel[] { Channel.B, Channel.G, Channel.G, Channel.R });

        private final Channel[] sites;

        CfaPattern(Channel[] sites) {
            this.sites = sites;
        }

        Channel channelAt(int x, int y) {
            return sites[((y & 1) << 1) | (x & 1)];
        }

        static CfaPattern fromDng(long[] repeatDim, byte[] pattern) {
            if (repeatDim != null && repeatDim.length >= 2 &&
                    (repeatDim[0] != 2 || repeatDim[1] != 2)) {
                throw new IllegalArgumentException("v0.4 requires a 2x2 Bayer CFA repeat; got " +
                        repeatDim[0] + "x" + repeatDim[1]);
            }
            if (pattern == null || pattern.length < 4) {
                throw new IllegalArgumentException("DNG CFA pattern is missing or shorter than 2x2");
            }
            int p0 = pattern[0] & 0xff;
            int p1 = pattern[1] & 0xff;
            int p2 = pattern[2] & 0xff;
            int p3 = pattern[3] & 0xff;
            if (p0 == 0 && p1 == 1 && p2 == 1 && p3 == 2) return RGGB;
            if (p0 == 1 && p1 == 0 && p2 == 2 && p3 == 1) return GRBG;
            if (p0 == 1 && p1 == 2 && p2 == 0 && p3 == 1) return GBRG;
            if (p0 == 2 && p1 == 1 && p2 == 1 && p3 == 0) return BGGR;
            throw new IllegalArgumentException(String.format(Locale.US,
                    "unsupported CFA pattern [%d,%d,%d,%d] (DNG plane ids must be R=0,G=1,B=2)",
                    p0, p1, p2, p3));
        }
    }

    public static final class PreviewResult {
        public final int width;
        public final int height;
        public final int sourceStride;
        public final int[] argb;
        public final CfaPattern cfaPattern;
        public final double blackLevel;
        public final double whiteLevel;
        public final double redGain;
        public final double greenGain;
        public final double blueGain;

        PreviewResult(int width, int height, int sourceStride, int[] argb,
                      CfaPattern cfaPattern, double blackLevel, double whiteLevel,
                      double redGain, double greenGain, double blueGain) {
            this.width = width;
            this.height = height;
            this.sourceStride = sourceStride;
            this.argb = argb;
            this.cfaPattern = cfaPattern;
            this.blackLevel = blackLevel;
            this.whiteLevel = whiteLevel;
            this.redGain = redGain;
            this.greenGain = greenGain;
            this.blueGain = blueGain;
        }

        public String diagnosticSummary() {
            return String.format(Locale.US,
                    "v0.4 SENSOR PREVIEW: %dx%d from CFA stride=%d\n" +
                    "Resolved CFA: %s\n" +
                    "Normalization: black=%.6f, white=%.6f\n" +
                    "AsShotNeutral WB gains: R=%.6f, G=%.6f, B=%.6f\n" +
                    "Preview transform: bilinear Bayer demosaic -> diagnostic WB -> sRGB gamma\n" +
                    "RENDER BOUNDARY: sensor-sanity preview only; no CA9/CC0/tone/DG/CC1.",
                    width, height, sourceStride, cfaPattern.name(),
                    blackLevel, whiteLevel, redGain, greenGain, blueGain);
        }
    }

    public static PreviewResult render(DngRawDecoder.RawImage raw,
                                       DngMetadataReader.DngInfo info) {
        return render(raw, info, DEFAULT_MAX_DIMENSION);
    }

    public static PreviewResult render(DngRawDecoder.RawImage raw,
                                       DngMetadataReader.DngInfo info,
                                       int maxDimension) {
        if (raw == null) throw new IllegalArgumentException("raw == null");
        if (info == null) throw new IllegalArgumentException("info == null");
        if (raw.width != info.width || raw.height != info.height) {
            throw new IllegalArgumentException("decoded RAW dimensions do not match DNG metadata");
        }
        return render(raw.samples, raw.width, raw.height,
                info.cfaRepeatPatternDim, info.cfaPattern,
                info.blackLevel, info.whiteLevel, info.asShotNeutral, maxDimension);
    }

    static PreviewResult render(short[] samples, int width, int height,
                                long[] repeatDim, byte[] cfaPattern,
                                double[] blackLevel, double[] whiteLevel,
                                double[] asShotNeutral, int maxDimension) {
        if (samples == null) throw new IllegalArgumentException("samples == null");
        if (width <= 1 || height <= 1) throw new IllegalArgumentException("RAW dimensions must exceed 1x1");
        if ((long) width * height != samples.length) {
            throw new IllegalArgumentException("RAW sample count does not match dimensions");
        }
        if (maxDimension <= 0) throw new IllegalArgumentException("maxDimension must be > 0");

        CfaPattern cfa = CfaPattern.fromDng(repeatDim, cfaPattern);
        validateLevels(blackLevel, "BlackLevel");
        validateLevels(whiteLevel, "WhiteLevel");
        double[] gains = whiteBalanceGains(asShotNeutral);

        // Integer source sampling bounds memory without allocating a full RGB float frame.
        int stride = Math.max(1, ceilDiv(Math.max(width, height), maxDimension));
        int outWidth = ceilDiv(width, stride);
        int outHeight = ceilDiv(height, stride);
        int[] argb = new int[Math.multiplyExact(outWidth, outHeight)];

        for (int oy = 0; oy < outHeight; oy++) {
            int sy = Math.min(oy * stride, height - 1);
            for (int ox = 0; ox < outWidth; ox++) {
                int sx = Math.min(ox * stride, width - 1);

                double r = interpolate(samples, width, height, sx, sy, Channel.R,
                        cfa, blackLevel, whiteLevel) * gains[0];
                double g = interpolate(samples, width, height, sx, sy, Channel.G,
                        cfa, blackLevel, whiteLevel) * gains[1];
                double b = interpolate(samples, width, height, sx, sy, Channel.B,
                        cfa, blackLevel, whiteLevel) * gains[2];

                int r8 = toSrgb8(r);
                int g8 = toSrgb8(g);
                int b8 = toSrgb8(b);
                argb[oy * outWidth + ox] = 0xff000000 | (r8 << 16) | (g8 << 8) | b8;
            }
        }

        return new PreviewResult(outWidth, outHeight, stride, argb, cfa,
                representativeLevel(blackLevel), representativeLevel(whiteLevel),
                gains[0], gains[1], gains[2]);
    }

    private static double interpolate(short[] samples, int width, int height,
                                      int x, int y, Channel wanted,
                                      CfaPattern cfa, double[] black, double[] white) {
        if (cfa.channelAt(x, y) == wanted) {
            return normalized(samples[y * width + x] & 0xffff, x, y, black, white);
        }

        // For a Bayer 2x2 mosaic, averaging all matching sites in the local 3x3 is exactly
        // bilinear: G at R/B has four orthogonal neighbours; R/B at G has two orthogonal
        // neighbours; opposite R/B sites have four diagonal neighbours.
        double sum = 0.0;
        int count = 0;
        for (int dy = -1; dy <= 1; dy++) {
            int yy = y + dy;
            if (yy < 0 || yy >= height) continue;
            for (int dx = -1; dx <= 1; dx++) {
                int xx = x + dx;
                if (xx < 0 || xx >= width || (dx == 0 && dy == 0)) continue;
                if (cfa.channelAt(xx, yy) != wanted) continue;
                sum += normalized(samples[yy * width + xx] & 0xffff, xx, yy, black, white);
                count++;
            }
        }
        if (count == 0) {
            throw new IllegalStateException("no Bayer neighbour available for " + wanted +
                    " at " + x + "," + y);
        }
        return sum / count;
    }

    static double normalized(int sample, int x, int y, double[] black, double[] white) {
        double lo = levelAt(black, x, y);
        double hi = levelAt(white, x, y);
        if (!(hi > lo)) {
            throw new IllegalArgumentException("WhiteLevel must be greater than BlackLevel");
        }
        return clamp01((sample - lo) / (hi - lo));
    }

    static double[] whiteBalanceGains(double[] neutral) {
        if (neutral == null || neutral.length != 3) {
            throw new IllegalArgumentException("AsShotNeutral must contain exactly R/G/B values");
        }
        for (double v : neutral) {
            if (!(v > 0.0) || !Double.isFinite(v)) {
                throw new IllegalArgumentException("AsShotNeutral values must be finite and > 0");
            }
        }
        return new double[] { neutral[1] / neutral[0], 1.0, neutral[1] / neutral[2] };
    }

    static int toSrgb8(double linear) {
        double c = clamp01(linear);
        double encoded = c <= 0.0031308
                ? 12.92 * c
                : 1.055 * Math.pow(c, 1.0 / 2.4) - 0.055;
        return (int) Math.round(clamp01(encoded) * 255.0);
    }

    private static void validateLevels(double[] levels, String name) {
        if (levels == null || levels.length == 0) {
            throw new IllegalArgumentException(name + " is missing");
        }
        if (levels.length != 1 && levels.length != 4) {
            throw new IllegalArgumentException(name +
                    " must be scalar or one value per 2x2 Bayer site in v0.4; count=" + levels.length);
        }
        for (double v : levels) {
            if (!Double.isFinite(v)) throw new IllegalArgumentException(name + " contains non-finite data");
        }
    }

    private static double levelAt(double[] levels, int x, int y) {
        return levels.length == 1 ? levels[0] : levels[((y & 1) << 1) | (x & 1)];
    }

    private static double representativeLevel(double[] levels) {
        double sum = 0.0;
        for (double v : levels) sum += v;
        return sum / levels.length;
    }

    private static int ceilDiv(int a, int b) {
        return (a + b - 1) / b;
    }

    private static double clamp01(double x) {
        if (x <= 0.0) return 0.0;
        if (x >= 1.0) return 1.0;
        return x;
    }
}
