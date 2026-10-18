package com.particlesdevs.photoncamera.m10r;

import android.opengl.GLES20;
import org.junit.Test;
import org.junit.After;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;
import java.util.concurrent.atomic.AtomicLong;
import java.util.ArrayList;

/** Real preview binder; only GL calls and asynchronous LUT production are test doubles. */
public class M10RPreviewGl1CTest {
    @After public void cleanup(){M10RPreviewState1A.clear(null);}
    @Test public void lateResultKeepsShaderEnabledButClearsCaptureAcknowledgement() {
        long initial=1_100_000_000L,ts=9_000_000_000L;
        AtomicLong clock=new AtomicLong(initial);
        var fixture=new M10RPreviewPlan1ATest();var p=fixture.plan(0,false);
        var o=fixture.frame(fixture.owner,"cam","controls",ts,initial);
        var f=new M10RPreviewColour1A.Frame(o,true,"ready",new byte[4],new byte[4],new float[9]);
        M10RPreviewState1A.observe(o);M10RPreviewState1A.publish(p);
        ArrayList<Integer> enabled=new ArrayList<>();
        try(var gl=mockStatic(GLES20.class);var lut=mockStatic(M10RPreviewColour1A.class)) {
            gl.when(()->GLES20.glGetUniformLocation(1,"m10rEnabled")).thenReturn(17);
            gl.when(()->GLES20.glUniform1i(eq(17),anyInt())).thenAnswer(inv->{enabled.add(inv.getArgument(1));return null;});
            lut.when(()->M10RPreviewColour1A.request(o,initial)).thenReturn(f);
            var preview=new M10RPreviewGl1A(clock::get);
            preview.bind(1,ts);preview.drawn();
            assertEquals(Integer.valueOf(1),enabled.get(enabled.size()-1));
            assertEquals(7,M10RPreviewState1A.display().planId);
            clock.addAndGet(33_000_000L);
            preview.bind(1,ts+33_000_000L);preview.drawn();
            assertEquals(Integer.valueOf(1),enabled.get(enabled.size()-1));
            assertEquals(0,M10RPreviewState1A.display().planId);
            assertTrue(M10RPreviewState1A.display().status.startsWith("display_only_metadata_grace"));
            // A prolonged metadata outage eventually uses the ordinary preview.
            clock.set(initial+121_000_000L);
            preview.bind(1,ts+121_000_000L);preview.drawn();
            assertEquals(Integer.valueOf(0),enabled.get(enabled.size()-1));
            assertEquals(0,M10RPreviewState1A.display().planId);
        }
    }
}
