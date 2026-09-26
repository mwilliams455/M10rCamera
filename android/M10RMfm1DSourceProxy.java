package com.particlesdevs.photoncamera.m10r;

/**
 * MFM1D SOURCEPROXY1A: physical-sensor preview -> common RAW-proxy adapter.
 *
 * This is source normalization, not Leica look tuning. The shared MFM1B
 * spatial decision remains unchanged for every lens/sensor.
 */
public final class M10RMfm1DSourceProxy {
    public static final double FALLBACK_EXPONENT = 1.00;

    public static final class Profile {
        public final String id;
        public final double exponent;
        public final String calibrationStatus;
        public final String basis;
        public final double sensorWidthMm;
        public final double physicalFocalMm;
        public final double aperture;
        public final int cfa;

        Profile(String id, double exponent, String calibrationStatus, String basis,
                double sensorWidthMm, double physicalFocalMm, double aperture, int cfa) {
            this.id=id;
            this.exponent=exponent;
            this.calibrationStatus=calibrationStatus;
            this.basis=basis;
            this.sensorWidthMm=sensorWidthMm;
            this.physicalFocalMm=physicalFocalMm;
            this.aperture=aperture;
            this.cfa=cfa;
        }
    }

    private M10RMfm1DSourceProxy() {}

    public static Profile resolve(double sensorWidthMm,
                                  double physicalFocalMm,
                                  double aperture,
                                  int cfa) {
        // Xiaomi 15 Ultra main sensor. Paired live/RAW anchors established that
        // the GL-preview meter requires substantial nonlinear decompression.
        if (near(sensorWidthMm, 13.1072, 0.30)
                && near(physicalFocalMm, 8.72, 0.35)
                && near(aperture, 1.63, 0.20)) {
            return new Profile(
                    "XIAOMI15U_MAIN24",
                    1.90,
                    "paired_live_raw_validated",
                    "15U_main_24mm_equiv_live_RAW_pairs",
                    sensorWidthMm, physicalFocalMm, aperture, cfa);
        }

        // Xiaomi 15 Ultra ~100 mm physical camera. The first paired live/RAW
        // capture showed the unmodified linearized preview already tracked RAW
        // closely; applying 1.90 created a false positive exposure assist.
        if (near(sensorWidthMm, 9.1392, 0.30)
                && near(physicalFocalMm, 25.10, 0.60)
                && near(aperture, 2.60, 0.25)) {
            return new Profile(
                    "XIAOMI15U_SUPERTELE100",
                    1.00,
                    "single_pair_provisional",
                    "15U_100mm_equiv_live_RAW_pair_no_decompression",
                    sensorWidthMm, physicalFocalMm, aperture, cfa);
        }

        // Safe portability default. Unknown sensors are not forced through the
        // main-camera transfer until a paired capture demonstrates the need.
        return new Profile(
                "UNVALIDATED_PHYSICAL_SENSOR",
                FALLBACK_EXPONENT,
                "uncalibrated_identity_fallback",
                "identity_until_sensor_specific_live_RAW_pair_available",
                sensorWidthMm, physicalFocalMm, aperture, cfa);
    }

    public static double[] transform(double[] linearPreviewGrid, Profile profile) {
        if (linearPreviewGrid == null) return null;
        final double exponent = profile != null && finite(profile.exponent)
                ? profile.exponent : FALLBACK_EXPONENT;
        double[] out = new double[linearPreviewGrid.length];
        for (int i=0;i<linearPreviewGrid.length;i++) {
            double v=linearPreviewGrid[i];
            if (!finite(v) || v < 0.0) {
                out[i]=Double.NaN;
                continue;
            }
            v=Math.max(0.0, Math.min(1.0, v));
            out[i]=Math.pow(v, exponent);
        }
        return out;
    }

    private static boolean near(double v,double target,double tol) {
        return finite(v) && Math.abs(v-target) <= tol;
    }

    private static boolean finite(double v) {
        return !Double.isNaN(v) && !Double.isInfinite(v);
    }
}
