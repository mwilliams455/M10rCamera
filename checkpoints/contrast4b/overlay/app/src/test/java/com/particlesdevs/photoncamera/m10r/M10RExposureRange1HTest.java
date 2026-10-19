package com.particlesdevs.photoncamera.m10r;

import java.util.Arrays;
import org.junit.Test;
import static org.junit.Assert.*;

public class M10RExposureRange1HTest {
    static final double SYNTHETIC_DEMAND=1.1783397459821496;
    // The wider-range tests need rendered dark-foreground evidence as well as
    // RAW contrast. Flat synthetic pixels can no longer authorize positive EV.
    static final M10RHighlightGuard1A.Stats SAFE=qualifiedStats(.005);
    static final M10RHighlightGuard1A.Stats CLIPPED=M10RExposureBaseline1FTest.CLIPPED;
    static double[] backlit() {
        double[] grid=new double[352];
        for(int y=0;y<16;y++)for(int x=0;x<22;x++)grid[y*22+x]=x<5?.5:(x>7&&x<16&&y>3&&y<12?.002:.025);
        return grid;
    }
    static M10RHighlightGuard1A.Stats[] stats(int count){var s=new M10RHighlightGuard1A.Stats[count];Arrays.fill(s,SAFE);return s;}
    static M10RExposure1A.Probe probe(int count,int rejectedStep,double user,boolean baselineLoss,double[] grid) {
        var candidates=stats(count);if(rejectedStep>=0)candidates[rejectedStep]=CLIPPED;
        return new M10RExposure1A.Probe("cam",1,1,"renderer",123,123,1_000_000_000,1_010_000_000,
                10_000_000,200,.5,.25,M10RExposure1A.ProbeDomain.M10R_RENDERED_USER_EV_REFERENCE,
                grid,candidates,M10RHighlightGuard1A.noSubject(count),user,
                new M10RHighlightGuard1A.Stats[]{baselineLoss?qualifiedStats(.10):SAFE,SAFE,SAFE});
    }
    static M10RHighlightGuard1A.Stats qualifiedStats(double clip) {
        int[] q=new int[24];double[] b=new double[24],c=new double[24];
        for(int f=0;f<24;f++)q[f]=f%6<2?200:70;
        return new M10RHighlightGuard1A.Stats(.02,clip,q,b,c);
    }
    static M10RExposure1A.Request request(double user,boolean auto,long now) {
        return new M10RExposure1A.Request("cam",1,"renderer",now,user,1.8,35,100,50000,auto);
    }
    static M10RExposure1A.Plan plan(int count,int rejectedStep,double user,boolean baselineLoss,double[] grid) {
        return M10RExposure1A.prepare(probe(count,rejectedStep,user,baselineLoss,grid),request(user,true,1_020_000_000));
    }
    @Test public void recordedFlowerDemandIsRetainedButLegacyEvidenceCannotAuthorizeIt() {
        double demand=1.0195660696518332;
        assertEquals(.75,M10RExposureRange1H.requested(.75,demand,.75,4),0);
        assertEquals(demand,M10RExposureRange1H.requested(.75,demand,.75,7),0);
        // This verifies demand handling only. There is no measured flower evidence
        // above +0.75 EV yet, so no final flower exposure is asserted here.
    }
    @Test public void widerCeilingIsNotAFixedLiftAndPreservesDeadbandAndNegativeRequests() {
        assertEquals(1.5,M10RExposureRange1H.requested(.75,3,.75,7),0);
        assertEquals(.4,M10RExposureRange1H.requested(.4,.4,.4,7),0);
        assertEquals(.49955,M10RExposureRange1H.requested(.28,.28,.49955,7),0);
        assertEquals(0,M10RExposureRange1H.requested(0,.07,0,7),0);
        assertEquals(-.3,M10RExposureRange1H.requested(-.3,-.3,-.3,7),0);
        assertEquals(.75,M10RExposureRange1H.requested(.75,Double.NaN,.75,7),0);
    }
    @Test public void completeSafeEvidenceCanDriveMoreThanThreeQuartersThroughRealAllocator() {
        double[] grid=backlit();var meter=M10RMfm1B.evaluate(grid);
        assertEquals(SYNTHETIC_DEMAND,meter.rawBlendEv,1e-12);
        var old=plan(4,-1,0,false,grid);var extended=plan(7,-1,0,false,grid);
        assertTrue(old.multiField.scene.qualified);assertTrue(extended.multiField.scene.qualified);
        assertEquals(.75,old.appliedAutoEv,0);assertEquals(SYNTHETIC_DEMAND,extended.appliedAutoEv,1e-12);
        var expected=M10RAe1BPolicy.solve(10_000_000,200,1.8,35,SYNTHETIC_DEMAND-.75,100,50000).oracle;
        var selected=M10RExposureCapture1B.select(probe(7,-1,0,false,grid),request(0,true,1_020_000_000),null,
                new M10RExposureCapture1B.Limits(1,1_000_000_000,50,6400));
        assertTrue(selected.apply);assertFalse(selected.fallback);
        assertEquals(expected.iso,selected.iso);assertEquals(10_000_000.0*200*Math.pow(2,SYNTHETIC_DEMAND-.75),(double)selected.exposureNs*selected.iso,selected.iso*.51);
        assertEquals(expected.shutterSeconds,selected.allocation.oracle.shutterSeconds,0);
    }
    @Test public void newCandidateFailureStopsAtPreviousSafeStepWithoutJumpingOverIt() {
        for(int step=1;step<7;step++) {
            var p=plan(7,step,0,false,backlit());assertTrue(p.ready());
            assertEquals(Math.min(SYNTHETIC_DEMAND,(step-1)*.25),p.appliedAutoEv,1e-12);assertEquals(step,p.highlight.firstRejectedStep);
            assertEquals(M10RHighlightGuard1A.Stop.GLOBAL_CHANNEL_CLIP_GROWTH,p.highlight.stop);
        }
    }
    @Test public void incompleteExtendedEvidenceNeverProducesReadyPlan() {
        for(int count:new int[]{2,3,5,6,8})
            assertEquals(M10RExposure1A.Status.INCOMPLETE_LATTICE,plan(count,-1,0,false,backlit()).status);
    }
    @Test public void userReferenceIntentAndManualStaleRulesRemainBound() {
        for(double user:new double[]{-1,0,1}) {
            var p=probe(7,-1,user,false,backlit());var ready=M10RExposure1A.prepare(p,request(user,true,1_020_000_000));
            assertEquals(user+SYNTHETIC_DEMAND,ready.totalIntentEv,1e-12);
            assertEquals(user+SYNTHETIC_DEMAND-.75,ready.deltaFromReferenceEv,1e-12);
            assertEquals(M10RExposure1A.Status.BYPASS_MANUAL,M10RExposure1A.prepare(p,request(user,false,1_020_000_000)).status);
            assertEquals(M10RExposure1A.Status.STALE_OR_FUTURE,M10RExposure1A.prepare(p,request(user,true,2_300_000_000L)).status);
            assertEquals(M10RExposure1A.Status.USER_EV_MISMATCH,M10RExposure1A.prepare(p,request(user+.5,true,1_020_000_000)).status);
        }
    }
    @Test public void baselineLossStillSuppressesExtendedLiftAndFlatSceneRemainsNeutral() {
        assertEquals(-.25,plan(7,-1,0,true,backlit()).appliedAutoEv,0);
        double[] flat=new double[352];Arrays.fill(flat,.12);
        assertEquals(0,plan(7,-1,0,false,flat).appliedAutoEv,0);
    }
    @Test public void reportsUncappedDemandActualRangeAndThreeExtraColourPasses()throws Exception {
        var p=plan(7,-1,0,false,backlit());
        var d=M10RExposureEvidence1F.build(stats(7),stats(3),p);
        assertTrue(d.getBoolean("extendedRangeEvidenceComplete"));assertTrue(d.getBoolean("extendedMeterRequestUsed"));
        assertEquals(7,d.getJSONArray("positiveCandidates").length());assertEquals(1.5,d.getDouble("measuredPositiveRangeEv"),0);
        assertEquals(p.mfm.rawBlendEv,d.getDouble("meterRequestBeforeLegacyCapEv"),0);
        var e=M10RExposureEvidence1G.build(p);assertEquals(SYNTHETIC_DEMAND,e.getDouble("requestedAutoEv"),1e-12);
        assertEquals(3,e.getInt("additionalColourPassesVersusE1G"));assertEquals(0,e.getInt("additionalRawFrames"));
        assertEquals(.75,e.getDouble("legacyRequestedEv"),0);
    }
}
