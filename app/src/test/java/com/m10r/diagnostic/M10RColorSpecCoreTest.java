package com.m10r.diagnostic;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class M10RColorSpecCoreTest {
    @Test
    public void sixVerifiedM10rAsnFixturesPass() {
        assertEquals(6, M10RColorSpecCore.verifiedFixturePassCount());
    }

    @Test
    public void firstVerifiedFixtureRecoversExpectedGains() {
        int[] got = M10RColorSpecCore.recoverCa9Gains(new double[] {
                0.2853957637, 1.0, 0.6564102564
        });
        assertArrayEquals(new int[] {897, 256, 390}, got);
    }

    @Test
    public void reciprocalTemperatureMidpointUsesTolerance() {
        double[][] m1 = {{1,0,0},{0,2,0},{0,0,3}};
        double[][] m2 = {{3,0,0},{0,4,0},{0,0,5}};
        double[][] got = M10RColorSpecCore.interpolateMatrix(3000, 6000, m1, m2, 4000);
        assertEquals(2.0, got[0][0], 1e-14);
        assertEquals(3.0, got[1][1], 1e-14);
        assertEquals(4.0, got[2][2], 1e-14);
    }

    @Test
    public void renderedCcUsesFirmwareClampAndRounding() {
        double[][] m = {{1.0, -1.0, 10.0}, {0.5, -0.5, 0.0}, {0.25, -0.25, 2.0}};
        M10RColorSpecCore.RenderedCCRecord rec = M10RColorSpecCore.quantizeRenderedCc(m, 0, 5000);
        assertEquals(512, rec.denominator());
        assertEquals(512, rec.coeff[0]);
        assertEquals(-512, rec.coeff[1]);
        assertEquals(2047, rec.coeff[2]);
        assertEquals(5000, rec.kelvin);
        assertEquals(2L, M10RColorSpecCore.roundHalfAwayFromZero(1.5));
        assertEquals(-2L, M10RColorSpecCore.roundHalfAwayFromZero(-1.5));
    }

    @Test
    public void d50BradfordIdentityMatchesStoredPrecision() {
        double[][] identity = {{1,0,0},{0,1,0},{0,0,1}};
        double[][] got = M10RColorSpecCore.mapWhiteMatrix(M10RColorSpecCore.D50_XY, M10RColorSpecCore.D50_XY);
        assertTrue(M10RColorSpecCore.maxAbsMatrixError(got, identity) < 1e-6);
    }

    @Test
    public void defaultOutputIsSrgb() {
        assertEquals("sRGB", M10RColorSpecCore.DEFAULT_OUTPUT);
    }
}
