package com.particlesdevs.photoncamera.m10r;

import android.opengl.GLES20;
import org.junit.After;
import org.junit.Test;
import java.util.ArrayList;
import java.util.concurrent.atomic.AtomicLong;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/** Exercises the production binder with realistic result/texture ordering and capture gaps. */
public class M10RPreviewGl1DTest {
    static final long START=1_100_000_000L, TS=9_000_000_000L, MS=1_000_000L;
    final M10RPreviewPlan1ATest fixture=new M10RPreviewPlan1ATest();
    @After public void cleanup(){M10RPreviewState1A.clear(null);}
    M10RPreviewState1A.Observation frame(long ts,long now,long exposure) {
        return new M10RPreviewState1A.Observation(fixture.owner,"cam","controls",null,null,
                now,0,0,ts,exposure,200);
    }
    M10RPreviewColour1A.Frame colour(M10RPreviewState1A.Observation o) {
        return new M10RPreviewColour1A.Frame(o,true,"ready",new byte[4],new byte[4],new float[9]);
    }
    @Test public void continuouslyArrivingOneFrameLateResultsDoNotCycleToOrdinaryPreview() {
        AtomicLong clock=new AtomicLong(START);ArrayList<Integer> enabled=new ArrayList<>();
        try(var gl=mockStatic(GLES20.class);var lut=mockStatic(M10RPreviewColour1A.class)) {
            gl.when(()->GLES20.glGetUniformLocation(1,"m10rEnabled")).thenReturn(17);
            gl.when(()->GLES20.glUniform1i(eq(17),anyInt())).thenAnswer(i->{enabled.add(i.getArgument(1));return null;});
            lut.when(()->M10RPreviewColour1A.request(any(),anyLong())).thenAnswer(i->colour(i.getArgument(0)));
            var preview=new M10RPreviewGl1A(clock::get);
            M10RPreviewState1A.observe(frame(TS,START,10_000_000L));
            M10RPreviewState1A.publish(fixture.plan(0,false));
            preview.bind(1,TS);preview.drawn();
            for(int i=1;i<=60;i++) {
                clock.set(START+i*33*MS);
                // Results remain fresh, but GL is one sensor frame ahead for seconds.
                M10RPreviewState1A.observe(frame(TS+(i-1)*33*MS,clock.get()-MS,10_000_000L));
                preview.bind(1,TS+i*33*MS);preview.drawn();
                assertEquals("Live frame "+i,Integer.valueOf(1),enabled.get(enabled.size()-1));
                assertEquals("Approximate display cannot approve a shutter",0,M10RPreviewState1A.display().planId);
            }
        }
    }
    @Test public void afterCaptureGapFreshLaggingMetadataCanRestoreColourWithoutAnExactDraw() {
        AtomicLong clock=new AtomicLong(START);ArrayList<Integer> enabled=new ArrayList<>();
        try(var gl=mockStatic(GLES20.class);var lut=mockStatic(M10RPreviewColour1A.class)) {
            gl.when(()->GLES20.glGetUniformLocation(1,"m10rEnabled")).thenReturn(17);
            gl.when(()->GLES20.glUniform1i(eq(17),anyInt())).thenAnswer(i->{enabled.add(i.getArgument(1));return null;});
            lut.when(()->M10RPreviewColour1A.request(any(),anyLong())).thenAnswer(i->colour(i.getArgument(0)));
            var preview=new M10RPreviewGl1A(clock::get);
            M10RPreviewState1A.observe(frame(TS,START,10_000_000L));
            preview.bind(1,TS);preview.drawn();
            clock.addAndGet(2_000*MS);
            preview.bind(1,TS+2_000*MS);preview.drawn();
            assertEquals(Integer.valueOf(0),enabled.get(enabled.size()-1));
            for(int i=1;i<=20;i++) {
                clock.addAndGet(33*MS);long timestamp=TS+clock.get()-START;
                M10RPreviewState1A.observe(frame(timestamp-33*MS,clock.get()-MS,10_000_000L));
                preview.bind(1,timestamp);preview.drawn();
                assertEquals(Integer.valueOf(1),enabled.get(enabled.size()-1));
                assertEquals(0,M10RPreviewState1A.display().planId);
            }
        }
    }
    @Test public void exposurePlanEligibilityBoundaryCannotMakeAOneFrameBrightnessStep() {
        AtomicLong clock=new AtomicLong(START);ArrayList<Float> scales=new ArrayList<>();
        try(var gl=mockStatic(GLES20.class);var lut=mockStatic(M10RPreviewColour1A.class)) {
            gl.when(()->GLES20.glGetUniformLocation(1,"m10rExposureScale")).thenReturn(18);
            gl.when(()->GLES20.glUniform1f(eq(18),anyFloat())).thenAnswer(i->{scales.add(i.getArgument(1));return null;});
            lut.when(()->M10RPreviewColour1A.request(any(),anyLong())).thenAnswer(i->colour(i.getArgument(0)));
            var preview=new M10RPreviewGl1A(clock::get);
            M10RPreviewState1A.observe(frame(TS,START,10_000_000L));
            M10RPreviewState1A.publish(fixture.plan(0,false));
            preview.bind(1,TS);preview.drawn();
            for(int i=1;i<=12;i++) {
                clock.addAndGet(33*MS);long timestamp=TS+i*33*MS;
                M10RPreviewState1A.observe(frame(timestamp,clock.get(),i%2==0?10_000_000L:12_000_000L));
                preview.bind(1,timestamp);preview.drawn();
                double step=Math.abs(Math.log(scales.get(i)/scales.get(i-1))/Math.log(2));
                assertTrue("Exposure step="+step,step<=.10001);
                if(i%2==1)assertEquals(0,M10RPreviewState1A.display().planId);
            }
        }
    }
}
