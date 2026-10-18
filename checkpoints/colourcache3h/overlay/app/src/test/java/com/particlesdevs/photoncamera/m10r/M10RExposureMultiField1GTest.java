package com.particlesdevs.photoncamera.m10r;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import org.json.*;
import org.junit.Test;
import static org.junit.Assert.*;

public class M10RExposureMultiField1GTest {
    // Recorded regional separation lies just below the full-confidence boundary.
    static final double TREE_EV=.49955034217124494;
    static final class Fixture {
        final double legacy;final double[] regions=new double[24];
        final M10RHighlightGuard1A.Stats[] positive,baseline;
        Fixture(String name)throws Exception {
            try(InputStream stream=getClass().getResourceAsStream("/exposure1g/"+name+".json")) {
                assertNotNull(stream);JSONObject d=new JSONObject(new String(stream.readAllBytes(),StandardCharsets.UTF_8));
                legacy=d.getDouble("legacyEv");for(int f=0;f<24;f++)regions[f]=d.getJSONArray("regions").getDouble(f);
                positive=readStats(d.getJSONArray("positive"));baseline=readStats(d.getJSONArray("baseline"));
            }
        }
        M10RMultiField1G.Decision decision(){return M10RMultiField1G.evaluate(regions,legacy,baseline[0],positive,M10RHighlightGuard1A.noSubject(4));}
        double[] grid() {
            double[] grid=new double[352];
            for(int r=0;r<4;r++)for(int c=0;c<6;c++)
                for(int y=r*16/4;y<(r+1)*16/4;y++)for(int x=c*22/6;x<(c+1)*22/6;x++)grid[y*22+x]=regions[r*6+c];
            return grid;
        }
    }
    static M10RHighlightGuard1A.Stats[] readStats(JSONArray a)throws Exception {
        var result=new M10RHighlightGuard1A.Stats[a.length()];
        for(int i=0;i<a.length();i++) {
            var d=a.getJSONObject(i);int[] q=new int[24];double[] b=new double[24],c=new double[24];
            for(int f=0;f<24;f++){q[f]=d.getJSONArray("fieldQ90").getInt(f);b[f]=d.getJSONArray("fieldNearWhiteFraction").getDouble(f);c[f]=d.getJSONArray("fieldChannelClipFraction").getDouble(f);}
            result[i]=new M10RHighlightGuard1A.Stats(d.getDouble("nearWhiteFraction"),d.getDouble("channelClipFraction"),q,b,c);
        }
        return result;
    }
    static M10RHighlightGuard1A.Stats change(M10RHighlightGuard1A.Stats s,double globalClip,int field,double bright,double clip) {
        int[] q=new int[24];double[] b=new double[24],c=new double[24];
        for(int f=0;f<24;f++){q[f]=s.q90(f);b[f]=s.bright(f);c[f]=s.clipped(f);}
        if(field>=0){b[field]=bright;c[field]=clip;}
        return new M10RHighlightGuard1A.Stats(s.bright,globalClip,q,b,c);
    }
    @Test public void recordedTreeGetsAboutHalfStopAndFoliageRemainsNeutral()throws Exception {
        for(String name:new String[]{"tree","foliage"}) {
            var f=new Fixture(name);var d=f.decision();var limit=M10RHighlightGuard1A.limit(f.positive,d.progress());
            double applied=Math.min(d.requestedEv,limit.maxPositiveEv);
            assertEquals(name.equals("tree")?TREE_EV:0,applied,1e-12);
            assertEquals(name.equals("tree"),d.scene.qualified);
            assertEquals(0,M10RExposureBaseline1F.evaluate(f.baseline).correctionEv,0);
            if(name.equals("tree")) {
                assertEquals(.25,M10RHighlightGuard1A.limit(f.positive,M10RHighlightGuard1A.noSubject(4)).maxPositiveEv,0);
                assertEquals(.5,limit.maxPositiveEv,0);assertEquals(3,limit.firstRejectedStep);
                assertTrue(d.foregroundQ90(2)>d.foregroundQ90(1));
            }
            System.out.println("E1G_REPLAY "+new JSONObject().put("scene",name).put("qualified",d.scene.qualified)
                    .put("legacyRequestedEv",f.legacy).put("newRequestedEv",d.requestedEv).put("appliedAutoEv",applied)
                    .put("limitEv",limit.maxPositiveEv).put("foregroundMask",d.scene.foregroundMask)
                    .put("backgroundMask",d.scene.backgroundMask).put("rawSeparationEv",d.scene.separationEv));
        }
    }
    @Test public void backgroundExceptionDoesNotWaiveClippingOrForegroundGrowth()throws Exception {
        var f=new Fixture("tree");var d=f.decision();var evidence=d.progress()[2];
        assertTrue(evidence.nearWhiteBackgroundMask!=0);assertFalse(evidence.canDeferBackgroundChannelClip);
        assertEquals(M10RHighlightGuard1A.Stop.NONE,M10RHighlightGuard1A.stopReason(f.positive[0],f.positive[2],evidence));
        var tooMuchClip=change(f.positive[2],.031,-1,0,0);
        assertNotEquals(M10RHighlightGuard1A.Stop.NONE,M10RHighlightGuard1A.stopReason(f.positive[0],tooMuchClip,evidence));
        var globalClip=change(f.positive[2],.09,-1,0,0);
        assertEquals(M10RHighlightGuard1A.Stop.GLOBAL_CHANNEL_CLIP_GROWTH,M10RHighlightGuard1A.stopReason(f.positive[0],globalClip,evidence));
        int subject=Integer.numberOfTrailingZeros(d.scene.foregroundMask);
        for(var unsafe:new M10RHighlightGuard1A.Stats[]{change(f.positive[2],f.positive[2].clipped,subject,.03,0),
                change(f.positive[2],f.positive[2].clipped,subject,0,.021)})
            assertNotEquals(M10RHighlightGuard1A.Stop.NONE,M10RHighlightGuard1A.stopReason(f.positive[0],unsafe,evidence));
    }
    @Test public void regionalChannelClippingStillStopsEvenWhenNearWhiteExceptionQualifies()throws Exception {
        var f=new Fixture("tree");var d=f.decision();
        // Two background regions whose baseline q90 is below the inherited 220 exclusion.
        var candidate=change(f.positive[2],.02,0,f.positive[2].bright(0),.10);
        candidate=change(candidate,.02,6,candidate.bright(6),.10);
        assertEquals(M10RHighlightGuard1A.Stop.REGIONAL_CHANNEL_CLIP_GROWTH,
                M10RHighlightGuard1A.stopReason(f.positive[0],candidate,d.progress()[2]));
    }
    @Test public void subjectMustImproveBeforeExceptionIsIssued()throws Exception {
        var f=new Fixture("tree");f.positive[2]=f.positive[1];var d=f.decision();
        assertEquals(0,d.progress()[2].nearWhiteBackgroundMask);
    }
    @Test public void explicitUserEvReferenceRemovalManualAndStaleRulesRemainIntact()throws Exception {
        var f=new Fixture("tree");
        for(double user:new double[]{-1,0,1}) {
            // Synthetic binding test: candidate fixtures are declared at each user
            // reference here; this is not a photometric simulation of +/-1 EV.
            var p=probe(f,user,.5,.25,f.baseline);var r=request(user,true,1_020_000_000);
            var plan=M10RExposure1A.prepare(p,r);assertTrue(plan.ready());
            assertEquals(TREE_EV,plan.appliedAutoEv,1e-12);assertEquals(user+TREE_EV,plan.totalIntentEv,1e-12);
            assertEquals(user+TREE_EV-.75,plan.deltaFromReferenceEv,1e-12);
            var expected=M10RAe1BPolicy.solve(10_000_000,200,1.8,35,user+TREE_EV-.75,100,50000).oracle;
            var selected=M10RExposureCapture1B.select(p,r,null,new M10RExposureCapture1B.Limits(1,1_000_000_000,50,6400));
            assertEquals(expected.iso,selected.iso);assertEquals(10_000_000.0*200*Math.pow(2,user+TREE_EV-.75),(double)selected.exposureNs*selected.iso,selected.iso*.51);
            assertEquals(expected.shutterSeconds,selected.allocation.oracle.shutterSeconds,0);
            assertEquals(M10RExposure1A.Status.BYPASS_MANUAL,M10RExposure1A.prepare(p,request(user,false,1_020_000_000)).status);
            assertEquals(M10RExposure1A.Status.STALE_OR_FUTURE,M10RExposure1A.prepare(p,request(user,true,2_300_000_000L)).status);
            assertEquals(M10RExposure1A.Status.USER_EV_MISMATCH,M10RExposure1A.prepare(p,request(user+.5,true,1_020_000_000)).status);
        }
    }
    @Test public void baselineProtectionOverridesAssistAndUnqualifiedNegativeMeterIsPreserved()throws Exception {
        var f=new Fixture("tree");var bad=change(f.baseline[0],.10,-1,0,0);
        var plan=M10RExposure1A.prepare(probe(f,0,0,0,new M10RHighlightGuard1A.Stats[]{bad,f.baseline[1],f.baseline[2]}),request(0,true,1_020_000_000));
        assertTrue(plan.multiField.scene.qualified);assertEquals(-.25,plan.appliedAutoEv,0);
        var unqualified=new Fixture("foliage");
        var negative=M10RMultiField1G.evaluate(unqualified.regions,-.3,unqualified.baseline[0],unqualified.positive,M10RHighlightGuard1A.noSubject(4));
        assertEquals(-.3,negative.requestedEv,0);assertEquals(0,negative.progress()[2].nearWhiteBackgroundMask);
    }
    @Test public void missingNeutralEvidenceSuppressesPositiveDecisionAndKeepsGuard()throws Exception {
        var f=new Fixture("tree");var d=M10RMultiField1G.evaluate(f.regions,f.legacy,null,f.positive,M10RHighlightGuard1A.noSubject(4));
        assertFalse(d.scene.qualified);assertEquals(0,d.requestedEv,0);
        assertTrue(f.legacy>0);assertEquals("positive_assist_missing_neutral_evidence",d.reason);
        assertEquals(.25,M10RHighlightGuard1A.limit(f.positive,d.progress()).maxPositiveEv,0);
    }
    @Test public void flatDarkFlatBrightSmallLampAndDisconnectedPatchesDoNotQualify() {
        double[] raw=new double[24];Arrays.fill(raw,.01);int all=(1<<24)-1;
        assertFalse(MultiFieldScene1G.evaluate(raw,all,0).qualified);
        assertFalse(MultiFieldScene1G.evaluate(raw,0,all).qualified);
        raw[0]=1;assertFalse(MultiFieldScene1G.evaluate(raw,all^1,1).qualified);
        int dark=0,bright=0;for(int f=0;f<24;f++)if(((f/6+f%6)&1)==0){dark|=1<<f;raw[f]=.01;}else{bright|=1<<f;raw[f]=.5;}
        assertFalse(MultiFieldScene1G.evaluate(raw,dark,bright).qualified);
        raw[0]=Double.NaN;assertFalse(MultiFieldScene1G.evaluate(raw,dark,bright).qualified);
    }
    @Test public void geometrySurvivesHorizontalVerticalAndHalfTurnReflections()throws Exception {
        var f=new Fixture("tree");var d=f.decision();
        for(int mode=1;mode<=3;mode++) {
            double[] raw=new double[24];int foreground=0,background=0;
            for(int i=0;i<24;i++) {
                int y=i/6,x=i%6;if((mode&1)!=0)x=5-x;if((mode&2)!=0)y=3-y;int n=y*6+x;raw[n]=f.regions[i];
                if((d.scene.foregroundMask&(1<<i))!=0)foreground|=1<<n;
                if((d.scene.backgroundMask&(1<<i))!=0)background|=1<<n;
            }
            var scene=MultiFieldScene1G.evaluate(raw,foreground,background);assertTrue(scene.qualified);
            assertEquals(d.scene.separationEv,scene.separationEv,1e-12);
        }
    }
    @Test public void evidenceRecordsOriginalRequestMasksAndEligibleSteps()throws Exception {
        var f=new Fixture("tree");var plan=M10RExposure1A.prepare(probe(f,0,0,0,f.baseline),request(0,true,1_020_000_000));
        var d=M10RExposureEvidence1G.build(plan);assertTrue(d.getBoolean("qualified"));assertEquals(TREE_EV,d.getDouble("appliedAutoEv"),1e-12);
        assertEquals(0,d.getInt("additionalRawOrRenderPasses"));assertFalse(d.getBoolean("otherRenderersEnabled"));
        assertTrue(d.getJSONArray("candidates").getJSONObject(2).getBoolean("nearWhiteBackgroundExceptionEligible"));
        assertFalse(d.getJSONArray("candidates").getJSONObject(3).getBoolean("nearWhiteBackgroundExceptionEligible"));
        var progress=plan.multiField.progress();progress[2]=M10RHighlightGuard1A.SubjectProgress.none();
        assertTrue(plan.multiField.progress()[2].nearWhiteBackgroundMask!=0);
    }
    static M10RExposure1A.Probe probe(Fixture f,double user,double refUser,double refAuto,M10RHighlightGuard1A.Stats[] lower) {
        return new M10RExposure1A.Probe("cam",1,1,"renderer",123,123,1_000_000_000,1_010_000_000,
                10_000_000,200,refUser,refAuto,M10RExposure1A.ProbeDomain.M10R_RENDERED_USER_EV_REFERENCE,
                f.grid(),f.positive,M10RHighlightGuard1A.noSubject(4),user,lower);
    }
    static M10RExposure1A.Request request(double user,boolean auto,long now) {
        return new M10RExposure1A.Request("cam",1,"renderer",now,user,1.8,35,100,50000,auto);
    }
}
