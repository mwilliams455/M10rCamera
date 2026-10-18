package com.particlesdevs.photoncamera.m10r;

/** One immutable, already guarded E1H allocation shared by display and still capture. */
public final class M10RPreviewPlan1A {
    public static final String REVISION = "M10R_PREVIEWPLAN1A";
    // Display may hold a recent decision to avoid flicker; capture never extends RAW evidence life.
    public static final long DISPLAY_HOLD_NS = 2_500_000_000L;
    public final long id, observedNs, completedNs, referenceNs;
    public final int referenceIso;
    public final Object owner;
    public final String cameraKey, controls;
    public final M10RExposureCapture1B.Selection selection;
    public final M10RExposureReport1C report;

    public M10RPreviewPlan1A(long id, Object owner, String cameraKey, String controls,
            long observedNs, long completedNs, long referenceNs, int referenceIso,
            M10RExposureCapture1B.Selection selection, M10RExposureReport1C report) {
        if(id<=0 || owner==null || cameraKey==null || controls==null || observedNs<=0
                || completedNs<observedNs || referenceNs<=0 || referenceIso<=0
                || selection==null || !selection.apply || selection.fallback || !selection.plan.ready()
                || completedNs-observedNs>M10RExposure1A.MAX_AGE_NS)
            throw new IllegalArgumentException("fresh guarded E1H plan required");
        this.id=id;this.owner=owner;this.cameraKey=cameraKey;this.controls=controls;
        this.observedNs=observedNs;this.completedNs=completedNs;this.referenceNs=referenceNs;
        this.referenceIso=referenceIso;this.selection=selection;this.report=report;
    }
    public boolean matches(Object owner,String key,String controls,long now) {
        return this.owner==owner && cameraKey.equals(key) && this.controls.equals(controls)
                && now>=completedNs && now-completedNs<=DISPLAY_HOLD_NS;
    }
    public boolean captureEligible(Object owner,String key,String controls,long now,
            long previewNs,int previewIso,long displayedId,long displayedAtNs) {
        return matches(owner,key,controls,now) && now>=observedNs
                && now-observedNs<=M10RExposure1A.MAX_AGE_NS
                && displayedId==id && displayedAtNs>=completedNs && now>=displayedAtNs
                && now-displayedAtNs<=250_000_000L && stableReference(previewNs,previewIso);
    }
    public boolean stableReference(long ns,int iso) {
        if(ns<=0||iso<=0)return false;
        double ev=Math.log(((double)ns*iso)/((double)referenceNs*referenceIso))/Math.log(2);
        return Double.isFinite(ev)&&Math.abs(ev)<=1.0/6.0;
    }
    /** Exposure is scaled before the M10-R tone curve, using the observed physical exposure. */
    public double previewScale(long observedExposure,int observedIso) {
        if(observedExposure<=0||observedIso<=0)throw new IllegalArgumentException("physical preview exposure");
        return ((double)selection.exposureNs*selection.iso)/((double)observedExposure*observedIso);
    }
}
