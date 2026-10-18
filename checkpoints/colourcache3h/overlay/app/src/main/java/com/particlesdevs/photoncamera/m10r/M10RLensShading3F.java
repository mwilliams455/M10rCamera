package com.particlesdevs.photoncamera.m10r;

/** Per-frame bilinear gain cache. Keeps the original double operation order.
 * Horizontal interpolation is reused across sensor rows; only two map rows
 * are retained (64 bytes per sensor column, plus coordinate arrays).
 * Single-threaded, like normalizeBayer. No gain clamp or headroom policy here.
 */
final class M10RLensShading3F {
    private final float[] map;
    private final int width, height, cols, rows;
    private final int[] x0, x1;
    private final double[] fx;
    private double[] low, high;
    private int lowRow = -1, highRow = -1;
    private double fy;

    M10RLensShading3F(float[] map, int cols, int rows, int width, int height) {
        this.map = map;
        this.cols = cols;
        this.rows = rows;
        this.width = width;
        this.height = height;
        x0 = new int[width];
        x1 = new int[width];
        fx = new double[width];
        low = new double[Math.multiplyExact(width, 4)];
        high = new double[low.length];
        for (int x = 0; x < width; x++) {
            double u = width > 1 ? x / (double)(width - 1) : 0.0;
            double gx = Math.max(0.0, Math.min(1.0, u)) * (cols - 1);
            x0[x] = (int)Math.floor(gx);
            x1[x] = Math.min(cols - 1, x0[x] + 1);
            fx[x] = gx - x0[x];
        }
    }

    void prepareRow(int y) {
        double v = height > 1 ? y / (double)(height - 1) : 0.0;
        double gy = Math.max(0.0, Math.min(1.0, v)) * (rows - 1);
        int y0 = (int)Math.floor(gy);
        int y1 = Math.min(rows - 1, y0 + 1);
        fy = gy - y0;
        if (lowRow != y0) {
            if (highRow == y0) {
                double[] swap = low; low = high; high = swap;
                int swapRow = lowRow; lowRow = highRow; highRow = swapRow;
            } else {
                fill(low, y0);
                lowRow = y0;
            }
        }
        if (highRow != y1) {
            fill(high, y1);
            highRow = y1;
        }
    }

    private void fill(double[] target, int row) {
        for (int x = 0; x < width; x++) {
            int a = (row * cols + x0[x]) * 4;
            int b = (row * cols + x1[x]) * 4;
            double f = fx[x];
            for (int c = 0; c < 4; c++) {
                // Same horizontal expression as bilinearGain; do not reassociate.
                target[x * 4 + c] = (double)map[a + c] * (1 - f)
                        + (double)map[b + c] * f;
            }
        }
    }

    double gain(int x, int channel) {
        int index = x * 4 + channel;
        return low[index] * (1 - fy) + high[index] * fy;
    }
}
