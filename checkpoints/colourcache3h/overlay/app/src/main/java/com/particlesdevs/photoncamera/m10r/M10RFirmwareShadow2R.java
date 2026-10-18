package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CaptureResult;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;
import java.nio.ByteBuffer;

/** Diagnostic sink only. Its immutable JSON is attached to the matching probe;
 * no result from this class is passed to an exposure request or preview plan. */
public final class M10RFirmwareShadow2R {
    public static final String REVISION="M10R_MFMSHADOW2R_UNCALIBRATED_PHONE_CODE_TRIAL";
    private M10RFirmwareShadow2R() {}
    private static final class Library {
        static final boolean verified;
        static { System.loadLibrary("m10rfirmwareshadow"); verified=nativeSelfTest(); }
    }
    static native boolean nativeSelfTest();
    static native int[] nativeEvaluate(long[] y,int sv,int tv);
    static int apexQ8(double value) {
        long q=Math.round(value*256);
        if(!Double.isFinite(value)||q< -32768||q>32767)throw new IllegalArgumentException("shadow APEX range");
        return (int)q;
    }
    public static String capture(ByteBuffer bytes,int w,int h,int cfa,double[] black,int white,
            CameraCharacteristics characteristics,CaptureResult result,M10RExposureProbe1B.Binding binding) {
        long start=System.nanoTime();JSONObject j=new JSONObject();
        try {
            j.put("revision",REVISION).put("controlsExposure",false)
                    .put("calibrated",false).put("recommendedExposureAvailable",false)
                    .put("cameraKey",binding.cameraKey).put("session",binding.session)
                    .put("generation",binding.generation).put("imageTimestampNs",binding.imageTimestampNs)
                    .put("meterBinding",binding.metering==null?JSONObject.NULL:binding.metering.key());
            Long ts=result.get(CaptureResult.SENSOR_TIMESTAMP),exposure=result.get(CaptureResult.SENSOR_EXPOSURE_TIME);
            Integer iso=result.get(CaptureResult.SENSOR_SENSITIVITY);
            if(binding.metering==null||ts==null||ts!=binding.imageTimestampNs||exposure==null
                    ||exposure!=binding.referenceExposureNs||iso==null||iso!=binding.referenceIso)
                throw new IllegalArgumentException("shadow frame binding");
            j.put("exposureNs",exposure).put("iso",iso).put("frameNumber",result.getFrameNumber())
                    .put("phoneAperture",optional(result.get(CaptureResult.LENS_APERTURE)))
                    .put("phoneFocalLengthMm",optional(result.get(CaptureResult.LENS_FOCAL_LENGTH)))
                    .put("phoneFocusDistance",optional(result.get(CaptureResult.LENS_FOCUS_DISTANCE)))
                    .put("focusDistanceCalibration",optional(characteristics.get(CameraCharacteristics.LENS_INFO_FOCUS_DISTANCE_CALIBRATION)))
                    .put("sensorOrientation",optional(characteristics.get(CameraCharacteristics.SENSOR_ORIENTATION)))
                    .put("lensFacing",optional(characteristics.get(CameraCharacteristics.LENS_FACING)))
                    .put("postRawSensitivityBoost",optional(result.get(CaptureResult.CONTROL_POST_RAW_SENSITIVITY_BOOST)))
                    .put("dynamicBlackPresent",result.get(CaptureResult.SENSOR_DYNAMIC_BLACK_LEVEL)!=null)
                    .put("dynamicWhitePresent",result.get(CaptureResult.SENSOR_DYNAMIC_WHITE_LEVEL)!=null)
                    .put("phoneModel",android.os.Build.MANUFACTURER+" "+android.os.Build.MODEL)
                    .put("androidSdk",android.os.Build.VERSION.SDK_INT);
            float[] dynamicBlack=result.get(CaptureResult.SENSOR_DYNAMIC_BLACK_LEVEL);
            boolean hasDynamicBlack=dynamicBlack!=null&&dynamicBlack.length>=4;
            boolean hasStaticBlack=characteristics.get(CameraCharacteristics.SENSOR_BLACK_LEVEL_PATTERN)!=null;
            j.put("blackSource",hasDynamicBlack?"capture_result":hasStaticBlack?"characteristics":"missing");
            // The old renderer has a legacy fallback; never treat that fallback as measured evidence.
            if(!hasDynamicBlack&&!hasStaticBlack)throw new IllegalArgumentException("shadow black metadata missing");
            var s=M10RFirmwareRaw2R.sample(bytes,0,w*2,w,h,cfa,black,white,binding.metering);
            appendSample(j,s);
            // Conventional APEX candidates, explicitly not a verified IMG metadata mapping.
            int sv=apexQ8(Math.log(iso/3.125)/Math.log(2)),tv=apexQ8(Math.log(1e9/exposure)/Math.log(2));
            j.put("svQ8Candidate",sv).put("tvQ8Candidate",tv).put("avQ8",0).put("fpos",0)
                    .put("metadataMappingValidated",false)
                    .put("metadataPolicy","SV=round(256*log2(ISO/3.125));TV=round(256*log2(1e9/exposureNs));AV=0;Fpos=unknown")
                    .put("yScalePolicy","native_phone_black_subtracted_code_means_no_Leica_scale_assigned")
                    .put("syntheticStepA",2).put("syntheticStepB",2)
                    .put("stepsPolicy","normalizer_1_for_mean_code_trial_not_hardware_windows")
                    .put("tiltPolicy","all_four_hypotheses_no_phone_orientation_mapping")
                    .put("highlightPolicy","retain_clipping_counts_no_reconstruction")
                    .put("nativeSelfTestPassed",Library.verified);
            if(!Library.verified)throw new IllegalStateException("original-firmware fixture failed");
            long nativeStart=System.nanoTime();int[] packed=nativeEvaluate(s.meanYCodes(),sv,tv);
            j.put("nativeDurationNs",System.nanoTime()-nativeStart);
            j.put("trials",trials(packed)).put("status","UNCALIBRATED_TRIAL_COMPLETE");
        } catch(JSONException|RuntimeException|LinkageError|OutOfMemoryError e) {
            try {j.put("status","DIAGNOSTIC_UNAVAILABLE").put("errorType",e.getClass().getSimpleName());}
            catch(JSONException|RuntimeException|OutOfMemoryError ignored) {return null;}
        }
        try {j.put("totalDurationNs",System.nanoTime()-start);return j.toString();}
        catch(JSONException|RuntimeException|OutOfMemoryError ignored) {return null;}
    }
    private static Object optional(Object x){return x==null?JSONObject.NULL:x;}
    static void appendSample(JSONObject j,M10RFirmwareRaw2R.Sample s)throws JSONException {
        j.put("rawWidth",s.width).put("rawHeight",s.height).put("cfa",s.cfa)
                .put("blackByCfaPhase",new JSONArray(s.black())).put("white",s.white)
                .put("channelOrder","R,Gr,Gb,B").put("gridRows",16).put("gridColumns",22)
                .put("sparseWidth",176).put("sparseHeight",128).put("excludedBorder",16)
                .put("sampleCounts",new JSONArray(s.counts()))
                .put("codeSumsCellMajor",new JSONArray(s.codeSums()))
                .put("blackSubtractedSumsCellMajor",new JSONArray(s.correctedSums()))
                .put("atWhiteCellMajor",new JSONArray(s.atWhite()))
                .put("aboveWhiteCellMajor",new JSONArray(s.aboveWhite()))
                .put("nearWhite98PercentCellMajor",new JSONArray(s.nearWhite()))
                .put("phoneWeightedYSums",new JSONArray(s.ySums()))
                .put("trialYCells",new JSONArray(s.meanYCodes()))
                .put("phoneYFormula","sum(floor((83*R+45*Gr+45*Gb+83*B+128)/256));floor(sum/count)")
                .put("phoneYFormulaStatus","Leica_still_weights_applied_as_unvalidated_phone_hypothesis")
                .put("beforeLscAndWb",true).put("upperClampApplied",false);
    }
    static JSONArray trials(int[] packed)throws JSONException {
        if(packed==null||packed.length!=916)throw new IllegalArgumentException("shadow JNI shape");
        JSONArray out=new JSONArray();
        for(int t=0;t<4;t++) {
            int b=t*229;JSONObject j=new JSONObject().put("tilt",t).put("returnCode",packed[b]);
            if(packed[b]!=0)throw new IllegalStateException("shadow native failure");
            j.put("integral",evaluator(packed,b+1));JSONArray regions=new JSONArray();
            for(int r=0;r<24;r++)regions.put(evaluator(packed,b+6+r*5));
            j.put("regions",regions).put("mfmStatus",packed[b+126]).put("mfmBvQ8",packed[b+127])
                    .put("mfmEvQ8",packed[b+128]);
            char[] hex=new char[800];final char[] digits="0123456789abcdef".toCharArray();
            for(int i=0;i<400;i++) {int v=(packed[b+129+i/4]>>>(8*(i%4)))&255;
                hex[2*i]=digits[v>>>4];hex[2*i+1]=digits[v&15];}
            j.put("aggregateWorkHex",new String(hex));out.put(j);
        }
        return out;
    }
    private static JSONObject evaluator(int[] p,int i)throws JSONException {
        return new JSONObject().put("status",p[i]).put("evQ8",p[i+1]).put("bvQ8",p[i+2])
                .put("normalizedY",Integer.toUnsignedLong(p[i+3]))
                .put("normalizedReference",Integer.toUnsignedLong(p[i+4]));
    }
    public static void appendTo(JSONObject parent,String snapshot) {
        try {parent.put("firmwareShadow2R",snapshot==null?
                new JSONObject().put("revision",REVISION).put("status","NOT_CAPTURED").put("controlsExposure",false):
                new JSONObject(snapshot));}
        catch(JSONException|RuntimeException|OutOfMemoryError ignored) { /* diagnostics cannot cancel capture */ }
    }
}
