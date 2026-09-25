package com.particlesdevs.photoncamera.m10r;

/** Phone-domain adapter for the first active M10-R AE experiment.
 * The Android HAL supplies a continuously metered preview exposure. AE1B converts
 * that exposure to APEX Bv and passes it to the recovered M10-R A-mode allocator.
 * Spatial metering is handled separately by forcing center-weighted Camera2 AE.
 */
public final class M10RAe1BPolicy {
    private M10RAe1BPolicy() {}

    public static final class Decision {
        public final boolean valid;
        public final long previewExposureNs;
        public final int previewIso;
        public final double aperture;
        public final double focalLength35mm;
        public final double previewTvEv;
        public final double previewAvEv;
        public final double previewSvEv;
        public final double previewBvEv;
        public final double tvIsoEv;
        public final double exposureCorrectionEv;
        public final M10RAeOracle.Result oracle;

        Decision(boolean valid, long previewExposureNs, int previewIso,
                 double aperture, double focalLength35mm,
                 double previewTvEv, double previewAvEv, double previewSvEv,
                 double previewBvEv, double tvIsoEv, double exposureCorrectionEv,
                 M10RAeOracle.Result oracle) {
            this.valid=valid;
            this.previewExposureNs=previewExposureNs;
            this.previewIso=previewIso;
            this.aperture=aperture;
            this.focalLength35mm=focalLength35mm;
            this.previewTvEv=previewTvEv;
            this.previewAvEv=previewAvEv;
            this.previewSvEv=previewSvEv;
            this.previewBvEv=previewBvEv;
            this.tvIsoEv=tvIsoEv;
            this.exposureCorrectionEv=exposureCorrectionEv;
            this.oracle=oracle;
        }
    }

    private static double log2(double x) {
        return Math.log(x) / Math.log(2.0);
    }

    /** Leica 1/f helper is half-stop quantized in the recovered firmware. */
    public static double oneOverFTv(double focalLengthMm) {
        if (!(focalLengthMm > 0.0) || !Double.isFinite(focalLengthMm)) return Double.NaN;
        return Math.round(log2(focalLengthMm) * 2.0) / 2.0;
    }

    public static Decision solve(long previewExposureNs, int previewIso,
                                 double aperture, double focalLength35mm,
                                 double exposureCorrectionEv,
                                 int svMinIso, int svMaxIso) {
        if (previewExposureNs <= 0L || previewIso <= 0
                || !(aperture > 0.0) || !(focalLength35mm > 0.0)
                || !Double.isFinite(aperture) || !Double.isFinite(focalLength35mm)
                || !Double.isFinite(exposureCorrectionEv)) {
            return new Decision(false,previewExposureNs,previewIso,aperture,focalLength35mm,
                    Double.NaN,Double.NaN,Double.NaN,Double.NaN,Double.NaN,
                    exposureCorrectionEv,null);
        }
        double seconds=previewExposureNs/1.0e9;
        double tv=log2(1.0/seconds);
        double av=2.0*log2(aperture);
        double sv=log2(previewIso/3.125);
        double bv=tv+av-sv;
        double tvIso=oneOverFTv(focalLength35mm);
        M10RAeOracle.Result result=M10RAeOracle.solveAModeQ8(
                M10RAeOracle.evToQ8(bv),
                M10RAeOracle.evToQ8(av),
                0,
                M10RAeOracle.evToQ8(exposureCorrectionEv),
                M10RAeOracle.evToQ8(tvIso),
                M10RAeOracle.isoToSvQ8(svMinIso),
                M10RAeOracle.isoToSvQ8(svMaxIso),
                M10RAeOracle.TV_MIN_Q8,
                M10RAeOracle.TV_MAX_Q8);
        return new Decision(true,previewExposureNs,previewIso,aperture,focalLength35mm,
                tv,av,sv,bv,tvIso,exposureCorrectionEv,result);
    }
}
