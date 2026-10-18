package com.particlesdevs.photoncamera.m10r;

import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import org.json.*;
import org.junit.Test;
import static org.junit.Assert.*;

public class M10RExposureClipGrowth1RTest {
    static JSONArray captures()throws Exception {
        try(var s=M10RExposureClipGrowth1RTest.class.getResourceAsStream("/clipgrowth1r/recorded_captures.json")) {
            assertNotNull(s);return new JSONArray(new String(s.readAllBytes(),StandardCharsets.UTF_8));
        }
    }
    static M10RHighlightGuard1A.SubjectProgress[] progress(JSONObject d,int n)throws Exception {
        var out=M10RHighlightGuard1A.noSubject(n);var a=d.getJSONArray("progress");
        for(int i=0;i<a.length();i++)if(a.getJSONObject(i).getBoolean("nearWhiteBackgroundExceptionEligible"))
            out[i]=M10RHighlightGuard1A.SubjectProgress.forNearWhiteBackground(d.getInt("foregroundMask"),d.getInt("backgroundMask"));
        return out;
    }
    @Test public void recordedLatticesChangeOnlyTheClippedWindowAssistance()throws Exception {
        var rows=captures();int changed=0;
        for(int n=0;n<rows.length();n++) {
            var d=rows.getJSONObject(n);String id=d.getString("id");
            var p=M10RExposureMultiField1GTest.readStats(d.getJSONArray("positive"));
            var b=M10RExposureMultiField1GTest.readStats(d.getJSONArray("baseline"));
            var limit=M10RHighlightGuard1A.limit(p,progress(d,p.length));
            double baseline=M10RExposureBaseline1F.evaluate(b).correctionEv;
            assertEquals(id,d.getDouble("recordedBaselineEv"),baseline,0);
            double request=d.getDouble("requestedEv"),applied=request>0?Math.min(request,limit.maxPositiveEv):request;
            if(baseline<0)applied=Math.min(Math.min(applied,baseline),Math.min(0,d.getDouble("legacyEv")));
            boolean window=id.contains("150451");
            assertEquals(id,window?1.0:d.getDouble("recordedAppliedEv"),applied,1e-12);
            if(window) {
                changed++;assertEquals(1.5,d.getDouble("recordedAppliedEv"),0);
                assertEquals(5,limit.firstRejectedStep);
                assertEquals(M10RHighlightGuard1A.Stop.GLOBAL_EXISTING_CHANNEL_CLIP_GROWTH,limit.stop);
                // The prior inverse predicate still sees no proven starting loss.
                assertEquals(0,baseline,0);
            }
            if(id.contains("152323")){assertEquals(0,applied,0);assertEquals(1.25,limit.maxPositiveEv,0);}
        }
        assertEquals(20,rows.length());assertEquals(1,changed);
    }
    static M10RHighlightGuard1A.Stats flat(double clip) {
        int[] q=new int[24];Arrays.fill(q,255);double[] a=new double[24];Arrays.fill(a,clip);
        return new M10RHighlightGuard1A.Stats(clip,clip,q,a,a);
    }
    @Test public void preexistingClippingWithoutGrowthDoesNotDarkenScene() {
        var s=flat(.35);var p=new M10RHighlightGuard1A.Stats[]{s,s,s,s};
        assertEquals(.75,M10RHighlightGuard1A.limit(p,M10RHighlightGuard1A.noSubject(4)).maxPositiveEv,0);
        assertEquals(0,M10RExposureBaseline1F.evaluate(new M10RHighlightGuard1A.Stats[]{s,s,s}).correctionEv,0);
    }
    @Test public void newPositiveRuleDoesNotBecomeANegativeBaselineRule() {
        var low=flat(.10);var high=flat(.14);
        assertEquals(M10RHighlightGuard1A.Stop.NONE,M10RHighlightGuard1A.stopReason(low,high,M10RHighlightGuard1A.SubjectProgress.none()));
        assertEquals(0,M10RExposureBaseline1F.evaluate(new M10RHighlightGuard1A.Stats[]{high,low,low}).correctionEv,0);
        assertEquals(0,M10RHighlightGuard1A.limit(new M10RHighlightGuard1A.Stats[]{low,high},M10RHighlightGuard1A.noSubject(2)).maxPositiveEv,0);
    }
    @Test public void cumulativeGrowthCannotHideBehindSmallIndividualSteps() {
        var p=new M10RHighlightGuard1A.Stats[]{flat(.09),flat(.10),flat(.12),flat(.13)};
        var limit=M10RHighlightGuard1A.limit(p,M10RHighlightGuard1A.noSubject(4));
        assertEquals(.5,limit.maxPositiveEv,0);assertEquals(3,limit.firstRejectedStep);
    }
    @Test public void rejectedStepCannotBeSkippedAndForegroundCannotWaiveIt() {
        var p=new M10RHighlightGuard1A.Stats[]{flat(.09),flat(.13),flat(.10),flat(.10)};
        var progress=M10RHighlightGuard1A.noSubject(4);
        progress[1]=M10RHighlightGuard1A.SubjectProgress.fromEvidence(1,true,true,true,true,true);
        assertTrue(progress[1].canDeferBackgroundChannelClip);
        assertEquals(0,M10RHighlightGuard1A.limit(p,progress).maxPositiveEv,0);
    }
    @Test public void originalLowBaselineRuleAndGrowthBoundaryRemainDistinct() {
        var p=new M10RHighlightGuard1A.Stats[]{flat(.01),flat(.09)};
        assertEquals(M10RHighlightGuard1A.Stop.GLOBAL_CHANNEL_CLIP_GROWTH,M10RHighlightGuard1A.limit(p,M10RHighlightGuard1A.noSubject(2)).stop);
        p=new M10RHighlightGuard1A.Stats[]{flat(.09),flat(.124),flat(.126)};
        var limit=M10RHighlightGuard1A.limit(p,M10RHighlightGuard1A.noSubject(3));
        assertEquals(.25,limit.maxPositiveEv,0);assertEquals(2,limit.firstRejectedStep);
    }
    @Test public void controllerPreservesUserIntentAndReportsPositiveOnlyReason()throws Exception {
        var f=new M10RExposureMultiField1GTest.Fixture("tree");
        for(int i=0;i<f.positive.length;i++)f.positive[i]=M10RExposureMultiField1GTest.change(f.positive[i],i==0?.09:.13,-1,0,0);
        for(double user:new double[]{-1.25,0,.75}) {
            // Binding exercise: these are fixed recorded statistics, not a
            // photographic simulation of altered user EV or RAW exposure.
            var probe=M10RExposureMultiField1GTest.probe(f,user,.5,.25,f.baseline);
            var request=M10RExposureMultiField1GTest.request(user,true,1_020_000_000L);
            var p=M10RExposure1A.prepare(probe,request);assertTrue(p.ready());
            assertTrue(p.requestedAutoEv>0);assertEquals(0,p.appliedAutoEv,0);
            assertEquals(user,p.totalIntentEv,0);assertEquals(user-.75,p.deltaFromReferenceEv,0);
            var evidence=M10RExposureEvidence1F.build(f.positive,f.baseline,p);
            assertEquals(M10RHighlightGuard1A.POSITIVE_REVISION,evidence.getString("positiveGuardRevision"));
            assertTrue(evidence.getBoolean("existingClipGrowthAppliesToPositiveAssistOnly"));
            assertEquals("GLOBAL_EXISTING_CHANNEL_CLIP_GROWTH",evidence.getString("positiveStop"));
            assertEquals(M10RExposure1A.Status.BYPASS_MANUAL,M10RExposure1A.prepare(probe,M10RExposureMultiField1GTest.request(user,false,1_020_000_000L)).status);
            assertEquals(M10RExposure1A.Status.STALE_OR_FUTURE,M10RExposure1A.prepare(probe,M10RExposureMultiField1GTest.request(user,true,2_300_000_000L)).status);
        }
    }
}
