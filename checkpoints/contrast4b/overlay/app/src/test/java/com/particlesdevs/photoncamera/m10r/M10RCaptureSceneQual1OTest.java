package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.*;
import java.util.Arrays;
import org.json.JSONObject;
import org.junit.*;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/** Production controller completion, shared preview selection, diagnostics and frozen still. */
public class M10RCaptureSceneQual1OTest {
    @BeforeClass public static void keys()throws Exception{M10RCaptureMeterReference1ITest.keys();}
    @AfterClass public static void restoreKeys()throws Exception{M10RCaptureMeterReference1ITest.restoreKeys();}
    @After public void clear(){M10RPreviewState1A.clear(null);}
    @Test public void suppressedAssistAndUserEvReachPreviewAndFrozenStillTogether()throws Exception {
        for(int steps:new int[]{0,-2,3})try(var f=new M10RCaptureMeterReference1ITest.Fixture(steps,true)) {
            f.start(true);long now=System.nanoTime();double user=steps/3.0;
            var positive=new M10RHighlightGuard1A.Stats[7];Arrays.fill(positive,M10RExposureBaseline1FTest.SAFE);
            var baseline=new M10RHighlightGuard1A.Stats[]{positive[0],positive[0],positive[0]};
            String renderer=M10RExposureRenderer1M.expectedRevision(com.particlesdevs.photoncamera.BuildConfig.M10R_METER_RENDERER1M,
                    com.particlesdevs.photoncamera.BuildConfig.M10R_RENDERED_COLOR1A,com.particlesdevs.photoncamera.BuildConfig.M10R_COLOR_ORDER1A);
            var probe=new M10RExposure1A.Probe(f.admitted.cameraKey,f.admitted.id,1,renderer,
                    123,123,now,now,40_000_000L,125,user,0,M10RExposure1A.ProbeDomain.M10R_RENDERED_USER_EV_REFERENCE,
                    M10RExposureRange1HTest.backlit(),positive,M10RHighlightGuard1A.noSubject(7),user,baseline);
            var raw=mock(M10RExposureRaw1B.Prepared.class);
            when(raw.atWhiteByCfaPhase()).thenReturn(new long[4]);when(raw.aboveWhiteByCfaPhase()).thenReturn(new long[4]);
            when(raw.nearWhiteByCfaPhase()).thenReturn(new long[4]);
            f.finish(new M10RExposureProbe1B.Output(probe,new short[3],new int[7][],raw,1,1,positive,baseline));
            var preview=M10RPreviewState1A.plan();assertNotNull(preview);var s=preview.selection;
            assertTrue(s.plan.mfm.recommendedEv>0);assertFalse(s.plan.multiField.scene.qualified);
            assertEquals(0,s.appliedAutoEv,0);assertEquals(user,s.plan.totalIntentEv,1e-12);
            assertEquals(0,s.plan.deltaFromReferenceEv,1e-12);
            assertEquals((double)s.exposureNs*s.iso/(40_000_000.0*125),preview.previewScale(40_000_000L,125),1e-12);
            var report=new JSONObject(preview.report.json).getJSONObject("multiFieldEvidence1G");
            assertTrue(report.getBoolean("legacyPositiveSuppressed"));assertEquals(user,report.getDouble("userEv"),1e-12);
            verifyNoInteractions(f.events);
            com.particlesdevs.photoncamera.processing.parameters.IsoExpoSelector.prepareM10rExposure1CCapture(f.controller,s);
            try(var logs=mockStatic(com.particlesdevs.photoncamera.util.Log.class)) {
                CaptureRequest.Builder still=mock(CaptureRequest.Builder.class);
                com.particlesdevs.photoncamera.processing.parameters.IsoExpoSelector.setExpo(still,0,f.controller);
                verify(still).set(CaptureRequest.SENSOR_SENSITIVITY,s.iso);
                verify(still).set(CaptureRequest.SENSOR_EXPOSURE_TIME,s.exposureNs);
            }
        }
    }
}
