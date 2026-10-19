package com.particlesdevs.photoncamera.m10r;

/** Frame-bound scene probes follow the selected photographic colour response.
 * This changes the evidence seen by the existing exposure policy, not its targets.
 */
public final class M10RExposureRenderer1M {
    public static final String REVISION="M10R_METER1M_PHOTOGRAPHIC_RENDERER";
    private M10RExposureRenderer1M() {}

    /** Independently expected by the request. Never trust the probe to name its own target.
     * A rejected colour preparation retains the legacy context; when current colour
     * was requested the existing RENDERER_MISMATCH gate then owns the fallback.
     */
    public static String expectedRevision(boolean followPhotographic,boolean renderedColor,boolean order) {
        if(!followPhotographic || !renderedColor)return M10RExposureNative1B.TARGET_REVISION;
        return M10RRenderedColor1A.REVISION+(order?":M10R_COLORORDER1A_CC1_BEFORE_DG":"");
    }

    public static String expectedRevision(boolean followPhotographic,boolean renderedColor,boolean order,
            M10RContrast4B.Level contrast) {
        return M10RContrast4B.rendererRevision(expectedRevision(followPhotographic,renderedColor,order),contrast);
    }

    static M10RExposureNative1B.Context select(M10RExposureNative1B.Context legacy,
            M10RRenderedColor1A preparation,boolean followPhotographic,boolean renderedColor,boolean order) {
        return followPhotographic?legacy.withRenderedColor(preparation,renderedColor,order):legacy;
    }
}
