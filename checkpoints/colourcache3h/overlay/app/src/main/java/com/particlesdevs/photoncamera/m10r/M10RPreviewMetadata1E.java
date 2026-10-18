package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.CaptureResult;
import android.util.Rational;

/** Preview metadata admission, after the caller has verified the physical source. */
public final class M10RPreviewMetadata1E {
    private M10RPreviewMetadata1E() {}
    public static M10RPreviewState1A.Observation observe(Object owner,String key,String controls,
            CameraCharacteristics c,CaptureResult r,CaptureRequest request,long now,double userEv) {
        return observe(owner,key,controls,c,r,request,now,userEv,true);
    }
    public static M10RPreviewState1A.Observation observe(Object owner,String key,String controls,
            CameraCharacteristics c,CaptureResult r,CaptureRequest request,long now,double userEv,
            boolean requestMatchesCurrentControls) {
        Integer steps=r.get(CaptureResult.CONTROL_AE_EXPOSURE_COMPENSATION);
        boolean reported=steps!=null;
        if(!reported){
            // Missing control echoes are distinct from missing physical sensor
            // readings. The callback's explicit submitted EV may seed a fresh RAW
            // measurement when its controls still match; it cannot reuse a plan.
            Integer ae=request==null?null:request.get(CaptureRequest.CONTROL_AE_MODE);
            steps=request==null?null:request.get(CaptureRequest.CONTROL_AE_EXPOSURE_COMPENSATION);
            if(steps==null||ae==null||ae!=CaptureRequest.CONTROL_AE_MODE_ON)
                throw new IllegalArgumentException("preview_AE_echo_and_safe_request_unavailable");
        }
        double reference=0;
        if(steps!=0){
            Rational unit=c.get(CameraCharacteristics.CONTROL_AE_COMPENSATION_STEP);
            if(unit==null||!Double.isFinite(unit.doubleValue())||unit.doubleValue()<=0)
                throw new IllegalArgumentException("AE compensation unit unavailable");
            reference=steps*unit.doubleValue();
        }
        if(r.get(CaptureResult.SENSOR_TIMESTAMP)==null)
            throw new IllegalArgumentException("preview_sensor_timestamp_missing");
        if(r.get(CaptureResult.SENSOR_EXPOSURE_TIME)==null)
            throw new IllegalArgumentException("preview_sensor_exposure_missing");
        if(r.get(CaptureResult.SENSOR_SENSITIVITY)==null)
            throw new IllegalArgumentException("preview_sensor_ISO_missing");
        return new M10RPreviewState1A.Observation(owner,key,controls,c,r,now,userEv,reference,
                reported,!reported&&requestMatchesCurrentControls);
    }

    /** Ignore trigger pulses; compare the settings affecting exposure/colour/crop.
     * This prevents a late result from being labelled with newly changed controls. */
    public static boolean requestMatchesCurrentControls(CaptureRequest request,CaptureRequest.Builder current) {
        if(request==null||current==null)return false;
        if(!java.util.Arrays.equals(request.get(CaptureRequest.CONTROL_AE_REGIONS),
                current.get(CaptureRequest.CONTROL_AE_REGIONS)))return false;
        CaptureRequest.Key<?>[] keys={CaptureRequest.CONTROL_AE_MODE,
                CaptureRequest.CONTROL_AE_EXPOSURE_COMPENSATION,CaptureRequest.FLASH_MODE,
                CaptureRequest.SCALER_CROP_REGION,CaptureRequest.CONTROL_AWB_MODE,
                CaptureRequest.COLOR_CORRECTION_GAINS,CaptureRequest.COLOR_CORRECTION_TRANSFORM,
                CaptureRequest.LENS_FOCUS_DISTANCE};
        for(CaptureRequest.Key<?> key:keys)
            if(!java.util.Objects.equals(request.get(key),current.get(key)))return false;
        return android.os.Build.VERSION.SDK_INT<30||java.util.Objects.equals(
                request.get(CaptureRequest.CONTROL_ZOOM_RATIO),current.get(CaptureRequest.CONTROL_ZOOM_RATIO));
    }
}
