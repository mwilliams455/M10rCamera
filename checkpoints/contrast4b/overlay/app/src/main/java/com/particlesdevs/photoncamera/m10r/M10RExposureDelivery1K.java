package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.CaptureResult;
import android.util.Range;
import org.json.JSONObject;

/** Capture-local evidence only. Never changes a frame, request, or future camera state. */
public final class M10RExposureDelivery1K {
    private M10RExposureDelivery1K() {}
    private static Object value(Object v){return v==null?JSONObject.NULL:v;}

    public static JSONObject snapshot(CaptureResult r)throws org.json.JSONException {
        JSONObject d=new JSONObject();
        if(r==null)return d.put("available",false);
        return d.put("available",true)
                .put("sensorTimestampNs",value(r.get(CaptureResult.SENSOR_TIMESTAMP)))
                .put("exposureTimeNs",value(r.get(CaptureResult.SENSOR_EXPOSURE_TIME)))
                .put("iso",value(r.get(CaptureResult.SENSOR_SENSITIVITY)))
                .put("postRawSensitivityBoost",value(r.get(CaptureResult.CONTROL_POST_RAW_SENSITIVITY_BOOST)))
                .put("aeMode",value(r.get(CaptureResult.CONTROL_AE_MODE)))
                .put("aeState",value(r.get(CaptureResult.CONTROL_AE_STATE)))
                .put("aeCompensationSteps",value(r.get(CaptureResult.CONTROL_AE_EXPOSURE_COMPENSATION)));
    }

    public static void append(JSONObject root,CameraCharacteristics c,CaptureResult r,CaptureRequest q)
            throws org.json.JSONException {
        JSONObject d=snapshot(r).put("revision",M10RExposureCapture1B.RAW_GAIN_REVISION)
                .put("diagnosticOnly",true).put("rawBrightnessCorrectionApplied",false)
                .put("postRawBoostIncludedInRawExposure",false);
        Range<Integer> isos=c.get(CameraCharacteristics.SENSOR_INFO_SENSITIVITY_RANGE);
        Range<Long> times=c.get(CameraCharacteristics.SENSOR_INFO_EXPOSURE_TIME_RANGE);
        d.put("physicalMinIso",isos==null?JSONObject.NULL:isos.getLower());
        d.put("physicalMaxIso",isos==null?JSONObject.NULL:isos.getUpper());
        d.put("physicalMaxAnalogIso",value(c.get(CameraCharacteristics.SENSOR_MAX_ANALOG_SENSITIVITY)));
        d.put("physicalMinExposureNs",times==null?JSONObject.NULL:times.getLower());
        d.put("physicalMaxExposureNs",times==null?JSONObject.NULL:times.getUpper());
        Long requestedNs=q==null?null:q.get(CaptureRequest.SENSOR_EXPOSURE_TIME);
        Integer requestedIso=q==null?null:q.get(CaptureRequest.SENSOR_SENSITIVITY);
        Integer ae=q==null?null:q.get(CaptureRequest.CONTROL_AE_MODE);
        d.put("requestedExposureNs",value(requestedNs)).put("requestedIso",value(requestedIso));
        d.put("requestedAeMode",value(ae));
        d.put("requestedPostRawSensitivityBoost",value(q==null?null:q.get(CaptureRequest.CONTROL_POST_RAW_SENSITIVITY_BOOST)));
        Long actualNs=r==null?null:r.get(CaptureResult.SENSOR_EXPOSURE_TIME);
        Integer actualIso=r==null?null:r.get(CaptureResult.SENSOR_SENSITIVITY);
        boolean valid=ae!=null&&ae==CaptureRequest.CONTROL_AE_MODE_OFF
                &&requestedNs!=null&&requestedNs>0&&requestedIso!=null&&requestedIso>0
                &&actualNs!=null&&actualNs>0&&actualIso!=null&&actualIso>0;
        d.put("manualRequestComparable",valid);
        if(valid){
            double delta=Math.log(((double)actualNs*actualIso)/((double)requestedNs*requestedIso))/Math.log(2);
            d.put("deliveredMinusRequestedEv",delta);
            d.put("deliveryShortfallOverOneSixthStop",delta < -1.0/6);
        }
        root.put("m10rExposureDelivery1K",d);
    }
}
