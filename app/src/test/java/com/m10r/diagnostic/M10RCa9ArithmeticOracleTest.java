package com.m10r.diagnostic;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotEquals;

import org.junit.Test;

public class M10RCa9ArithmeticOracleTest {
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

    @Test
    public void sixGenuineM10rAsnFixturesRecoverExactIntegerGains() {
        for (int i = 0; i < VERIFIED_ASN.length; i++) {
            assertArrayEquals(VERIFIED_GAINS[i],
                    M10RCa9ArithmeticOracle.recoverSourceGainsFromAsn(VERIFIED_ASN[i]));
        }
    }

    @Test
    public void sourceGainAbiRoundTripsExhaustivelyAcrossOneToTwoThousand() {
        for (int gain = M10RCa9ArithmeticOracle.GAIN_MIN;
             gain <= M10RCa9ArithmeticOracle.GAIN_MAX; gain++) {
            double asn = M10RCa9ArithmeticOracle.encodeAsnFromSourceGain(gain);
            assertEquals(gain, M10RCa9ArithmeticOracle.recoverSourceGainFromAsn(asn));
        }
    }

    @Test
    public void helperUsesHalfAwayFromZeroNotTiesToEven() {
        assertEquals(1L, M10RCa9ArithmeticOracle.roundHalfAwayFromZero(0.5));
        assertEquals(3L, M10RCa9ArithmeticOracle.roundHalfAwayFromZero(2.5));
        assertEquals(4L, M10RCa9ArithmeticOracle.roundHalfAwayFromZero(3.5));
        assertEquals(-1L, M10RCa9ArithmeticOracle.roundHalfAwayFromZero(-0.5));
        assertEquals(-3L, M10RCa9ArithmeticOracle.roundHalfAwayFromZero(-2.5));
        assertEquals(-4L, M10RCa9ArithmeticOracle.roundHalfAwayFromZero(-3.5));

        // Discriminator against the current ColorSpec diagnostic implementation.
        assertNotEquals((long) Math.rint(2.5),
                M10RCa9ArithmeticOracle.roundHalfAwayFromZero(2.5));
    }

    @Test
    public void sourceGainRecoveryExposesCurrentTiesToEvenBoundaryMismatch() {
        // 256 / ASN = 100.5 exactly. Firmware helper model -> 101;
        // current M10RColorSpecCore Math.rint boundary -> 100.
        double tieAsn = 256.0 / 100.5;
        int exact = M10RCa9ArithmeticOracle.recoverSourceGainFromAsn(tieAsn);
        int current = M10RColorSpecCore.recoverCa9Gains(new double[] {tieAsn, 1.0, 1.0})[0];
        assertEquals(101, exact);
        assertEquals(100, current);
    }

    @Test
    public void sourceAbiClampAndCandidateBoundaryAreExplicit() {
        assertEquals(1, M10RCa9ArithmeticOracle.recoverSourceGainFromAsn(1000.0));
        assertEquals(2000, M10RCa9ArithmeticOracle.recoverSourceGainFromAsn(0.01));
        assertEquals(256.0 / 897.0,
                M10RCa9ArithmeticOracle.promotedCandidateCameraBoundary(897), 0.0);
    }
}
