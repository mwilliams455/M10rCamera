package com.m10r.diagnostic;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class M10RLinearReferenceRendererTest {
    private static final double EPS = 1e-12;

    @Test
    public void linearNormalizationKeepsWhiteAtOne() {
        assertEquals(1.0,
                M10RLinearReferenceRenderer.normalizedLinear(
                        15000, 0, 0, new double[] {0.0}, new double[] {15000.0}),
                EPS);
    }

    @Test
    public void linearNormalizationPreservesFourteenBitHeadroomAboveDngWhite() {
        double v = M10RLinearReferenceRenderer.normalizedLinear(
                16383, 0, 0, new double[] {0.0}, new double[] {15000.0});
        assertEquals(16383.0 / 15000.0, v, EPS);
        assertTrue(v > 1.0);
    }

    @Test
    public void linearNormalizationFloorsBelowBlackWithoutHighlightClamp() {
        assertEquals(0.0,
                M10RLinearReferenceRenderer.normalizedLinear(
                        50, 0, 0, new double[] {100.0}, new double[] {15100.0}),
                EPS);
        assertEquals((16000.0 - 100.0) / (15100.0 - 100.0),
                M10RLinearReferenceRenderer.normalizedLinear(
                        16000, 0, 0, new double[] {100.0}, new double[] {15100.0}),
                EPS);
    }

    @Test
    public void v04DisplayNormalizationRemainsClampedWhileV051LinearKeepsHeadroom() {
        double v04 = SensorPreviewCore.normalized(
                16383, 0, 0, new double[] {0.0}, new double[] {15000.0});
        double v051 = M10RLinearReferenceRenderer.normalizedLinear(
                16383, 0, 0, new double[] {0.0}, new double[] {15000.0});

        assertEquals(1.0, v04, EPS);
        assertTrue(v051 > v04);
    }

    @Test
    public void linearNormalizationHonorsPerSiteLevels() {
        double[] black = {10.0, 20.0, 30.0, 40.0};
        double[] white = {1010.0, 2020.0, 3030.0, 4040.0};
        assertEquals((2120.0 - 20.0) / (2020.0 - 20.0),
                M10RLinearReferenceRenderer.normalizedLinear(2120, 1, 0, black, white), EPS);
        assertEquals((4140.0 - 40.0) / (4040.0 - 40.0),
                M10RLinearReferenceRenderer.normalizedLinear(4140, 1, 1, black, white), EPS);
    }
}
