package com.particlesdevs.photoncamera.m10r;

import android.graphics.Bitmap;
import java.util.function.LongSupplier;
import org.json.JSONObject;

/** Manual, default-off JPEG colour trial shared by PHOTO and MOTION. */
final class M10RTungsten3J {
    private M10RTungsten3J() {}
    private static final class Native {
        static { System.loadLibrary("m10rtungsten3j"); }
        static native long apply(Bitmap bitmap);
    }
    static Result apply(boolean enabled, Bitmap bitmap) {
        return run(enabled, () -> Native.apply(bitmap));
    }
    static Result run(boolean enabled, LongSupplier operation) {
        if (!enabled) return new Result(false, false, 0, 0, "disabled");
        final long start = System.nanoTime();
        long changed;
        try { changed = operation.getAsLong(); }
        catch (LinkageError unavailable) {
            return new Result(true, false, 0, elapsed(start), "native_unavailable_baseline_retained");
        }
        if (changed == -1 || changed == -2 || changed == -3)
            return new Result(true, false, 0, elapsed(start), "preflight_rejected_baseline_retained");
        if (changed < 0) throw new IllegalStateException("TUNGSTEN3J bitmap pass failed: " + changed);
        return new Result(true, true, changed, elapsed(start), changed > 0
                ? "manual_warm_chroma_guard_applied" : "completed_no_matching_colours");
    }
    private static double elapsed(long start) { return (System.nanoTime()-start)/1_000_000.0; }
    static final class Result {
        final boolean requested, executed;
        final long changedPixels;
        final double elapsedMs;
        final String status;
        Result(boolean requested, boolean executed, long changedPixels, double elapsedMs, String status) {
            this.requested=requested; this.executed=executed; this.changedPixels=changedPixels;
            this.elapsedMs=elapsedMs; this.status=status;
        }
        JSONObject diagnostics() throws Exception {
            return new JSONObject().put("revision", "M10R_TUNGSTEN3J")
                    .put("requested", requested).put("executed", executed)
                    .put("applied", changedPixels > 0).put("status", status)
                    .put("changedPixels", changedPixels).put("elapsedMs", elapsedMs)
                    .put("activation", "manual_global_preference_snapshot_at_renderer_entry")
                    .put("automaticIlluminantDetection", false).put("sourceCctUsedForActivation", false)
                    .put("stage", "saved_bitmap_after_TONECAL1A_and_DETAIL3D_before_JPEG")
                    .put("maxWarmChromaReduction", .12).put("hueGateDegrees", "7.2_to_81_smooth_edges")
                    .put("nearNeutralBypassSaturation", .06)
                    .put("shadowLumaFade", "20_to_60_code_values")
                    .put("highlightLumaFade", "210_to_250_code_values")
                    .put("codeLumaPreservedBeforeRounding", true).put("linearLuminancePreservationClaimed", false)
                    .put("newChannelExtremaCreated", false).put("clippedDetailRecovered", false)
                    .put("empiricalNotFirmware", true).put("whiteBalanceChanged", false)
                    .put("captureExposureChanged", false).put("rawDngChanged", false)
                    .put("livePreviewChanged", false).put("upstreamCountersArePreGuard", true);
        }
    }
}
