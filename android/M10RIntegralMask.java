package com.particlesdevs.photoncamera.m10r;

/** Exact recovered Leica M10-R Integral AE quantity mask.
 * Firmware: 16 rows x 22 columns, sum 14160, weights 0..100.
 * This class contains only the recovered spatial weights; it does not claim that
 * a phone preview Y plane is numerically identical to Leica CA9 Y statistics.
 */
public final class M10RIntegralMask {
    public static final int ROWS = 16;
    public static final int COLS = 22;
    public static final int WEIGHT_SUM = 14160;

    private static final int[] W = {
        0,0,0,0,10,10,10,10,10,10,10,10,10,10,10,10,10,10,0,0,0,0,
        0,0,0,10,10,20,20,20,30,30,30,30,30,30,20,20,20,10,10,0,0,0,
        0,0,10,10,20,30,30,30,30,40,50,50,40,30,30,30,30,20,10,10,0,0,
        0,10,10,20,30,40,50,50,50,60,60,60,60,50,50,50,40,30,20,10,10,0,
        10,10,20,30,40,50,60,80,80,80,80,80,80,80,80,60,50,40,30,20,10,10,
        10,20,30,40,50,60,80,80,100,100,100,100,100,100,80,80,60,50,40,30,20,10,
        10,20,30,40,50,80,100,100,100,100,100,100,100,100,100,100,80,50,40,30,20,10,
        10,20,30,40,50,80,100,100,100,100,100,100,100,100,100,100,80,50,40,30,20,10,
        10,20,30,40,50,80,100,100,100,100,100,100,100,100,100,100,80,50,40,30,20,10,
        10,20,30,40,50,80,100,100,100,100,100,100,100,100,100,100,80,50,40,30,20,10,
        10,20,30,40,50,60,80,80,100,100,100,100,100,100,80,80,60,50,40,30,20,10,
        10,10,20,30,40,50,60,80,80,80,80,80,80,80,80,60,50,40,30,20,10,10,
        0,10,10,20,30,40,50,50,50,60,60,60,60,50,50,50,40,30,20,10,10,0,
        0,0,10,10,20,30,30,30,30,40,50,50,40,30,30,30,30,20,10,10,0,0,
        0,0,0,10,10,20,20,20,30,30,30,30,30,30,20,20,20,10,10,0,0,0,
        0,0,0,0,10,10,10,10,10,10,10,10,10,10,10,10,10,10,0,0,0,0
    };

    private M10RIntegralMask() {}

    public static int weight(int row, int col) {
        if (row < 0 || row >= ROWS || col < 0 || col >= COLS) return 0;
        return W[row * COLS + col];
    }

    public static int weightForPixel(int x, int y, int width, int height) {
        if (width <= 0 || height <= 0) return 0;
        int col = Math.min(COLS - 1, Math.max(0, (int)((long)x * COLS / width)));
        int row = Math.min(ROWS - 1, Math.max(0, (int)((long)y * ROWS / height)));
        return weight(row, col);
    }

    public static int[] copyWeights() { return W.clone(); }
}
