package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.params.ColorSpaceTransform;
import com.particlesdevs.photoncamera.processing.parameters.ColorTemperatureConverter;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import org.json.JSONArray;
import org.junit.AfterClass;
import org.junit.Before;
import org.junit.BeforeClass;
import org.junit.Test;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/** Deterministic cross-sensor refresh checks, with no probabilistic race loop. */
public class M10RTemperatureCache3NTest {
    private static Field cache;
    private static Method get;
    private static Object oldCache;
    @BeforeClass public static void keys() throws Exception {
        M10RSourceCalibration3CTest.keys();
        cache=ColorTemperatureConverter.class.getDeclaredField("sCachedCalibration");
        cache.setAccessible(true);oldCache=cache.get(null);
        get=ColorTemperatureConverter.class.getDeclaredMethod("getCalibrationData",CameraCharacteristics.class);
        get.setAccessible(true);
    }
    @AfterClass public static void restore() throws Exception {
        try { cache.set(null,oldCache); }
        finally { M10RSourceCalibration3CTest.restore(); }
    }
    @Before public void clearCache() throws Exception { cache.set(null,null); }
    private static Object data(CameraCharacteristics c) throws Exception { return get.invoke(null,c); }
    private static Object field(Object value,String name) throws Exception {
        Field f=value.getClass().getDeclaredField(name);f.setAccessible(true);return f.get(value);
    }
    private static float[] floats(JSONArray source) throws Exception {
        float[] values=new float[source.length()];
        for(int i=0;i<values.length;i++)values[i]=(float)source.getDouble(i);
        return values;
    }
    private static void assertCalibration(M10RSourceCalibration3CTest.Fixture fixture,Object data) throws Exception {
        assertNotNull(data);
        for(String name:new String[]{"color1","color2","forward1","forward2"}) {
            String key=name.replace("color","cm").replace("forward","fm");
            assertArrayEquals(floats(fixture.j.getJSONArray(key)),(float[])field(data,name),0);
        }
        assertEquals(6504,field(data,"colorTemp1"));
        assertEquals(2856,field(data,"colorTemp2"));
        assertEquals(true,field(data,"hasForwardMatrix"));
    }

    @Test public void inProgressOtherLensRefreshCannotChangeHeldOrCachedSourceCalibration() throws Exception {
        var a=new M10RSourceCalibration3CTest.Fixture(0,true);
        var b=new M10RSourceCalibration3CTest.Fixture(2,true);
        Object dataA=data(a.c),snapshotA=cache.get(null);
        assertCalibration(a,dataA);
        CountDownLatch extractingB=new CountDownLatch(1),releaseB=new CountDownLatch(1);
        ColorSpaceTransform matrixB=b.c.get(CameraCharacteristics.SENSOR_COLOR_TRANSFORM1);
        when(b.c.get(CameraCharacteristics.SENSOR_COLOR_TRANSFORM1)).thenAnswer(invocation->{
            extractingB.countDown();
            if(!releaseB.await(5,TimeUnit.SECONDS))throw new IllegalStateException("test release missing");
            return matrixB;
        });
        ExecutorService worker=Executors.newSingleThreadExecutor();
        try {
            var future=worker.submit(()->data(b.c));
            assertTrue(extractingB.await(5,TimeUnit.SECONDS));
            // Lens B is extracting under the cache lock. Lens A still reads the
            // complete previously published snapshot without waiting on that lock.
            assertSame(dataA,data(a.c));
            assertSame(snapshotA,cache.get(null));
            assertSame(a.c,field(snapshotA,"characteristics"));
            assertSame(dataA,field(snapshotA,"data"));
            releaseB.countDown();
            Object dataB=future.get(5,TimeUnit.SECONDS),snapshotB=cache.get(null);
            assertCalibration(b,dataB);
            assertSame(b.c,field(snapshotB,"characteristics"));
            assertSame(dataB,field(snapshotB,"data"));
            assertSame(dataB,data(b.c));
            // A held snapshot cannot turn into B when the single volatile entry changes.
            assertSame(a.c,field(snapshotA,"characteristics"));
            assertSame(dataA,field(snapshotA,"data"));
            assertCalibration(a,dataA);
            assertCalibration(a,data(a.c));
        } finally {
            releaseB.countDown();worker.shutdownNow();
            assertTrue(worker.awaitTermination(5,TimeUnit.SECONDS));
        }
    }

    @Test public void calibrationPublicationKeepsIdentityAndDataInOneImmutableEntry() throws Exception {
        // This is the publication invariant behind the deterministic refresh test:
        // one volatile read yields both values, with no later field reassignment.
        assertTrue(Modifier.isVolatile(cache.getModifiers()));
        var a=new M10RSourceCalibration3CTest.Fixture(0,true);
        var b=new M10RSourceCalibration3CTest.Fixture(2,true);
        for(var fixture:new M10RSourceCalibration3CTest.Fixture[]{a,b,a,b}) {
            Object value=data(fixture.c),snapshot=cache.get(null);
            assertSame(fixture.c,field(snapshot,"characteristics"));
            assertSame(value,field(snapshot,"data"));
            for(Field member:snapshot.getClass().getDeclaredFields())
                assertTrue(member.getName(),Modifier.isFinal(member.getModifiers()));
            assertCalibration(fixture,value);
        }
    }

    @Test public void missingCalibrationDoesNotBorrowPreviousLensAndRemainsRetryable() throws Exception {
        var a=new M10RSourceCalibration3CTest.Fixture(0,true);
        assertCalibration(a,data(a.c));
        CameraCharacteristics incomplete=mock(CameraCharacteristics.class);
        assertNull(data(incomplete));
        Object missing=cache.get(null);
        assertSame(incomplete,field(missing,"characteristics"));
        assertNull(field(missing,"data"));
        assertNull(data(null));
        assertSame(missing,cache.get(null));
        ColorSpaceTransform recoveredMatrix=M10RSourceCalibration3CTest.matrix(a.j.getJSONArray("cm1"));
        when(incomplete.get(CameraCharacteristics.SENSOR_COLOR_TRANSFORM1)).thenReturn(recoveredMatrix);
        Object recovered=data(incomplete);
        assertNotNull(recovered);
        assertArrayEquals(floats(a.j.getJSONArray("cm1")),(float[])field(recovered,"color1"),0);
        assertArrayEquals((float[])field(recovered,"color1"),(float[])field(recovered,"color2"),0);
        assertEquals(false,field(recovered,"hasForwardMatrix"));
        assertSame(recovered,data(incomplete));
    }
}
