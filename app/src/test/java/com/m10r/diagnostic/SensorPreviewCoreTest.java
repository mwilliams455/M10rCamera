package com.m10r.diagnostic;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;

import org.junit.Test;

public class SensorPreviewCoreTest {
    @Test
    public void resolvesAllFourStandardBayerPatterns() {
        long[] dim = {2, 2};
        assertEquals(SensorPreviewCore.CfaPattern.RGGB,
                SensorPreviewCore.CfaPattern.fromDng(dim, new byte[] {0, 1, 1, 2}));
        assertEquals(SensorPreviewCore.CfaPattern.GRBG,
                SensorPreviewCore.CfaPattern.fromDng(dim, new byte[] {1, 0, 2, 1}));
        assertEquals(SensorPreviewCore.CfaPattern.GBRG,
                SensorPreviewCore.CfaPattern.fromDng(dim, new byte[] {1, 2, 0, 1}));
        assertEquals(SensorPreviewCore.CfaPattern.BGGR,
                SensorPreviewCore.CfaPattern.fromDng(dim, new byte[] {2, 1, 1, 0}));
    }

    @Test
    public void normalizesAgainstDngBlackAndWhite() {
        double[] black = {100.0};
        double[] white = {1100.0};
        assertEquals(0.0, SensorPreviewCore.normalized(100, 0, 0, black, white), 0.0);
        assertEquals(0.5, SensorPreviewCore.normalized(600, 0, 0, black, white), 1e-15);
        assertEquals(1.0, SensorPreviewCore.normalized(1100, 0, 0, black, white), 0.0);
        assertEquals(0.0, SensorPreviewCore.normalized(0, 0, 0, black, white), 0.0);
        assertEquals(1.0, SensorPreviewCore.normalized(2000, 0, 0, black, white), 0.0);
    }

    @Test
    public void supportsPerBayerSiteBlackAndWhiteLevels() {
        double[] black = {0, 100, 200, 300};
        double[] white = {1000, 1100, 1200, 1300};
        assertEquals(0.5, SensorPreviewCore.normalized(500, 0, 0, black, white), 1e-15);
        assertEquals(0.5, SensorPreviewCore.normalized(600, 1, 0, black, white), 1e-15);
        assertEquals(0.5, SensorPreviewCore.normalized(700, 0, 1, black, white), 1e-15);
        assertEquals(0.5, SensorPreviewCore.normalized(800, 1, 1, black, white), 1e-15);
    }

    @Test
    public void asShotNeutralUsesGreenReferencedReciprocalGains() {
        assertArrayEquals(new double[] {2.0, 1.0, 0.5},
                SensorPreviewCore.whiteBalanceGains(new double[] {0.5, 1.0, 2.0}), 1e-15);
    }

    @Test
    public void constantChannelGbrgMosaicDemosaicsDeterministically() {
        int width = 6;
        int height = 6;
        short[] samples = new short[width * height];
        SensorPreviewCore.CfaPattern cfa = SensorPreviewCore.CfaPattern.GBRG;
        for (int y = 0; y < height; y++) {
            for (int x = 0; x < width; x++) {
                int value;
                switch (cfa.channelAt(x, y)) {
                    case R: value = 7500; break;
                    case G: value = 6000; break;
                    case B: value = 3000; break;
                    default: throw new AssertionError();
                }
                samples[y * width + x] = (short) value;
            }
        }

        SensorPreviewCore.PreviewResult preview = SensorPreviewCore.render(
                samples, width, height,
                new long[] {2, 2}, new byte[] {1, 2, 0, 1},
                new double[] {0}, new double[] {15000},
                new double[] {1, 1, 1}, 6);

        assertEquals(SensorPreviewCore.CfaPattern.GBRG, preview.cfaPattern);
        assertEquals(6, preview.width);
        assertEquals(6, preview.height);
        int expected = 0xff000000 |
                (SensorPreviewCore.toSrgb8(0.5) << 16) |
                (SensorPreviewCore.toSrgb8(0.4) << 8) |
                SensorPreviewCore.toSrgb8(0.2);
        for (int pixel : preview.argb) assertEquals(expected, pixel);
    }

    @Test
    public void previewDimensionIsBoundedWithoutFullRgbAllocation() {
        int width = 100;
        int height = 60;
        short[] samples = new short[width * height];
        for (int i = 0; i < samples.length; i++) samples[i] = 5000;

        SensorPreviewCore.PreviewResult preview = SensorPreviewCore.render(
                samples, width, height,
                new long[] {2, 2}, new byte[] {0, 1, 1, 2},
                new double[] {0}, new double[] {15000},
                new double[] {1, 1, 1}, 20);

        assertEquals(5, preview.sourceStride);
        assertEquals(20, preview.width);
        assertEquals(12, preview.height);
        assertEquals(240, preview.argb.length);
    }
}
