package com.m10r.diagnostic;

import java.util.Locale;

/**
 * v0.5 Leica M10-R reference-color core.
 *
 * This sits downstream of the frozen v0.4 sensor decode/demosaic boundary and ports the
 * firmware-derived ColorSpec behavior that is sufficiently closed for an executable reference:
 * Leica xy->temperature locus, D50-start NeutralToXY iteration, reciprocal-temperature CM1/CM2
 * interpolation, Bradford adaptation, CC0 camera->internal working RGB, and default CC1
 * internal->sRGB.
 *
 * The DNG CalibrationIlluminant enum -> exact firmware parser bridge is not fully closed in the
 * research. For the validated M10-R reference files only, illuminants 17/21 are therefore mapped
 * explicitly to nominal Standard Light A / D65 temperatures (2856 K / 6504 K) and are reported as
 * a first-parity reference-fixture bridge rather than a universal firmware claim.
 */
public final class M10RReferenceColorCore {
    private M10RReferenceColorCore() {}

    public static final double NEUTRAL_TO_XY_EPSILON = 1.0e-7;
    public static final int NEUTRAL_TO_XY_MAX_PASSES = 15;
    public static final int NEUTRAL_TO_XY_AVERAGE_PASS = 14;

    public static final class CalibrationTemperatures {
        public final double t1;
        public final double t2;
        public final String provenance;

        CalibrationTemperatures(double t1, double t2, String provenance) {
            this.t1 = t1;
            this.t2 = t2;
            this.provenance = provenance;
        }
    }

    public static final class WhiteSolution {
        public final double[] xy;
        public final double kelvin;
        public final int passes;
        public final double maxDelta;
        public final double[][] interpolatedColorMatrix;
        public final double[][] cameraToInternal;
        public final double[][] cameraToSrgbLinear;

        WhiteSolution(double[] xy, double kelvin, int passes, double maxDelta,
                      double[][] interpolatedColorMatrix,
                      double[][] cameraToInternal,
                      double[][] cameraToSrgbLinear) {
            this.xy = xy;
            this.kelvin = kelvin;
            this.passes = passes;
            this.maxDelta = maxDelta;
            this.interpolatedColorMatrix = interpolatedColorMatrix;
            this.cameraToInternal = cameraToInternal;
            this.cameraToSrgbLinear = cameraToSrgbLinear;
        }

        public String diagnosticSummary(String temperatureProvenance) {
            return String.format(Locale.US,
                    "v0.5 LEICA LINEAR REFERENCE\n" +
                    "NeutralToXY: x=%.9f, y=%.9f, CCT=%.3f K, passes=%d, delta=%.3e\n" +
                    "Calibration temperature bridge: %s\n" +
                    "Color path: interpolated Leica CM -> Bradford source/D50 -> CC0 internal RGB -> CC1 sRGB\n" +
                    "NONLINEAR BOUNDARY: MEDIUM tone + Differential Gamma are not applied in this linear reference.",
                    xy[0], xy[1], kelvin, passes, maxDelta, temperatureProvenance);
        }
    }

    // Leica firmware locus table recovered in v2.37. Columns are:
    // reciprocal-temperature coordinate (mired), 1960 UCS u, v, isotemperature slope,
    // sqrt(1+slope^2). The first coordinate is converted back with 1e6/mired.
    private static final double[][] LOCUS = {
            {0,   0.18006, 0.26352, -0.24341, 1.029197954},
            {10,  0.18066, 0.26589, -0.25479, 1.031948615},
            {20,  0.18133, 0.26846, -0.26876, 1.035486329},
            {30,  0.18208, 0.27119, -0.28539, 1.039926657},
            {40,  0.18293, 0.27407, -0.30470, 1.045390879},
            {50,  0.18388, 0.27709, -0.32675, 1.052029259},
            {60,  0.18494, 0.28021, -0.35156, 1.059997374},
            {70,  0.18611, 0.28342, -0.37915, 1.069464690},
            {80,  0.18740, 0.28668, -0.40955, 1.080616122},
            {90,  0.18880, 0.28997, -0.44278, 1.093642596},
            {100, 0.19032, 0.29326, -0.47888, 1.108749771},
            {125, 0.19462, 0.30141, -0.58204, 1.157052532},
            {150, 0.19962, 0.30921, -0.70471, 1.223362654},
            {175, 0.20525, 0.31647, -0.84901, 1.311799520},
            {200, 0.21142, 0.32312, -1.01820, 1.427140932},
            {225, 0.21807, 0.32909, -1.21680, 1.574992775},
            {250, 0.22511, 0.33439, -1.45120, 1.762379482},
            {275, 0.23247, 0.33904, -1.72980, 1.998051060},
            {300, 0.24010, 0.34308, -2.06370, 2.293219939},
            {325, 0.24792, 0.34655, -2.46810, 2.662990350},
            {350, 0.25591, 0.34951, -2.96410, 3.128240529},
            {375, 0.26400, 0.35200, -3.58140, 3.718390238},
            {400, 0.27218, 0.35407, -4.36330, 4.476425682},
            {425, 0.28039, 0.35577, -5.37620, 5.468411693},
            {450, 0.28863, 0.35714, -6.72620, 6.800129884},
            {475, 0.29685, 0.35823, -8.59550, 8.653474461},
            {500, 0.30505, 0.35907, -11.3240, 11.368068260},
            {525, 0.31320, 0.35968, -15.6280, 15.659961170},
            {550, 0.32129, 0.36011, -23.3250, 23.346426390},
            {575, 0.32931, 0.36038, -40.7700, 40.782262080},
            {600, 0.33724, 0.36051, -116.450, 116.454293600}
    };

    /**
     * Explicit v0.5 reference-fixture bridge. Do not generalize other DNG illuminant enums here.
     */
    public static CalibrationTemperatures referenceTemperaturesForIlluminants(int illuminant1, int illuminant2) {
        if (illuminant1 == 17 && illuminant2 == 21) {
            return new CalibrationTemperatures(2856.0, 6504.0,
                    "first-parity fixture bridge: DNG illuminants 17/21 -> nominal A 2856 K / D65 6504 K; exact firmware enum parser not yet closed");
        }
        throw new IllegalArgumentException("v0.5 reference bridge only supports the validated M10-R 17/21 illuminant pair");
    }

    /** Leica firmware xy -> temperature locus calculation, using recovered table precision. */
    public static double xyToTemperatureLeica(double[] xy) {
        validateXy(xy);
        double x = xy[0];
        double y = xy[1];
        double denominator = 1.5 - x + 6.0 * y;
        if (!(denominator > 0.0) || !Double.isFinite(denominator)) {
            throw new IllegalArgumentException("xy cannot be converted to Leica 1960 UCS");
        }
        double u = 2.0 * x / denominator;
        double v = 3.0 * y / denominator;

        double previousDistance = Double.NaN;
        for (int i = 1; i < LOCUS.length; i++) {
            double[] row = LOCUS[i];
            double distance = ((v - row[2]) - (u - row[1]) * row[3]) / row[4];
            if (distance <= 0.0) {
                double currentDistance = -distance;
                double fraction;
                if (i == 1) {
                    fraction = 0.0;
                } else {
                    double sum = previousDistance + currentDistance;
                    fraction = sum > 0.0 ? currentDistance / sum : 0.5;
                }
                double previousMired = LOCUS[i - 1][0];
                double currentMired = row[0];
                double mired = previousMired * fraction + currentMired * (1.0 - fraction);
                if (!(mired > 0.0)) return 100000.0; // firmware table's hot-end boundary (10 mired)
                return 1_000_000.0 / mired;
            }
            previousDistance = distance;
        }
        return 1_000_000.0 / LOCUS[LOCUS.length - 1][0];
    }

    /**
     * Firmware-derived NeutralToXY loop: D50 start, Leica CCT lookup, reciprocal-temperature CM
     * interpolation, inverse profile matrix applied to neutral, 1e-7 convergence, at most 15
     * passes, with pass-14 averaging fallback.
     */
    public static WhiteSolution solveNeutralToXy(double[] neutral,
                                                 double[][] colorMatrix1,
                                                 double[][] colorMatrix2,
                                                 double t1,
                                                 double t2) {
        validateNeutral(neutral);
        validateMatrix(colorMatrix1);
        validateMatrix(colorMatrix2);
        if (!(t1 > 0.0 && t2 > t1 && Double.isFinite(t1) && Double.isFinite(t2))) {
            throw new IllegalArgumentException("expected finite calibration temperatures T1 < T2");
        }

        double[] current = M10RColorSpecCore.D50_XY.clone();
        double delta = Double.POSITIVE_INFINITY;
        int passes = 0;

        for (int pass = 0; pass < NEUTRAL_TO_XY_MAX_PASSES; pass++) {
            double kelvin = xyToTemperatureLeica(current);
            double[][] profile = M10RColorSpecCore.interpolateMatrix(t1, t2,
                    colorMatrix1, colorMatrix2, kelvin);
            double[] xyz = M10RColorSpecCore.matVecMul(invert3x3(profile), neutral);
            double[] next = xyzToXy(xyz);
            delta = Math.max(Math.abs(next[0] - current[0]), Math.abs(next[1] - current[1]));
            passes = pass + 1;

            if (delta < NEUTRAL_TO_XY_EPSILON) {
                current = next;
                break;
            }
            if (pass == NEUTRAL_TO_XY_AVERAGE_PASS) {
                current = new double[] {(current[0] + next[0]) * 0.5, (current[1] + next[1]) * 0.5};
            } else {
                current = next;
            }
        }

        double finalKelvin = xyToTemperatureLeica(current);
        double[][] finalProfile = M10RColorSpecCore.interpolateMatrix(t1, t2,
                colorMatrix1, colorMatrix2, finalKelvin);
        double[][] cameraToInternal = cameraToInternal(finalProfile, current);
        double[][] cameraToSrgb = M10RColorSpecCore.matMul(
                M10RColorSpecCore.DEFAULT_SRGB_CC1, cameraToInternal);
        return new WhiteSolution(current, finalKelvin, passes, delta,
                finalProfile, cameraToInternal, cameraToSrgb);
    }

    /** Profile matrix is XYZ->camera; invert it, adapt source white to D50, then enter Leica PCS. */
    public static double[][] cameraToInternal(double[][] profileXyzToCamera, double[] sourceWhiteXy) {
        validateMatrix(profileXyzToCamera);
        validateXy(sourceWhiteXy);
        double[][] cameraToXyz = invert3x3(profileXyzToCamera);
        double[][] sourceToD50 = M10RColorSpecCore.mapWhiteMatrix(sourceWhiteXy, M10RColorSpecCore.D50_XY);
        return M10RColorSpecCore.matMul(M10RColorSpecCore.PCS_TO_INTERNAL,
                M10RColorSpecCore.matMul(sourceToD50, cameraToXyz));
    }

    public static double[] xyzToXy(double[] xyz) {
        if (xyz == null || xyz.length != 3) throw new IllegalArgumentException("XYZ must have 3 components");
        double sum = xyz[0] + xyz[1] + xyz[2];
        if (!(sum > 0.0) || !Double.isFinite(sum)) throw new IllegalArgumentException("XYZ sum must be positive and finite");
        return new double[] {xyz[0] / sum, xyz[1] / sum};
    }

    public static double[][] invert3x3(double[][] m) {
        validateMatrix(m);
        double a=m[0][0], b=m[0][1], c=m[0][2];
        double d=m[1][0], e=m[1][1], f=m[1][2];
        double g=m[2][0], h=m[2][1], i=m[2][2];
        double det = a*(e*i-f*h) - b*(d*i-f*g) + c*(d*h-e*g);
        if (!Double.isFinite(det) || Math.abs(det) <= 1.0e-15) {
            throw new IllegalArgumentException("singular/invalid 3x3 matrix");
        }
        double s = 1.0 / det;
        return new double[][] {
                {(e*i-f*h)*s, (c*h-b*i)*s, (b*f-c*e)*s},
                {(f*g-d*i)*s, (a*i-c*g)*s, (c*d-a*f)*s},
                {(d*h-e*g)*s, (b*g-a*h)*s, (a*e-b*d)*s}
        };
    }

    private static void validateNeutral(double[] neutral) {
        if (neutral == null || neutral.length != 3) throw new IllegalArgumentException("neutral must have 3 channels");
        for (double v : neutral) if (!(v > 0.0) || !Double.isFinite(v))
            throw new IllegalArgumentException("neutral channels must be positive and finite");
    }

    private static void validateXy(double[] xy) {
        if (xy == null || xy.length != 2 || !Double.isFinite(xy[0]) || !Double.isFinite(xy[1]) ||
                xy[1] <= 0.0 || xy[0] < 0.0 || xy[0] + xy[1] > 1.0) {
            throw new IllegalArgumentException("invalid xy");
        }
    }

    private static void validateMatrix(double[][] m) {
        if (m == null || m.length != 3) throw new IllegalArgumentException("expected 3x3 matrix");
        for (double[] row : m) {
            if (row == null || row.length != 3) throw new IllegalArgumentException("expected 3x3 matrix");
            for (double v : row) if (!Double.isFinite(v)) throw new IllegalArgumentException("matrix contains non-finite value");
        }
    }
}
