package com.m10r.diagnostic;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class M10RReferenceColorCoreTest {
    private static final double[][] USER_CM1 = {
            {0.71240234, -0.25000000, -0.04345703},
            {-0.57373047, 1.55224609, 0.35961914},
            {-0.10961914, 0.29223633, 0.77441406}
    };

    private static final double[][] USER_CM2 = {
            {0.48779297, -0.12866211, -0.04858398},
            {-0.58398438, 1.37011719, 0.22070313},
            {-0.18041992, 0.33691406, 0.52514648}
    };

    @Test
    public void leicaLocusReturnsKnownReferenceTemperatures() {
        assertEquals(5000.7,
                M10RReferenceColorCore.xyToTemperatureLeica(new double[] {0.3457, 0.3585}), 2.0);
        assertEquals(6503.7,
                M10RReferenceColorCore.xyToTemperatureLeica(new double[] {0.3127, 0.3290}), 2.0);
        assertEquals(2855.8,
                M10RReferenceColorCore.xyToTemperatureLeica(new double[] {0.44757, 0.40745}), 2.0);
    }

    @Test
    public void validatedM10rReferenceNeutralConvergesNear4049K() {
        double[] neutral = {0.3672883788, 1.0, 0.5791855204};
        M10RReferenceColorCore.WhiteSolution solution =
                M10RReferenceColorCore.solveNeutralToXy(neutral, USER_CM1, USER_CM2, 2856.0, 6504.0);

        assertEquals(0.3760587, solution.xy[0], 2.0e-6);
        assertEquals(0.3668555, solution.xy[1], 2.0e-6);
        assertEquals(4049.2, solution.kelvin, 3.0);
        assertTrue(solution.passes <= M10RReferenceColorCore.NEUTRAL_TO_XY_MAX_PASSES);
        assertTrue(solution.maxDelta < M10RReferenceColorCore.NEUTRAL_TO_XY_EPSILON);
    }

    @Test
    public void cameraToSrgbMatrixIsFinite() {
        double[] neutral = {0.3672883788, 1.0, 0.5791855204};
        M10RReferenceColorCore.WhiteSolution solution =
                M10RReferenceColorCore.solveNeutralToXy(neutral, USER_CM1, USER_CM2, 2856.0, 6504.0);
        for (int r = 0; r < 3; r++) {
            for (int c = 0; c < 3; c++) {
                assertTrue(Double.isFinite(solution.cameraToSrgbLinear[r][c]));
            }
        }
    }

    @Test
    public void fixtureBridgeIsExplicitlyBoundedToSeventeenTwentyOne() {
        M10RReferenceColorCore.CalibrationTemperatures t =
                M10RReferenceColorCore.referenceTemperaturesForIlluminants(17, 21);
        assertEquals(2856.0, t.t1, 0.0);
        assertEquals(6504.0, t.t2, 0.0);
        assertTrue(t.provenance.contains("first-parity"));
    }

    @Test(expected = IllegalArgumentException.class)
    public void fixtureBridgeRejectsUnknownIlluminants() {
        M10RReferenceColorCore.referenceTemperaturesForIlluminants(20, 21);
    }
}
