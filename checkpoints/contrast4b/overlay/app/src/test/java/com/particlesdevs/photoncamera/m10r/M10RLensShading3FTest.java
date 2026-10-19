package com.particlesdevs.photoncamera.m10r;

import org.junit.Test;
import java.util.Random;
import static org.junit.Assert.assertEquals;

public class M10RLensShading3FTest {
    // Frozen pre-3F bilinear expression, including double precision and ordering.
    private static double reference(float[] map, int cols, int rows, int channel,
                                    int x, int y, int width, int height) {
        double u = width > 1 ? x / (double)(width - 1) : 0.0;
        double v = height > 1 ? y / (double)(height - 1) : 0.0;
        double gx = Math.max(0.0, Math.min(1.0, u)) * (cols - 1);
        double gy = Math.max(0.0, Math.min(1.0, v)) * (rows - 1);
        int x0 = (int)Math.floor(gx), y0 = (int)Math.floor(gy);
        int x1 = Math.min(cols - 1, x0 + 1), y1 = Math.min(rows - 1, y0 + 1);
        double fx = gx - x0, fy = gy - y0;
        double a = map[(y0 * cols + x0) * 4 + channel];
        double b = map[(y0 * cols + x1) * 4 + channel];
        double c = map[(y1 * cols + x0) * 4 + channel];
        double e = map[(y1 * cols + x1) * 4 + channel];
        return (a * (1 - fx) + b * fx) * (1 - fy)
                + (c * (1 - fx) + e * fx) * fy;
    }

    private static void compare(int width, int height, int cols, int rows,
                                boolean special, boolean shuffled) {
        Random random = new Random(3106L);
        float[] map = new float[cols * rows * 4];
        for (int i = 0; i < map.length; i++) map[i] = random.nextFloat() * 8;
        if (special) {
            map[0] = Float.NaN; map[3] = Float.POSITIVE_INFINITY;
            map[4] = Float.NEGATIVE_INFINITY; map[7] = -0.0f;
            map[8] = -2; map[9] = Float.MAX_VALUE;
        }
        M10RLensShading3F cache = new M10RLensShading3F(map, cols, rows, width, height);
        for (int row = 0; row < height * 2; row++) {
            int y = shuffled ? random.nextInt(height) : row % height;
            cache.prepareRow(y);
            for (int x = 0; x < width; x++) for (int c = 0; c < 4; c++) {
                assertEquals("exact double bits at " + x + "," + y + "," + c,
                        Double.doubleToLongBits(reference(map, cols, rows, c, x, y, width, height)),
                        Double.doubleToLongBits(cache.gain(x, c)));
            }
        }
    }

    @Test public void oddSensorDimensionsAndAllChannels() { compare(97, 73, 17, 13, false, false); }
    @Test public void cacheRowReplacementAndNonSequentialAccess() { compare(43, 29, 9, 7, false, true); }
    @Test public void mapDenserThanSensorAndExactEndpoints() { compare(7, 5, 17, 13, false, false); }
    @Test public void singletonSensorAxes() {
        compare(1, 1, 2, 2, false, false);
        compare(1, 39, 7, 5, false, false);
        compare(41, 1, 7, 5, false, false);
    }
    @Test public void nonFiniteSubUnityAndExtremeGainArithmetic() { compare(47, 31, 5, 3, true, true); }
}
