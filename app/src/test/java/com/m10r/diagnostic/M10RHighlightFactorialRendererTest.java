package com.m10r.diagnostic;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class M10RHighlightFactorialRendererTest {
    @Test
    public void whiteLevelClampAndHeadroomNormalizationAreDistinct() {
        double[] black = {0.0};
        double[] white = {15000.0};
        double clamped = M10RHighlightFactorialRenderer.normalize(
                16383, 0, 0, black, white, false);
        double headroom = M10RHighlightFactorialRenderer.normalize(
                16383, 0, 0, black, white, true);

        assertEquals(1.0, clamped, 0.0);
        assertEquals(16383.0 / 15000.0, headroom, 1e-12);
        assertTrue(headroom > clamped);
    }

    @Test
    public void neutralClipCanActEvenWhenCameraValueIsBelowWhiteLevel() {
        int[] gains = {697, 256, 442};
        double[] camera = {0.50, 0.50, 0.50};
        double[] guarded = M10RNeutralClipReferenceRenderer.applyCa9NeutralSaturation(camera, gains);

        // Red is above unity after 697/256 balancing, while green and blue are not.
        assertEquals(256.0 / 697.0, guarded[0], 1e-12);
        assertEquals(0.50, guarded[1], 1e-12);
        assertEquals(0.50, guarded[2], 1e-12);
    }

    @Test
    public void whiteLevelClampAloneDoesNotApplyNeutralRatioLimit() {
        double[] black = {0.0};
        double[] white = {15000.0};
        double camera = M10RHighlightFactorialRenderer.normalize(
                7500, 0, 0, black, white, false);
        assertEquals(0.50, camera, 1e-12);
    }
}
