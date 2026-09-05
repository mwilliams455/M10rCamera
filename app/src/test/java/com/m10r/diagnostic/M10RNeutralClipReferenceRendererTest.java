package com.m10r.diagnostic;

import static org.junit.Assert.assertArrayEquals;

import org.junit.Test;

public class M10RNeutralClipReferenceRendererTest {
    private static final double EPS = 1.0e-12;

    @Test
    public void belowNeutralSaturationIsUnchanged() {
        int[] gains = {697, 256, 442};
        double[] neutral = M10RColorSpecCore.gainsToFirmwareNeutral(gains);
        double[] camera = {neutral[0] * 0.5, neutral[1] * 0.5, neutral[2] * 0.5};
        assertArrayEquals(camera,
                M10RNeutralClipReferenceRenderer.applyCa9NeutralSaturation(camera, gains), EPS);
    }

    @Test
    public void fullCameraCodeCollapsesToQuantizedNeutralBoundary() {
        int[] gains = {697, 256, 442};
        double[] expected = M10RColorSpecCore.gainsToFirmwareNeutral(gains);
        assertArrayEquals(expected,
                M10RNeutralClipReferenceRenderer.applyCa9NeutralSaturation(
                        new double[] {1.0, 1.0, 1.0}, gains), EPS);
    }

    @Test
    public void channelsClipIndependentlyInCa9GainDomain() {
        int[] gains = {697, 256, 442};
        double[] neutral = M10RColorSpecCore.gainsToFirmwareNeutral(gains);
        double[] camera = {neutral[0] * 2.0, neutral[1] * 0.5, neutral[2] * 1.2};
        double[] expected = {neutral[0], neutral[1] * 0.5, neutral[2]};
        assertArrayEquals(expected,
                M10RNeutralClipReferenceRenderer.applyCa9NeutralSaturation(camera, gains), EPS);
    }
}
