package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.CaptureResult;
import android.hardware.camera2.params.ColorSpaceTransform;
import android.hardware.camera2.params.TonemapCurve;
import android.util.Rational;
import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.After;
import org.junit.AfterClass;
import org.junit.Before;
import org.junit.BeforeClass;
import org.junit.Test;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/** Real observation/cache/worker guards; native LUT output alone is replaced. */
public class M10RManualPreviewCache3OTest {
    static final long NOW=2_000_000_000L;
    final Object owner=new Object();
    final CameraCharacteristics characteristics=mock(CameraCharacteristics.class);
    @BeforeClass public static void keys() throws Exception { M10RCaptureMeterReference1ITest.keys(); }
    @AfterClass public static void restore() throws Exception { M10RCaptureMeterReference1ITest.restoreKeys(); }
    static Field cache(String name) throws Exception {
        Field field=M10RPreviewColour1A.class.getDeclaredField(name);field.setAccessible(true);return field;
    }
    @Before public void setup() throws Exception { clear(); }
    @After public void clear() throws Exception {
        M10RPreviewState1A.clear(null);cache("latest").set(null,null);cache("failure").set(null,null);
        cache("attemptedAt").setLong(null,0);((AtomicBoolean)cache("busy").get(null)).set(false);
    }
    CaptureResult result(CaptureRequest request,long offset) {
        CaptureResult result=mock(CaptureResult.class);
        when(result.getRequest()).thenReturn(request);
        when(result.get(CaptureResult.SENSOR_TIMESTAMP)).thenReturn(9_000_000_000L+offset);
        when(result.get(CaptureResult.SENSOR_EXPOSURE_TIME)).thenReturn(10_000_000L);
        when(result.get(CaptureResult.SENSOR_SENSITIVITY)).thenReturn(200);
        return result;
    }
    M10RPreviewState1A.Observation observe(CaptureResult result,long offset) {
        // Deliberately hold the outer controls string fixed: the exact request
        // white identity must independently reject an old transform/worker.
        var observation=new M10RPreviewState1A.Observation(owner,"sensor0","same_controls",characteristics,
                result,NOW+offset,0,0);
        M10RPreviewState1A.observe(observation);return observation;
    }
    static M10RPreviewColour1A.Frame fakeFrame(M10RPreviewState1A.Observation observation) {
        return new M10RPreviewColour1A.Frame(observation,true,"test_native_output",
                new byte[4],new byte[4],new float[9]);
    }
    static M10RPreviewColour1A.Frame refresh(M10RPreviewState1A.Observation observation) {
        M10RPreviewColour1A.request(observation,observation.observedNs,Runnable::run,M10RManualPreviewCache3OTest::fakeFrame);
        return M10RPreviewColour1A.request(observation,observation.observedNs,Runnable::run,M10RManualPreviewCache3OTest::fakeFrame);
    }

    @Test public void exactManualRequestIdentityRetiresOldCacheEvenWithSameOuterControls() {
        CaptureRequest[] requests={M10RRequestedWhite3OTest.request(2,1,1,4),
                M10RRequestedWhite3OTest.request(4,2,2,8), // same neutral, different submitted gains
                M10RRequestedWhite3OTest.request(1.4f,1,1,2.8f),
                M10RRequestedWhite3OTest.autoRequest()};
        M10RPreviewState1A.Observation previous=null;M10RPreviewColour1A.Frame old=null;
        for(int i=0;i<requests.length;i++) {
            var observation=observe(result(requests[i],i*1_000_000L),i*1_000_000L);
            if(previous!=null) {
                assertFalse(M10RPreviewState1A.current(previous));
                assertFalse(old.matches(observation));
                assertNull(M10RPreviewColour1A.available(old,null,observation,observation.observedNs));
            }
            var fresh=refresh(observation);assertNotNull(fresh);assertTrue(fresh.ready);
            assertTrue(fresh.matches(observation));assertNotSame(old,fresh);
            previous=observation;old=fresh;
        }
    }

    @Test public void oldManualWorkerCannotPublishAfterWhiteChangeWithSameOuterControls() throws Exception {
        var first=observe(result(M10RRequestedWhite3OTest.request(2,1,1,1.4f),0),0);
        ArrayList<Runnable> tasks=new ArrayList<>();
        M10RPreviewColour1A.request(first,NOW,tasks::add,M10RManualPreviewCache3OTest::fakeFrame);
        assertEquals(1,tasks.size());
        var second=observe(result(M10RRequestedWhite3OTest.request(1.4f,1,1,2.8f),1_000_000),1_000_000);
        tasks.get(0).run();
        assertNull(cache("latest").get(null));assertNull(cache("failure").get(null));
        var fresh=refresh(second);assertNotNull(fresh);assertTrue(fresh.matches(second));
        assertFalse(fresh.matches(first));
    }

    @Test public void requestedWhiteDoesNotReplaceDeliveredIspUndo() throws Exception {
        CaptureRequest request=M10RRequestedWhite3OTest.request(7,1,1,.7f);
        CaptureResult result=result(request,0);
        when(characteristics.get(CameraCharacteristics.TONEMAP_MAX_CURVE_POINTS)).thenReturn(16);
        when(result.get(CaptureResult.TONEMAP_MODE)).thenReturn(CaptureRequest.TONEMAP_MODE_CONTRAST_CURVE);
        when(result.get(CaptureResult.CONTROL_POST_RAW_SENSITIVITY_BOOST)).thenReturn(100);
        TonemapCurve curve=mock(TonemapCurve.class);float[] points=M10RPreviewMath1A.srgbCurve(16);
        when(curve.getPointCount(anyInt())).thenReturn(points.length/2);
        doAnswer(i->{System.arraycopy(points,0,i.getArgument(1),i.getArgument(2),points.length);return null;})
                .when(curve).copyColorCurve(anyInt(),any(float[].class),anyInt());
        when(result.get(CaptureResult.TONEMAP_CURVE)).thenReturn(curve);
        ColorSpaceTransform matrix=mock(ColorSpaceTransform.class);
        for(int y=0;y<3;y++)for(int x=0;x<3;x++) {
            Rational cell=mock(Rational.class);when(cell.doubleValue()).thenReturn(x==y?1.0:0.0);
            when(matrix.getElement(x,y)).thenReturn(cell);
        }
        when(result.get(CaptureResult.COLOR_CORRECTION_TRANSFORM)).thenReturn(matrix);
        var delivered=M10RRequestedWhite3OTest.gains(2,1,1,1.5f);
        when(result.get(CaptureResult.COLOR_CORRECTION_GAINS)).thenReturn(delivered);
        var nativeContext=mock(M10RExposureNative1B.Context.class);
        when(nativeContext.render(any(short[].class),eq(4.0))).thenReturn(new int[]{0xff808080});
        var frame=M10RPreviewColour1A.build(observe(result,0),ignored->nativeContext);
        assertArrayEquals(new float[]{.5f,0,0,0,1,0,0,0,2f/3f},frame.undo,0);
        assertTrue(frame.ready);
    }
}
