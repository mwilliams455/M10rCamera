package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.*;
import org.json.JSONObject;
import org.junit.*;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/** Ensure the bounded decision reaches the real controller's preview and still paths. */
public class M10RCaptureForeground1QTest {
    static final double ROOM_EV=.25;
    @BeforeClass public static void keys()throws Exception{M10RCaptureMeterReference1ITest.keys();}
    @AfterClass public static void restoreKeys()throws Exception{M10RCaptureMeterReference1ITest.restoreKeys();}
    @After public void clear(){M10RPreviewState1A.clear(null);}
    @Test public void qualifiedNegativeConflictSharesBoundedCorrectionWithPreviewAndFrozenStill()throws Exception {
        for(int steps:new int[]{0,-2,3})try(var f=new M10RCaptureMeterReference1ITest.Fixture(steps,true)) {
            f.start(true);long now=System.nanoTime();double user=steps/3.0;
            var data=new M10RExposureForeground1QTest.Fixture();
            String renderer=M10RExposureRenderer1M.expectedRevision(com.particlesdevs.photoncamera.BuildConfig.M10R_METER_RENDERER1M,
                    com.particlesdevs.photoncamera.BuildConfig.M10R_RENDERED_COLOR1A,com.particlesdevs.photoncamera.BuildConfig.M10R_COLOR_ORDER1A);
            var probe=new M10RExposure1A.Probe(f.admitted.cameraKey,f.admitted.id,1,renderer,
                    123,123,now,now,792_748L,50,user,0,M10RExposure1A.ProbeDomain.M10R_RENDERED_USER_EV_REFERENCE,
                    data.grid(),data.positive,M10RHighlightGuard1A.noSubject(7),user,data.baseline);
            var raw=mock(M10RExposureRaw1B.Prepared.class);
            when(raw.atWhiteByCfaPhase()).thenReturn(new long[4]);when(raw.aboveWhiteByCfaPhase()).thenReturn(new long[4]);
            when(raw.nearWhiteByCfaPhase()).thenReturn(new long[4]);
            f.finish(new M10RExposureProbe1B.Output(probe,new short[3],new int[7][],raw,1,1,data.positive,data.baseline));
            var preview=M10RPreviewState1A.plan();assertNotNull(preview);var s=preview.selection;
            assertEquals(ROOM_EV,s.appliedAutoEv,1e-12);assertEquals(user+ROOM_EV,s.plan.totalIntentEv,1e-12);
            assertEquals(ROOM_EV,s.plan.deltaFromReferenceEv,1e-12);
            assertEquals((double)s.exposureNs*s.iso/(792_748.0*50),preview.previewScale(792_748L,50),1e-12);
            var report=new JSONObject(preview.report.json).getJSONObject("multiFieldEvidence1G");
            assertEquals(M10RMultiField1G.REVISION,report.getString("revision"));
            assertFalse(report.getBoolean("splitBrightBackground"));assertTrue(report.getBoolean("legacyNegativeOverrideApplied"));assertEquals(ROOM_EV,report.getDouble("positiveRequestLimitEv"),1e-12);
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
