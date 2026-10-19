package com.particlesdevs.photoncamera.manual;

import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.params.ColorSpaceTransform;
import android.hardware.camera2.params.RggbChannelVector;
import android.os.Build;

import com.particlesdevs.photoncamera.processing.parameters.ColorTemperatureConverter;
import com.particlesdevs.photoncamera.util.Log;

/** One selected WB and one calibration reference, frozen before request tuning. */
public final class WhiteBalanceRequest3O {
    public final int kelvin;
    public final boolean measured;
    public final CameraCharacteristics characteristics;
    public final RggbChannelVector gains;
    public final ColorSpaceTransform transform;
    public final String controlKey;

    WhiteBalanceRequest3O(int kelvin, boolean measured, RggbChannelVector measuredGains,
            ColorSpaceTransform measuredTransform, String tint, CameraCharacteristics characteristics) {
        this.kelvin = kelvin;
        this.measured = kelvin != 0 && measured && measuredGains != null;
        this.characteristics = characteristics;
        controlKey = kelvin + ":" + measured + ":" + tint + ":" + measuredGains + ":" + measuredTransform;
        if (kelvin == 0) {
            gains = null;
            transform = null;
        } else {
            gains = this.measured ? measuredGains
                    : ColorTemperatureConverter.kelvinToRggb(kelvin, characteristics);
            transform = this.measured && measuredTransform != null ? measuredTransform
                    : ColorTemperatureConverter.createColorTransform(kelvin, characteristics);
        }
    }

    public boolean isManual() { return kelvin != 0; }

    /** Auto leaves the template/tunables exactly as before. Explicit WB wins last. */
    public void apply(CaptureRequest.Builder builder, String physicalId) {
        if (!isManual()) return;
        set(builder, CaptureRequest.CONTROL_AWB_MODE, CaptureRequest.CONTROL_AWB_MODE_OFF, physicalId);
        set(builder, CaptureRequest.COLOR_CORRECTION_MODE,
                CaptureRequest.COLOR_CORRECTION_MODE_TRANSFORM_MATRIX, physicalId);
        set(builder, CaptureRequest.COLOR_CORRECTION_GAINS, gains, physicalId);
        if (transform != null)
            set(builder, CaptureRequest.COLOR_CORRECTION_TRANSFORM, transform, physicalId);
    }

    /** An explicit Auto choice must also release a prior physical manual override. */
    static void applyAuto(CaptureRequest.Builder builder, String physicalId) {
        set(builder, CaptureRequest.CONTROL_AWB_MODE, CaptureRequest.CONTROL_AWB_MODE_AUTO, physicalId);
        set(builder, CaptureRequest.COLOR_CORRECTION_MODE, CaptureRequest.COLOR_CORRECTION_MODE_FAST, physicalId);
    }

    private static <T> void set(CaptureRequest.Builder builder, CaptureRequest.Key<T> key,
            T value, String physicalId) {
        builder.set(key, value);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P && physicalId != null && !physicalId.isEmpty()) {
            try {
                builder.setPhysicalCameraKey(key, value, physicalId);
            } catch (IllegalArgumentException | UnsupportedOperationException unsupported) {
                // Direct physical-camera requests and some logical-camera keys
                // do not support a separate per-member override. Logical WB is set.
                Log.d("WB_REQUEST_DEBUG", "Physical WB key unavailable: " + key.getName());
            }
        }
    }
}
