package com.particlesdevs.photoncamera.m10r;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import org.json.*;
import org.junit.Test;
import static org.junit.Assert.*;

public class M10RExposureSceneQual1OTest {
    @Test public void recordedCapturesSuppressOnlyUnqualifiedPositiveAssistance()throws Exception {
        JSONArray rows;
        try(InputStream s=getClass().getResourceAsStream("/scenequal1o/recorded_captures.json")) {
            assertNotNull(s);rows=new JSONArray(new String(s.readAllBytes(),StandardCharsets.UTF_8));
        }
        int changed=0,qualified=0,negative=0;
        for(int n=0;n<rows.length();n++) {
            var row=rows.getJSONObject(n);String id=row.getString("id");double[] regions=new double[24];
            for(int f=0;f<24;f++)regions[f]=row.getJSONArray("regions").getDouble(f);
            var pos=M10RExposureMultiField1GTest.readStats(row.getJSONArray("positive"));
            var base=M10RExposureMultiField1GTest.readStats(row.getJSONArray("baseline"));
            double legacy=row.getDouble("legacyEv");
            var d=M10RMultiField1G.evaluate(regions,legacy,base[0],pos,M10RHighlightGuard1A.noSubject(pos.length));
            // MIDGAP1S admits this previously rejected geometry through two
            // supported intermediate fields, retaining the half-stop ceiling.
            boolean bridge=id.equals("IMG_20261017_083319_M10R_CAPTURE1B.json");
            assertEquals(id,row.getBoolean("recordedQualified")||bridge,d.scene.qualified);
            var limit=M10RHighlightGuard1A.limit(pos,d.progress());
            assertEquals(id,row.getDouble("recordedLimitEv"),limit.maxPositiveEv,0);
            double request=M10RExposureRange1H.requested(legacy,row.getDouble("beforeCapEv"),d,pos.length);
            double applied=request>0?Math.min(request,limit.maxPositiveEv):request;
            double baseline=M10RExposureBaseline1F.evaluate(base).correctionEv;
            assertEquals(id,row.getDouble("recordedBaselineEv"),baseline,0);
            if(baseline<0)applied=Math.min(applied,baseline);
            boolean suppress=legacy>0&&!d.scene.qualified;
            assertEquals(id,bridge?.5:suppress?0:row.getDouble("recordedAutoEv"),applied,1e-12);
            if(bridge){assertTrue(d.scene.midtoneBridge);assertTrue(d.positiveRequestLimitEv<=.5);}
            if(suppress){changed++;assertEquals("positive_assist_unqualified_foreground",d.reason);}
            if(d.scene.qualified)qualified++;
            if(applied<0)negative++;
        }
        assertEquals(13,rows.length());assertEquals(3,changed);assertEquals(2,qualified);assertEquals(1,negative);
    }

    @Test public void widerMeasuredRangeCannotReviveZeroOrNegativeRegionalDecision() {
        for(int count:new int[]{4,7})for(double beforeCap:new double[]{.31,.42,1.2,3}) {
            assertEquals(0,M10RExposureRange1H.requested(.75,beforeCap,0,count),0);
            assertEquals(-.25,M10RExposureRange1H.requested(.75,beforeCap,-.25,count),0);
        }
    }

    static M10RExposure1A.Probe unqualified(double user,double refUser,double refAuto) {
        var stats=new M10RHighlightGuard1A.Stats[7];Arrays.fill(stats,M10RExposureBaseline1FTest.SAFE);
        return new M10RExposure1A.Probe("cam",1,1,"renderer",123,123,1_000_000_000,1_010_000_000,
                10_000_000,200,refUser,refAuto,M10RExposure1A.ProbeDomain.M10R_RENDERED_USER_EV_REFERENCE,
                M10RExposureRange1HTest.backlit(),stats,M10RHighlightGuard1A.noSubject(7),user,
                new M10RHighlightGuard1A.Stats[]{stats[0],stats[0],stats[0]});
    }

    @Test public void rawContrastCannotBrightenOpenRenderedSceneAndUserIntentIsAppliedOnce() {
        for(double user:new double[]{-1.25,-2.0/3,0,.75}) {
            var probe=unqualified(user,.5,.25);var request=M10RExposureRange1HTest.request(user,true,1_020_000_000L);
            var p=M10RExposure1A.prepare(probe,request);
            assertTrue(p.ready());assertTrue(p.mfm.recommendedEv>0);assertFalse(p.multiField.scene.qualified);
            assertEquals(0,p.requestedAutoEv,0);assertEquals(0,p.appliedAutoEv,0);
            assertEquals(user,p.totalIntentEv,0);assertEquals(user-.75,p.deltaFromReferenceEv,1e-12);
            var selected=M10RExposureCapture1B.select(probe,request,null,
                    new M10RExposureCapture1B.Limits(1,1_000_000_000L,50,6400));
            var expected=M10RAe1BPolicy.solve(10_000_000,200,1.8,35,user-.75,100,50000).oracle;
            assertTrue(selected.apply);assertFalse(selected.fallback);
            assertEquals(expected.iso,selected.iso);assertEquals(10_000_000.0*200*Math.pow(2,user-.75),(double)selected.exposureNs*selected.iso,selected.iso*.51);
            assertEquals(expected.shutterSeconds,selected.allocation.oracle.shutterSeconds,0);
        }
    }

    @Test public void missingOrRejectedEvidenceDoesNotInventAnAutomaticCorrection() {
        var p=unqualified(0,0,0);
        assertEquals(M10RExposure1A.Status.BYPASS_MANUAL,M10RExposure1A.prepare(p,
                M10RExposureRange1HTest.request(0,false,1_020_000_000L)).status);
        assertEquals(M10RExposure1A.Status.STALE_OR_FUTURE,M10RExposure1A.prepare(p,
                M10RExposureRange1HTest.request(0,true,2_300_000_000L)).status);
        assertEquals(M10RExposure1A.Status.USER_EV_MISMATCH,M10RExposure1A.prepare(p,
                M10RExposureRange1HTest.request(.5,true,1_020_000_000L)).status);
    }

    @Test public void diagnosticDistinguishesRejectedDemandFromAvailableHighlightHeadroom()throws Exception {
        var plan=M10RExposure1A.prepare(unqualified(0,0,0),M10RExposureRange1HTest.request(0,true,1_020_000_000L));
        var d=M10RExposureEvidence1G.build(plan);
        assertEquals(M10RMultiField1G.REVISION,d.getString("revision"));
        assertTrue(d.getBoolean("positiveAssistRequiresQualifiedForeground"));
        assertTrue(d.getBoolean("legacyPositiveSuppressed"));assertTrue(d.getDouble("positiveLimitEv")>0);
        assertEquals(0,d.getDouble("requestedAutoEv"),0);assertEquals(0,d.getDouble("fixedExposureBiasEv"),0);
    }
}
