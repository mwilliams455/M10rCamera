package com.m10r.diagnostic;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * REFERENCE_TRANSFER_RGB1B domain-placement factorial.
 *
 * Frozen upstream boundary:
 * DNG WhiteLevel clamp -> bilinear Bayer -> CA9 neutral clip -> frozen Leica ColorSpec
 * -> linear sRGB.
 *
 * Exact recovered MEDIUM -> Differential Gamma is then exercised in five placements:
 *   LL_OETF     : linear luma -> shared gain on linear RGB -> standard sRGB OETF (RGB1A ON)
 *   LL_IDENTITY : linear luma -> shared gain on linear RGB -> identity output (RGB1A OFF control)
 *   LE_IDENTITY : linear luma -> shared gain on bounded encoded sRGB -> identity output
 *   EL_OETF     : bounded encoded-sRGB luma -> shared gain on linear RGB -> standard sRGB OETF
 *   EE_IDENTITY : bounded encoded-sRGB luma -> shared gain on bounded encoded sRGB -> identity output
 *
 * There is no fitted gamma, exposure, WB, colour, affine or tone term. This research renderer
 * does not alter the live Android capture branch.
 */
public final class M10RTransferRgb1BRenderer {
    private M10RTransferRgb1BRenderer() {}

    public static final int INPUT_MAX = 0x3fff;
    public static final int TONE_ENTRIES = 10240;
    public static final int DG_ENTRIES = 32768;
    public static final int DG_OUT_MAX = 0x3fff;

    public static final String LL_OETF = "linear_luma_linear_gain_oetf";
    public static final String LL_IDENTITY = "linear_luma_linear_gain_identity";
    public static final String LE_IDENTITY = "linear_luma_encoded_gain_identity";
    public static final String EL_OETF = "encoded_luma_linear_gain_oetf";
    public static final String EE_IDENTITY = "encoded_luma_encoded_gain_identity";

    public static final class Assets {
        final int[] tone;
        final int[] dg;

        private Assets(int[] tone, int[] dg) {
            this.tone = tone;
            this.dg = dg;
        }

        public static Assets load(Path tonePath, Path dgPath) throws IOException {
            byte[] tb = Files.readAllBytes(tonePath);
            byte[] db = Files.readAllBytes(dgPath);
            if (tb.length != TONE_ENTRIES * 4) {
                throw new IllegalArgumentException("MEDIUM asset byte length=" + tb.length);
            }
            if (db.length != DG_ENTRIES * 2) {
                throw new IllegalArgumentException("DG asset byte length=" + db.length);
            }
            ByteBuffer tbuf = ByteBuffer.wrap(tb).order(ByteOrder.LITTLE_ENDIAN);
            ByteBuffer dbuf = ByteBuffer.wrap(db).order(ByteOrder.LITTLE_ENDIAN);
            int[] tone = new int[TONE_ENTRIES];
            int[] dg = new int[DG_ENTRIES];
            for (int i = 0; i < tone.length; i++) tone[i] = tbuf.getInt();
            for (int i = 0; i < dg.length; i++) dg[i] = dbuf.getShort() & 0xffff;
            return new Assets(tone, dg);
        }
    }

    private static final class MapStats {
        long inputLow;
        long inputHigh;
        long inputNonFinite;
        long dgLow;
        long dgHigh;
    }

    public static final class Result {
        public final int width;
        public final int height;
        public final int sourceStride;
        public final int[] llOetfArgb;
        public final int[] llIdentityArgb;
        public final int[] leIdentityArgb;
        public final int[] elOetfArgb;
        public final int[] eeIdentityArgb;
        public final int[] ca9Gains;
        public final long[] neutralClipCounts;
        public final long linearLumaInputLow;
        public final long linearLumaInputHigh;
        public final long linearLumaInputNonFinite;
        public final long linearDgIndexLow;
        public final long linearDgIndexHigh;
        public final long encodedLumaInputLow;
        public final long encodedLumaInputHigh;
        public final long encodedLumaInputNonFinite;
        public final long encodedDgIndexLow;
        public final long encodedDgIndexHigh;

        Result(int width, int height, int sourceStride,
               int[] llOetfArgb, int[] llIdentityArgb, int[] leIdentityArgb,
               int[] elOetfArgb, int[] eeIdentityArgb,
               int[] ca9Gains, long[] neutralClipCounts,
               MapStats linearStats, MapStats encodedStats) {
            this.width = width;
            this.height = height;
            this.sourceStride = sourceStride;
            this.llOetfArgb = llOetfArgb;
            this.llIdentityArgb = llIdentityArgb;
            this.leIdentityArgb = leIdentityArgb;
            this.elOetfArgb = elOetfArgb;
            this.eeIdentityArgb = eeIdentityArgb;
            this.ca9Gains = ca9Gains;
            this.neutralClipCounts = neutralClipCounts;
            this.linearLumaInputLow = linearStats.inputLow;
            this.linearLumaInputHigh = linearStats.inputHigh;
            this.linearLumaInputNonFinite = linearStats.inputNonFinite;
            this.linearDgIndexLow = linearStats.dgLow;
            this.linearDgIndexHigh = linearStats.dgHigh;
            this.encodedLumaInputLow = encodedStats.inputLow;
            this.encodedLumaInputHigh = encodedStats.inputHigh;
            this.encodedLumaInputNonFinite = encodedStats.inputNonFinite;
            this.encodedDgIndexLow = encodedStats.dgLow;
            this.encodedDgIndexHigh = encodedStats.dgHigh;
        }
    }

    public static Result render(DngRawDecoder.RawImage raw,
                                DngMetadataReader.DngInfo info,
                                Assets assets,
                                int maxDimension) {
        if (raw == null || info == null || assets == null) {
            throw new IllegalArgumentException("raw/info/assets must not be null");
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
        int n = Math.multiplyExact(outWidth, outHeight);
        int[] llOetf = new int[n];
        int[] llIdentity = new int[n];
        int[] leIdentity = new int[n];
        int[] elOetf = new int[n];
        int[] eeIdentity = new int[n];
        long[] neutralClips = new long[3];
        MapStats linearStats = new MapStats();
        MapStats encodedStats = new MapStats();

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

                for (int c = 0; c < 3; c++) {
                    double balanced = camera[c] * gains[c] / M10RColorSpecCore.ASN_SCALE;
                    if (balanced > 1.0) neutralClips[c]++;
                }
                double[] guarded = M10RNeutralClipReferenceRenderer.applyCa9NeutralSaturation(camera, gains);
                double[] linear = M10RColorSpecCore.matVecMul(white.cameraToSrgbLinear, guarded);
                double[] encodedBase = {
                        srgbCode(linear[0]), srgbCode(linear[1]), srgbCode(linear[2])
                };

                double yLinear = luma(linear);
                double yEncoded = luma(encodedBase);
                double mappedLinear = mapY(yLinear, assets, linearStats);
                double mappedEncoded = mapY(yEncoded, assets, encodedStats);
                double gainLinear = yLinear > 1.0e-12 ? mappedLinear / yLinear : 0.0;
                double gainEncoded = yEncoded > 1.0e-12 ? mappedEncoded / yEncoded : 0.0;

                int i = oy * outWidth + ox;
                llOetf[i] = argbSrgb(linear[0] * gainLinear,
                                     linear[1] * gainLinear,
                                     linear[2] * gainLinear);
                llIdentity[i] = argbIdentity(linear[0] * gainLinear,
                                             linear[1] * gainLinear,
                                             linear[2] * gainLinear);
                leIdentity[i] = argbIdentity(encodedBase[0] * gainLinear,
                                             encodedBase[1] * gainLinear,
                                             encodedBase[2] * gainLinear);
                elOetf[i] = argbSrgb(linear[0] * gainEncoded,
                                     linear[1] * gainEncoded,
                                     linear[2] * gainEncoded);
                eeIdentity[i] = argbIdentity(encodedBase[0] * gainEncoded,
                                             encodedBase[1] * gainEncoded,
                                             encodedBase[2] * gainEncoded);
            }
        }

        return new Result(outWidth, outHeight, stride,
                llOetf, llIdentity, leIdentity, elOetf, eeIdentity,
                gains, neutralClips, linearStats, encodedStats);
    }

    private static double mapY(double y, Assets assets, MapStats stats) {
        int x;
        if (!Double.isFinite(y)) {
            stats.inputNonFinite++;
            x = 0;
        } else if (y <= 0.0) {
            if (y < 0.0) stats.inputLow++;
            x = 0;
        } else if (y >= 1.0) {
            if (y > 1.0) stats.inputHigh++;
            x = INPUT_MAX;
        } else {
            x = clamp((int) Math.round(y * INPUT_MAX), 0, INPUT_MAX);
        }
        int m = medium(x, assets.tone);
        int di = m;
        if (di < 0) { stats.dgLow++; di = 0; }
        else if (di >= assets.dg.length) { stats.dgHigh++; di = assets.dg.length - 1; }
        return assets.dg[di] / (double) DG_OUT_MAX;
    }

    static int medium(int x, int[] tone) {
        int xx = clamp(x, 0, tone.length * 2 - 1);
        return (int) (((long) xx * (long) tone[xx >> 1]) >> 15);
    }

    private static double luma(double[] rgb) {
        return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2];
    }

    private static double srgbCode(double linear) {
        double c = clamp01(linear);
        return c <= 0.0031308 ? 12.92 * c : 1.055 * Math.pow(c, 1.0 / 2.4) - 0.055;
    }

    private static int argbSrgb(double r, double g, double b) {
        return 0xff000000 | (SensorPreviewCore.toSrgb8(r) << 16)
                | (SensorPreviewCore.toSrgb8(g) << 8) | SensorPreviewCore.toSrgb8(b);
    }

    private static int argbIdentity(double r, double g, double b) {
        return 0xff000000 | (toIdentity8(r) << 16) | (toIdentity8(g) << 8) | toIdentity8(b);
    }

    private static int toIdentity8(double code) {
        return (int) Math.round(clamp01(code) * 255.0);
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

    private static int clamp(int v, int lo, int hi) {
        return v < lo ? lo : (v > hi ? hi : v);
    }

    private static double clamp01(double x) {
        return x <= 0.0 ? 0.0 : (x >= 1.0 ? 1.0 : x);
    }
}
