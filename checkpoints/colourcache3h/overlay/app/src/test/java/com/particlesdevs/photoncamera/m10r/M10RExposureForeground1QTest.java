package com.particlesdevs.photoncamera.m10r;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import org.json.*;
import org.junit.Test;
import static org.junit.Assert.*;

public class M10RExposureForeground1QTest {
    static class Fixture {
        final double[] regions=new double[24];
        final M10RHighlightGuard1A.Stats[] positive,baseline;
        final double legacy,beforeCap;
        Fixture()throws Exception{this(2);}
        Fixture(int index)throws Exception {
            try(InputStream s=getClass().getResourceAsStream("/foreground1q/recorded_captures.json")) {
                assertNotNull(s);var d=new JSONArray(new String(s.readAllBytes(),StandardCharsets.UTF_8)).getJSONObject(index);
                for(int i=0;i<24;i++)regions[i]=d.getJSONArray("regions").getDouble(i);
                legacy=d.getDouble("legacyEv");beforeCap=d.getDouble("beforeCapEv");
                positive=M10RExposureMultiField1GTest.readStats(d.getJSONArray("positive"));
                baseline=M10RExposureMultiField1GTest.readStats(d.getJSONArray("baseline"));
            }
        }
        M10RMultiField1G.Decision decision(){return decision(legacy);}
        M10RMultiField1G.Decision decision(double legacy){return M10RMultiField1G.evaluate(regions,legacy,baseline[0],positive,M10RHighlightGuard1A.noSubject(7));}
        // Piecewise-constant expansion for controller/binding tests only. Exact
        // recorded legacy demand is replayed independently through decision().
        double[] grid() {
            double[] g=new double[352];
            for(int r=0;r<4;r++)for(int c=0;c<6;c++)
                for(int y=r*16/4;y<(r+1)*16/4;y++)for(int x=c*22/6;x<(c+1)*22/6;x++)g[y*22+x]=regions[r*6+c];
            return g;
        }
        M10RExposure1A.Probe probe(double user,double refUser,double refAuto) {
            return new M10RExposure1A.Probe("cam",1,1,"renderer",123,123,1_000_000_000,1_010_000_000,
                    792_748,50,refUser,refAuto,M10RExposure1A.ProbeDomain.M10R_RENDERED_USER_EV_REFERENCE,
                    grid(),positive,M10RHighlightGuard1A.noSubject(7),user,baseline);
        }
        M10RExposure1A.Plan plan(){return M10RExposure1A.prepare(probe(0,0,0),M10RExposureRange1HTest.request(0,true,1_020_000_000L));}
    }
    static M10RHighlightGuard1A.Stats edit(M10RHighlightGuard1A.Stats s,int mask,Integer q,Double bright,Double clip,Double global) {
        return M10RExposureSplitBg1PTest.edit(s,mask,q,bright,clip,global);
    }

    @Test public void recordedStreetOverridesContrastModerationOnlyWithinMeasuredHeadroom()throws Exception {
        var f=new Fixture();var d=f.decision();
        assertEquals(-.10896936288179483,f.legacy,1e-12);
        assertTrue(d.scene.qualified);assertFalse(d.scene.splitBackground);
        assertEquals(9,Integer.bitCount(d.scene.foregroundMask));assertEquals(4.350702535453647,d.scene.separationEv,1e-12);
        assertEquals(.25,d.requestedEv,0);assertEquals(.25,d.positiveRequestLimitEv,0);
        assertEquals("qualified_foreground_overrides_negative_meter",d.reason);
        assertEquals(.25,M10RExposureRange1H.requested(f.legacy,f.beforeCap,d,7),0);
        var limit=M10RHighlightGuard1A.limit(f.positive,d.progress());
        assertEquals(.25,limit.maxPositiveEv,0);assertEquals(2,limit.firstRejectedStep);
        assertEquals(M10RHighlightGuard1A.Stop.REGIONAL_CHANNEL_CLIP_GROWTH,limit.stop);
        for(var p:d.progress()){assertEquals(0,p.nearWhiteBackgroundMask);assertFalse(p.canDeferBackgroundChannelClip);}
        assertEquals(0,M10RExposureBaseline1F.evaluate(f.baseline).correctionEv,0);
    }

    @Test public void indoorAndDaylightControlsKeepZeroAssistance()throws Exception {
        for(int i=0;i<2;i++){var f=new Fixture(i);assertFalse(f.decision().scene.qualified);assertEquals(0,f.decision().requestedEv,0);}
    }

    @Test public void unqualifiedOrMissingNeutralEvidencePreservesNegativeDemand()throws Exception {
        for(int i=0;i<2;i++)assertEquals(-.3,new Fixture(i).decision(-.3).requestedEv,0);
        var f=new Fixture();var d=M10RMultiField1G.evaluate(f.regions,f.legacy,null,f.positive,M10RHighlightGuard1A.noSubject(7));
        assertEquals(f.legacy,d.requestedEv,0);assertFalse(d.scene.qualified);
    }

    @Test public void noProgressOrUnsafeForegroundPreservesNegativeDemand()throws Exception {
        for(int failure=0;failure<5;failure++) {
            var f=new Fixture();int mask=f.decision().scene.foregroundMask;
            if(failure==0)f.positive[1]=f.positive[0];
            if(failure==1)f.positive[0]=edit(f.positive[0],mask,96,null,null,null);
            if(failure>=2)f.positive[1]=edit(f.positive[1],Integer.lowestOneBit(mask),failure==2?129:null,failure==3?.02:null,failure==4?.02:null,null);
            assertEquals(f.legacy,f.decision().requestedEv,0);
        }
    }

    @Test public void firstHighlightFailureCannotBeSkipped()throws Exception {
        var f=new Fixture();f.positive[1]=edit(f.positive[1],0,null,null,null,.10);
        assertEquals(f.legacy,f.decision().requestedEv,0);
        assertEquals("legacy_negative_no_safe_foreground_assist",f.decision().reason);
    }

    @Test public void wideRangeCannotExceedHalfStopEvenWithOpenHighlightHeadroom()throws Exception {
        var f=new Fixture();int mask=f.decision().scene.foregroundMask;
        for(int i=0;i<7;i++)f.positive[i]=edit(f.positive[0],mask,25+5*i,null,null,null);
        var d=f.decision();assertEquals(.5,d.requestedEv,0);assertEquals(.5,d.positiveRequestLimitEv,0);
        assertEquals(.5,M10RExposureRange1H.requested(f.legacy,8,d,7),0);
    }

    @Test public void lowerSeparationReducesAssistBeforeTheDeadband()throws Exception {
        var f=new Fixture();var original=f.decision();
        double[] dark=new double[Integer.bitCount(original.scene.foregroundMask)];int n=0;
        for(int i=0;i<24;i++)if((original.scene.foregroundMask&(1<<i))!=0)dark[n++]=f.regions[i];
        Arrays.sort(dark);double median=dark[dark.length/2];
        for(int i=0;i<24;i++)if((original.scene.backgroundMask&(1<<i))!=0)f.regions[i]=median*Math.pow(2,2.5);
        assertEquals(f.legacy,f.decision().requestedEv,0); // smooth ramp is below existing 0.08 EV deadband
        for(int i=0;i<24;i++)if((original.scene.backgroundMask&(1<<i))!=0)f.regions[i]=median*Math.pow(2,3);
        assertEquals(.25,f.decision().requestedEv,1e-12);
    }

    @Test public void provenBaselineLossStillOverridesForegroundProposal()throws Exception {
        var f=new Fixture();f.baseline[0]=edit(f.baseline[0],0,null,null,null,.10);
        for(int i=1;i<3;i++)f.baseline[i]=edit(f.baseline[i],0,null,null,null,.005);
        var p=f.plan();assertTrue(p.ready());assertTrue(p.mfm.recommendedEv<0);
        assertTrue(p.requestedAutoEv>0);assertEquals(Math.min(-.25,p.mfm.recommendedEv),p.appliedAutoEv,1e-12);
        var evidence=M10RExposureEvidence1G.build(p);
        assertTrue(evidence.getBoolean("legacyNegativeOverrideRequested"));assertFalse(evidence.getBoolean("legacyNegativeOverrideApplied"));
    }

    @Test public void explicitUserIntentAndReferenceRemainSeparateThroughAllocation()throws Exception {
        var f=new Fixture();
        var limits=new M10RExposureCapture1B.Limits(1,1_000_000_000L,50,6400);
        var zero=M10RExposureCapture1B.select(f.probe(0,.5,.25),M10RExposureRange1HTest.request(0,true,1_020_000_000L),null,limits);
        for(double user:new double[]{-1.25,-2.0/3,0,.75}) {
            // Binding verification; fixtures declared at each reference do not
            // simulate a new photograph taken at a different user EV.
            var probe=f.probe(user,.5,.25);var request=M10RExposureRange1HTest.request(user,true,1_020_000_000L);
            var p=M10RExposure1A.prepare(probe,request);assertTrue(p.ready());assertTrue(p.mfm.recommendedEv<0);
            assertEquals(.25,p.appliedAutoEv,0);assertEquals(user+.25,p.totalIntentEv,1e-12);assertEquals(user-.5,p.deltaFromReferenceEv,1e-12);
            var s=M10RExposureCapture1B.select(probe,request,null,limits);
            var expected=M10RAe1BPolicy.solve(792_748,50,1.8,35,user-.5,100,50000).oracle;
            assertEquals(expected.iso,p.allocation.oracle.iso);assertEquals(expected.shutterSeconds,p.allocation.oracle.shutterSeconds,0);
            // Physical delivery must preserve intent even across the inherited
            // firmware shutter floor, where BRIGHTRANGE1N departs from its pair.
            assertEquals(user,Math.log(((double)s.exposureNs*s.iso)/((double)zero.exposureNs*zero.iso))/Math.log(2),.006);
            assertEquals(0,s.allocationResidualEv,1e-4);
            var evidence=M10RExposureEvidence1G.build(p);assertTrue(evidence.getBoolean("legacyNegativeConflict"));assertTrue(evidence.getBoolean("legacyNegativeOverrideApplied"));
            assertEquals(.25,evidence.getDouble("positiveRequestLimitEv"),0);
            assertEquals(M10RExposure1A.Status.BYPASS_MANUAL,M10RExposure1A.prepare(probe,M10RExposureRange1HTest.request(user,false,1_020_000_000L)).status);
            assertEquals(M10RExposure1A.Status.STALE_OR_FUTURE,M10RExposure1A.prepare(probe,M10RExposureRange1HTest.request(user,true,2_300_000_000L)).status);
        }
    }
}
