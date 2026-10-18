package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.*;
import android.hardware.camera2.params.*;
import android.graphics.Rect;
import android.view.Surface;
import com.particlesdevs.photoncamera.api.VendorTagUtils;
import java.util.*;
import org.json.JSONObject;
import org.junit.*;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/** Exercise actual controller requests: periodic measurement must not insert AE-off stills. */
public class M10RPreviewBackgroundMeter1LTest {
    @BeforeClass public static void keys()throws Exception{M10RCaptureMeterReference1ITest.keys();}
    @AfterClass public static void restoreKeys()throws Exception{M10RCaptureMeterReference1ITest.restoreKeys();}
    @After public void clear(){M10RPreviewState1A.clear(null);}

    static void liveControls(M10RCaptureMeterReference1ITest.Fixture f){
        when(f.request.getKeys()).thenReturn(Arrays.asList(CaptureRequest.CONTROL_AE_MODE,
                CaptureRequest.CONTROL_AE_EXPOSURE_COMPENSATION,CaptureRequest.FLASH_MODE,
                CaptureRequest.CONTROL_AE_LOCK,CaptureRequest.CONTROL_AF_MODE,
                CaptureRequest.CONTROL_CAPTURE_INTENT,CaptureRequest.CONTROL_POST_RAW_SENSITIVITY_BOOST));
        when(f.request.get(CaptureRequest.CONTROL_AE_LOCK)).thenReturn(true);
        when(f.request.get(CaptureRequest.CONTROL_AF_MODE)).thenReturn(CaptureRequest.CONTROL_AF_MODE_CONTINUOUS_PICTURE);
        when(f.request.get(CaptureRequest.CONTROL_CAPTURE_INTENT)).thenReturn(CaptureRequest.CONTROL_CAPTURE_INTENT_PREVIEW);
        when(f.request.get(CaptureRequest.CONTROL_POST_RAW_SENSITIVITY_BOOST)).thenReturn(200);
        Map<CaptureRequest.Key<?>,Object> values=new HashMap<>();
        doAnswer(i->{values.put(i.getArgument(0),i.getArgument(1));return null;}).when(f.meter).set(any(),any());
        when(f.meter.get(any())).thenAnswer(i->values.get(i.getArgument(0)));
    }
    @Test public void backgroundRequestKeepsAutoExposureAndPreviewTemplate()throws Exception{
        try(var f=new M10RCaptureMeterReference1ITest.Fixture(0)){
            liveControls(f);Surface raw=mock(Surface.class);when(f.reader.getSurface()).thenReturn(raw);
            f.start(true);assertNotNull(f.admitted);
            verify(f.device).createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW);
            verify(f.device,never()).createCaptureRequest(CameraDevice.TEMPLATE_STILL_CAPTURE);
            verify(f.meter).set(CaptureRequest.CONTROL_AE_MODE,CaptureRequest.CONTROL_AE_MODE_ON);
            verify(f.meter,never()).set(CaptureRequest.CONTROL_AE_MODE,CaptureRequest.CONTROL_AE_MODE_OFF);
            verify(f.meter,never()).set(eq(CaptureRequest.SENSOR_EXPOSURE_TIME),any());
            verify(f.meter,never()).set(eq(CaptureRequest.SENSOR_SENSITIVITY),any());
            verify(f.meter,never()).set(eq(CaptureRequest.SENSOR_FRAME_DURATION),any());
            verify(f.meter).addTarget(raw);
            f.vendor.verify(()->VendorTagUtils.builderSessionApply(f.meter,false,false,"2"));
            f.vendor.verify(()->VendorTagUtils.builderSessionApply(f.meter,true,false,"2"),never());
            verifyNoInteractions(f.events);
        }
    }
    @Test public void backgroundRetainsEvLockFocusAndPostRawBoost()throws Exception{
        for(int steps:new int[]{-3,0,3})try(var f=new M10RCaptureMeterReference1ITest.Fixture(steps)){
            liveControls(f);f.start(true);assertNotNull(f.admitted);
            assertEquals(steps/3.0,f.admitted.referenceUserEv,1e-12);
            assertEquals(steps/3.0,f.admitted.userEv,1e-12);
            verify(f.meter).set(CaptureRequest.CONTROL_AE_EXPOSURE_COMPENSATION,steps);
            verify(f.meter).set(CaptureRequest.CONTROL_AE_LOCK,true);
            verify(f.meter).set(CaptureRequest.CONTROL_AF_MODE,CaptureRequest.CONTROL_AF_MODE_CONTINUOUS_PICTURE);
            verify(f.meter).set(CaptureRequest.CONTROL_POST_RAW_SENSITIVITY_BOOST,200);
            verify(f.meter).set(CaptureRequest.CONTROL_CAPTURE_INTENT,CaptureRequest.CONTROL_CAPTURE_INTENT_PREVIEW);
            verify(f.meter).set(CaptureRequest.CONTROL_AF_TRIGGER,CaptureRequest.CONTROL_AF_TRIGGER_IDLE);
        }
    }
    @Test public void backgroundPreservesPreviewColourOisAndCropWithoutStillOverrides()throws Exception{
        try(var f=new M10RCaptureMeterReference1ITest.Fixture(0)){
            liveControls(f);Rect crop=mock(Rect.class);RggbChannelVector wb=mock(RggbChannelVector.class);
            ColorSpaceTransform matrix=mock(ColorSpaceTransform.class);TonemapCurve curve=mock(TonemapCurve.class);
            when(f.request.getKeys()).thenReturn(Arrays.asList(CaptureRequest.CONTROL_AE_MODE,
                    CaptureRequest.SCALER_CROP_REGION,CaptureRequest.LENS_OPTICAL_STABILIZATION_MODE,
                    CaptureRequest.COLOR_CORRECTION_GAINS,CaptureRequest.COLOR_CORRECTION_TRANSFORM,
                    CaptureRequest.TONEMAP_MODE,CaptureRequest.TONEMAP_CURVE));
            when(f.request.get(CaptureRequest.SCALER_CROP_REGION)).thenReturn(crop);
            when(f.request.get(CaptureRequest.LENS_OPTICAL_STABILIZATION_MODE)).thenReturn(1);
            when(f.request.get(CaptureRequest.COLOR_CORRECTION_GAINS)).thenReturn(wb);
            when(f.request.get(CaptureRequest.COLOR_CORRECTION_TRANSFORM)).thenReturn(matrix);
            when(f.request.get(CaptureRequest.TONEMAP_MODE)).thenReturn(0);
            when(f.request.get(CaptureRequest.TONEMAP_CURVE)).thenReturn(curve);
            f.start(true);assertNotNull(f.admitted);
            assertSame(crop,f.meter.get(CaptureRequest.SCALER_CROP_REGION));
            assertSame(wb,f.meter.get(CaptureRequest.COLOR_CORRECTION_GAINS));
            assertSame(matrix,f.meter.get(CaptureRequest.COLOR_CORRECTION_TRANSFORM));
            assertSame(curve,f.meter.get(CaptureRequest.TONEMAP_CURVE));
            verify(f.meter,times(1)).set(eq(CaptureRequest.LENS_OPTICAL_STABILIZATION_MODE),any());
            verify(f.meter,never()).set(CaptureRequest.SCALER_CROP_REGION,null);
            verify(f.controller,never()).applyZoom(f.meter,false);
        }
    }
    @Test public void foregroundShutterMeterRetainsItsExactManualExposure()throws Exception{
        try(var f=new M10RCaptureMeterReference1ITest.Fixture(0)){
            liveControls(f);when(f.result.get(CaptureResult.SENSOR_FRAME_DURATION)).thenReturn(33_000_000L);
            f.start(false);assertNotNull(f.admitted);
            verify(f.device).createCaptureRequest(CameraDevice.TEMPLATE_STILL_CAPTURE);
            verify(f.device,never()).createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW);
            verify(f.meter).set(CaptureRequest.CONTROL_AE_MODE,CaptureRequest.CONTROL_AE_MODE_OFF);
            verify(f.meter).set(CaptureRequest.SENSOR_EXPOSURE_TIME,40_000_000L);
            verify(f.meter).set(CaptureRequest.SENSOR_SENSITIVITY,125);
            verify(f.meter).set(CaptureRequest.SENSOR_FRAME_DURATION,40_000_000L);
            f.vendor.verify(()->VendorTagUtils.builderSessionApply(f.meter,true,false,"2"));
            verifyNoInteractions(f.events);
        }
    }
    @Test public void changedAeOrFlashControlsCannotUseOldReference()throws Exception{
        for(boolean flash:new boolean[]{false,true})try(var f=new M10RCaptureMeterReference1ITest.Fixture(0)){
            liveControls(f);
            if(flash)when(f.preview.get(CaptureRequest.FLASH_MODE)).thenReturn(CaptureRequest.FLASH_MODE_TORCH);
            else when(f.preview.get(CaptureRequest.CONTROL_AE_MODE)).thenReturn(CaptureRequest.CONTROL_AE_MODE_OFF);
            f.start(true);assertNull(f.admitted);verify(f.exposure,never()).start(any());
            verify(f.device,never()).createCaptureRequest(anyInt());
        }
    }
    static M10RExposureProbe1B.Output measured(M10RCaptureMeterReference1ITest.Fixture f,long now){
        var p=M10RExposureRawGain1KTest.probe(f.admitted.cameraKey,f.admitted.id,now,30_000_000L,6402,f.admitted.metering);
        var raw=mock(M10RExposureRaw1B.Prepared.class);
        when(raw.atWhiteByCfaPhase()).thenReturn(new long[4]);when(raw.aboveWhiteByCfaPhase()).thenReturn(new long[4]);
        when(raw.nearWhiteByCfaPhase()).thenReturn(new long[4]);
        return new M10RExposureProbe1B.Output(p,new short[3],new int[7][],raw,1,1,
                M10RExposureRange1HTest.stats(7),M10RExposureRange1HTest.stats(3));
    }
    @Test public void repeatedBackgroundCyclesUseActualRawMeasurementsAndKeepAeOn()throws Exception{
        try(var f=new M10RCaptureMeterReference1ITest.Fixture(0)){
            liveControls(f);when(f.chars.get(CameraCharacteristics.SENSOR_MAX_ANALOG_SENSITIVITY)).thenReturn(6400);
            for(int cycle=0;cycle<5;cycle++){
                f.start(true);assertNotNull(f.admitted);f.finish(measured(f,System.nanoTime()));
                var p=M10RPreviewState1A.plan();assertNotNull(p);assertEquals(cycle+1,p.id);
                assertEquals(6402,p.referenceIso);assertEquals(30_000_000L,p.referenceNs);
                assertEquals(6402,p.selection.autoIsoCeiling);
                JSONObject d=new JSONObject(p.report.json);
                assertEquals(CameraDevice.TEMPLATE_PREVIEW,d.getInt("meterRequestTemplate"));
                assertEquals(CaptureRequest.CONTROL_AE_MODE_ON,d.getInt("meterRequestedAeMode"));
                assertEquals(6402,d.getInt("meterDeliveredIso"));assertEquals(125,d.getJSONObject("previewReferenceAtSelection").getInt("iso"));
                assertEquals("M10R_PREVIEW1L_CONTINUOUS_AE_METER",d.getString("backgroundMeterRevision"));
            }
            verify(f.device,times(5)).createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW);
            verify(f.meter,never()).set(CaptureRequest.CONTROL_AE_MODE,CaptureRequest.CONTROL_AE_MODE_OFF);
            verifyNoInteractions(f.events);
        }
    }
}
