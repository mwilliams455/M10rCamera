package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.CaptureResult;
import android.hardware.camera2.params.BlackLevelPattern;
import android.graphics.Rect;
import com.particlesdevs.photoncamera.processing.ImageFrame;
import org.json.JSONArray;
import org.json.JSONObject;

/** Actual photographic RAW evidence. No request, exposure, or pixel is modified. */
public final class M10RRawResponse2S {
    public static final String REVISION="M10R_MFMRESPONSE2S_PHOTOGRAPHIC_RAW";
    private M10RRawResponse2S() {}
    private static Object optional(Object value) { return value==null?JSONObject.NULL:value; }
    private static Object rect(Rect r) throws org.json.JSONException {
        return r==null?JSONObject.NULL:new JSONArray(new int[]{r.left,r.top,r.right,r.bottom});
    }
    public static void append(JSONObject parent,ImageFrame frame,CameraCharacteristics c,
            CaptureResult r,CaptureRequest request) {
        long start=System.nanoTime();
        try {
            JSONObject j=new JSONObject().put("revision",REVISION).put("diagnosticOnly",true)
                    .put("controlsExposure",false).put("calibrated",false)
                    .put("source","photographic_RAW_before_normalization_LSC_WB")
                    .put("additionalRawFrames",0).put("leicaScaleAssigned",false);
            parent.put("photographicRawResponse2S",j);
            try {
                if(frame==null||c==null||r==null)throw new IllegalArgumentException("missing_frame_metadata");
                frame.requireM10rRaw16();
                if(frame.cropOriginX!=0||frame.cropOriginY!=0
                        ||(frame.fullWidth!=0&&frame.fullWidth!=frame.width)
                        ||(frame.fullHeight!=0&&frame.fullHeight!=frame.height)
                        ||frame.buffer.capacity()!=2L*frame.width*frame.height)
                    throw new IllegalArgumentException("full_tight_RAW16_required");
                Long ts=r.get(CaptureResult.SENSOR_TIMESTAMP),exposure=r.get(CaptureResult.SENSOR_EXPOSURE_TIME);
                Integer iso=r.get(CaptureResult.SENSOR_SENSITIVITY);
                j.put("imageTimestampNs",frame.timestamp).put("resultTimestampNs",optional(ts))
                        .put("frameNumber",r.getFrameNumber());
                if(ts==null||ts<=0||ts!=frame.timestamp||exposure==null||exposure<=0||iso==null||iso<=0)
                    throw new IllegalArgumentException("photographic_frame_binding");
                Integer cfa=c.get(CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT);
                if(cfa==null||cfa<0||cfa>3)throw new IllegalArgumentException("physical_CFA_missing");
                float[] dyn=r.get(CaptureResult.SENSOR_DYNAMIC_BLACK_LEVEL);
                double[] black=new double[4];
                if(dyn!=null&&dyn.length>=4) {
                    for(int i=0;i<4;i++)black[i]=dyn[i];j.put("blackSource","capture_result");
                } else {
                    BlackLevelPattern pattern=c.get(CameraCharacteristics.SENSOR_BLACK_LEVEL_PATTERN);
                    if(pattern==null)throw new IllegalArgumentException("black_metadata_missing");
                    int[] values=new int[4];pattern.copyTo(values,0);
                    for(int i=0;i<4;i++)black[i]=values[i];j.put("blackSource","characteristics");
                }
                Integer white=r.get(CaptureResult.SENSOR_DYNAMIC_WHITE_LEVEL);
                boolean dynamicWhite=white!=null&&white>0;
                if(!dynamicWhite)white=c.get(CameraCharacteristics.SENSOR_INFO_WHITE_LEVEL);
                if(white==null||white<=0)throw new IllegalArgumentException("white_metadata_missing");
                Float focal=r.get(CaptureResult.LENS_FOCAL_LENGTH),aperture=r.get(CaptureResult.LENS_APERTURE);
                var identity=M10RMfm1DSourceProxy.resolve(c,focal==null?Double.NaN:focal,
                        aperture==null?Double.NaN:aperture);
                j.put("physicalFingerprint",identity.fingerprint)
                        .put("physicalDescriptor",identity.canonicalDescriptor)
                        .put("identityDoesNotEstablishCalibration",true)
                        .put("phoneModel",android.os.Build.MANUFACTURER+" "+android.os.Build.MODEL)
                        .put("whiteSource",dynamicWhite?"capture_result":"characteristics")
                        .put("exposureNs",exposure).put("iso",iso)
                        .put("phoneFocalLengthMm",optional(focal)).put("phoneAperture",optional(aperture))
                        .put("phoneFocusDistance",optional(r.get(CaptureResult.LENS_FOCUS_DISTANCE)))
                        .put("aeMode",optional(r.get(CaptureResult.CONTROL_AE_MODE)))
                        .put("cropRegion",rect(r.get(CaptureResult.SCALER_CROP_REGION)))
                        .put("sensorOrientation",optional(c.get(CameraCharacteristics.SENSOR_ORIENTATION)))
                        .put("postRawSensitivityBoost",optional(r.get(CaptureResult.CONTROL_POST_RAW_SENSITIVITY_BOOST)))
                        .put("requestedExposureNs",optional(request==null?null:request.get(CaptureRequest.SENSOR_EXPOSURE_TIME)))
                        .put("requestedIso",optional(request==null?null:request.get(CaptureRequest.SENSOR_SENSITIVITY)))
                        .put("requestedAeMode",optional(request==null?null:request.get(CaptureRequest.CONTROL_AE_MODE)))
                        .put("samplingRegion","full_buffer_16_pixel_border_excluded_unrotated_sensor_axes")
                        .put("rawOriginEvidence","full_ImageFrame_origin_zero_no_independent_sensor_crop_proof");
                var sample=M10RFirmwareRaw2R.sample(frame.buffer,0,frame.width*2,frame.width,frame.height,
                        cfa,black,white,new M10RMetering1U.Config(M10RMetering1U.Mode.MULTI_FIELD));
                M10RFirmwareShadow2R.appendSample(j,sample);
                j.put("status","PHOTOGRAPHIC_RAW_MEASURED").put("frameTimestampMatched",true);
            } catch(RuntimeException|LinkageError|OutOfMemoryError failure) {
                j.put("status","DIAGNOSTIC_UNAVAILABLE").put("errorType",failure.getClass().getSimpleName())
                        .put("reason",optional(failure.getMessage()));
            }
            j.put("measurementAndObjectBuildNs",System.nanoTime()-start)
                    .put("timingExcludesFinalSidecarSerialization",true);
        } catch(Exception|LinkageError|OutOfMemoryError ignored) {
            // A diagnostic failure cannot cancel the photograph.
        }
    }
}
