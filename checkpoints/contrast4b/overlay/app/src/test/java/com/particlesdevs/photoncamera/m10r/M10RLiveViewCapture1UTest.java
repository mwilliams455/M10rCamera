package com.particlesdevs.photoncamera.m10r;

import android.graphics.Rect;
import com.particlesdevs.photoncamera.BuildConfig;
import com.particlesdevs.photoncamera.settings.PreferenceKeys;
import org.junit.*;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/** Actual controller input, completion and preview publication with mode-bound evidence. */
public class M10RLiveViewCapture1UTest {
    @BeforeClass public static void keys()throws Exception{M10RCaptureMeterReference1ITest.keys();}
    @AfterClass public static void restore()throws Exception{M10RCaptureMeterReference1ITest.restoreKeys();}
    static M10RExposureProbe1B.Output output(M10RCaptureMeterReference1ITest.Fixture f) {
        var in=f.admitted;long now=System.nanoTime();
        var measurement=M10RMetering1U.measure(M10RLiveView1UTest.split(),4096,3072,in.metering);
        var positive=M10RExposureRange1HTest.stats(7);var baseline=M10RExposureRange1HTest.stats(3);
        var probe=new M10RExposure1A.Probe(in.cameraKey,in.id,1,
                M10RExposureRenderer1M.expectedRevision(BuildConfig.M10R_METER_RENDERER1M,BuildConfig.M10R_RENDERED_COLOR1A,BuildConfig.M10R_COLOR_ORDER1A),
                123,123,now,now,40_000_000,125,in.referenceUserEv,0,
                M10RExposure1A.ProbeDomain.M10R_RENDERED_USER_EV_REFERENCE,
                measurement.cells(),positive,M10RHighlightGuard1A.noSubject(7),in.userEv,baseline,measurement);
        var raw=mock(M10RExposureRaw1B.Prepared.class);
        when(raw.atWhiteByCfaPhase()).thenReturn(new long[4]);when(raw.aboveWhiteByCfaPhase()).thenReturn(new long[4]);
        when(raw.nearWhiteByCfaPhase()).thenReturn(new long[4]);
        return new M10RExposureProbe1B.Output(probe,new short[3],new int[7][],raw,1,1,positive,baseline);
    }
    @Test public void allThreeModesReachControllerPreviewPlanAndReport()throws Exception {
        for(int mode:new int[]{0,1,2})try(var f=new M10RCaptureMeterReference1ITest.Fixture(0,mode)) {
            f.start(true);assertNotNull(f.admitted);assertNotNull(f.admitted.metering);
            assertEquals(M10RMetering1U.mode(mode),f.admitted.metering.mode);
            f.finish(output(f));var p=M10RPreviewState1A.plan();assertNotNull(p);
            assertNull(p.selection.plan.multiField);assertEquals(f.admitted.metering.key(),p.selection.plan.metering.config.key());
            var report=new org.json.JSONObject(p.report.json);
            assertEquals(f.admitted.metering.mode.name(),report.getJSONObject("liveViewMetering1U").getString("mode"));
            assertEquals(1,report.getInt("photographicRawFrameCount"));assertFalse(report.getBoolean("frameFusion"));
            verifyNoInteractions(f.events);
        }
    }
    @Test public void modeChangeDuringMeasurementCannotPublishOldPlan()throws Exception {
        try(var f=new M10RCaptureMeterReference1ITest.Fixture(0,1)) {
            f.start(true);var output=output(f);
            f.prefs.when(PreferenceKeys::getAeMeteringStd).thenReturn(2);
            f.finish(output);assertNull(M10RPreviewState1A.plan());verifyNoInteractions(f.events);
        }
    }
    @Test public void spotTapDuringMeasurementCannotPublishOldPosition()throws Exception {
        try(var f=new M10RCaptureMeterReference1ITest.Fixture(0,2)) {
            f.start(true);var output=output(f);
            Rect tap=mock(Rect.class);when(tap.exactCenterX()).thenReturn(500f);when(tap.exactCenterY()).thenReturn(800f);
            f.controller.setM10RSpotMeteringPoint(tap);
            f.finish(output);assertNull(M10RPreviewState1A.plan());verifyNoInteractions(f.events);
            String current=(String)f.call("m10rControls1C",new Class<?>[0]);assertNotEquals(f.controls,current);
            f.controller.resetM10RSpotMeteringPoint();assertEquals(f.controls,f.call("m10rControls1C",new Class<?>[0]));
        }
    }
    @Test public void spotTapDoesNotAlterCentreOrMultiFieldBinding()throws Exception {
        for(int mode:new int[]{0,1})try(var f=new M10RCaptureMeterReference1ITest.Fixture(0,mode)) {
            f.controller.setM10RSpotMeteringPoint(mock(Rect.class));
            assertEquals(f.controls,f.call("m10rControls1C",new Class<?>[0]));
        }
    }
}
