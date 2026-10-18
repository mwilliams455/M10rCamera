package com.particlesdevs.photoncamera.m10r;

import android.graphics.Rect;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.params.BlackLevelPattern;
import android.hardware.camera2.params.ColorSpaceTransform;
import android.util.Rational;
import android.util.Size;
import android.util.SizeF;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Locale;
import java.util.TreeSet;

/**
 * SOURCEPROXY1C: a metadata signature, NOT a hardware serial or an inferred ISP curve.
 * Current focal/aperture values are telemetry only. No capture result, scene white
 * balance, ISO, focus distance or crop/zoom state is used to identify the source.
 * Static matrix values are serialized as exact reduced rationals, row-major.
 * Unknown signatures remain uncalibrated; identity is a fallback, not a proof of
 * preview/RAW parity. No online learning or automatic calibration is performed.
 */
public final class M10RMfm1DSourceProxy {
    public static final double FALLBACK_EXPONENT = 1.00;
    public static final String IDENTITY_VERSION = "SOURCEPROXY1C_STATIC_V1";
    private static final String LEGACY_FP_A = "03d973b6411b4879";
    private static final String LEGACY_FP_B = "f76d00db34b9480f";

    public static final class Profile {
        public final String id, fingerprint, canonicalDescriptor;
        public final double exponent;
        public final String calibrationStatus, calibrationEvidenceId, basis;
        public final int activeWidth, activeHeight, cfa;
        public final double sensorWidthMm, physicalFocalMm, aperture;
        public final int whiteLevel, referenceIlluminant1, referenceIlluminant2;
        Profile(String fingerprint, String canonical, double exponent, String status,
                String evidence, String basis, int aw, int ah, int cfa, double sw,
                double focal, double aperture, int white, int i1, int i2) {
            this.id = "FP1C_" + fingerprint.substring(0, 16);
            this.fingerprint = fingerprint;
            this.canonicalDescriptor = canonical;
            this.exponent = exponent;
            this.calibrationStatus = status;
            this.calibrationEvidenceId = evidence;
            this.basis = basis;
            this.activeWidth = aw; this.activeHeight = ah; this.cfa = cfa;
            this.sensorWidthMm = sw;
            this.physicalFocalMm = focal; this.aperture = aperture;
            this.whiteLevel = white;
            this.referenceIlluminant1 = i1; this.referenceIlluminant2 = i2;
        }
    }

    private M10RMfm1DSourceProxy() {}

    /** The last two arguments are copied only into diagnostic telemetry. */
    public static Profile resolve(CameraCharacteristics c,
                                  double currentFocalMm, double currentAperture) {
        Rect active = get(c, CameraCharacteristics.SENSOR_INFO_ACTIVE_ARRAY_SIZE);
        SizeF sensor = get(c, CameraCharacteristics.SENSOR_INFO_PHYSICAL_SIZE);
        int aw = active != null ? active.width() : -1;
        int ah = active != null ? active.height() : -1;
        int cfa = number(get(c, CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT));
        int white = number(get(c, CameraCharacteristics.SENSOR_INFO_WHITE_LEVEL));
        int i1 = number(get(c, CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT1));
        Byte i2b = get(c, CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT2);
        int i2 = i2b != null ? i2b & 0xff : -1;
        double sw = sensor != null ? sensor.getWidth() : Double.NaN;
        double sh = sensor != null ? sensor.getHeight() : Double.NaN;
        String focals = opticalSet(get(c, CameraCharacteristics.LENS_INFO_AVAILABLE_FOCAL_LENGTHS));
        String apertures = opticalSet(get(c, CameraCharacteristics.LENS_INFO_AVAILABLE_APERTURES));
        String matrices = "cm1=" + matrix(get(c, CameraCharacteristics.SENSOR_COLOR_TRANSFORM1))
                + ";cm2=" + matrix(get(c, CameraCharacteristics.SENSOR_COLOR_TRANSFORM2))
                + ";fm1=" + matrix(get(c, CameraCharacteristics.SENSOR_FORWARD_MATRIX1))
                + ";fm2=" + matrix(get(c, CameraCharacteristics.SENSOR_FORWARD_MATRIX2))
                + ";cc1=" + matrix(get(c, CameraCharacteristics.SENSOR_CALIBRATION_TRANSFORM1))
                + ";cc2=" + matrix(get(c, CameraCharacteristics.SENSOR_CALIBRATION_TRANSFORM2));
        String canonical = IDENTITY_VERSION
                + ";active=" + rect(active)
                + ";precorr=" + rect(get(c, CameraCharacteristics.SENSOR_INFO_PRE_CORRECTION_ACTIVE_ARRAY_SIZE))
                + ";pixel=" + size(get(c, CameraCharacteristics.SENSOR_INFO_PIXEL_ARRAY_SIZE))
                + ";cfa=" + cfa + ";swum=" + quantize(sw) + ";shum=" + quantize(sh)
                + ";wl=" + white + ";black=" + black(get(c, CameraCharacteristics.SENSOR_BLACK_LEVEL_PATTERN))
                + ";i1=" + i1 + ";i2=" + i2
                + ";focals_um=" + focals + ";apertures_milli=" + apertures
                + ";matrices_sha256=" + sha256(matrices)
                + ";matrix_presence=" + presence(c);
        String fingerprint = sha256(canonical);

        // Compatibility with the two previously shipped, empirical seeds. Only
        // a fixed focal and a fixed aperture may use this bridge. It NEVER picks
        // one member of a variable-optics array using the current capture state.
        // These old seeds lack the full static matrices: explicitly provisional,
        // and not represented as a new full-signature or cross-device calibration.
        String legacy = "";
        Long fixedFocal = singleton(focals), fixedAperture = singleton(apertures);
        if (active != null && active.left == 0 && active.top == 0 && aw > 0 && ah > 0
                && quantize(sw) > 0 && quantize(sh) > 0 && cfa >= 0 && cfa <= 3
                && white > 0 && i1 >= 0 && i2 >= 0
                && fixedFocal != null && fixedAperture != null) {
            String old = String.format(Locale.US,
                    "aw=%d;ah=%d;cfa=%d;swum=%d;fumm=%d;apm=%d;wl=%d;i1=%d;i2=%d",
                    aw, ah, cfa, quantize(sw), fixedFocal, fixedAperture, white, i1, i2);
            legacy = sha256(old).substring(0, 16);
        }
        double exponent = FALLBACK_EXPONENT;
        String status = "uncalibrated_identity_fallback", evidence = "NONE";
        String basis = "no_full_signature_calibration;identity_not_parity_claim";
        if (LEGACY_FP_A.equals(legacy) || LEGACY_FP_B.equals(legacy)) {
            boolean a = LEGACY_FP_A.equals(legacy);
            exponent = a ? 1.90 : 1.00;
            status = "inherited_pair_seed_provisional";
            evidence = a ? "PAIR_A_20260926" : "PAIR_B_20260926";
            basis = "legacy_static_singleton_alias:" + legacy
                    + ";full_signature_validation_pending";
        }
        return new Profile(fingerprint, canonical, exponent, status, evidence, basis,
                aw, ah, cfa, sw, currentFocalMm, currentAperture, white, i1, i2);
    }

    // Identical arithmetic and input handling to SOURCEPROXY1B.
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

    private static <T> T get(CameraCharacteristics c, CameraCharacteristics.Key<T> key) {
        if (c == null) return null;
        try { return c.get(key); } catch (IllegalArgumentException | IllegalStateException e) { return null; }
    }
    private static int number(Integer v) { return v != null ? v : -1; }
    private static boolean finite(double v) { return !Double.isNaN(v) && !Double.isInfinite(v); }
    private static long quantize(double v) {
        return finite(v) && v > 0 && v < 1e6 ? Math.round(v * 1000.0) : -1L;
    }
    private static String opticalSet(float[] values) {
        if (values == null) return "missing";
        if (values.length == 0) return "empty";
        TreeSet<Long> normalized = new TreeSet<>();
        for (float v : values) {
            long q = quantize(v);
            if (q <= 0) return "invalid";
            normalized.add(q);
        }
        StringBuilder b = new StringBuilder();
        for (long v : normalized) { if (b.length() > 0) b.append(','); b.append(v); }
        return b.toString();
    }
    private static Long singleton(String s) {
        if (s.indexOf(',') >= 0) return null;
        try { long n = Long.parseLong(s); return n > 0 ? n : null; }
        catch (NumberFormatException e) { return null; }
    }
    private static String rect(Rect r) {
        return r == null ? "missing" : r.left + "," + r.top + "," + r.right + "," + r.bottom;
    }
    private static String size(Size s) {
        return s == null ? "missing" : s.getWidth() + "," + s.getHeight();
    }
    private static String black(BlackLevelPattern b) {
        if (b == null) return "missing";
        return b.getOffsetForIndex(0,0) + "," + b.getOffsetForIndex(1,0) + ","
                + b.getOffsetForIndex(0,1) + "," + b.getOffsetForIndex(1,1);
    }
    private static String matrix(ColorSpaceTransform m) {
        if (m == null) return "missing";
        StringBuilder b = new StringBuilder();
        for (int row = 0; row < 3; row++) for (int col = 0; col < 3; col++) {
            Rational r = m.getElement(col, row);
            long n = r.getNumerator(), d = r.getDenominator();
            if (d == 0) return "invalid";
            if (d < 0) { n = -n; d = -d; }
            long a = Math.abs(n), z = d;
            while (z != 0) { long t = a % z; a = z; z = t; }
            if (a != 0) { n /= a; d /= a; }
            if (b.length() > 0) b.append(',');
            b.append(n).append('/').append(d);
        }
        return b.toString();
    }
    private static String presence(CameraCharacteristics c) {
        return (get(c, CameraCharacteristics.SENSOR_COLOR_TRANSFORM1) != null ? "1" : "0")
                + (get(c, CameraCharacteristics.SENSOR_COLOR_TRANSFORM2) != null ? "1" : "0")
                + (get(c, CameraCharacteristics.SENSOR_FORWARD_MATRIX1) != null ? "1" : "0")
                + (get(c, CameraCharacteristics.SENSOR_FORWARD_MATRIX2) != null ? "1" : "0")
                + (get(c, CameraCharacteristics.SENSOR_CALIBRATION_TRANSFORM1) != null ? "1" : "0")
                + (get(c, CameraCharacteristics.SENSOR_CALIBRATION_TRANSFORM2) != null ? "1" : "0");
    }
    private static String sha256(String text) {
        try {
            byte[] hash = MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8));
            char[] hex = "0123456789abcdef".toCharArray();
            StringBuilder b = new StringBuilder(64);
            for (byte v : hash) { b.append(hex[(v & 255) >>> 4]); b.append(hex[v & 15]); }
            return b.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("Required SHA-256 provider unavailable", e);
        }
    }
}
