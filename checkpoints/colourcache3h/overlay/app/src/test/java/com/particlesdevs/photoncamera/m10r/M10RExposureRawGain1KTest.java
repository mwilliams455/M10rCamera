package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.*;
import java.util.Arrays;
import org.json.JSONObject;
import org.junit.*;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/** Reproduce a real requested/delivered ISO shortfall; exercise the production allocator and freeze. */
public class M10RExposureRawGain1KTest {
    @BeforeClass public static void keys()throws Exception{M10RCaptureMeterReference1ITest.keys();}
    @AfterClass public static void restoreKeys()throws Exception{M10RCaptureMeterReference1ITest.restoreKeys();}
    @After public void clear(){M10RPreviewState1A.clear(null);}
    static final long NOW=2_000_000_000L;
    static M10RExposure1A.Request request(String key,boolean auto){
        return new M10RExposure1A.Request(key,1,M10RExposureRenderer1M.expectedRevision(com.particlesdevs.photoncamera.BuildConfig.M10R_METER_RENDERER1M,
                com.particlesdevs.photoncamera.BuildConfig.M10R_RENDERED_COLOR1A,com.particlesdevs.photoncamera.BuildConfig.M10R_COLOR_ORDER1A),NOW,0,2.6,98.8708,100,50000,auto);
    }
    static M10RExposure1A.Probe probe(String key,long session,long now,long ns,int iso){return probe(key,session,now,ns,iso,null);}
    static M10RExposure1A.Probe probe(String key,long session,long now,long ns,int iso,M10RMetering1U.Config config){
        double[] grid=new double[352];Arrays.fill(grid,.12);
        return new M10RExposure1A.Probe(key,session,1,M10RExposureRenderer1M.expectedRevision(com.particlesdevs.photoncamera.BuildConfig.M10R_METER_RENDERER1M,
                com.particlesdevs.photoncamera.BuildConfig.M10R_RENDERED_COLOR1A,com.particlesdevs.photoncamera.BuildConfig.M10R_COLOR_ORDER1A),
                123,123,now,now,ns,iso,0,0,M10RExposure1A.ProbeDomain.M10R_RENDERED_USER_EV_REFERENCE,
                grid,M10RExposureRange1HTest.stats(7),M10RHighlightGuard1A.noSubject(7),0,M10RExposureRange1HTest.stats(3),config==null?null:M10RMetering1U.measure(M10RLiveView1UTest.flat(.12),4096,3072,config));
    }
    static M10RExposureCapture1B.Limits limits(Integer analog,long maxNs){
        return new M10RExposureCapture1B.Limits(1000,maxNs,50,51200,analog);
    }
    static double energy(M10RExposureCapture1B.Selection s){return (double)s.exposureNs*s.iso;}
    @Test public void telephotoShortfallTransfersUnverifiedGainToShutter(){
        var p=probe("physical",1,NOW,30_000_000L,6402);
        var old=M10RExposureCapture1B.select(p,request("physical",true),null,limits(null,1_000_000_000L));
        var fixed=M10RExposureCapture1B.select(p,request("physical",true),null,limits(6400,1_000_000_000L));
        assertEquals(20000,old.iso);assertEquals(9_603_000L,old.exposureNs);
        assertEquals(6402,fixed.iso);assertEquals(6402,fixed.autoIsoCeiling);assertTrue(fixed.clamped);
        assertTrue(fixed.exposureNs>3*old.exposureNs);
        assertEquals(energy(old),energy(fixed),fixed.iso*.51);
        assertEquals(0,fixed.allocationResidualEv,1e-7);assertEquals(0,fixed.appliedAutoEv,0);
    }
    @Test public void belowCeilingCaptureIsUnchanged(){
        var p=probe("physical",1,NOW,10_000_000L,1090);
        var old=M10RExposureCapture1B.select(p,request("physical",true),null,limits(null,1_000_000_000L));
        var fixed=M10RExposureCapture1B.select(p,request("physical",true),null,limits(6400,1_000_000_000L));
        assertEquals(old.iso,fixed.iso);assertEquals(old.exposureNs,fixed.exposureNs);assertFalse(fixed.clamped);
    }
    @Test public void genuineHigherRawIsoIsPermittedOnlyUpToCurrentMeasurement(){
        var p=probe("other_sensor",1,NOW,30_000_000L,12800);
        var s=M10RExposureCapture1B.select(p,request("other_sensor",true),null,limits(3200,1_000_000_000L));
        assertTrue(s.apply);assertEquals(12800,s.autoIsoCeiling);assertEquals(12800,s.verifiedRawIso);
        assertEquals(12800,s.iso);assertEquals(0,s.allocationResidualEv,1e-7);
    }
    @Test public void fallbackPreviewIsoDoesNotAuthorizeRawGain(){
        var ref=new M10RExposureCapture1B.Reference("physical",1,NOW,30_000_000L,25000,0,0);
        var s=M10RExposureCapture1B.select(null,request("physical",true),ref,limits(3200,1_000_000_000L));
        assertTrue(s.fallback);assertEquals(3200,s.autoIsoCeiling);assertEquals(0,s.verifiedRawIso);assertEquals(3200,s.iso);
    }
    @Test public void rejectedSourceOrStaleRawCannotExpandCeiling(){
        var ref=new M10RExposureCapture1B.Reference("physical",1,NOW,30_000_000L,25000,0,0);
        for(var p:new M10RExposure1A.Probe[]{probe("other",1,NOW,30_000_000L,25000),
                probe("physical",2,NOW,30_000_000L,25000),probe("physical",1,1,30_000_000L,25000)}){
            var s=M10RExposureCapture1B.select(p,request("physical",true),ref,limits(3200,1_000_000_000L));
            assertTrue(s.fallback);assertEquals(3200,s.autoIsoCeiling);assertEquals(0,s.verifiedRawIso);
        }
    }
    @Test public void absentOrInvalidAnalogRangeDoesNotInventALimit(){
        var p=probe("physical",1,NOW,30_000_000L,6402);
        for(Integer analog:new Integer[]{null,0,-1,49,60000}){
            var s=M10RExposureCapture1B.select(p,request("physical",true),null,limits(analog,1_000_000_000L));
            assertEquals(51200,s.autoIsoCeiling);assertEquals(20000,s.iso);assertFalse(s.clamped);
        }
    }
    @Test public void shutterRangeShortfallIsReportedInsteadOfExceedingLimits(){
        var s=M10RExposureCapture1B.select(probe("physical",1,NOW,30_000_000L,6402),
                request("physical",true),null,limits(6400,20_000_000L));
        assertEquals(20_000_000L,s.exposureNs);assertEquals(6402,s.iso);assertEquals(Math.log(2.0/3)/Math.log(2),s.allocationResidualEv,1e-12);
    }
    @Test public void manualExposureRemainsBypassed(){
        var s=M10RExposureCapture1B.select(probe("physical",1,NOW,30_000_000L,6402),
                request("physical",false),null,limits(6400,1_000_000_000L));
        assertFalse(s.apply);assertTrue(s.manualBypass);assertEquals(0,s.exposureNs);
    }
    @Test public void actualControllerUsesPhysicalAnalogLimitAndPublishesSamePreviewPlan()throws Exception{
        try(var f=new M10RCaptureMeterReference1ITest.Fixture(0)){
            when(f.chars.get(CameraCharacteristics.SENSOR_MAX_ANALOG_SENSITIVITY)).thenReturn(400);
            f.start(true);long now=System.nanoTime();
            var p=probe(f.admitted.cameraKey,f.admitted.id,now,100_000_000L,300,f.admitted.metering);
            var raw=mock(M10RExposureRaw1B.Prepared.class);
            when(raw.atWhiteByCfaPhase()).thenReturn(new long[4]);when(raw.aboveWhiteByCfaPhase()).thenReturn(new long[4]);
            when(raw.nearWhiteByCfaPhase()).thenReturn(new long[4]);
            f.finish(new M10RExposureProbe1B.Output(p,new short[3],new int[7][],raw,1,1,
                    M10RExposureRange1HTest.stats(7),M10RExposureRange1HTest.stats(3)));
            var plan=M10RPreviewState1A.plan();assertNotNull(plan);assertEquals(400,plan.selection.autoIsoCeiling);
            assertTrue(plan.selection.clamped);assertEquals(400,plan.selection.iso);
            var d=new JSONObject(plan.report.json);assertEquals(400,d.getInt("physicalMaxAnalogIso"));
            assertEquals(300,d.getInt("verifiedMeterRawIso"));assertEquals(300,d.getInt("meterDeliveredIso"));
            assertEquals(125,d.getJSONObject("previewReferenceAtSelection").getInt("iso"));
            assertEquals(0,plan.selection.allocationResidualEv,1e-7);verifyNoInteractions(f.events);
            com.particlesdevs.photoncamera.processing.parameters.IsoExpoSelector.prepareM10rExposure1CCapture(f.controller,plan.selection);
            try(var logs=mockStatic(com.particlesdevs.photoncamera.util.Log.class)){
                CaptureRequest.Builder still=mock(CaptureRequest.Builder.class);
                com.particlesdevs.photoncamera.processing.parameters.IsoExpoSelector.setExpo(still,0,f.controller);
                verify(still).set(CaptureRequest.SENSOR_SENSITIVITY,plan.selection.iso);
                verify(still).set(CaptureRequest.SENSOR_EXPOSURE_TIME,plan.selection.exposureNs);
            }
        }
    }
    @Test public void deliveryReportSeparatesRawGainFromPostRawBoost()throws Exception{
        var c=mock(CameraCharacteristics.class);var r=mock(CaptureResult.class);var q=mock(CaptureRequest.class);
        when(q.get(CaptureRequest.CONTROL_AE_MODE)).thenReturn(CaptureRequest.CONTROL_AE_MODE_OFF);
        when(q.get(CaptureRequest.SENSOR_EXPOSURE_TIME)).thenReturn(10_381_482L);
        when(q.get(CaptureRequest.SENSOR_SENSITIVITY)).thenReturn(20000);
        when(r.get(CaptureResult.SENSOR_EXPOSURE_TIME)).thenReturn(10_381_482L);
        when(r.get(CaptureResult.SENSOR_SENSITIVITY)).thenReturn(6410);
        when(r.get(CaptureResult.CONTROL_POST_RAW_SENSITIVITY_BOOST)).thenReturn(312);
        var root=new JSONObject();M10RExposureDelivery1K.append(root,c,r,q);var d=root.getJSONObject("m10rExposureDelivery1K");
        assertEquals(-1.6416,d.getDouble("deliveredMinusRequestedEv"),.001);
        assertTrue(d.getBoolean("deliveryShortfallOverOneSixthStop"));assertFalse(d.getBoolean("rawBrightnessCorrectionApplied"));
        assertEquals(312,d.getInt("postRawSensitivityBoost"));assertFalse(d.getBoolean("postRawBoostIncludedInRawExposure"));
        when(r.get(CaptureResult.SENSOR_SENSITIVITY)).thenReturn(20000);
        root=new JSONObject();M10RExposureDelivery1K.append(root,c,r,q);
        assertEquals(0,root.getJSONObject("m10rExposureDelivery1K").getDouble("deliveredMinusRequestedEv"),0);
    }
    @Test public void missingOrAutomaticRequestDoesNotReportFalseDeliveryFailure()throws Exception{
        var c=mock(CameraCharacteristics.class);var r=mock(CaptureResult.class);var q=mock(CaptureRequest.class);
        when(q.get(CaptureRequest.CONTROL_AE_MODE)).thenReturn(CaptureRequest.CONTROL_AE_MODE_ON);
        for(CaptureRequest request:new CaptureRequest[]{null,q}){
            var root=new JSONObject();M10RExposureDelivery1K.append(root,c,r,request);
            var d=root.getJSONObject("m10rExposureDelivery1K");assertFalse(d.getBoolean("manualRequestComparable"));
            assertFalse(d.has("deliveredMinusRequestedEv"));
        }
    }
}
