package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.CaptureResult;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.params.RggbChannelVector;
import android.util.Rational;

/**
 * Immutable input to source-colour preparation. Auto preserves the exact
 * Camera2 neutral values. Explicit manual requests own their sensor white via
 * the same inverse-gains convention used by Photon's Parameters.
 */
public final class M10RSourceWhite3N {
    static final String REVISION = "M10R_SOURCEWHITE3N_EXACT_VENDOR_SNAPSHOT";
    static final String MANUAL_REVISION = "M10R_SOURCEWHITE3O_FROZEN_REQUEST_GAINS";
    static final String SOURCE_AUTHORITY = "capture_result_SENSOR_NEUTRAL_COLOR_POINT";
    static final String MANUAL_SOURCE_AUTHORITY = "capture_request_COLOR_CORRECTION_GAINS";

    enum Authority { VENDOR_CAPTURE_RESULT, MANUAL_CAPTURE_REQUEST_GAINS }

    private final float[] sourceNeutral;
    private final Long sensorTimestampNs;
    private final long frameNumber;
    private final float[] requestedGains;

    private M10RSourceWhite3N(float[] sourceNeutral, Long sensorTimestampNs, long frameNumber) {
        this(sourceNeutral, sensorTimestampNs, frameNumber, null);
    }

    private M10RSourceWhite3N(float[] sourceNeutral, Long sensorTimestampNs, long frameNumber,
            float[] requestedGains) {
        this.sourceNeutral = sourceNeutral.clone();
        this.sensorTimestampNs = sensorTimestampNs;
        this.frameNumber = frameNumber;
        this.requestedGains = requestedGains == null ? null : requestedGains.clone();
    }

    /** Missing neutral retains the existing source-calibration admission path. */
    static M10RSourceWhite3N fromCaptureResult(CaptureResult result) {
        Rational[] neutral = result.get(CaptureResult.SENSOR_NEUTRAL_COLOR_POINT);
        if (neutral == null || neutral.length < 3) return null;
        // SOURCEWHITE3N: retain the original rationalVector float conversion.
        // Additional normalization or double-first conversion would change the
        // compatibility contract even though it described the same chromaticity.
        float[] imported = {
                neutral[0].floatValue(), neutral[1].floatValue(), neutral[2].floatValue()
        };
        return new M10RSourceWhite3N(imported,
                result.get(CaptureResult.SENSOR_TIMESTAMP), result.getFrameNumber());
    }

    /** The request is the immutable request for this frame, never a live builder. */
    static M10RSourceWhite3N select(CaptureResult result, CaptureRequest request) {
        float[] gains = manualGains(request);
        if (gains == null) return fromCaptureResult(result);
        return new M10RSourceWhite3N(neutralFromGains(gains),
                result.get(CaptureResult.SENSOR_TIMESTAMP), result.getFrameNumber(), gains);
    }

    /**
     * Shared PHOTO/MOTION renderer and DNG contract. Auto returns null so callers
     * retain their existing vendor path. Invalid explicit manual controls are
     * rejected instead of silently importing an unrelated vendor estimate.
     * The result is a fresh array and is not a calibrated-Kelvin assertion.
     */
    public static float[] manualNeutral(CaptureRequest request) {
        float[] gains = manualGains(request);
        return gains == null ? null : neutralFromGains(gains);
    }

    private static float[] manualGains(CaptureRequest request) {
        if (request == null) return null;
        Integer mode = request.get(CaptureRequest.CONTROL_AWB_MODE);
        if (mode == null || mode != CaptureRequest.CONTROL_AWB_MODE_OFF) return null;
        RggbChannelVector vector = request.get(CaptureRequest.COLOR_CORRECTION_GAINS);
        if (vector == null) throw new IllegalArgumentException("manual_WB_request_gains_missing");
        float[] gains = { vector.getRed(), vector.getGreenEven(), vector.getGreenOdd(), vector.getBlue() };
        for (float gain : gains) {
            if (!Float.isFinite(gain) || gain <= 0.0f)
                throw new IllegalArgumentException("manual_WB_request_gains_invalid");
        }
        return gains;
    }

    private static float[] neutralFromGains(float[] gains) {
        // Match Photon's float arithmetic, including its average of the greens.
        float green = (gains[1] + gains[2]) / 2.0f;
        float[] neutral = { green / gains[0], 1.0f, green / gains[3] };
        for (float value : neutral) {
            if (!Float.isFinite(value) || value <= 0.0f)
                throw new IllegalArgumentException("manual_WB_request_neutral_invalid");
        }
        return neutral;
    }

    /** Auto keeps the prior cache identity; manual identity contains exact input/output bits. */
    static String requestKey(CaptureRequest request) {
        try {
            float[] gains = manualGains(request);
            if (gains == null) return Authority.VENDOR_CAPTURE_RESULT.name();
            float[] neutral = neutralFromGains(gains);
            StringBuilder key = new StringBuilder(Authority.MANUAL_CAPTURE_REQUEST_GAINS.name());
            for (float gain : gains) key.append(':').append(Integer.toHexString(Float.floatToRawIntBits(gain)));
            for (float value : neutral) key.append(':').append(Integer.toHexString(Float.floatToRawIntBits(value)));
            return key.toString();
        } catch (IllegalArgumentException invalid) {
            // Failed metadata may be displayed as a rejection, never as an old manual LUT.
            return Authority.MANUAL_CAPTURE_REQUEST_GAINS.name() + ":rejected:" + invalid.getMessage();
        }
    }

    /**
     * AMaZE balances and then unbalances its temporary input using these same
     * values. Its supported conditioning range does not clamp the renderer white.
     * Auto deliberately uses its original Rational.doubleValue()/green path.
     */
    double[] copyManualAmazeNeutral() {
        if (!isManual()) throw new IllegalStateException("manual_WB_conditioning_requires_manual_selection");
        return new double[] {
                Math.max(1.0 / 16.0, Math.min(16.0, (double) sourceNeutral[0] / sourceNeutral[1])),
                Math.max(1.0 / 16.0, Math.min(16.0, (double) sourceNeutral[2] / sourceNeutral[1]))
        };
    }

    boolean isManual() { return requestedGains != null; }
    Authority authority() { return isManual() ? Authority.MANUAL_CAPTURE_REQUEST_GAINS : Authority.VENDOR_CAPTURE_RESULT; }
    String revision() { return isManual() ? MANUAL_REVISION : REVISION; }
    String sourceAuthority() { return isManual() ? MANUAL_SOURCE_AUTHORITY : SOURCE_AUTHORITY; }
    float[] copyRequestedGains() { return requestedGains == null ? null : requestedGains.clone(); }
    float[] copySourceNeutral() { return sourceNeutral.clone(); }
    Long sensorTimestampNs() { return sensorTimestampNs; }
    long frameNumber() { return frameNumber; }
}
