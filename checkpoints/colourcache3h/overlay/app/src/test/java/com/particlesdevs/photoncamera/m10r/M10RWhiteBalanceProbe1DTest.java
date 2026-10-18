package com.particlesdevs.photoncamera.m10r;

import java.util.Arrays;
import org.junit.Test;
import static org.junit.Assert.*;

public class M10RWhiteBalanceProbe1DTest {
    static final int W=256,H=192;
    static final double[] RECORDED={.525390625,1,.498046875},WHITE={.56,1,.41},WOOD={.70,1,.32};
    interface Field { double[] at(int tx,int ty); }
    static short[] scene(int cfa,double scale,double level,Field field) {
        short[] raw=new short[W*H];int[] red={0,1,2,3},blue={3,2,1,0};
        for(int y=0;y<H;y+=2)for(int x=0;x<W;x+=2) {
            double[] n=field.at(x/8,y/8);
            for(int p=0;p<4;p++){
                double v=n[p==red[cfa]?0:p==blue[cfa]?2:1]*level*scale;
                raw[(y+p/2)*W+x+p%2]=(short)Math.round(Math.max(0,Math.min(1,v))*65535);
            }
        }
        return raw;
    }
    @Test public void allBayerOrdersFindWhiteDespiteDominantYellowFloorWithoutMutatingRaw() {
        for(int cfa=0;cfa<4;cfa++)for(double scale:new double[]{1,.19579349904397705})for(double level:new double[]{.10,.20,.40}) {
            short[] raw=scene(cfa,scale,level,(x,y)->x<8&&y<8?WHITE:y>=10?WOOD:new double[]{.3,1,.8});
            short[] original=raw.clone();
            var r=M10RWhiteBalanceProbe1D.inspect(raw,W,H,cfa,scale,RECORDED);
            assertTrue(r.reason,r.hasProposal());assertArrayEquals(WHITE,r.proposedNeutral,.001);
            for(var t:r.selected)assertTrue(t.x<8&&t.y<8);
            assertArrayEquals(original,raw);
        }
    }
    @Test public void correctNeutralAndWoodOnlyScenesProduceNoProposal() {
        assertFalse(M10RWhiteBalanceProbe1D.inspect(scene(0,1,.2,(x,y)->WHITE),W,H,0,1,WHITE).hasProposal());
        assertFalse(M10RWhiteBalanceProbe1D.inspect(scene(0,1,.2,(x,y)->WOOD),W,H,0,1,RECORDED).hasProposal());
    }
    @Test public void comparableDistinctModesAreRejected() {
        var r=M10RWhiteBalanceProbe1D.inspect(scene(0,1,.2,(x,y)->x<16?WHITE:new double[]{.50,1,.46}),W,H,0,1,RECORDED);
        assertFalse(r.hasProposal());assertEquals("competing_neutral_modes",r.reason);
    }
    @Test public void oneColumnOfEvidenceIsInsufficient() {
        var r=M10RWhiteBalanceProbe1D.inspect(scene(0,1,.2,(x,y)->x==0?WHITE:WOOD),W,H,0,1,RECORDED);
        assertFalse(r.hasProposal());assertEquals("insufficient_spatial_support",r.reason);
    }
    @Test public void lowSignalClippingAndUnequalGreenEdgesAreRejected() {
        for(double level:new double[]{.001,1})assertFalse(M10RWhiteBalanceProbe1D.inspect(scene(0,1,level,(x,y)->WHITE),W,H,0,1,RECORDED).hasProposal());
        short[] raw=scene(0,1,.2,(x,y)->WHITE);
        for(int y=0;y<H;y+=2)for(int x=0;x<W;x+=2)raw[y*W+x+1]=(short)1000;
        assertEquals("insufficient_valid_tiles",M10RWhiteBalanceProbe1D.inspect(raw,W,H,0,1,RECORDED).reason);
    }
    @Test public void invalidInputsNeverProposeAWhitePoint() {
        short[] raw=new short[W*H];
        for(double scale:new double[]{0,-1,Double.NaN,Double.POSITIVE_INFINITY,2})
            assertFalse(M10RWhiteBalanceProbe1D.inspect(raw,W,H,0,scale,RECORDED).hasProposal());
        for(double[] n:new double[][]{null,new double[]{1,1},new double[]{1,0,1},new double[]{Double.NaN,1,1}})
            assertFalse(M10RWhiteBalanceProbe1D.inspect(raw,W,H,0,1,n).hasProposal());
        assertFalse(M10RWhiteBalanceProbe1D.inspect(raw,W-1,H,0,1,RECORDED).hasProposal());
        assertFalse(M10RWhiteBalanceProbe1D.inspect(raw,W,H,4,1,RECORDED).hasProposal());
    }
    @Test public void proposalIsAlwaysSerializedAsObservationOnly()throws Exception {
        var r=M10RWhiteBalanceProbe1D.inspect(scene(0,1,.2,(x,y)->WHITE),W,H,0,1,RECORDED);
        var d=M10RWhiteBalanceDiagnostics1D.describe(r);
        assertTrue(d.getBoolean("hasProposal"));assertFalse(d.getBoolean("applied"));
        assertFalse(d.getBoolean("automaticCorrectionEnabled"));assertFalse(d.getBoolean("materialNeutralityProven"));
        assertEquals("observation_only",d.getString("mode"));
        assertEquals(r.valid.size(),d.getJSONArray("validTileStatistics").length());
    }
}
