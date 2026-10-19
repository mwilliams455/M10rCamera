package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CaptureResult;
import android.util.Base64;
import android.util.Rational;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.AfterClass;
import org.junit.BeforeClass;
import org.junit.Test;
import org.mockito.MockedStatic;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/** Compared with a fixed corpus captured from the untouched GUARDOFF3L implementation. */
public class M10RColourPreparation3NTest {
    private static MockedStatic<Base64> base64;
    @BeforeClass public static void keys() throws Exception {
        M10RSourceCalibration3CTest.keys();
        // Android's host stub has no decoder. Use the real fixed table bytes,
        // retaining the production inflater and native rendering arithmetic.
        base64=mockStatic(Base64.class);
        base64.when(()->Base64.decode(anyString(),anyInt()))
                .thenAnswer(i->java.util.Base64.getDecoder().decode((String)i.getArgument(0)));
    }
    @AfterClass public static void restore() throws Exception {
        try { if(base64!=null)base64.close(); }
        finally { M10RSourceCalibration3CTest.restore(); }
    }

    private static JSONObject corpus() throws Exception {
        try(var in=M10RColourPreparation3NTest.class.getResourceAsStream("/sourcewhite3n/guardoff3l_colour_baseline.json")) {
            assertNotNull(in);
            JSONObject corpus=new JSONObject(new String(in.readAllBytes(),StandardCharsets.UTF_8));
            assertEquals("ce859a197e33ab100a020766429e7728ac2323164104ac28636b1a14f7ae4365",
                    corpus.getString("sourceRendererSha256"));
            return corpus;
        }
    }
    private static double[] doubles(JSONArray array) throws Exception {
        double[] result=new double[array.length()];
        for(int i=0;i<result.length;i++)result[i]=array.getDouble(i);
        return result;
    }
    private static int[] ints(JSONArray array) throws Exception {
        int[] result=new int[array.length()];
        for(int i=0;i<result.length;i++)result[i]=array.getInt(i);
        return result;
    }
    private static Object field(Object value,String name) throws Exception {
        Field f=value.getClass().getDeclaredField(name);f.setAccessible(true);return f.get(value);
    }
    private static void assertJsonExact(String path,Object expected,Object actual) throws Exception {
        if(expected instanceof JSONArray) {
            assertTrue(path,actual instanceof JSONArray);
            JSONArray a=(JSONArray)expected,b=(JSONArray)actual;
            assertEquals(path,a.length(),b.length());
            for(int i=0;i<a.length();i++)assertJsonExact(path+"["+i+"]",a.get(i),b.get(i));
        } else if(expected instanceof JSONObject) {
            assertTrue(path,actual instanceof JSONObject);
            JSONObject a=(JSONObject)expected,b=(JSONObject)actual;
            assertEquals(path,a.length(),b.length());
            var keys=a.keys();
            while(keys.hasNext()) {
                String key=keys.next();assertTrue(path+"."+key,b.has(key));
                assertJsonExact(path+"."+key,a.get(key),b.get(key));
            }
        } else if(expected instanceof Number) {
            assertTrue(path,actual instanceof Number);
            // Compare the exact JSON decimal value, so 1 and 1.0 match without
            // widening a recorded Float to a different binary Double value.
            assertEquals(path,0,new BigDecimal(expected.toString()).compareTo(new BigDecimal(actual.toString())));
        } else assertEquals(path,expected,actual);
    }
    private static M10RSourceCalibration3CTest.Fixture fixture(JSONObject golden) throws Exception {
        var f=new M10RSourceCalibration3CTest.Fixture(golden.getInt("fixtureIndex"),true);
        when(f.r.get(CaptureResult.SENSOR_TIMESTAMP)).thenReturn(golden.getJSONObject("legacy").getLong("frameTimestampNs"));
        return f;
    }
    private static M10RNativeRenderer.PreparedColour prepare(M10RSourceCalibration3CTest.Fixture fixture,
            M10RSourceWhite3N white,JSONObject diagnostics) throws Exception {
        try(var log=mockStatic(com.particlesdevs.photoncamera.util.Log.class)) {
            return M10RNativeRenderer.prepareColour(fixture.c,white,diagnostics);
        }
    }
    private static M10RExposureNative1B.Context legacy(M10RSourceCalibration3CTest.Fixture fixture,
            String key) throws Exception {
        Method method=M10RNativeRenderer.class.getDeclaredMethod("legacyExposureContext1B",
                CameraCharacteristics.class,CaptureResult.class,String.class);method.setAccessible(true);
        try(var log=mockStatic(com.particlesdevs.photoncamera.util.Log.class)) {
            return (M10RExposureNative1B.Context)method.invoke(null,fixture.c,fixture.r,key);
        }
    }
    private static void assertPrepared(JSONObject golden,M10RNativeRenderer.PreparedColour prepared) throws Exception {
        JSONObject expected=golden.getJSONObject("legacy");
        assertArrayEquals(doubles(golden.getJSONArray("targetAsn")),prepared.copyTargetAsn(),0);
        assertArrayEquals(ints(expected.getJSONArray("ca9")),prepared.copyCa9());
        assertArrayEquals(doubles(expected.getJSONArray("sourceToTarget")),prepared.copySourceToTargetCamera(),0);
        assertArrayEquals(doubles(expected.getJSONArray("targetToWorking")),prepared.copyTargetToWorking(),0);
        assertArrayEquals(doubles(expected.getJSONArray("workingToOutput")),prepared.copyWorkingToOutput(),0);
    }
    private static void assertContext(JSONObject expected,M10RExposureNative1B.Context actual) throws Exception {
        for(String name:new String[]{"sourceToTarget","targetToWorking","workingToOutput"})
            assertArrayEquals(doubles(expected.getJSONArray(name)),(double[])field(actual,name),0);
        assertArrayEquals(ints(expected.getJSONArray("ca9")),(int[])field(actual,"ca9"));
        assertEquals(expected.getBoolean("cc1BeforeDg"),field(actual,"cc1BeforeDg"));
        assertEquals(expected.getString("revision"),actual.revision);
        assertEquals(expected.getString("cameraKey"),actual.cameraKey);
        assertEquals(expected.getLong("frameTimestampNs"),actual.frameTimestampNs);
    }

    @Test public void sharedPreparationAndLegacyFactoryMatchOriginalGoldenExactly() throws Exception {
        JSONArray cases=corpus().getJSONArray("cases");
        for(int i=0;i<cases.length();i++) {
            JSONObject golden=cases.getJSONObject(i);var f=fixture(golden);JSONObject d=new JSONObject();
            M10RSourceWhite3N white=M10RSourceWhite3N.fromCaptureResult(f.r);
            var prepared=prepare(f,white,d);
            assertSame(white,prepared.sourceWhite());
            assertPrepared(golden,prepared);
            assertContext(golden.getJSONObject("legacy"),legacy(f,golden.getJSONObject("legacy").getString("cameraKey")));
            JSONObject old=golden.getJSONObject("sourceModelDiagnostics");
            for(String name:new String[]{"sourceSensorNeutral","sourceSensorToXYZD50","whiteBalanceAuthority3L"})
                assertJsonExact(name,old.get(name),d.get(name));
            JSONObject snapshot=d.getJSONObject("whiteBalanceSnapshot3N");
            assertEquals("VENDOR_CAPTURE_RESULT",snapshot.getString("authority"));
            assertFalse(snapshot.getBoolean("sourceNeutralRenormalized"));
            assertFalse(snapshot.getBoolean("sceneWhiteReselected"));
        }
    }

    @Test public void allOriginalNativeProbePixelsAndRenderedCoefficientVariantsRemainExact() throws Exception {
        JSONArray cases=corpus().getJSONArray("cases");
        Field p=M10RNativeRenderer.class.getDeclaredField("RENDERED_COLOR");p.setAccessible(true);
        var rendered=(M10RRenderedColor1A)p.get(null);
        for(int i=0;i<cases.length();i++) {
            JSONObject golden=cases.getJSONObject(i);var f=fixture(golden);
            var original=legacy(f,golden.getJSONObject("legacy").getString("cameraKey"));
            int[] values=ints(golden.getJSONArray("sensorRgbU16"));short[] rgb=new short[values.length];
            for(int k=0;k<values.length;k++)rgb[k]=(short)values[k];
            M10RExposureNative1B.Context[] variants={original,original.withRenderedColor(rendered,true,false),
                    original.withRenderedColor(rendered,true,true)};
            String[] names={"legacy","renderedBeforeOrder","renderedCurrentOrder"};
            for(int variant=0;variant<variants.length;variant++) {
                JSONObject expected=golden.getJSONObject(names[variant]);
                assertContext(expected,variants[variant]);
                assertArrayEquals(ints(expected.getJSONArray("argb")),
                        variants[variant].render(rgb,golden.getDouble("inverseScale")));
            }
        }
    }

    @Test public void frozenSelectionAndPreparedArraysCannotBeReplacedByLaterResultOrCaller() throws Exception {
        JSONObject golden=corpus().getJSONArray("cases").getJSONObject(0);var f=fixture(golden);
        M10RSourceWhite3N selected=M10RSourceWhite3N.fromCaptureResult(f.r);
        var prepared=prepare(f,selected,new JSONObject());
        prepared.copySourceToTargetCamera()[0]=42;
        prepared.copyTargetToWorking()[0]=42;
        prepared.copyWorkingToOutput()[0]=42;
        prepared.copyTargetAsn()[0]=42;
        prepared.copyCa9()[0]=42;
        prepared.sourceWhite().copySourceNeutral()[0]=42;
        Rational[] changedNeutral={
                M10RSourceCalibration3CTest.number(.2),M10RSourceCalibration3CTest.number(1),
                M10RSourceCalibration3CTest.number(.8)};
        when(f.r.get(CaptureResult.SENSOR_NEUTRAL_COLOR_POINT)).thenReturn(changedNeutral);
        assertPrepared(golden,prepared);
        assertPrepared(golden,prepare(f,selected,new JSONObject()));
        var next=prepare(f,M10RSourceWhite3N.fromCaptureResult(f.r),new JSONObject());
        assertFalse(Arrays.equals(prepared.copySourceToTargetCamera(),next.copySourceToTargetCamera()));
    }

    @Test public void sourcePreparationKeepsOptionalFrameProvenanceAndMissingNeutralBehaviour() throws Exception {
        var f=new M10RSourceCalibration3CTest.Fixture(0,true);JSONObject d=new JSONObject();
        assertNotNull(prepare(f,M10RSourceWhite3N.fromCaptureResult(f.r),d));
        assertTrue(d.getJSONObject("whiteBalanceSnapshot3N").isNull("sensorTimestampNs"));
        assertEquals(0L,d.getJSONObject("whiteBalanceSnapshot3N").getLong("frameNumber"));
        assertThrows(IllegalStateException.class,()->prepare(f,null,new JSONObject()));
    }
}
