package com.particlesdevs.photoncamera.m10r;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import org.json.*;
import org.junit.Test;
import static org.junit.Assert.*;

public class M10RExposureSplitBg1PTest {
    // The weaker bright group falls below the existing full-confidence boundary.
    static final double ROOM_EV=0.4821207373029584;
    static class Fixture {
        final double[] regions=new double[24];
        final M10RHighlightGuard1A.Stats[] positive,baseline;
        final double legacy,beforeCap;
        Fixture()throws Exception {
            try(InputStream s=getClass().getResourceAsStream("/splitbg1p/room_121049.json")) {
                assertNotNull(s);var d=new JSONObject(new String(s.readAllBytes(),StandardCharsets.UTF_8));
                for(int i=0;i<24;i++)regions[i]=d.getJSONArray("regions").getDouble(i);
                legacy=d.getDouble("legacyEv");beforeCap=d.getDouble("beforeCapEv");
                positive=M10RExposureMultiField1GTest.readStats(d.getJSONArray("positive"));
                baseline=M10RExposureMultiField1GTest.readStats(d.getJSONArray("baseline"));
            }
        }
        M10RMultiField1G.Decision decision(){return M10RMultiField1G.evaluate(regions,legacy,baseline[0],positive,M10RHighlightGuard1A.noSubject(positive.length));}
        double[] grid() {
            double[] g=new double[352];
            for(int r=0;r<4;r++)for(int c=0;c<6;c++)
                for(int y=r*16/4;y<(r+1)*16/4;y++)for(int x=c*22/6;x<(c+1)*22/6;x++)g[y*22+x]=regions[r*6+c];
            return g;
        }
        M10RExposure1A.Probe probe(double user,double refUser,double refAuto) {
            return new M10RExposure1A.Probe("cam",1,1,"renderer",123,123,1_000_000_000,1_010_000_000,
                    10_000_000,206,refUser,refAuto,M10RExposure1A.ProbeDomain.M10R_RENDERED_USER_EV_REFERENCE,
                    grid(),positive,M10RHighlightGuard1A.noSubject(positive.length),user,baseline);
        }
        M10RExposure1A.Plan plan(){return M10RExposure1A.prepare(probe(0,0,0),M10RExposureRange1HTest.request(0,true,1_020_000_000L));}
    }
    static M10RHighlightGuard1A.Stats edit(M10RHighlightGuard1A.Stats s,int mask,Integer value,
            Double bright,Double clip,Double globalClip) {
        int[] q=new int[24];double[] b=new double[24],c=new double[24];
        for(int f=0;f<24;f++) {
            boolean selected=(mask&(1<<f))!=0;
            q[f]=selected&&value!=null?value:s.q90(f);
            b[f]=selected&&bright!=null?bright:s.bright(f);
            c[f]=selected&&clip!=null?clip:s.clipped(f);
        }
        return new M10RHighlightGuard1A.Stats(s.bright,globalClip==null?s.clipped:globalClip,q,b,c);
    }
    static int flip(int i,int mode){int y=i/6,x=i%6;return ((mode&2)==0?y:3-y)*6+((mode&1)==0?x:5-x);}
    static M10RHighlightGuard1A.Stats flip(M10RHighlightGuard1A.Stats s,int mode) {
        int[] q=new int[24];double[] b=new double[24],c=new double[24];
        for(int f=0;f<24;f++){int n=flip(f,mode);q[n]=s.q90(f);b[n]=s.bright(f);c[n]=s.clipped(f);}
        return new M10RHighlightGuard1A.Stats(s.bright,s.clipped,q,b,c);
    }

    @Test public void recordedRoomGetsBoundedAssistInsteadOfUncappedContrastDemand()throws Exception {
        var f=new Fixture();var d=f.decision();
        assertTrue(d.scene.qualified);assertTrue(d.scene.splitBackground);assertEquals(2,d.scene.backgroundComponents);
        assertEquals(14,Integer.bitCount(d.scene.foregroundMask));assertEquals(5,Integer.bitCount(d.scene.backgroundMask));
        assertEquals(ROOM_EV,d.requestedEv,1e-12);assertEquals(ROOM_EV,d.positiveRequestLimitEv,1e-12);
        assertEquals(44.857142857142854,d.foregroundQ90(0),1e-12);
        assertEquals(63.357142857142854,d.foregroundQ90(2),1e-12);
        assertTrue(f.beforeCap>1.5);
        assertEquals(ROOM_EV,M10RExposureRange1H.requested(f.legacy,f.beforeCap,d,7),1e-12);
        assertEquals(ROOM_EV,M10RExposureRange1H.requested(f.legacy,10,d,4),1e-12);
        for(var p:d.progress()){assertEquals(0,p.nearWhiteBackgroundMask);assertFalse(p.canDeferBackgroundChannelClip);}
        // CLIPGROWTH1R limits further clipping; the bounded ROOM_EV request remains below this ceiling.
        assertEquals(1.25,M10RHighlightGuard1A.limit(f.positive,d.progress()).maxPositiveEv,0);
        var plan=f.plan();assertTrue(plan.ready());assertEquals(ROOM_EV,plan.appliedAutoEv,1e-12);
    }

    @Test public void isolatedLightsAndInteriorPatchesCannotAccumulateIntoBrightBackground()throws Exception {
        var f=new Fixture();var scene=f.decision().scene;
        for(int bright:new int[]{(1<<6)|(1<<18),(1<<6)|(1<<7)|(1<<8)|(1<<18),
                (1<<7)|(1<<8)|(1<<13)|(1<<14)}) {
            int dark=scene.foregroundMask&~bright;
            assertFalse(MultiFieldScene1G.evaluate(f.regions,dark,bright).qualified);
        }
    }

    @Test public void eachSeparateGroupMustSupportRawSeparation()throws Exception {
        var f=new Fixture();var d=f.decision();f.regions[18]=.001;f.regions[19]=.001;
        var scene=MultiFieldScene1G.evaluate(f.regions,d.scene.foregroundMask,d.scene.backgroundMask);
        assertFalse(scene.qualified);assertEquals("insufficient_raw_separation",scene.reason);
        f.regions[18]=0;f.regions[19]=0;
        scene=MultiFieldScene1G.evaluate(f.regions,d.scene.foregroundMask,d.scene.backgroundMask);
        assertFalse(scene.qualified);assertTrue(Double.isFinite(scene.separationEv));
    }

    @Test public void reflectedGeometryAndRenderedMeasurementsGiveSameBound()throws Exception {
        var original=new Fixture();var expected=original.decision();
        for(int mode=1;mode<=3;mode++) {
            var f=new Fixture();for(int i=0;i<24;i++)f.regions[flip(i,mode)]=original.regions[i];
            for(int i=0;i<f.positive.length;i++)f.positive[i]=flip(original.positive[i],mode);
            for(int i=0;i<f.baseline.length;i++)f.baseline[i]=flip(original.baseline[i],mode);
            var d=f.decision();assertTrue(d.scene.qualified);assertTrue(d.scene.splitBackground);
            assertEquals(expected.scene.separationEv,d.scene.separationEv,1e-12);assertEquals(ROOM_EV,d.requestedEv,1e-12);
        }
    }

    @Test public void alreadyOpenForegroundDoesNotReceiveExtraAutomaticLift()throws Exception {
        for(int q:new int[]{96,110,129}) {
            var f=new Fixture();int mask=f.decision().scene.foregroundMask;
            f.positive[0]=edit(f.positive[0],mask,q,null,null,null);
            var d=f.decision();assertTrue(d.scene.qualified);assertEquals(0,d.requestedEv,0);
            assertEquals(0,M10RExposureRange1H.requested(f.legacy,f.beforeCap,d,7),0);
        }
    }

    @Test public void searchStopsAtMissingProgressWithoutJumpingToLaterRecovery()throws Exception {
        var f=new Fixture();f.positive[1]=f.positive[0];assertEquals(0,f.decision().requestedEv,0);
        f=new Fixture();f.positive[2]=f.positive[1];assertEquals(.25,f.decision().requestedEv,0);
    }

    @Test public void searchStopsOnceForegroundLeavesDarkRange()throws Exception {
        var f=new Fixture();int mask=f.decision().scene.foregroundMask;
        f.positive[0]=edit(f.positive[0],mask,90,null,null,null);
        f.positive[1]=edit(f.positive[1],mask,100,null,null,null);
        f.positive[2]=edit(f.positive[2],mask,110,null,null,null);
        assertEquals(.25,f.decision().requestedEv,0);
    }

    @Test public void anyForegroundFieldOverBrightnessOrClippingBoundStopsTheSearch()throws Exception {
        for(int step:new int[]{1,2})for(int failure=0;failure<3;failure++) {
            var f=new Fixture();int field=Integer.lowestOneBit(f.decision().scene.foregroundMask);
            f.positive[step]=edit(f.positive[step],field,failure==0?129:null,
                    failure==1?.02:null,failure==2?.02:null,null);
            assertEquals((step-1)*.25,f.decision().requestedEv,0);
        }
    }

    @Test public void existingHighlightProtectionAndNegativeWithoutNeutralEvidenceStillWin()throws Exception {
        var f=new Fixture();f.positive[0]=edit(f.positive[0],0,null,null,null,.005);
        f.positive[1]=edit(f.positive[1],0,null,null,null,.10);
        var plan=f.plan();assertEquals(ROOM_EV,plan.requestedAutoEv,1e-12);assertEquals(0,plan.appliedAutoEv,0);
        assertEquals(M10RHighlightGuard1A.Stop.GLOBAL_CHANNEL_CLIP_GROWTH,plan.highlight.stop);
        f=new Fixture();f.baseline[0]=edit(f.baseline[0],0,null,null,null,.10);
        for(int i=1;i<3;i++)f.baseline[i]=edit(f.baseline[i],0,null,null,null,.005);
        assertEquals(-.25,f.plan().appliedAutoEv,0);
        var d=M10RMultiField1G.evaluate(f.regions,-.3,null,f.positive,M10RHighlightGuard1A.noSubject(7));
        assertEquals(-.3,d.requestedEv,0);assertEquals(-.3,M10RExposureRange1H.requested(-.3,-.3,d,7),0);
    }

    @Test public void explicitIntentAndDiagnosticCeilingRemainBoundThroughAllocator()throws Exception {
        var f=new Fixture();
        for(double user:new double[]{-1.25,-2.0/3,0,.75}) {
            // Binding test: the same measured statistics are declared at each
            // reference; this does not simulate a different user-EV photograph.
            var p=f.probe(user,.5,.25);var r=M10RExposureRange1HTest.request(user,true,1_020_000_000L);
            var plan=M10RExposure1A.prepare(p,r);assertEquals(user+ROOM_EV,plan.totalIntentEv,1e-12);
            assertEquals(user+ROOM_EV-.75,plan.deltaFromReferenceEv,1e-12);
            var s=M10RExposureCapture1B.select(p,r,null,new M10RExposureCapture1B.Limits(1,1_000_000_000L,50,6400));
            var expected=M10RAe1BPolicy.solve(10_000_000,206,1.8,35,user+ROOM_EV-.75,100,50000).oracle;
            assertEquals(expected.iso,s.iso);assertEquals(10_000_000.0*206*Math.pow(2,user+ROOM_EV-.75),(double)s.exposureNs*s.iso,s.iso*.51);
            assertEquals(expected.shutterSeconds,s.allocation.oracle.shutterSeconds,0);
            var d=M10RExposureEvidence1G.build(plan);
            assertTrue(d.getBoolean("splitBrightBackground"));assertEquals(2,d.getInt("brightBackgroundComponents"));
            assertEquals(ROOM_EV,d.getDouble("positiveRequestLimitEv"),1e-12);assertTrue(d.getBoolean("legacyPositiveReduced"));
            assertEquals(M10RExposure1A.Status.BYPASS_MANUAL,M10RExposure1A.prepare(p,M10RExposureRange1HTest.request(user,false,1_020_000_000L)).status);
            assertEquals(M10RExposure1A.Status.STALE_OR_FUTURE,M10RExposure1A.prepare(p,M10RExposureRange1HTest.request(user,true,2_300_000_000L)).status);
        }
    }
}
