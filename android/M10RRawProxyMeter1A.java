package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CaptureResult;
import android.hardware.camera2.params.BlackLevelPattern;
import android.media.Image;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;

/**
 * MFM1C RAWPROXY1A diagnostic state.
 *
 * A low-cadence preview-time RAW request is made against the already configured
 * RAW surface using the current preview exposure/ISO. Only the same sparse
 * semantic-green samples used by the post-capture RAW oracle are accumulated
 * into the recovered 16x22 M10-R meter grid; the RAW image is then closed.
 *
 * Diagnostic only in RAWPROXY1A: active MFM1B still consumes the frozen GL grid.
 */
public final class M10RRawProxyMeter1A {
    public static final int GRID_R = 16;
    public static final int GRID_C = 22;
    public static final long MIN_INTERVAL_NS = 800_000_000L;
    private static final long STALE_INFLIGHT_NS = 3_000_000_000L;

    private M10RRawProxyMeter1A() {}

    public static final class Snapshot {
        public final boolean valid;
        public final long generation;
        public final long imageTimestampNs;
        public final long publishedRealtimeNs;
        public final long requestedExposureNs;
        public final int requestedIso;
        public final long actualExposureNs;
        public final int actualIso;
        public final int cfa;
        public final int width;
        public final int height;
        public final int rowStrideBytes;
        public final int pixelStrideBytes;
        public final boolean dynamicBlackUsed;
        public final boolean dynamicWhiteUsed;
        public final double[] grid;
        public final String status;

        Snapshot(boolean valid, long generation, long imageTimestampNs, long publishedRealtimeNs,
                 long requestedExposureNs, int requestedIso,
                 long actualExposureNs, int actualIso, int cfa,
                 int width, int height, int rowStrideBytes, int pixelStrideBytes,
                 boolean dynamicBlackUsed, boolean dynamicWhiteUsed,
                 double[] grid, String status) {
            this.valid = valid;
            this.generation = generation;
            this.imageTimestampNs = imageTimestampNs;
            this.publishedRealtimeNs = publishedRealtimeNs;
            this.requestedExposureNs = requestedExposureNs;
            this.requestedIso = requestedIso;
            this.actualExposureNs = actualExposureNs;
            this.actualIso = actualIso;
            this.cfa = cfa;
            this.width = width;
            this.height = height;
            this.rowStrideBytes = rowStrideBytes;
            this.pixelStrideBytes = pixelStrideBytes;
            this.dynamicBlackUsed = dynamicBlackUsed;
            this.dynamicWhiteUsed = dynamicWhiteUsed;
            this.grid = grid != null ? grid.clone() : null;
            this.status = status;
        }
    }

    private static Snapshot latest = invalidSnapshot("not_sampled");
    private static Snapshot frozen = invalidSnapshot("not_frozen");

    private static boolean pausedForStill = false;
    private static boolean inFlight = false;
    private static boolean resultReceived = false;
    private static boolean imageReceived = false;
    private static long armedRealtimeNs = 0L;
    private static long lastRequestRealtimeNs = Long.MIN_VALUE;
    private static long expectedImageTimestampNs = Long.MIN_VALUE;
    private static long requestedExposureNs = 0L;
    private static int requestedIso = 0;
    private static int requestedCfa = -1;

    private static long actualExposureNs = 0L;
    private static int actualIso = 0;
    private static float[] dynamicBlack = null;
    private static int dynamicWhite = -1;

    private static Snapshot invalidSnapshot(String status) {
        return new Snapshot(false, 0L, 0L, 0L, 0L, 0, 0L, 0, -1,
                0, 0, 0, 0, false, false, null, status);
    }

    public static synchronized boolean tryArm(long nowRealtimeNs,
                                              long previewExposureNs,
                                              int previewIso,
                                              int physicalCfa) {
        if (pausedForStill || previewExposureNs <= 0L || previewIso <= 0
                || physicalCfa < 0 || physicalCfa > 3) {
            return false;
        }
        if (inFlight && nowRealtimeNs - armedRealtimeNs <= STALE_INFLIGHT_NS) {
            return false;
        }
        if (inFlight) {
            // Fail open after a stale request so metering can recover.
            inFlight = false;
        }
        if (lastRequestRealtimeNs != Long.MIN_VALUE
                && nowRealtimeNs - lastRequestRealtimeNs < MIN_INTERVAL_NS) {
            return false;
        }

        inFlight = true;
        resultReceived = false;
        imageReceived = false;
        armedRealtimeNs = nowRealtimeNs;
        lastRequestRealtimeNs = nowRealtimeNs;
        expectedImageTimestampNs = Long.MIN_VALUE;
        requestedExposureNs = previewExposureNs;
        requestedIso = previewIso;
        requestedCfa = physicalCfa;
        actualExposureNs = 0L;
        actualIso = 0;
        dynamicBlack = null;
        dynamicWhite = -1;
        return true;
    }

    public static synchronized void onCaptureStarted(long sensorTimestampNs) {
        if (!inFlight) return;
        expectedImageTimestampNs = sensorTimestampNs;
    }

    public static synchronized void onCaptureCompleted(CaptureResult result) {
        if (!inFlight || result == null) return;
        Long ts = result.get(CaptureResult.SENSOR_TIMESTAMP);
        if (ts == null || expectedImageTimestampNs == Long.MIN_VALUE
                || ts.longValue() != expectedImageTimestampNs) {
            return;
        }
        Long exp = result.get(CaptureResult.SENSOR_EXPOSURE_TIME);
        Integer iso = result.get(CaptureResult.SENSOR_SENSITIVITY);
        float[] db = result.get(CaptureResult.SENSOR_DYNAMIC_BLACK_LEVEL);
        Integer dw = result.get(CaptureResult.SENSOR_DYNAMIC_WHITE_LEVEL);
        actualExposureNs = exp != null ? exp : 0L;
        actualIso = iso != null ? iso : 0;
        dynamicBlack = db != null ? db.clone() : null;
        dynamicWhite = dw != null ? dw : -1;
        resultReceived = true;

        if (latest.valid && latest.imageTimestampNs == expectedImageTimestampNs) {
            latest = new Snapshot(true, latest.generation, latest.imageTimestampNs,
                    latest.publishedRealtimeNs, latest.requestedExposureNs, latest.requestedIso,
                    actualExposureNs, actualIso, latest.cfa, latest.width, latest.height,
                    latest.rowStrideBytes, latest.pixelStrideBytes,
                    latest.dynamicBlackUsed, latest.dynamicWhiteUsed,
                    latest.grid, latest.status);
        }
        if (imageReceived) inFlight = false;
    }

    public static synchronized void onCaptureAborted() {
        inFlight = false;
        resultReceived = false;
        imageReceived = false;
        expectedImageTimestampNs = Long.MIN_VALUE;
    }

    /**
     * Called after ImageSaver has acquired an Image. Returns true only for the
     * exact RAW meter timestamp and closes the image itself in that case.
     */
    public static boolean tryConsume(Image image, CameraCharacteristics characteristics) {
        if (image == null || characteristics == null) return false;

        final long ts = image.getTimestamp();
        final long reqExp;
        final int reqIso;
        final int cfa;
        final long actExp;
        final int actIso;
        final float[] dynBlack;
        final int dynWhite;

        synchronized (M10RRawProxyMeter1A.class) {
            if (!inFlight || expectedImageTimestampNs == Long.MIN_VALUE
                    || ts != expectedImageTimestampNs) {
                return false;
            }
            reqExp = requestedExposureNs;
            reqIso = requestedIso;
            cfa = requestedCfa;
            actExp = actualExposureNs;
            actIso = actualIso;
            dynBlack = dynamicBlack != null ? dynamicBlack.clone() : null;
            dynWhite = dynamicWhite;
            imageReceived = true;
        }

        Snapshot sampled;
        try {
            sampled = sample(image, characteristics, reqExp, reqIso, actExp, actIso,
                    cfa, dynBlack, dynWhite);
        } catch (Throwable t) {
            sampled = new Snapshot(false, 0L, ts, System.nanoTime(),
                    reqExp, reqIso, actExp, actIso, cfa,
                    image.getWidth(), image.getHeight(), 0, 0,
                    false, false, null, "sample_failed:" + t.getClass().getSimpleName());
        } finally {
            image.close();
        }

        synchronized (M10RRawProxyMeter1A.class) {
            long gen = latest.generation + 1L;
            latest = new Snapshot(sampled.valid, gen, sampled.imageTimestampNs,
                    sampled.publishedRealtimeNs, sampled.requestedExposureNs, sampled.requestedIso,
                    actualExposureNs != 0L ? actualExposureNs : sampled.actualExposureNs,
                    actualIso != 0 ? actualIso : sampled.actualIso,
                    sampled.cfa, sampled.width, sampled.height,
                    sampled.rowStrideBytes, sampled.pixelStrideBytes,
                    sampled.dynamicBlackUsed, sampled.dynamicWhiteUsed,
                    sampled.grid, sampled.status);
            if (resultReceived) inFlight = false;
        }
        return true;
    }

    private static Snapshot sample(Image image,
                                   CameraCharacteristics characteristics,
                                   long reqExp, int reqIso,
                                   long actExp, int actIso,
                                   int cfa, float[] dynBlack, int dynWhite) {
        if (image.getFormat() != android.graphics.ImageFormat.RAW_SENSOR) {
            throw new IllegalArgumentException("not_RAW_SENSOR");
        }
        if (cfa < 0 || cfa > 3) throw new IllegalArgumentException("unsupported_CFA_" + cfa);
        Image.Plane[] planes = image.getPlanes();
        if (planes == null || planes.length != 1) throw new IllegalStateException("RAW_plane_count");
        Image.Plane p = planes[0];
        ByteBuffer b = p.getBuffer().duplicate().order(ByteOrder.LITTLE_ENDIAN);
        int rowStride = p.getRowStride();
        int pixelStride = p.getPixelStride();
        int width = image.getWidth();
        int height = image.getHeight();
        if (width <= 1 || height <= 1 || rowStride <= 0 || pixelStride < 2) {
            throw new IllegalStateException("invalid_RAW_geometry");
        }

        int[] staticBlack = new int[4];
        BlackLevelPattern bp = characteristics.get(CameraCharacteristics.SENSOR_BLACK_LEVEL_PATTERN);
        if (bp == null) throw new IllegalStateException("missing_static_black");
        bp.copyTo(staticBlack, 0);
        Integer staticWhiteObj = characteristics.get(CameraCharacteristics.SENSOR_INFO_WHITE_LEVEL);
        if (staticWhiteObj == null || staticWhiteObj <= 0) {
            throw new IllegalStateException("missing_static_white");
        }
        int white = dynWhite > 0 ? dynWhite : staticWhiteObj;
        boolean dynamicWhiteUsed = dynWhite > 0;
        boolean dynamicBlackUsed = dynBlack != null && dynBlack.length >= 4;

        int[] semantic = semanticChannels(cfa);
        double[] sum = new double[GRID_R * GRID_C];
        long[] count = new long[GRID_R * GRID_C];

        for (int by = 0; by < height; by += 8) {
            for (int bx = 0; bx < width; bx += 8) {
                for (int oy = 0; oy <= 1; oy++) {
                    int y = by + oy;
                    if (y >= height) continue;
                    for (int ox = 0; ox <= 1; ox++) {
                        int x = bx + ox;
                        if (x >= width) continue;
                        int site = ((y & 1) << 1) | (x & 1);
                        int plane = semantic[site];
                        if (plane != 1 && plane != 2) continue;

                        int offset = y * rowStride + x * pixelStride;
                        if (offset < 0 || offset + 1 >= b.capacity()) continue;
                        int raw = b.getShort(offset) & 0xffff;
                        double black = dynamicBlackUsed ? dynBlack[site] : staticBlack[site];
                        double denom = Math.max(1.0, white - black);
                        double unit = (raw - black) / denom;
                        if (unit < 0.0) unit = 0.0;
                        if (unit > 1.0) unit = 1.0;

                        int row = Math.min(GRID_R - 1,
                                Math.max(0, (int)((long)y * GRID_R / height)));
                        int col = Math.min(GRID_C - 1,
                                Math.max(0, (int)((long)x * GRID_C / width)));
                        int idx = row * GRID_C + col;
                        sum[idx] += unit;
                        count[idx]++;
                    }
                }
            }
        }

        double[] grid = new double[GRID_R * GRID_C];
        for (int i = 0; i < grid.length; i++) {
            if (count[i] <= 0L) throw new IllegalStateException("empty_meter_cell_" + i);
            grid[i] = sum[i] / count[i];
        }

        return new Snapshot(true, 0L, image.getTimestamp(), System.nanoTime(),
                reqExp, reqIso, actExp, actIso, cfa, width, height,
                rowStride, pixelStride, dynamicBlackUsed, dynamicWhiteUsed,
                grid, "success");
    }

    /** Maps local 2x2 sites to Camera2 semantic channels [R,G-even,G-odd,B]. */
    private static int[] semanticChannels(int cfa) {
        switch (cfa) {
            case 0: return new int[]{0,1,2,3}; // RGGB
            case 1: return new int[]{1,0,3,2}; // GRBG
            case 2: return new int[]{1,3,0,2}; // GBRG
            case 3: return new int[]{3,1,2,0}; // BGGR
            default: throw new IllegalArgumentException("unsupported_CFA_" + cfa);
        }
    }

    public static synchronized void pauseAndFreezeForStill() {
        pausedForStill = true;
        frozen = copy(latest);
    }

    public static synchronized void resumePreview() {
        pausedForStill = false;
    }

    public static synchronized Snapshot snapshot() {
        return copy(latest);
    }

    public static synchronized Snapshot frozenSnapshot() {
        return copy(frozen);
    }

    private static Snapshot copy(Snapshot s) {
        return new Snapshot(s.valid, s.generation, s.imageTimestampNs, s.publishedRealtimeNs,
                s.requestedExposureNs, s.requestedIso, s.actualExposureNs, s.actualIso,
                s.cfa, s.width, s.height, s.rowStrideBytes, s.pixelStrideBytes,
                s.dynamicBlackUsed, s.dynamicWhiteUsed, s.grid, s.status);
    }
}
