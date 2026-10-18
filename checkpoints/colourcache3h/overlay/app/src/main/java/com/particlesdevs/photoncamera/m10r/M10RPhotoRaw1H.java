package com.particlesdevs.photoncamera.m10r;

import android.media.Image;
import android.media.ImageReader;
import com.particlesdevs.photoncamera.processing.ImageSaver;

/** One photographic RAW, identified by its request's sensor timestamp.
 * All producer, cancellation and cleanup operations share this monitor, so a late
 * ImageReader callback cannot repopulate a buffer after the shot has released it.
 */
public final class M10RPhotoRaw1H {
    public static final String REVISION = "M10R_PREVIEW1H_RAW_RECOVERY";
    private final ImageReader reader;
    private final ImageSaver saver;
    private Image pending;
    private long pendingTimestamp;
    private long expectedTimestamp;
    private boolean copied;
    private boolean sealed;
    private String failure;

    public M10RPhotoRaw1H(ImageReader reader, ImageSaver saver) {
        this.reader = reader;
        this.saver = saver;
    }

    public synchronized void started(long timestamp) {
        if (sealed || copied || timestamp <= 0 || expectedTimestamp != 0) return;
        expectedTimestamp = timestamp;
        if (pending != null) {
            Image image = pending; pending = null;
            if (pendingTimestamp == timestamp) copy(image);
            else image.close();
        }
    }

    public synchronized void image(ImageReader source, Image image) {
        if (image == null) return;
        if (source != reader || sealed || copied || failure != null) { image.close(); return; }
        long timestamp;
        try { timestamp = image.getTimestamp(); }
        catch (RuntimeException e) { image.close(); fail("RAW timestamp unavailable"); return; }
        if (timestamp <= 0) { image.close(); fail("RAW timestamp unavailable"); return; }
        if (expectedTimestamp == 0) {
            // Image and metadata callbacks may arrive in either order. Keep only
            // the newest frame; a late frame from a failed earlier shot is older.
            if (pending != null && timestamp <= pendingTimestamp) { image.close(); return; }
            if (pending != null) pending.close();
            pending = image; pendingTimestamp = timestamp;
        } else if (timestamp == expectedTimestamp) copy(image);
        else image.close();
    }

    private void copy(Image image) {
        try {
            saver.initOwnedRaw1C(reader, image);
            if (saver.bufferSize() != 1) throw new IllegalStateException("No photographic RAW copied");
            copied = true;
        } catch (RuntimeException | OutOfMemoryError e) {
            // initOwnedRaw1C closes on failure, including before addImage is entered.
            fail("RAW read failed: " + e.getClass().getSimpleName() + ": " + e.getMessage());
        }
    }

    public synchronized boolean ready() { return copied; }
    public synchronized String failure() { return failure; }

    public synchronized void seal() {
        sealed = true;
        if (pending != null) { pending.close(); pending = null; }
    }

    public synchronized void fail(String reason) {
        if (failure == null) failure = reason;
        seal();
    }

    public synchronized void retireCamera() {
        if (!copied) fail("Camera closed before RAW delivery");
        else seal();
    }

    /** Only the acquisition owner or the finished saver may release copied RAW. */
    public synchronized void discard() {
        seal();
        saver.discardRaw1H();
    }

    /** Allows the requested long exposure/frame duration plus a callback margin.
     * This deadline applies to acquisition only, never to native rendering. */
    public static long acquisitionTimeoutMillis(Long exposureNs, Long frameDurationNs) {
        long exposure = exposureNs == null ? 0 : Math.max(0, exposureNs);
        long duration = frameDurationNs == null ? 0 : Math.max(0, frameDurationNs);
        return 10_000L + Math.max(exposure, duration) / 1_000_000L;
    }
}
