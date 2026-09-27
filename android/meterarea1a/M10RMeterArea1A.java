package com.particlesdevs.photoncamera.m10r;

import android.graphics.Rect;
import android.graphics.SurfaceTexture;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.CaptureResult;
import android.hardware.camera2.TotalCaptureResult;
import android.opengl.GLES20;
import android.os.Build;
import android.util.Size;
import com.particlesdevs.photoncamera.capture.CaptureController;
import com.particlesdevs.photoncamera.util.Log;
import org.json.JSONArray;
import org.json.JSONObject;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.LinkedHashMap;
import java.util.Map;

/** METERAREA1A: shadow diagnostics only. Never read by IsoExpoSelector or MFM state writers. */
public final class M10RMeterArea1A {
    private static final String TAG="M10RMeterArea1A";
    private M10RMeterArea1A() {}
    private static final LinkedHashMap<String,Sample> samples=new LinkedHashMap<>();
    private static final LinkedHashMap<Long,String> metadata=new LinkedHashMap<>();
    private static final LinkedHashMap<String,Long> freezes=new LinkedHashMap<>();
    private static CameraCharacteristics cachedCharacteristics;
    private static String cachedSelectedId="", cachedFingerprint="";
    private static M10RLiveMeterState.Snapshot frozenLegacy;
    private static long frozenAtNs;
    private static String key(M10RLiveMeterState.Snapshot s) { return s.generation+":"+s.timestampNs; }
    private static <K,V> void trim(LinkedHashMap<K,V> m,int capacity) {
        while(m.size()>capacity) m.remove(m.keySet().iterator().next());
    }
    private static final class Sample {
        final M10RLiveMeterState.Snapshot legacy;
        final M10RMeterAreaMath.Grid area;
        final long textureNs, startNs, endNs;
        final float[] transform;
        final String fingerprint, error, matchedMetadata;
        Sample(M10RLiveMeterState.Snapshot legacy,M10RMeterAreaMath.Grid area,
               long textureNs,long startNs,long endNs,float[] transform,
               String fingerprint,String error,String matchedMetadata) {
            this.legacy=legacy;this.area=area;this.textureNs=textureNs;
            this.startNs=startNs;this.endNs=endNs;
            this.transform=transform!=null?transform.clone():null;
            this.fingerprint=fingerprint;this.error=error;this.matchedMetadata=matchedMetadata;
        }
    }
    public static final class Bound {
        final Sample sample;
        final M10RLiveMeterState.Snapshot legacy;
        final long freezeNs,renderEntryNs;
        final String matchedMetadata;
        Bound(Sample sample,M10RLiveMeterState.Snapshot legacy,long freezeNs,String meta) {
            this.sample=sample;this.legacy=legacy;this.freezeNs=freezeNs;
            this.renderEntryNs=System.nanoTime();this.matchedMetadata=meta;
        }
    }
    public static synchronized void freeze() {
        try {
            frozenLegacy=M10RLiveMeterState.frozenSnapshot();
            frozenAtNs=System.nanoTime();
            freezes.put(key(frozenLegacy),frozenAtNs);trim(freezes,64);
        } catch(RuntimeException e) { Log.e(TAG,"freeze diagnostic: "+e); }
    }
    public static synchronized Bound bind() {
        M10RLiveMeterState.Snapshot s=frozenLegacy;
        Sample p=s!=null?samples.get(key(s)):null;
        String meta=p!=null?p.matchedMetadata:null;
        if(meta==null && p!=null) meta=metadata.get(p.textureNs);
        return new Bound(p,s,frozenAtNs,meta);
    }
    private static synchronized void publish(Sample p) {
        samples.put(key(p.legacy),p);trim(samples,64);
    }
    private static synchronized String exactMetadata(long timestamp) { return metadata.get(timestamp); }

    /** Observe existing results only. No camera requests or surfaces are added. */
    public static synchronized void observePreview(TotalCaptureResult parent,CameraCharacteristics c,
                                                   String selectedId,String logicalId,Size previewSize) {
        try {
            if(parent==null) return;
            CaptureResult selected=parent;
            boolean physical=false;
            if(Build.VERSION.SDK_INT>=28 && selectedId!=null) {
                CaptureResult pr=parent.getPhysicalCameraResults().get(selectedId);
                if(pr!=null) { selected=pr;physical=true; }
            }
            if(c!=cachedCharacteristics || !String.valueOf(selectedId).equals(cachedSelectedId)) {
                cachedFingerprint=M10RMfm1DSourceProxy.resolve(c,0,0).fingerprint;
                cachedCharacteristics=c;cachedSelectedId=String.valueOf(selectedId);
            }
            JSONObject o=resultMetadata(selected);
            Long parentTs=parent.get(CaptureResult.SENSOR_TIMESTAMP);
            o.put("parentSensorTimestampNs",nullable(parentTs));
            o.put("parentFrameNumber",parent.getFrameNumber());
            o.put("selectedPhysicalId",nullable(selectedId));
            o.put("logicalCameraId",nullable(logicalId));
            o.put("physicalResultMetadataUsed",physical);
            o.put("metadataAuthority",physical?"selected_physical_result":"parent_result_physical_binding_unproven");
            o.put("characteristicsFingerprint",cachedFingerprint);
            o.put("previewBufferSize",previewSize!=null?previewSize.toString():JSONObject.NULL);
            if(Build.VERSION.SDK_INT>=28)
                o.put("reportedActivePhysicalId",nullable(parent.get(CaptureResult.LOGICAL_MULTI_CAMERA_ACTIVE_PHYSICAL_ID)));
            o.put("callbackSystemNanoTime",System.nanoTime());
            if(c!=null) {
                o.put("sensorTimestampSource",nullable(c.get(CameraCharacteristics.SENSOR_INFO_TIMESTAMP_SOURCE)));
                o.put("sensorOrientation",nullable(c.get(CameraCharacteristics.SENSOR_ORIENTATION)));
                o.put("lensFacing",nullable(c.get(CameraCharacteristics.LENS_FACING)));
                o.put("activeArray",rect(c.get(CameraCharacteristics.SENSOR_INFO_ACTIVE_ARRAY_SIZE)));
                o.put("preCorrectionActiveArray",rect(c.get(CameraCharacteristics.SENSOR_INFO_PRE_CORRECTION_ACTIVE_ARRAY_SIZE)));
            }
            // Match the texture to the parent stream timestamp, not to a nearby callback.
            if(parentTs!=null && parentTs>0) { metadata.put(parentTs,o.toString());trim(metadata,192); }
        } catch(Exception e) { Log.e(TAG,"preview diagnostic: "+e); }
    }
    private static Object nullable(Object x) { return x!=null?x:JSONObject.NULL; }
    private static JSONArray rect(Rect r) {
        return r==null?null:new JSONArray(new int[]{r.left,r.top,r.right,r.bottom});
    }
    private static JSONObject resultMetadata(CaptureResult r) throws Exception {
        JSONObject o=new JSONObject();
        if(r==null) return o.put("available",false);
        o.put("available",true).put("frameNumber",r.getFrameNumber());
        o.put("sensorTimestampNs",nullable(r.get(CaptureResult.SENSOR_TIMESTAMP)));
        o.put("exposureTimeNs",nullable(r.get(CaptureResult.SENSOR_EXPOSURE_TIME)));
        o.put("iso",nullable(r.get(CaptureResult.SENSOR_SENSITIVITY)));
        o.put("frameDurationNs",nullable(r.get(CaptureResult.SENSOR_FRAME_DURATION)));
        o.put("focusDistanceDioptres",nullable(r.get(CaptureResult.LENS_FOCUS_DISTANCE)));
        o.put("focalLengthMm",nullable(r.get(CaptureResult.LENS_FOCAL_LENGTH)));
        o.put("aperture",nullable(r.get(CaptureResult.LENS_APERTURE)));
        o.put("cropRegion",nullable(rect(r.get(CaptureResult.SCALER_CROP_REGION))));
        o.put("shadingMode",nullable(r.get(CaptureResult.SHADING_MODE)));
        o.put("lensShadingMapMode",nullable(r.get(CaptureResult.STATISTICS_LENS_SHADING_MAP_MODE)));
        o.put("lensShadingMapPresent",r.get(CaptureResult.STATISTICS_LENS_SHADING_CORRECTION_MAP)!=null);
        o.put("tonemapMode",nullable(r.get(CaptureResult.TONEMAP_MODE)));
        o.put("oisMode",nullable(r.get(CaptureResult.LENS_OPTICAL_STABILIZATION_MODE)));
        o.put("videoStabilizationMode",nullable(r.get(CaptureResult.CONTROL_VIDEO_STABILIZATION_MODE)));
        o.put("aeState",nullable(r.get(CaptureResult.CONTROL_AE_STATE)));
        o.put("afState",nullable(r.get(CaptureResult.CONTROL_AF_STATE)));
        if(Build.VERSION.SDK_INT>=28) o.put("distortionCorrectionMode",nullable(r.get(CaptureResult.DISTORTION_CORRECTION_MODE)));
        if(Build.VERSION.SDK_INT>=30) o.put("zoomRatio",nullable(r.get(CaptureResult.CONTROL_ZOOM_RATIO)));
        return o;
    }
    public static JSONArray grid(double[] a) throws Exception {
        JSONArray rows=new JSONArray();
        if(a==null || a.length!=352) return rows;
        for(int r=0;r<16;r++) {
            JSONArray row=new JSONArray();
            for(int c=0;c<22;c++) row.put(a[r*22+c]);
            rows.put(row);
        }
        return rows;
    }
    public static double[] readGrid(JSONArray rows) {
        if(rows==null || rows.length()!=16) return null;
        double[] a=new double[352];
        for(int r=0;r<16;r++) {
            JSONArray row=rows.optJSONArray(r);if(row==null || row.length()!=22) return null;
            for(int c=0;c<22;c++) a[r*22+c]=row.optDouble(c,Double.NaN);
        }
        return a;
    }
    public static JSONObject decision(double[] a) throws Exception {
        M10RMfm1B.Decision d=M10RMfm1B.evaluate(a);
        JSONObject o=new JSONObject().put("valid",d.valid).put("wouldApply",d.wouldApply)
                .put("recommendedEv",d.recommendedEv).put("reason",d.reason);
        if(d.valid) o.put("integralY",d.integralY).put("regionalMedianY",d.regionalMedianY)
                .put("center8Y",d.center8Y).put("sceneSpreadEv",d.sceneSpreadEv)
                .put("brightestSideVsInnerEv",d.brightestSideVsInnerEv)
                .put("positiveBaseEv",d.positiveBaseEv).put("sideGeometryConfidence",d.sideGeometryConfidence)
                .put("positiveCandidateEv",d.positiveCandidateEv).put("rawBlendEv",d.rawBlendEv);
        return o;
    }
    public static void append(JSONObject d,Bound bound,CameraCharacteristics c,
                              CaptureResult still,CaptureRequest request) {
        try {
            JSONObject o=new JSONObject().put("revision","METERAREA1A_SHADOW")
                    .put("diagnosticOnly",true).put("affectsExposure",false).put("affectsPixels",false)
                    .put("activeMeterInput","unchanged_legacy_sparse_grid")
                    .put("samplesPerCell",64).put("subgrid","8x8_stratified")
                    .put("denseFboWidth",128).put("denseFboHeight",176)
                    .put("exactFullResolutionAreaAverage",false)
                    .put("inverseSrgbBeforeAverage",true)
                    .put("rawCoverageParityVerified",false)
                    .put("previewRawSamePhotometricDomainClaimed",false)
                    .put("producerTransformAppliedByProbe",false)
                    .put("producerTransformPolicy","record_only_same_shader_and_coordinates_as_active_sparse_meter")
                    .put("previewIspTransferInverted",false)
                    .put("stillMetadata",resultMetadata(still));
            d.put("m10rMeterArea1A",o);
            if(bound==null || bound.legacy==null || bound.sample==null) {
                o.put("status","exact_sparse_area_pair_unavailable");return;
            }
            Sample s=bound.sample;
            o.put("legacyGeneration",s.legacy.generation).put("legacyPublishedSystemNanoTime",s.legacy.timestampNs)
                    .put("textureTimestampNs",s.textureNs).put("freezeSystemNanoTime",bound.freezeNs)
                    .put("renderEntrySystemNanoTime",bound.renderEntryNs)
                    .put("sampleElapsedMs",(s.endNs-s.startNs)/1e6)
                    .put("legacyAgeAtFreezeMs",(bound.freezeNs-s.legacy.timestampNs)/1e6)
                    .put("areaCompletedBeforeFreeze",s.endNs<=bound.freezeNs)
                    .put("sampleSourceFingerprint",s.fingerprint);
            if(s.transform!=null) o.put("surfaceTextureTransformColumnMajor",new JSONArray(s.transform));
            JSONObject active=d.optJSONObject("m10rMfm1D");
            double exponent=active!=null?active.optDouble("liveRawProxyExponent",Double.NaN):Double.NaN;
            boolean generation=active!=null && active.optLong("liveGridGeneration",-1)==s.legacy.generation;
            boolean fingerprint=active!=null && s.fingerprint.equals(active.optString("sourceProxyPhysicalFingerprint",""));
            o.put("matchesActiveDecisionGeneration",generation).put("matchesActiveSourceFingerprint",fingerprint);
            String actualFp=M10RMfm1DSourceProxy.resolve(c,0,0).fingerprint;
            o.put("stillCharacteristicsFingerprint",actualFp)
                    .put("sampleMatchesStillCharacteristics",s.fingerprint.equals(actualFp));
            o.put("frameMetadataExactTimestampMatch",bound.matchedMetadata!=null);
            if(bound.matchedMetadata!=null) {
                JSONObject meta=new JSONObject(bound.matchedMetadata);o.put("previewMetadata",meta);
                o.put("matchedMetadataFingerprintAgrees",s.fingerprint.equals(meta.optString("characteristicsFingerprint","")));
                Long st=still.get(CaptureResult.SENSOR_TIMESTAMP);
                if(st!=null) o.put("stillMinusPreviewSensorTimestampNs",st-s.textureNs);
                o.put("timestampDeltaMeaning","sensor_stream_interval_not_SystemNanoTime_difference;physical_binding_must_be_checked");
            }
            if(s.area==null) { o.put("status","area_sample_failed").put("error",s.error);return; }
            boolean exp=Double.isFinite(exponent) && exponent==s.area.exponent;
            o.put("sampleExponent",s.area.exponent).put("matchesActiveExponent",exp)
                    .put("status",generation&&fingerprint&&exp?"shadow_pair_available":"binding_mismatch_do_not_calibrate");
            o.put("areaCodeGrid16x22",grid(s.area.code))
                    .put("areaLinearYGrid16x22",grid(s.area.linear))
                    .put("areaLinearGreenGrid16x22",grid(s.area.green))
                    .put("areaProxyBeforeAverageGrid16x22",grid(s.area.proxyBeforeAverage));
            o.put("pointLinearDecision",decision(s.legacy.linearGrid));
            o.put("pointProxyDecision",decision(M10RMeterAreaMath.proxyAfterAverage(s.legacy.linearGrid,s.area.exponent)));
            o.put("areaLinearDecision",decision(s.area.linear));
            o.put("areaProxyAfterAverageDecision",decision(M10RMeterAreaMath.proxyAfterAverage(s.area.linear,s.area.exponent)));
            o.put("areaProxyBeforeAverageDecision",decision(s.area.proxyBeforeAverage));
            JSONArray phases=new JSONArray();
            for(double[] phase:s.area.linearPhases) phases.put(decision(phase));
            o.put("fourInterleaved4x4LinearPhaseDecisions",phases);
            JSONObject raw=d.optJSONObject("m10rAe1A_rawMeterProbe");
            if(raw!=null) o.put("rawPreShadingDecision",decision(readGrid(raw.optJSONArray("leicaRawGrid16x22"))));
            JSONObject post=d.optJSONObject("m10rMeterAreaRaw1A");
            if(post!=null) o.put("rawPostShadingDecision",decision(readGrid(post.optJSONArray("greenPostShadingGrid16x22"))));
        } catch(Exception e) {
            try { d.put("m10rMeterArea1A",new JSONObject().put("diagnosticOnly",true)
                    .put("affectsExposure",false).put("status","telemetry_failed").put("error",e.toString())); }
            catch(Exception ignored) {}
        }
    }

    /** Uses the existing bound preview shader with peaking/mirror already disabled. */
    public static final class GlSampler {
        private int fbo,texture;
        private ByteBuffer pixels;
        public void reset() { fbo=0;texture=0;pixels=null; }
        public void sample(SurfaceTexture st,M10RLiveMeterState.Snapshot legacy) {
            if(st==null || legacy==null || !legacy.valid) return;
            long start=System.nanoTime(),texNs=0;
            int[] oldFbo=new int[1],oldViewport=new int[4],oldTexture=new int[1];
            GLES20.glGetIntegerv(GLES20.GL_FRAMEBUFFER_BINDING,oldFbo,0);
            GLES20.glGetIntegerv(GLES20.GL_VIEWPORT,oldViewport,0);
            GLES20.glGetIntegerv(GLES20.GL_TEXTURE_BINDING_2D,oldTexture,0);
            float[] transform=new float[16];String fp="unavailable";
            try {
                texNs=st.getTimestamp();st.getTransformMatrix(transform);
                M10RMfm1DSourceProxy.Profile source=M10RMfm1DSourceProxy.resolve(CaptureController.mCameraCharacteristics,0,0);
                fp=source.fingerprint;
                if(fbo==0) {
                    int[] ids=new int[1];GLES20.glGenTextures(1,ids,0);texture=ids[0];
                    GLES20.glBindTexture(GLES20.GL_TEXTURE_2D,texture);
                    GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D,GLES20.GL_TEXTURE_MIN_FILTER,GLES20.GL_NEAREST);
                    GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D,GLES20.GL_TEXTURE_MAG_FILTER,GLES20.GL_NEAREST);
                    GLES20.glTexImage2D(GLES20.GL_TEXTURE_2D,0,GLES20.GL_RGBA,128,176,0,GLES20.GL_RGBA,GLES20.GL_UNSIGNED_BYTE,null);
                    GLES20.glGenFramebuffers(1,ids,0);fbo=ids[0];
                    GLES20.glBindFramebuffer(GLES20.GL_FRAMEBUFFER,fbo);
                    GLES20.glFramebufferTexture2D(GLES20.GL_FRAMEBUFFER,GLES20.GL_COLOR_ATTACHMENT0,GLES20.GL_TEXTURE_2D,texture,0);
                    if(GLES20.glCheckFramebufferStatus(GLES20.GL_FRAMEBUFFER)!=GLES20.GL_FRAMEBUFFER_COMPLETE)
                        throw new IllegalStateException("area framebuffer incomplete");
                    pixels=ByteBuffer.allocateDirect(128*176*4).order(ByteOrder.nativeOrder());
                }
                GLES20.glBindFramebuffer(GLES20.GL_FRAMEBUFFER,fbo);
                GLES20.glViewport(0,0,128,176);
                GLES20.glDrawArrays(GLES20.GL_TRIANGLE_STRIP,0,4);
                pixels.clear();GLES20.glReadPixels(0,0,128,176,GLES20.GL_RGBA,GLES20.GL_UNSIGNED_BYTE,pixels);
                int error=GLES20.glGetError();
                if(error!=GLES20.GL_NO_ERROR) throw new IllegalStateException("GL error observed: "+error);
                pixels.position(0);
                M10RMeterAreaMath.Grid area=M10RMeterAreaMath.reduce(pixels,source.exponent);
                if(st.getTimestamp()!=texNs) throw new IllegalStateException("texture changed within diagnostic pair");
                publish(new Sample(legacy,area,texNs,start,System.nanoTime(),transform,fp,"",exactMetadata(texNs)));
            } catch(Exception e) {
                publish(new Sample(legacy,null,texNs,start,System.nanoTime(),transform,fp,e.toString(),exactMetadata(texNs)));
                Log.e(TAG,"shadow sample: "+e);
            } finally {
                GLES20.glBindTexture(GLES20.GL_TEXTURE_2D,oldTexture[0]);
                GLES20.glBindFramebuffer(GLES20.GL_FRAMEBUFFER,oldFbo[0]);
                GLES20.glViewport(oldViewport[0],oldViewport[1],oldViewport[2],oldViewport[3]);
            }
        }
    }
}
