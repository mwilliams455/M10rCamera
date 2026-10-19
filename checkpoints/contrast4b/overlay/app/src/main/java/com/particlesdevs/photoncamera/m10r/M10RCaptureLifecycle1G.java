package com.particlesdevs.photoncamera.m10r;

/** Owns one photographic RAW from shutter admission through saver cleanup.
 * Preview metering is independent. Old session callbacks cannot finish a newer shot.
 */
public final class M10RCaptureLifecycle1G {
    public static final String REVISION = "M10R_PREVIEW1G_CAPTURE_LIFECYCLE";
    private long sequence;
    private long active;
    private String phase = "idle";

    public synchronized long begin() {
        if (active != 0) return 0;
        active = ++sequence;
        phase = "preparing";
        return active;
    }

    public synchronized long active() { return active; }
    public synchronized boolean busy() { return active != 0; }
    public synchronized boolean preparing() { return "preparing".equals(phase); }
    public synchronized boolean owns(long ticket) { return ticket != 0 && active == ticket; }
    public synchronized boolean acquiring(long ticket) {
        return owns(ticket) && !"saving".equals(phase);
    }

    public synchronized boolean submitted(long ticket) {
        if (!owns(ticket) || !preparing()) return false;
        phase = "submitted";
        return true;
    }

    public synchronized boolean processing(long ticket) {
        if (!owns(ticket) || !"submitted".equals(phase)) return false;
        phase = "saving";
        return true;
    }

    public synchronized boolean finish(long ticket) {
        if (!owns(ticket)) return false;
        active = 0;
        phase = "idle";
        return true;
    }

    /** A camera restart may cancel acquisition, but must not admit another RAW
     * while an already dispatched worker still owns the shared saver buffer. */
    public synchronized void retireCamera() {
        if (!"saving".equals(phase)) finish(active);
    }

    public synchronized String status() { return phase + " #" + active; }
}
