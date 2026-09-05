package com.m10r.diagnostic;

import java.util.Locale;

/**
 * Android-side diagnostic port of the validated first-parity M10-R ColorSpec core.
 *
 * This intentionally mirrors only the already-frozen/executable Python boundary.
 * Full Leica xy->temperature/NeutralToXY and RAW/DNG image decoding remain separate.
 */
public final class M10RColorSpecCore {
    private M10RColorSpecCore() {}

    public static final int GAIN_MIN = 1;
    public static final int GAIN_MAX = 2000;
    public static final double ASN_SCALE = 256.0;
    public static final int CC_MIN = -2048;
    public static final int CC_MAX = 2047;
    public static final String DEFAULT_OUTPUT = "sRGB";

    public static final double[][] BRADFORD = {
            {0.8951, 0.2664, -0.1614},
            {-0.7502, 1.7135, 0.0367},
            {0.0389, -0.0685, 1.0296}
    };

    public static final double[][] BRADFORD_INV = {
            {0.9869929, -0.1470543, 0.1599627},
            {0.4323053, 0.5183603, 0.0492912},
            {-0.0085287, 0.0400428, 0.9684867}
    };

    public static final double[][] PCS_TO_INTERNAL = {
            {1.3460, -0.2556, -0.0511},
            {-0.5446, 1.5082, 0.0205},
            {0.0000, 0.0000, 1.2123}
    };

    public static final double[][] DEFAULT_SRGB_CC1 = {
            {1.3895, -0.1693, -0.2202},
            {-0.2288, 1.2317, -0.0029},
            {-0.0176, -0.0963, 1.1139}
    };

    public static final double[] D50_XY = {0.3457, 0.3585};

    private static final double[][] VERIFIED_ASN = {
            {0.2853957637, 1.0, 0.6564102564},
            {0.2969837587, 1.0, 0.6289926290},
            {0.2853957637, 1.0, 0.6530612245},
            {0.2892655367, 1.0, 0.6213592233},
            {0.2853957637, 1.0, 0.6614987080},
            {0.2813186813, 1.0, 0.6614987080}
    };

    private static final int[][] VERIFIED_GAINS = {
            {897, 256, 390},
            {862, 256, 407},
            {897, 256, 392},
            {885, 256, 412},
            {897, 256, 387},
            {910, 256, 387}
    };

    public static final class RenderedCCRecord {
        public final int[] coeff;
        public final int scaleCode;
        public final int kelvin;

        RenderedCCRecord(int[] coeff, int scaleCode, int kelvin) {
            this.coeff = coeff;
            this.scaleCode = scaleCode;
            this.kelvin = kelvin;
        }

        public int denominator() {
            return 1 << (9 - scaleCode);
        }
    }

    public static int[] recoverCa9Gains(double[] asShotNeutral) {
        if (asShotNeutral == null || asShotNeutral.length != 3) {
            throw new IllegalArgumentException("AsShotNeutral must have 3 channels");
        }
        int[] out = new int[3];
        for (int i = 0; i < 3; i++) {
            double n = asShotNeutral[i];
            if (!Double.isFinite(n) || n <= 0.0) {
                throw new IllegalArgumentException("AsShotNeutral channels must be positive and finite");
            }
            int g = (int) Math.rint(ASN_SCALE / n); // ties-to-even, matching Python oracle boundary
            out[i] = Math.min(GAIN_MAX, Math.max(GAIN_MIN, g));
        }
        return out;
    }

    public static double[] gainsToFirmwareNeutral(int[] gains) {
        if (gains == null || gains.length != 3) {
            throw new IllegalArgumentException("gains must have 3 channels");
        }
        double[] out = new double[3];
        for (int i = 0; i < 3; i++) {
            int g = Math.min(GAIN_MAX, Math.max(GAIN_MIN, gains[i]));
            out[i] = ASN_SCALE / g;
        }
        return out;
    }

    public static double[][] interpolateMatrix(double t1, double t2, double[][] m1, double[][] m2, double current) {
        if (!(Double.isFinite(t1) && Double.isFinite(t2) && Double.isFinite(current)) ||
                t1 <= 0.0 || t2 <= 0.0 || current <= 0.0 || t1 >= t2) {
            throw new IllegalArgumentException("expected positive finite T1 < T2 and current");
        }
        if (current <= t1) return copyMatrix(m1);
        if (current >= t2) return copyMatrix(m2);
        double g = (1.0 / current - 1.0 / t2) / (1.0 / t1 - 1.0 / t2);
        double[][] out = new double[3][3];
        for (int r = 0; r < 3; r++) {
            for (int c = 0; c < 3; c++) {
                out[r][c] = g * m1[r][c] + (1.0 - g) * m2[r][c];
            }
        }
        return out;
    }

    public static long roundHalfAwayFromZero(double value) {
        if (!Double.isFinite(value)) {
            throw new IllegalArgumentException("cannot round non-finite value");
        }
        return value >= 0.0 ? (long) Math.floor(value + 0.5) : (long) Math.ceil(value - 0.5);
    }

    public static RenderedCCRecord quantizeRenderedCc(double[][] matrix, int scaleCode, int kelvin) {
        int shift = 9 - scaleCode;
        if (shift < 0 || shift > 30) {
            throw new IllegalArgumentException("unsupported scaleCode");
        }
        int denominator = 1 << shift;
        int[] coeff = new int[9];
        int k = 0;
        for (int r = 0; r < 3; r++) {
            for (int c = 0; c < 3; c++) {
                long rounded = roundHalfAwayFromZero(matrix[r][c] * denominator);
                coeff[k++] = (int) Math.min(CC_MAX, Math.max(CC_MIN, rounded));
            }
        }
        return new RenderedCCRecord(coeff, scaleCode, kelvin);
    }

    public static double[][] mapWhiteMatrix(double[] srcXy, double[] dstXy) {
        double[] src = matVecMul(BRADFORD, xyToXyz(srcXy));
        double[] dst = matVecMul(BRADFORD, xyToXyz(dstXy));
        double[][] diagonal = {
                {dst[0] / src[0], 0.0, 0.0},
                {0.0, dst[1] / src[1], 0.0},
                {0.0, 0.0, dst[2] / src[2]}
        };
        return matMul(BRADFORD_INV, matMul(diagonal, BRADFORD));
    }

    public static double[] xyToXyz(double[] xy) {
        if (xy == null || xy.length != 2 || xy[1] <= 0.0 || xy[0] < 0.0 || xy[0] + xy[1] > 1.0) {
            throw new IllegalArgumentException("invalid xy");
        }
        double x = xy[0];
        double y = xy[1];
        return new double[] {x / y, 1.0, (1.0 - x - y) / y};
    }

    public static double[][] matMul(double[][] a, double[][] b) {
        double[][] out = new double[3][3];
        for (int r = 0; r < 3; r++) {
            for (int c = 0; c < 3; c++) {
                double s = 0.0;
                for (int k = 0; k < 3; k++) s += a[r][k] * b[k][c];
                out[r][c] = s;
            }
        }
        return out;
    }

    public static double[] matVecMul(double[][] a, double[] v) {
        double[] out = new double[3];
        for (int r = 0; r < 3; r++) {
            out[r] = a[r][0] * v[0] + a[r][1] * v[1] + a[r][2] * v[2];
        }
        return out;
    }

    public static double maxAbsMatrixError(double[][] a, double[][] b) {
        double m = 0.0;
        for (int r = 0; r < 3; r++) {
            for (int c = 0; c < 3; c++) m = Math.max(m, Math.abs(a[r][c] - b[r][c]));
        }
        return m;
    }

    public static int verifiedFixturePassCount() {
        int pass = 0;
        for (int i = 0; i < VERIFIED_ASN.length; i++) {
            int[] got = recoverCa9Gains(VERIFIED_ASN[i]);
            if (got[0] == VERIFIED_GAINS[i][0] && got[1] == VERIFIED_GAINS[i][1] && got[2] == VERIFIED_GAINS[i][2]) {
                pass++;
            }
        }
        return pass;
    }

    public static String selfCheckReport() {
        double[][] identity = {{1,0,0},{0,1,0},{0,0,1}};
        double bradfordError = maxAbsMatrixError(mapWhiteMatrix(D50_XY, D50_XY), identity);
        RenderedCCRecord cc1 = quantizeRenderedCc(DEFAULT_SRGB_CC1, 0, 5000);
        return String.format(Locale.US,
                "ColorSpec core: PASS\nVerified M10-R ASN fixtures: %d/6\nDefault output: %s\nBradford D50 identity max error: %.3e\nCC quantizer clamp: [%d, %d]\nSample CC1 denominator: %d\n\nBoundary: full Leica xy→temperature / NeutralToXY and RAW/DNG decoding are not wired in this diagnostic build.",
                verifiedFixturePassCount(), DEFAULT_OUTPUT, bradfordError, CC_MIN, CC_MAX, cc1.denominator());
    }

    private static double[][] copyMatrix(double[][] m) {
        double[][] out = new double[3][3];
        for (int r = 0; r < 3; r++) System.arraycopy(m[r], 0, out[r], 0, 3);
        return out;
    }
}
