package com.m10r.diagnostic;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class M10RProductionRendererTest {
    @Test
    public void promotedDefaultIsCanonicalC() {
        assertEquals(
                M10RHighlightFactorialRenderer.Mode.C_CA9_CLIP,
                M10RProductionRenderer.PROMOTED_MODE);
        assertFalse(M10RProductionRenderer.PROMOTED_MODE.retainRawHeadroom);
        assertTrue(M10RProductionRenderer.PROMOTED_MODE.applyCa9NeutralClip);
    }

    @Test
    public void factorialMatrixRemainsCanonical() {
        assertMode(M10RHighlightFactorialRenderer.Mode.A_BASELINE, false, false);
        assertMode(M10RHighlightFactorialRenderer.Mode.B_HEADROOM, true, false);
        assertMode(M10RHighlightFactorialRenderer.Mode.C_CA9_CLIP, false, true);
        assertMode(M10RHighlightFactorialRenderer.Mode.D_HEADROOM_CA9, true, true);
    }

    private static void assertMode(M10RHighlightFactorialRenderer.Mode mode,
                                   boolean headroom, boolean ca9Clip) {
        assertEquals(headroom, mode.retainRawHeadroom);
        assertEquals(ca9Clip, mode.applyCa9NeutralClip);
    }
}
