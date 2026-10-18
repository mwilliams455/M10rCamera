package com.particlesdevs.photoncamera.m10r;

import java.nio.charset.StandardCharsets;
import org.json.*;
import org.junit.Test;
import static org.junit.Assert.*;

public class M10RExposureMidgap1STest {
    static JSONArray captures()throws Exception {
        try(var s=M10RExposureMidgap1STest.class.getResourceAsStream("/midgap1s/recorded_captures.json")) {
            assertNotNull(s);return new JSONArray(new String(s.readAllBytes(),StandardCharsets.UTF_8));
        }
    }
    static class Fixture {
        final double[] raw=new double[24];
        final M10RHighlightGuard1A.Stats[] positive,baseline;
        int dark,bright,mid;
        Fixture()throws Exception {
            var a=captures();var row=a.getJSONObject(a.length()-1);
            assertTrue(row.getString("id").contains("161216"));
            positive=M10RExposureMultiField1GTest.readStats(row.getJSONArray("positive"));
            baseline=M10RExposureMultiField1GTest.readStats(row.getJSONArray("baseline"));
            // Controlled RAW evidence isolates geometric requirements. The separate
            // recorded-meter replay exercises the phone's original input values.
            for(int f=0;f<24;f++) {
                var n=baseline[0];
                if(n.q90(f)<=96&&n.bright(f)<.01&&n.clipped(f)<.02)dark|=1<<f;
                if(n.q90(f)>=192)bright|=1<<f;
                if(n.q90(f)>96&&n.q90(f)<192)mid|=1<<f;
                raw[f]=(bright&(1<<f))!=0?.64:(dark&(1<<f))!=0?.01:.08;
            }
        }
        M10RMultiField1G.Decision decision(double previous) {
            return M10RMultiField1G.evaluate(raw,previous,baseline[0],positive,M10RHighlightGuard1A.noSubject(positive.length));
        }
        MultiFieldScene1G.Scene geometry(int middle){return MultiFieldScene1G.evaluate(raw,dark,bright,middle);}
        M10RExposure1A.Probe probe(double user) {
            double[] grid=new double[352];
            for(int r=0;r<4;r++)for(int c=0;c<6;c++)
                for(int y=r*4;y<(r+1)*4;y++)for(int x=c*22/6;x<(c+1)*22/6;x++)grid[y*22+x]=raw[r*6+c];
            return new M10RExposure1A.Probe("cam",1,1,"renderer",123,123,1_000_000_000,1_010_000_000,
                    10_000_000,206,.5,.25,M10RExposure1A.ProbeDomain.M10R_RENDERED_USER_EV_REFERENCE,
                    grid,positive,M10RHighlightGuard1A.noSubject(positive.length),user,baseline);
        }
    }
    @Test public void toyGeometryRequiresTwoDistinctIntermediateFieldsAndKeepsMasks()throws Exception {
        var f=new Fixture();assertFalse(f.geometry(0).qualified);
        var d=f.decision(.75);assertTrue(d.scene.qualified);assertTrue(d.scene.midtoneBridge);
        assertEquals((1<<8)|(1<<22),d.scene.midtoneBridgeMask);
        assertEquals(9,Integer.bitCount(d.scene.foregroundMask));assertEquals(7,Integer.bitCount(d.scene.backgroundMask));
        assertEquals(0,d.scene.foregroundMask&d.scene.midtoneBridgeMask);
        assertEquals(.5,d.requestedEv,0);assertEquals(.5,d.positiveRequestLimitEv,0);
        assertEquals(1,M10RHighlightGuard1A.limit(f.positive,d.progress()).maxPositiveEv,0);
    }
    @Test public void oneBridgeOrNoDirectContactCannotAuthorizeAssist()throws Exception {
        var f=new Fixture();assertFalse(f.geometry(f.mid&~(1<<8)).qualified);
        assertFalse(f.geometry(f.mid&~(1<<22)).qualified);
        assertFalse(MultiFieldScene1G.evaluate(f.raw,f.dark&~(1<<3),f.bright,f.mid).qualified);
    }
    @Test public void intermediateFieldsCannotChainOrOverlapMasks()throws Exception {
        var f=new Fixture();
        // Field 14 reaches the background, but needs another non-foreground
        // field to reach the selected foreground; it cannot replace field 8.
        assertFalse(f.geometry((1<<14)|(1<<22)).qualified);
        assertEquals("invalid_regions",f.geometry(f.mid|(1<<3)).reason);
        assertEquals("invalid_regions",f.geometry(f.mid|(1<<25)).reason);
    }
    @Test public void eachBridgeRequiresIncreasingRawAndSceneRequiresTwoStops()throws Exception {
        for(double bad:new double[]{0,.01,.64,1}) {
            var f=new Fixture();f.raw[8]=bad;assertFalse(f.geometry(f.mid).qualified);
        }
        var f=new Fixture();for(int i=0;i<24;i++)f.raw[i]=(f.bright&(1<<i))!=0?.03:(f.dark&(1<<i))!=0?.01:.02;
        assertEquals("insufficient_raw_separation",f.geometry(f.mid).reason);
        f.raw[8]=Double.NaN;assertEquals("invalid_regions",f.geometry(f.mid).reason);
    }
    @Test public void broadForegroundAndBoundaryBackgroundRequirementsRemain()throws Exception {
        var f=new Fixture();
        assertFalse(MultiFieldScene1G.evaluate(f.raw,(1<<3)|(1<<9)|(1<<16),f.bright,f.mid).qualified);
        assertFalse(MultiFieldScene1G.evaluate(f.raw,f.dark,(1<<7)|(1<<13)|(1<<19),f.mid).qualified);
        assertFalse(MultiFieldScene1G.evaluate(f.raw,f.dark,(1<<1)|(1<<7)|(1<<13)|(1<<14),f.mid&~(1<<14)).qualified);
    }
    @Test public void reflectionsPreserveDecisionWithoutAnUpDirection()throws Exception {
        var original=new Fixture();
        for(int mode=1;mode<=3;mode++) {
            var f=new Fixture();for(int i=0;i<24;i++)f.raw[M10RExposureSplitBg1PTest.flip(i,mode)]=original.raw[i];
            for(int i=0;i<f.positive.length;i++)f.positive[i]=M10RExposureSplitBg1PTest.flip(original.positive[i],mode);
            for(int i=0;i<f.baseline.length;i++)f.baseline[i]=M10RExposureSplitBg1PTest.flip(original.baseline[i],mode);
            var d=f.decision(.75);assertTrue(d.scene.midtoneBridge);assertEquals(.5,d.requestedEv,0);
        }
    }
    @Test public void newGeometryNeverRestoresUnboundedLegacyDemandOrHighlightExceptions()throws Exception {
        var f=new Fixture();
        for(double legacy:new double[]{-.4,0,.75,4}) {
            var d=f.decision(legacy);assertEquals(.5,d.requestedEv,0);
            assertEquals(.5,M10RExposureRange1H.requested(legacy,8,d,7),0);
            for(var p:d.progress()){assertEquals(0,p.nearWhiteBackgroundMask);assertFalse(p.canDeferBackgroundChannelClip);}
        }
    }
    @Test public void missingProgressOrUnsafeForegroundStopsAtFirstStep()throws Exception {
        var f=new Fixture();f.positive[1]=f.positive[0];assertEquals(0,f.decision(.75).requestedEv,0);
        f=new Fixture();f.positive[2]=f.positive[1];assertEquals(.25,f.decision(.75).requestedEv,0);
        for(int failure=0;failure<3;failure++) {
            f=new Fixture();int field=Integer.lowestOneBit(f.decision(.75).scene.foregroundMask);
            f.positive[1]=M10RExposureSplitBg1PTest.edit(f.positive[1],field,failure==0?129:null,
                    failure==1?.02:null,failure==2?.02:null,null);
            assertEquals(0,f.decision(.75).requestedEv,0);
        }
    }
    @Test public void globalHighlightAndProvenBaselineLossStillOverrideAssistance()throws Exception {
        var f=new Fixture();f.positive[1]=M10RExposureSplitBg1PTest.edit(f.positive[1],0,null,null,null,.10);
        var r=M10RExposureRange1HTest.request(0,true,1_020_000_000L);
        var p=M10RExposure1A.prepare(f.probe(0),r);assertEquals(0,p.appliedAutoEv,0);
        f=new Fixture();f.baseline[0]=M10RExposureSplitBg1PTest.edit(f.baseline[0],0,null,null,null,.10);
        for(int i=1;i<f.baseline.length;i++)f.baseline[i]=M10RExposureSplitBg1PTest.edit(f.baseline[i],0,null,null,null,.005);
        assertEquals(-.25,M10RExposure1A.prepare(f.probe(0),r).appliedAutoEv,0);
    }
    @Test public void userIntentAndCaptureBindingRemainIntactAndExactMeterRegionsAreLogged()throws Exception {
        var f=new Fixture();
        for(double user:new double[]{-1.25,0,.75}) {
            var probe=f.probe(user);var r=M10RExposureRange1HTest.request(user,true,1_020_000_000L);
            var p=M10RExposure1A.prepare(probe,r);assertTrue(p.ready());assertEquals(user+.5,p.totalIntentEv,1e-12);
            assertEquals(user-.25,p.deltaFromReferenceEv,1e-12);
            var d=M10RExposureEvidence1G.build(p);assertTrue(d.getBoolean("midtoneBridge"));
            assertEquals(M10RMultiField1G.GEOMETRY_REVISION,d.getString("geometryRevision"));
            assertEquals(0,d.getInt("additionalRawFrames"));
            for(int i=0;i<24;i++)assertEquals(p.mfm.regions4x6[i],d.getJSONArray("meterRawRegions4x6").getDouble(i),0);
            assertEquals(M10RExposure1A.Status.BYPASS_MANUAL,M10RExposure1A.prepare(probe,M10RExposureRange1HTest.request(user,false,1_020_000_000L)).status);
            assertEquals(M10RExposure1A.Status.STALE_OR_FUTURE,M10RExposure1A.prepare(probe,M10RExposureRange1HTest.request(user,true,2_300_000_000L)).status);
        }
    }
}
