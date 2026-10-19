package com.particlesdevs.photoncamera.m10r;

import java.lang.reflect.Field;
import java.util.Arrays;
import org.json.JSONObject;
import org.junit.Test;
import static org.junit.Assert.*;

public class M10RExposureRenderer1MTest {
    private static M10RExposureNative1B.Context legacy(JSONObject c,int[] gains) throws Exception {
        return new M10RExposureNative1B.Context(new double[]{1,0,0,0,1,0,0,0,1},gains,
                M10RRenderedColor1ATest.doubles(c.getJSONArray("baselineWork")),
                M10RRenderedColor1ATest.doubles(c.getJSONArray("baselineOutput")),"cam",123);
    }
    @Test public void meterAndPreviewSelectIdenticalMatricesAndOrderForAllGoldenCaptureStates() throws Exception {
        JSONObject f=M10RRenderedColor1ATest.fixture();var prep=M10RRenderedColor1ATest.prep(f);
        for(int i=0;i<f.getJSONArray("cases").length();i++) {
            var c=f.getJSONArray("cases").getJSONObject(i);
            var old=legacy(c,M10RRenderedColor1ATest.ints(c.getJSONArray("gains")));
            for(boolean colour:new boolean[]{false,true})for(boolean order:new boolean[]{false,true}) {
                var meter=M10RExposureRenderer1M.select(old,prep,true,colour,order);
                var preview=old.withRenderedColor(prep,colour,order);
                assertEquals(M10RExposureRenderer1M.expectedRevision(true,colour,order),meter.revision);
                assertEquals(preview.revision,meter.revision);
                assertEquals(old.cameraKey,meter.cameraKey);assertEquals(old.frameTimestampNs,meter.frameTimestampNs);
                for(String name:new String[]{"sourceToTarget","targetToWorking","workingToOutput"}) {
                    Field a=meter.getClass().getDeclaredField(name);a.setAccessible(true);
                    assertArrayEquals((double[])a.get(preview),(double[])a.get(meter),0);
                }
                Field a=meter.getClass().getDeclaredField("cc1BeforeDg");a.setAccessible(true);
                assertEquals(colour&&order,a.getBoolean(meter));
                assertFalse(a.getBoolean(old));
                assertSame(old,M10RExposureRenderer1M.select(old,prep,false,colour,order));
            }
        }
    }
    private static M10RExposure1A.Plan plan(String actual,String expected,double user) {
        var s=M10RExposureBaseline1FTest.SAFE;double[] grid=new double[352];Arrays.fill(grid,.12);
        var probe=new M10RExposure1A.Probe("cam",1,1,actual,123,123,1_000_000_000,1_010_000_000,
                10_000_000,200,.5,.25,M10RExposure1A.ProbeDomain.M10R_RENDERED_USER_EV_REFERENCE,
                grid,new M10RHighlightGuard1A.Stats[]{s,s,s,s},M10RHighlightGuard1A.noSubject(4),user,
                new M10RHighlightGuard1A.Stats[]{s,s,s});
        return M10RExposure1A.prepare(probe,new M10RExposure1A.Request("cam",1,expected,
                1_020_000_000,user,1.8,35,100,50000,true));
    }
    @Test public void preparationFailureCannotMasqueradeAsPhotographicMeterEvidence() throws Exception {
        JSONObject f=M10RRenderedColor1ATest.fixture(),c=f.getJSONArray("cases").getJSONObject(0);
        var old=legacy(c,new int[]{1,2000,1});
        var meter=M10RExposureRenderer1M.select(old,M10RRenderedColor1ATest.prep(f),true,true,true);
        assertEquals(M10RExposureNative1B.TARGET_REVISION,meter.revision);
        assertEquals(M10RExposure1A.Status.RENDERER_MISMATCH,
                plan(meter.revision,M10RExposureRenderer1M.expectedRevision(true,true,true),0).status);
    }
    @Test public void oldAndNewProbeRevisionsCannotCrossAuthorizeEachOther() {
        String old=M10RExposureNative1B.TARGET_REVISION;
        String current=M10RExposureRenderer1M.expectedRevision(true,true,true);
        assertEquals(M10RExposure1A.Status.RENDERER_MISMATCH,plan(old,current,0).status);
        assertEquals(M10RExposure1A.Status.RENDERER_MISMATCH,plan(current,old,0).status);
        for(double user:new double[]{-2,-1.1666666666666665,0,.5,2}) {
            var p=plan(current,current,user);assertTrue(p.ready());
            assertEquals(0,p.appliedAutoEv,0);assertEquals(user,p.totalIntentEv,0);
            assertEquals(user-.75,p.deltaFromReferenceEv,1e-12);
        }
    }
}
