package com.particlesdevs.photoncamera.m10r;

/** Session-scoped store. A late old-camera callback cannot repopulate a new session. */
public final class M10RExposureProbeStore1A {
    private String cameraKey;
    private long session;
    private M10RExposure1A.Probe latest;
    public synchronized void activate(String cameraKey, long session) {
        if (cameraKey == null || cameraKey.isEmpty() || session <= this.session)
            throw new IllegalArgumentException("strictly increasing capture-session token required");
        this.cameraKey = cameraKey; this.session = session; latest = null;
    }
    public synchronized boolean publish(M10RExposure1A.Probe probe) {
        if (probe == null || !probe.cameraKey.equals(cameraKey) || probe.session != session) return false;
        if (latest != null && (probe.generation <= latest.generation
                || probe.textureTimestampNs <= latest.textureTimestampNs
                || probe.observedAtNs < latest.observedAtNs)) return false;
        latest = probe; return true;
    }
    /** Freeze returns immutable data, not a view onto mutable global state. */
    public synchronized M10RExposure1A.Probe freeze() { return latest; }
    public synchronized void clear() { latest = null; cameraKey = null; }
}
