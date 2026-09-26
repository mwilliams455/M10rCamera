package com.particlesdevs.photoncamera.m10r;

import android.graphics.Rect;
import android.hardware.camera2.CameraCharacteristics;
import android.util.SizeF;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Locale;

/**
 * MFM1D SOURCEPROXY1B: generic physical-camera preview -> common RAW-proxy adapter.
 *
 * This class contains no manufacturer/model/lens-name matching. A physical camera
 * is identified only by a deterministic fingerprint derived from Camera2/RAW
 * characteristics. Calibration belongs to the phone-source adapter, not to the
 * shared Leica MFM logic or photographic renderer.
 */
public final class M10RMfm1DSourceProxy {
    public static final double FALLBACK_EXPONENT = 1.00;

    // Calibration registry keys are generic physical-camera fingerprints.
    // They intentionally carry no manufacturer/model/lens semantics.
    private static final String CAL_FP_A = "03d973b6411b4879";
    private static final String CAL_FP_B = "f76d00db34b9480f";

    public static final class Profile {
        public final String id;
        public final String fingerprint;
        public final String canonicalDescriptor;
        public final double exponent;
        public final String calibrationStatus;
        public final String calibrationEvidenceId;
        public final String basis;
        public final int activeWidth;
        public final int activeHeight;
        public final int cfa;
        public final double sensorWidthMm;
        public final double physicalFocalMm;
        public final double aperture;
        public final int whiteLevel;
        public final int referenceIlluminant1;
        public final int referenceIlluminant2;

        Profile(String id, String fingerprint, String canonicalDescriptor,
                double exponent, String calibrationStatus, String calibrationEvidenceId,
                String basis, int activeWidth, int activeHeight, int cfa,
                double sensorWidthMm, double physicalFocalMm, double aperture,
                int whiteLevel, int referenceIlluminant1, int referenceIlluminant2) {
            this.id=id;
            this.fingerprint=fingerprint;
            this.canonicalDescriptor=canonicalDescriptor;
            this.exponent=exponent;
            this.calibrationStatus=calibrationStatus;
            this.calibrationEvidenceId=calibrationEvidenceId;
            this.basis=basis;
            this.activeWidth=activeWidth;
            this.activeHeight=activeHeight;
            this.cfa=cfa;
            this.sensorWidthMm=sensorWidthMm;
            this.physicalFocalMm=physicalFocalMm;
            this.aperture=aperture;
            this.whiteLevel=whiteLevel;
            this.referenceIlluminant1=referenceIlluminant1;
            this.referenceIlluminant2=referenceIlluminant2;
        }
    }

    private M10RMfm1DSourceProxy() {}

    public static Profile resolve(CameraCharacteristics characteristics,
                                  double physicalFocalMm,
                                  double aperture) {
        Rect active = characteristics != null
                ? characteristics.get(CameraCharacteristics.SENSOR_INFO_ACTIVE_ARRAY_SIZE) : null;
        Integer cfaObj = characteristics != null
                ? characteristics.get(CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT) : null;
        SizeF sensor = characteristics != null
                ? characteristics.get(CameraCharacteristics.SENSOR_INFO_PHYSICAL_SIZE) : null;
        Integer whiteObj = characteristics != null
                ? characteristics.get(CameraCharacteristics.SENSOR_INFO_WHITE_LEVEL) : null;
        Integer illum1Obj = characteristics != null
                ? characteristics.get(CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT1) : null;
        Byte illum2Obj = characteristics != null
                ? characteristics.get(CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT2) : null;

        int activeWidth = active != null ? active.width() : -1;
        int activeHeight = active != null ? active.height() : -1;
        int cfa = cfaObj != null ? cfaObj : -1;
        double sensorWidthMm = sensor != null ? sensor.getWidth() : Double.NaN;
        int whiteLevel = whiteObj != null ? whiteObj : -1;
        int illum1 = illum1Obj != null ? illum1Obj : -1;
        int illum2 = illum2Obj != null ? (illum2Obj & 0xff) : -1;

        long swum = finite(sensorWidthMm) ? Math.round(sensorWidthMm * 1000.0) : -1L;
        long fumm = finite(physicalFocalMm) ? Math.round(physicalFocalMm * 1000.0) : -1L;
        long apm = finite(aperture) ? Math.round(aperture * 1000.0) : -1L;

        String canonical = String.format(Locale.US,
                "aw=%d;ah=%d;cfa=%d;swum=%d;fumm=%d;apm=%d;wl=%d;i1=%d;i2=%d",
                activeWidth, activeHeight, cfa, swum, fumm, apm,
                whiteLevel, illum1, illum2);
        String fingerprint = sha256Prefix16(canonical);

        if (CAL_FP_A.equals(fingerprint)) {
            return profile(fingerprint, canonical, 1.90,
                    "paired_live_raw_validated",
                    "PAIR_A_20260926",
                    "generic_physical_camera_fingerprint_calibration",
                    activeWidth,activeHeight,cfa,sensorWidthMm,physicalFocalMm,aperture,
                    whiteLevel,illum1,illum2);
        }
        if (CAL_FP_B.equals(fingerprint)) {
            return profile(fingerprint, canonical, 1.00,
                    "single_pair_provisional",
                    "PAIR_B_20260926",
                    "generic_physical_camera_fingerprint_calibration",
                    activeWidth,activeHeight,cfa,sensorWidthMm,physicalFocalMm,aperture,
                    whiteLevel,illum1,illum2);
        }

        return profile(fingerprint, canonical, FALLBACK_EXPONENT,
                "uncalibrated_identity_fallback",
                "NONE",
                "identity_until_paired_live_raw_calibration_exists",
                activeWidth,activeHeight,cfa,sensorWidthMm,physicalFocalMm,aperture,
                whiteLevel,illum1,illum2);
    }

    private static Profile profile(String fingerprint, String canonical,
                                   double exponent, String status, String evidenceId,
                                   String basis, int activeWidth, int activeHeight, int cfa,
                                   double sensorWidthMm, double physicalFocalMm, double aperture,
                                   int whiteLevel, int illum1, int illum2) {
        return new Profile("FP_" + fingerprint, fingerprint, canonical,
                exponent, status, evidenceId, basis,
                activeWidth, activeHeight, cfa, sensorWidthMm, physicalFocalMm, aperture,
                whiteLevel, illum1, illum2);
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

    private static String sha256Prefix16(String s) {
        try {
            MessageDigest md=MessageDigest.getInstance("SHA-256");
            byte[] h=md.digest(s.getBytes(StandardCharsets.UTF_8));
            StringBuilder b=new StringBuilder(32);
            for (int i=0;i<8;i++) b.append(String.format(Locale.US,"%02x",h[i] & 0xff));
            return b.toString();
        } catch (Throwable ignored) {
            return "hash_unavailable";
        }
    }

    private static boolean finite(double v) {
        return !Double.isNaN(v) && !Double.isInfinite(v);
    }
}
