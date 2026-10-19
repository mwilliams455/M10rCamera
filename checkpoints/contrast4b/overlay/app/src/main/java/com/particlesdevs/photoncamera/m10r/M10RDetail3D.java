package com.particlesdevs.photoncamera.m10r;

import java.util.function.IntToLongFunction;

/** Bounded opt-in dispatch of the retained bitmap-domain edge experiment. */
final class M10RDetail3D {
    private M10RDetail3D() {}

    static final class Result {
        final boolean executed;
        final int iso;
        final long affectedPixels;
        final double elapsedMs;

        Result(boolean executed, int iso, long affectedPixels, double elapsedMs) {
            this.executed = executed;
            this.iso = iso;
            this.affectedPixels = affectedPixels;
            this.elapsedMs = elapsedMs;
        }
    }

    static Result run(boolean enabled, Integer sensorSensitivity, IntToLongFunction nativePass) {
        int iso = sensorSensitivity != null && sensorSensitivity > 0 ? sensorSensitivity : 100;
        if (!enabled) return new Result(false, iso, 0L, 0.0);
        long start = System.nanoTime();
        long affected = nativePass.applyAsLong(iso);
        if (affected < 0L) {
            // The renderer's existing failure path recycles the bitmap and records
            // an error instead of presenting a failed trial as a completed render.
            throw new IllegalStateException("DETAIL3D native edge pass failed: " + affected);
        }
        return new Result(true, iso, affected, (System.nanoTime() - start) / 1_000_000.0);
    }
}
