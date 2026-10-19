package com.particlesdevs.photoncamera.m10r;

/** Wider measured positive range, not a new brightness target or a fixed offset.
 * Only complete seven-step evidence authorizes escaping the legacy 0.75 EV cap.
 * SCENEQUAL1O: widening a qualified request cannot revive a rejected one.
 */
public final class M10RExposureRange1H {
    public static final String REVISION="M10R_EXPOSURE1H_MEASURED_POSITIVE_RANGE";
    public static final int LEGACY_CANDIDATES=4, POSITIVE_CANDIDATES=7;
    public static final double MAX_POSITIVE_EV=1.50;
    private M10RExposureRange1H() {}
    public static boolean completeLattice(int count){return count==LEGACY_CANDIDATES||count==POSITIVE_CANDIDATES;}
    public static double requested(M10RMfm1B.Decision meter,M10RMultiField1G.Decision regional,int count) {
        if(meter==null||!meter.valid||regional==null)
            throw new IllegalArgumentException("complete meter and candidate evidence required");
        return requested(meter.wouldApply?meter.recommendedEv:0,meter.rawBlendEv,regional,count);
    }
    static double requested(double legacyRequest,double beforeCap,M10RMultiField1G.Decision regional,int count) {
        double request=requested(legacyRequest,beforeCap,regional.requestedEv,count);
        // SPLITBG1P's measured foreground ceiling survives range expansion.
        return request>0?Math.min(request,regional.positiveRequestLimitEv):request;
    }
    // Numerical seam for replaying a recorded meter decision, not fabricated image evidence.
    static double requested(double legacyRequest,double beforeCap,double regionalRequest,int count) {
        if(!Double.isFinite(legacyRequest)||!Double.isFinite(regionalRequest)||!completeLattice(count))
            throw new IllegalArgumentException("complete meter and candidate evidence required");
        if(regionalRequest<=0||count!=POSITIVE_CANDIDATES||legacyRequest<=0
                ||!Double.isFinite(beforeCap))return regionalRequest;
        return Math.max(regionalRequest,Math.min(MAX_POSITIVE_EV,beforeCap));
    }
}
