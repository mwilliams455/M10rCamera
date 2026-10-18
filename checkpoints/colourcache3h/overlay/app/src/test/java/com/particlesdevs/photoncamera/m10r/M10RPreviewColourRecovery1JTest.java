package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.*;
import android.hardware.camera2.params.*;
import android.opengl.GLES20;
import android.util.Rational;
import org.junit.*;
import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/** Real metadata admission, colour validation, cache and GL binder. Only GL,
 * the native LUT calculation and worker dispatch are replaced in these tests. */
public class M10RPreviewColourRecovery1JTest {
    static final long MS=1_000_000L, START=2_000_000_000L, TS=9_000_000_000L;
    final Object owner=new Object();
    final CameraCharacteristics chars=mock(CameraCharacteristics.class);
    final CaptureRequest request=mock(CaptureRequest.class);
    final M10RExposureNative1B.Context nativeContext=mock(M10RExposureNative1B.Context.class);

    @BeforeClass public static void keys() throws Exception {
        M10RPreviewMetadata1ETest.installFrameworkKeyIdentities();
        var method=M10RPreviewMetadata1ETest.class.getDeclaredMethod("keys",Class.class,Class.class,String[].class);
        method.setAccessible(true);
        method.invoke(null,CaptureResult.class,CaptureResult.Key.class,new String[]{"TONEMAP_MODE","TONEMAP_CURVE",
                "COLOR_CORRECTION_TRANSFORM","COLOR_CORRECTION_GAINS","CONTROL_POST_RAW_SENSITIVITY_BOOST"});
        method.invoke(null,CameraCharacteristics.class,CameraCharacteristics.Key.class,new String[]{"TONEMAP_MAX_CURVE_POINTS"});
    }
    @AfterClass public static void restoreKeys() throws Exception {M10RPreviewMetadata1ETest.restoreFrameworkKeys();}
    static Field cacheField(String name) throws Exception {
        Field f=M10RPreviewColour1A.class.getDeclaredField(name);f.setAccessible(true);return f;
    }
    static void resetCache() throws Exception {
        cacheField("latest").set(null,null);cacheField("failure").set(null,null);
        cacheField("attemptedAt").setLong(null,0);
        ((AtomicBoolean)cacheField("busy").get(null)).set(false);
    }
    @Before public void setup() throws Exception {
        resetCache();M10RPreviewState1A.clear(null);
        when(chars.get(CameraCharacteristics.TONEMAP_MAX_CURVE_POINTS)).thenReturn(16);
        when(request.get(CaptureRequest.CONTROL_AE_MODE)).thenReturn(CaptureRequest.CONTROL_AE_MODE_ON);
        when(request.get(CaptureRequest.CONTROL_AE_EXPOSURE_COMPENSATION)).thenReturn(0);
        when(nativeContext.render(any(short[].class),eq(4.0))).thenReturn(new int[33*33*33]);
    }
    @After public void cleanup() throws Exception {
        resetCache();M10RPreviewState1A.clear(null);
    }
    CaptureResult colourResult(long ms,Integer echo) {
        CaptureResult r=mock(CaptureResult.class);
        when(r.get(CaptureResult.SENSOR_TIMESTAMP)).thenReturn(TS+ms*MS);
        when(r.get(CaptureResult.SENSOR_EXPOSURE_TIME)).thenReturn(10_000_000L);
        when(r.get(CaptureResult.SENSOR_SENSITIVITY)).thenReturn(200);
        when(r.get(CaptureResult.CONTROL_AE_EXPOSURE_COMPENSATION)).thenReturn(echo);
        when(r.get(CaptureResult.TONEMAP_MODE)).thenReturn(CaptureRequest.TONEMAP_MODE_CONTRAST_CURVE);
        when(r.get(CaptureResult.CONTROL_POST_RAW_SENSITIVITY_BOOST)).thenReturn(100);
        TonemapCurve curve=mock(TonemapCurve.class);
        float[] points=M10RPreviewMath1A.srgbCurve(16);
        when(curve.getPointCount(anyInt())).thenReturn(points.length/2);
        doAnswer(i->{System.arraycopy(points,0,i.getArgument(1),i.getArgument(2),points.length);return null;})
                .when(curve).copyColorCurve(anyInt(),any(float[].class),anyInt());
        when(r.get(CaptureResult.TONEMAP_CURVE)).thenReturn(curve);
        ColorSpaceTransform ccm=mock(ColorSpaceTransform.class);
        for(int y=0;y<3;y++)for(int x=0;x<3;x++) {
            Rational cell=mock(Rational.class);when(cell.doubleValue()).thenReturn(x==y?1.0:0.0);
            when(ccm.getElement(x,y)).thenReturn(cell);
        }
        when(r.get(CaptureResult.COLOR_CORRECTION_TRANSFORM)).thenReturn(ccm);
        RggbChannelVector wb=mock(RggbChannelVector.class);
        when(wb.getRed()).thenReturn(2f);when(wb.getGreenEven()).thenReturn(1f);
        when(wb.getGreenOdd()).thenReturn(1f);when(wb.getBlue()).thenReturn(1.5f);
        when(r.get(CaptureResult.COLOR_CORRECTION_GAINS)).thenReturn(wb);
        return r;
    }
    M10RPreviewState1A.Observation observe(CaptureResult r,long ms,boolean matches) {
        var o=M10RPreviewMetadata1E.observe(owner,"main","controls",chars,r,request,START+ms*MS,0,matches);
        M10RPreviewState1A.observe(o);return o;
    }
    M10RPreviewState1A.Observation observe(long ms,Integer echo) {return observe(colourResult(ms,echo),ms,true);}
    M10RPreviewColour1A.Frame buildColour(M10RPreviewState1A.Observation o) throws Exception {
        return M10RPreviewColour1A.build(o,ignored->nativeContext);
    }
    M10RPreviewColour1A.Frame refresh(M10RPreviewState1A.Observation o,long now) {
        M10RPreviewColour1A.request(o,now,Runnable::run,this::buildColour);
        return M10RPreviewColour1A.request(o,now,Runnable::run,this::buildColour);
    }

    @Test public void sustainedMissingAeEchoRefreshesRealColourAfterOriginalLutExpires() throws Exception {
        var full=observe(0,0);assertNotNull(refresh(full,START));
        M10RPreviewColour1A.Frame latest=null;
        for(int i=1;i<=12;i++) {
            long ms=i*330L;var sparse=observe(ms,null);
            latest=refresh(sparse,START+ms*MS);
            assertNotNull("fresh colour must survive missing AE echo at "+ms+"ms",latest);
            assertTrue(latest.ready);
            assertFalse(sparse.captureEvidence);
        }
        assertEquals(START+3960*MS,latest.observedNs);
        assertNull(M10RPreviewState1A.captureReference(owner,"main","controls",START+3960*MS));
        verify(nativeContext,times(13)).render(any(short[].class),eq(4.0));
    }

    @Test public void realBinderRestoresColourAfterFiveCaptureSizedGapsWithoutCaptureAcknowledgement() {
        AtomicLong clock=new AtomicLong(START);ArrayList<Integer> enabled=new ArrayList<>();
        // Do not retain millions of calls to the real LUT sampling helpers in
        // Mockito's invocation history; only dispatch is stubbed here.
        try(var gl=mockStatic(GLES20.class);var colour=mockStatic(M10RPreviewColour1A.class,
                withSettings().stubOnly().defaultAnswer(CALLS_REAL_METHODS))) {
            gl.when(()->GLES20.glGetUniformLocation(1,"m10rEnabled")).thenReturn(17);
            gl.when(()->GLES20.glUniform1i(eq(17),anyInt())).thenAnswer(i->{enabled.add(i.getArgument(1));return null;});
            colour.when(()->M10RPreviewColour1A.request(any(),anyLong())).thenAnswer(i->
                    M10RPreviewColour1A.request(i.getArgument(0),i.getArgument(1),Runnable::run,this::buildColour));
            var preview=new M10RPreviewGl1A(clock::get);
            var template=new M10RPreviewPlan1ATest().plan(0,false);
            var full=observe(0,0);preview.bind(1,full.timestamp);preview.drawn();
            for(int shot=1;shot<=5;shot++) {
                for(int frame=0;frame<35;frame++) {
                    long ms=shot*3300L+frame*33L;clock.set(START+ms*MS);
                    var sparse=observe(ms,null);
                    if(frame==0)M10RPreviewState1A.publish(new M10RPreviewPlan1A(77,owner,"main","controls",
                            clock.get(),clock.get(),sparse.exposureNs,sparse.iso,template.selection,template.report));
                    preview.bind(1,sparse.timestamp);preview.drawn();
                    if(frame>0)assertEquals("shot="+shot+", frame="+frame,Integer.valueOf(1),enabled.get(enabled.size()-1));
                    assertEquals(0,M10RPreviewState1A.display().planId);
                }
            }
            assertEquals("display_only_request_EV",M10RPreviewState1A.display().status);
        }
    }

    @Test public void missingColourMetadataStillRejectsInsteadOfBorrowingExpiredTransform() {
        var full=observe(0,0);assertTrue(refresh(full,START).ready);
        CaptureResult r=colourResult(2000,null);when(r.get(CaptureResult.COLOR_CORRECTION_GAINS)).thenReturn(null);
        var sparse=observe(r,2000,true);var failed=refresh(sparse,START+2000*MS);
        assertNotNull(failed);assertFalse(failed.ready);
        assertEquals("incomplete_controlled_preview_metadata",failed.reason);
        verify(nativeContext,times(1)).render(any(short[].class),eq(4.0));
    }

    @Test public void changedRequestControlsCannotRefreshColour() {
        var mismatched=observe(colourResult(0,null),0,false);
        assertNull(refresh(mismatched,START));verifyNoInteractions(nativeContext);
    }

    @Test public void staleOrRetiredObservationCannotScheduleColour() {
        var sparse=observe(0,null);
        assertNull(refresh(sparse,START+251*MS));
        assertNull(refresh(sparse,START-1));
        M10RPreviewState1A.clear(owner);
        assertNull(refresh(sparse,START));verifyNoInteractions(nativeContext);
    }

    @Test public void workerCompletionFromRetiredSessionCannotPublishColour() {
        var sparse=observe(0,null);ArrayList<Runnable> tasks=new ArrayList<>();
        M10RPreviewColour1A.request(sparse,START,tasks::add,this::buildColour);
        assertEquals(1,tasks.size());M10RPreviewState1A.clear(owner);tasks.get(0).run();
        assertNull(M10RPreviewColour1A.request(sparse,START,tasks::add,this::buildColour));
        assertEquals(1,tasks.size());
    }

    @Test public void missingAeEchoDoesNotChangeColourMath() throws Exception {
        var full=observe(0,0);var expected=buildColour(full);
        var sparse=observe(33,null);var actual=buildColour(sparse);
        assertArrayEquals(expected.pixels,actual.pixels);assertArrayEquals(expected.inverse,actual.inverse);
        assertArrayEquals(expected.undo,actual.undo,0f);
    }

    @Test public void rejectedWorkerSubmissionDoesNotLatchColourBusy() {
        var sparse=observe(0,null);
        assertNull(M10RPreviewColour1A.request(sparse,START,r->{throw new java.util.concurrent.RejectedExecutionException();},this::buildColour));
        assertTrue(refresh(sparse,START).ready);
    }
}
