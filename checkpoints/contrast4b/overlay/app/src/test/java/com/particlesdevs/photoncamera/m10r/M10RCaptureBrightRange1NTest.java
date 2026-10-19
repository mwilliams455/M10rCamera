package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.*;
import org.json.JSONObject;
import org.junit.*;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/** Actual controller completion, shared preview plan and frozen still request. */
public class M10RCaptureBrightRange1NTest {
    @BeforeClass public static void keys()throws Exception{M10RCaptureMeterReference1ITest.keys();}
    @AfterClass public static void restoreKeys()throws Exception{M10RCaptureMeterReference1ITest.restoreKeys();}
    @After public void clear(){M10RPreviewState1A.clear(null);}
    @Test public void correctedAllocationReachesPreviewReportAndStillRequest()throws Exception{
        try(var f=new M10RCaptureMeterReference1ITest.Fixture(0,true)){
            when(f.result.get(CaptureResult.LENS_APERTURE)).thenReturn(1.63f);
            when(f.chars.get(CameraCharacteristics.SENSOR_MAX_ANALOG_SENSITIVITY)).thenReturn(3200);
            f.start(true);long now=System.nanoTime();
            var p=M10RExposureRawGain1KTest.probe(f.admitted.cameraKey,f.admitted.id,now,214467,50);
            var raw=mock(M10RExposureRaw1B.Prepared.class);
            when(raw.atWhiteByCfaPhase()).thenReturn(new long[4]);when(raw.aboveWhiteByCfaPhase()).thenReturn(new long[4]);
            when(raw.nearWhiteByCfaPhase()).thenReturn(new long[4]);
            f.finish(new M10RExposureProbe1B.Output(p,new short[3],new int[7][],raw,1,1,
                    M10RExposureRange1HTest.stats(7),M10RExposureRange1HTest.stats(3)));
            var plan=M10RPreviewState1A.plan();assertNotNull(plan);var s=plan.selection;
            assertEquals(107234,s.exposureNs);assertEquals(100,s.iso);
            assertEquals(-1.08203125,s.brightRangeCorrectionEv,0);
            var report=new JSONObject(plan.report.json);var range=report.getJSONObject("allocationRange1N");
            assertTrue(range.getBoolean("applied"));assertEquals("firmware_fast_shutter_limit",range.getString("reason"));
            assertEquals(s.targetExposureProduct,range.getDouble("targetExposureProductNsIso"),0);
            assertEquals((double)s.exposureNs*s.iso,range.getDouble("selectedExposureProductNsIso"),0);
            assertEquals(s.allocationResidualEv,range.getDouble("physicalRangeResidualEv"),0);
            assertEquals(0,range.getDouble("fixedExposureBiasEv"),0);
            assertFalse(range.getBoolean("sceneExposurePolicyChanged"));
            assertTrue(range.getBoolean("legacyCorrectionDiagnosticOnly"));
            var phone=report.getJSONObject("phoneExposure2U");
            assertEquals(M10RPhoneExposure2U.REVISION,phone.getString("revision"));
            assertEquals(214467.0*50,phone.getDouble("targetExposureProductNsIso"),0);
            assertFalse(phone.getBoolean("leicaSensitivityCorrectionTransferred"));
            assertFalse(phone.getBoolean("phoneGainCalibrated"));
            assertFalse(report.getBoolean("hardwareClamped"));
            assertTrue(report.getJSONObject("meterRenderer1M").getBoolean("applied"));
            assertEquals(3200,s.autoIsoCeiling);assertEquals(50,s.verifiedRawIso);verifyNoInteractions(f.events);
            com.particlesdevs.photoncamera.processing.parameters.IsoExpoSelector.prepareM10rExposure1CCapture(f.controller,s);
            try(var logs=mockStatic(com.particlesdevs.photoncamera.util.Log.class)){
                CaptureRequest.Builder still=mock(CaptureRequest.Builder.class);
                com.particlesdevs.photoncamera.processing.parameters.IsoExpoSelector.setExpo(still,0,f.controller);
                verify(still).set(CaptureRequest.SENSOR_SENSITIVITY,100);
                verify(still).set(CaptureRequest.SENSOR_EXPOSURE_TIME,107234L);
            }
        }
    }
}
