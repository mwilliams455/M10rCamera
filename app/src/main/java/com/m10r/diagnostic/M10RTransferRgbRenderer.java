package com.m10r.diagnostic;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * REFERENCE_TRANSFER_RGB1A.
 *
 * Full-RGB controlled transfer experiment built on the promoted RENDER_PARITY1A C path:
 * DNG WhiteLevel clamp -> bilinear Bayer -> CA9 neutral-domain clip -> frozen ColorSpec
 * -> linear sRGB -> TONEDG1B luma MEDIUM->DG shared RGB gain -> transfer toggle.
 *
 * The only A/B variable is the final transfer:
 *   OETF_ON  = standard sRGB OETF
 *   OETF_OFF = identity code mapping
 *
 * This is a research renderer. It does not alter the live Android capture branch.
 */
public final class M10RTransferRgbRenderer {
    private M10RTransferRgbRenderer() {}

    public static final int INPUT_MAX = 0x3fff;
    public static final int TONE_ENTRIES = 10240;
    public static final int DG_ENTRIES = 32768;
    public static final int DG_OUT_MAX = 0x3fff;

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

    public static final class Result {
        public final int width;
        public final int height;
        public final int sourceStride;
        public final int[] oetfOnArgb;
        public final int[] oetfOffArgb;
        public final int[] ca9Gains;
        public final long[] neutralClipCounts;
        public final long[] preTransferBelowZero;
        public final long[] preTransferAboveOne;
        public final long lumaInputClipLow;
        public final long lumaInputClipHigh;
        public final long dgIndexClipLow;
        public final long dgIndexClipHigh;

        Result(int width, int height, int sourceStride,
               int[] oetfOnArgb, int[] oetfOffArgb,
               int[] ca9Gains, long[] neutralClipCounts,
               long[] preTransferBelowZero, long[] preTransferAboveOne,
               long lumaInputClipLow, long lumaInputClipHigh,
               long dgIndexClipLow, long dgIndexClipHigh) {
            this.width = width;
            this.height = height;
            this.sourceStride = sourceStride;
            this.oetfOnArgb = oetfOnArgb;
            this.oetfOffArgb = oetfOffArgb;
            this.ca9Gains = ca9Gains;
            this.neutralClipCounts = neutralClipCounts;
            this.preTransferBelowZero = preTransferBelowZero;
            this.preTransferAboveOne = preTransferAboveOne;
            this.lumaInputClipLow = lumaInputClipLow;
            this.lumaInputClipHigh = lumaInputClipHigh;
            this.dgIndexClipLow = dgIndexClipLow;
            this.dgIndexClipHigh = dgIndexClipHigh;
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
        int[] on = new int[n];
        int[] off = new int[n];
        long[] neutralClips = new long[3];
        long[] below = new long[3];
        long[] above = new long[3];
        long lumaLow = 0, lumaHigh = 0, dgLow = 0, dgHigh = 0;

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

                double y = 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
                int x;
                if (!Double.isFinite(y) || y <= 0.0) {
                    x = 0;
                    if (y < 0.0) lumaLow++;
                } else if (y >= 1.0) {
                    x = INPUT_MAX;
                    if (y > 1.0) lumaHigh++;
                } else {
                    x = clamp((int) Math.round(y * INPUT_MAX), 0, INPUT_MAX);
                }

                int m = medium(x, assets.tone);
                int di = m;
                if (di < 0) { dgLow++; di = 0; }
                else if (di >= assets.dg.length) { dgHigh++; di = assets.dg.length - 1; }
                int d = assets.dg[di];
                double mappedY = d / (double) DG_OUT_MAX;
                double gain = y > 1.0e-12 ? mappedY / y : 0.0;
                double nr = linear[0] * gain;
                double ng = linear[1] * gain;
                double nb = linear[2] * gain;
                double[] pre = {nr, ng, nb};
                for (int c = 0; c < 3; c++) {
                    if (pre[c] < 0.0) below[c]++;
                    if (pre[c] > 1.0) above[c]++;
                }

                int rOn = SensorPreviewCore.toSrgb8(nr);
                int gOn = SensorPreviewCore.toSrgb8(ng);
                int bOn = SensorPreviewCore.toSrgb8(nb);
                int rOff = toIdentity8(nr);
                int gOff = toIdentity8(ng);
                int bOff = toIdentity8(nb);
                int i = oy * outWidth + ox;
                on[i] = 0xff000000 | (rOn << 16) | (gOn << 8) | bOn;
                off[i] = 0xff000000 | (rOff << 16) | (gOff << 8) | bOff;
            }
        }

        return new Result(outWidth, outHeight, stride, on, off, gains, neutralClips,
                below, above, lumaLow, lumaHigh, dgLow, dgHigh);
    }

    static int medium(int x, int[] tone) {
        int xx = clamp(x, 0, tone.length * 2 - 1);
        return (int) (((long) xx * (long) tone[xx >> 1]) >> 15);
    }

    private static int toIdentity8(double code) {
        double c = code <= 0.0 ? 0.0 : (code >= 1.0 ? 1.0 : code);
        return (int) Math.round(c * 255.0);
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
}
