package com.particlesdevs.photoncamera.m10r;

import java.nio.ByteBuffer;

/** Reuse the shipped native RAW preparation only within its exact supported domain.
 * Unsupported layouts/metadata or a failed native call retain the 3F Java path.
 * No camera request, exposure decision or additional RAW is created here.
 */
final class M10RPhotoNormalization3G {
    static final String REVISION = "M10R_NATIVE_NORMALIZE3G";
    private M10RPhotoNormalization3G() {}

    interface Backend {
        M10RExposureRaw1B.Prepared prepare(ByteBuffer data, int width, int height, int cfa,
                double[] black, int white, float[] map, int cols, int rows);
    }

    static final class Result {
        final M10RExposureRaw1B.Prepared prepared;
        final String status;
        final long elapsedNs;
        Result(M10RExposureRaw1B.Prepared prepared, String status, long elapsedNs) {
            this.prepared = prepared;
            this.status = status;
            this.elapsedNs = elapsedNs;
        }
    }

    static Result tryPrepare(boolean enabled, ByteBuffer data, int width, int height, int cfa,
            double[] black, int white, float[] map, int cols, int rows, double expectedScale) {
        return tryPrepare(enabled, data, width, height, cfa, black, white, map, cols, rows,
                expectedScale, (b, w, h, c, bl, wh, m, nc, nr) -> M10RExposureRaw1E.prepare(
                        b, 0, w * 2, 2, w, h, 0, 0, c, bl, wh, m, nc, nr, 4));
    }

    static Result tryPrepare(boolean enabled, ByteBuffer data, int width, int height, int cfa,
            double[] black, int white, float[] map, int cols, int rows, double expectedScale,
            Backend backend) {
        long start = System.nanoTime();
        if (!enabled) return new Result(null, "disabled_3F_control", System.nanoTime() - start);
        // At least eight sensor sites per meter-cell axis guarantee a complete
        // native 16x22 lattice, including every CFA and odd sensor dimensions.
        boolean supported = data != null && width >= 176 && height >= 128
                && width <= 8192 && height <= 8192 && (long)width * height * 2 <= data.limit()
                && cfa >= 0 && cfa <= 3 && black != null && black.length == 4
                && white >= 2 && white <= 65535;
        if (supported) for (double b : black)
            if (!Double.isFinite(b) || b < 0 || b >= white) supported = false;
        if (map == null) supported &= cols == 0 && rows == 0;
        else {
            supported &= cols >= 2 && rows >= 2 && cols <= 256 && rows <= 256
                    && map.length == (long)cols * rows * 4;
            if (supported) for (float g : map)
                if (!Float.isFinite(g) || g <= 0 || g > 64) supported = false;
        }
        if (!supported) return new Result(null, "unsupported_native_domain_3F_fallback", System.nanoTime() - start);
        try {
            M10RExposureRaw1B.Prepared result = backend.prepare(data.duplicate(), width, height,
                    cfa, black, white, map, cols, rows);
            if (result == null || result.normalized == null
                    || result.normalized.length != (long)width * height
                    || result.width != width || result.height != height || result.cfa != cfa
                    || Double.doubleToLongBits(result.storageScale) != Double.doubleToLongBits(expectedScale))
                return new Result(null, "native_result_mismatch_3F_fallback", System.nanoTime() - start);
            return new Result(result, "native_existing_EXPOSURE1E", System.nanoTime() - start);
        } catch (LinkageError | RuntimeException failure) {
            // A partial native output never reaches the renderer. OOM is not hidden.
            return new Result(null, "native_failure_3F_fallback_" + failure.getClass().getSimpleName(),
                    System.nanoTime() - start);
        }
    }
}
