package com.m10r.diagnostic;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class M10RHighlightFactorialRendererTest {
    @Test
    public void canonicalModesEncodeAuthoritativeTwoByTwoMatrix() {
        assertMode(M10RHighlightFactorialRenderer.Mode.A_BASELINE, false, false);
        assertMode(M10RHighlightFactorialRenderer.Mode.B_HEADROOM, true, false);
        assertMode(M10RHighlightFactorialRenderer.Mode.C_CA9_CLIP, false, true);
        assertMode(M10RHighlightFactorialRenderer.Mode.D_HEADROOM_CA9, true, true);
    }

    @SuppressWarnings("deprecation")
    @Test
    public void legacyModeAliasesPreserveTheirOldMechanisms() {
        assertMode(M10RHighlightFactorialRenderer.Mode.WHITELEVEL_CLAMP_ONLY, false, false);
        assertMode(M10RHighlightFactorialRenderer.Mode.HEADROOM_NEUTRAL_CLIP_ONLY, true, true);
    }

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

        assertEquals(256.0 / 697.0, guarded[0], 1e-12);
        assertEquals(0.50, guarded[1], 1e-12);
        assertEquals(0.50, guarded[2], 1e-12);
    }

    @Test
    public void baselineDoesNotApplyNeutralRatioLimit() {
        double[] black = {0.0};
        double[] white = {15000.0};
        double camera = M10RHighlightFactorialRenderer.normalize(
                7500, 0, 0, black, white,
                M10RHighlightFactorialRenderer.Mode.A_BASELINE.retainRawHeadroom);
        assertEquals(0.50, camera, 1e-12);
        assertFalse(M10RHighlightFactorialRenderer.Mode.A_BASELINE.applyCa9NeutralClip);
    }

    private static void assertMode(M10RHighlightFactorialRenderer.Mode mode,
                                   boolean headroom, boolean ca9Clip) {
        assertEquals(headroom, mode.retainRawHeadroom);
        assertEquals(ca9Clip, mode.applyCa9NeutralClip);
    }
}
