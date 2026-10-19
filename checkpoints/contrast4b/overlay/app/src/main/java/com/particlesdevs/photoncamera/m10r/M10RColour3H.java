package com.particlesdevs.photoncamera.m10r;

import com.particlesdevs.photoncamera.BuildConfig;
import org.json.JSONObject;

/** Per-render exact tone-calibration cache dispatch and aggregate diagnostics. */
final class M10RColour3H {
    private static final boolean AVAILABLE;
    static {
        boolean available;
        try { System.loadLibrary("m10rcolour3h"); available = true; }
        catch (LinkageError failure) { available = false; }
        AVAILABLE = available;
    }
    private static native boolean nativeProcessTile(short[] rgb, int pixels,
            double inverseStorageScale, double[] src, int[] ca9, double[] working,
            double[] out, int[] tone, int[] dg, int[] argb, long[] counts,
            boolean cc1BeforeDg, boolean cacheEnabled, long[] performance);

    private final long[] performance = new long[10];
    private final long[] totals = new long[6];
    private long pixels;
    private int appliedBands, fallbackBands, maxWorkers;
    private String status = "not_called";

    boolean process(short[] rgb, int count, double inverseStorageScale,
            double[] src, int[] ca9, double[] working, double[] out, int[] tone,
            int[] dg, int[] argb, long[] counts, boolean cc1BeforeDg) {
        if (!BuildConfig.M10R_TONE_CACHE3H || !AVAILABLE) {
            fallbackBands++;
            status = BuildConfig.M10R_TONE_CACHE3H ? "library_unavailable_3G_fallback" : "disabled_3G_control";
            return false;
        }
        final boolean applied;
        try {
            applied = nativeProcessTile(rgb, count, inverseStorageScale, src, ca9,
                    working, out, tone, dg, argb, counts, cc1BeforeDg, true, performance);
        } catch (UnsatisfiedLinkError failure) {
            fallbackBands++;
            status = "symbol_unavailable_3G_fallback";
            return false;
        }
        if (!applied) {
            fallbackBands++;
            status = "native_input_rejected_3G_fallback";
            return false;
        }
        appliedBands++;
        for (int i = 0; i < totals.length; i++) totals[i] += performance[i];
        pixels += performance[8];
        maxWorkers = Math.max(maxWorkers, (int) performance[6]);
        status = "exact_tone_cache_applied";
        return true;
    }

    JSONObject diagnostics() throws org.json.JSONException {
        return new JSONObject()
                .put("revision", "M10R_COLOURCACHE3H")
                .put("requested", BuildConfig.M10R_TONE_CACHE3H)
                .put("nativeAvailable", AVAILABLE)
                .put("nativeApplied", appliedBands > 0)
                .put("status", status)
                .put("appliedBands", appliedBands).put("fallbackBands", fallbackBands)
                .put("pixels", pixels).put("cacheHits", totals[4]).put("cacheMisses", totals[5])
                .put("cacheCountPartitionValid", totals[4] + totals[5] == pixels)
                .put("cacheHitFraction", pixels == 0 ? 0.0 : totals[4] / (double) pixels)
                .put("cacheEntriesPerWorker", 16384).put("cachePayloadBytesPerWorker", 131072)
                .put("maxWorkers", maxWorkers)
                .put("cacheScope", "private_per_worker_per_band")
                .put("cacheKey", "exact_RGB24_alpha_preserved")
                .put("missPolicy", "unchanged_TONECAL1A_function")
                .put("nativeSubtotalMs", totals[0] / 1e6)
                .put("jniSetupMs", totals[1] / 1e6)
                .put("workerWallMs", totals[2] / 1e6)
                .put("jniReleaseAndCountsMs", totals[3] / 1e6)
                .put("nativeTimingPartitionValid", totals[0] == totals[1] + totals[2] + totals[3])
                .put("subtimingsNestedIn", "rendererTiming3E.nativeColourAndTone")
                .put("subtimingsExclude", "Java_dispatch_JNI_entry_return_and_performance_publication")
                .put("interpolationOrApproximation", false);
    }
}
