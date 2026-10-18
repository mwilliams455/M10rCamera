package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.*;
import android.hardware.camera2.params.ColorSpaceTransform;
import android.util.Rational;
import android.util.SparseIntArray;
import com.particlesdevs.photoncamera.processing.render.Converter;
import java.lang.reflect.*;
import java.nio.charset.StandardCharsets;
import org.json.*;
import org.junit.*;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/** Real production source-model arithmetic, with Camera2 metadata containers mocked. */
public class M10RSourceCalibration3CTest {
    static Object oldIlluminants;
    @BeforeClass public static void keys() throws Exception {
        M10RCaptureMeterReference1ITest.keys();
        Field f=Converter.class.getField("sStandardIlluminates");oldIlluminants=f.get(null);
        SparseIntArray illuminants=mock(SparseIntArray.class);
        when(illuminants.get(anyInt(),anyInt())).thenAnswer(i->{int k=i.getArgument(0);return k==21?6504:k==17?2856:(Integer)i.getArgument(1);});
        M10RCaptureMeterReference1ITest.put(f,illuminants);
    }
    @AfterClass public static void restore() throws Exception {
        M10RCaptureMeterReference1ITest.put(Converter.class.getField("sStandardIlluminates"),oldIlluminants);
        M10RCaptureMeterReference1ITest.restoreKeys();
    }
    static JSONObject input(int n)throws Exception {
        try(var in=M10RSourceCalibration3CTest.class.getResourceAsStream("/sourceaudit3c/metadata.json")){
            assertNotNull(in);return new JSONArray(new String(in.readAllBytes(),StandardCharsets.UTF_8)).getJSONObject(n);
        }
    }
    static Rational number(double x){Rational r=mock(Rational.class);when(r.floatValue()).thenReturn((float)x);return r;}
    static ColorSpaceTransform matrix(JSONArray a){
        ColorSpaceTransform m=mock(ColorSpaceTransform.class);
        when(m.getElement(anyInt(),anyInt())).thenAnswer(i->number(a.getDouble(3*(Integer)i.getArgument(1)+(Integer)i.getArgument(0))));return m;
    }
    static class Fixture {
        final CameraCharacteristics c=mock(CameraCharacteristics.class);
        final CaptureResult r=mock(CaptureResult.class);
        final JSONObject j;
        Fixture(int n,boolean dual)throws Exception {
            j=input(n);when(c.get(CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT1)).thenReturn(j.getInt("ref1"));
            ColorSpaceTransform cal1=matrix(j.getJSONArray("cal1"));when(c.get(CameraCharacteristics.SENSOR_CALIBRATION_TRANSFORM1)).thenReturn(cal1);
            ColorSpaceTransform cm1=matrix(j.getJSONArray("cm1"));when(c.get(CameraCharacteristics.SENSOR_COLOR_TRANSFORM1)).thenReturn(cm1);
            ColorSpaceTransform fm1=matrix(j.getJSONArray("fm1"));when(c.get(CameraCharacteristics.SENSOR_FORWARD_MATRIX1)).thenReturn(fm1);
            if(dual){
                when(c.get(CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT2)).thenReturn((byte)j.getInt("ref2"));
                ColorSpaceTransform cal2=matrix(j.getJSONArray("cal2"));when(c.get(CameraCharacteristics.SENSOR_CALIBRATION_TRANSFORM2)).thenReturn(cal2);
                ColorSpaceTransform cm2=matrix(j.getJSONArray("cm2"));when(c.get(CameraCharacteristics.SENSOR_COLOR_TRANSFORM2)).thenReturn(cm2);
                ColorSpaceTransform fm2=matrix(j.getJSONArray("fm2"));when(c.get(CameraCharacteristics.SENSOR_FORWARD_MATRIX2)).thenReturn(fm2);
            }
            JSONArray a=j.getJSONArray("neutral");Rational[] neutral={number(a.getDouble(0)),number(a.getDouble(1)),number(a.getDouble(2))};when(r.get(CaptureResult.SENSOR_NEUTRAL_COLOR_POINT)).thenReturn(neutral);
        }
        Object run(JSONObject d)throws Exception {
            Method m=M10RNativeRenderer.class.getDeclaredMethod("buildSourceModel",CameraCharacteristics.class,CaptureResult.class,JSONObject.class);m.setAccessible(true);
            try(var log=mockStatic(com.particlesdevs.photoncamera.util.Log.class)){
                try{return m.invoke(null,c,r,d);}catch(InvocationTargetException e){throw (Exception)e.getCause();}
            }
        }
    }
    static Object field(Object m,String name)throws Exception{Field f=m.getClass().getDeclaredField(name);f.setAccessible(true);return f.get(m);}
    static void assertNeutral(Fixture f,Object m)throws Exception{
        float[] a=(float[])field(m,"sensorToXyzD50");JSONArray n=f.j.getJSONArray("neutral");double[] white={.9642,1,.8249};
        for(int row=0;row<3;row++)assertEquals(white[row],a[3*row]*n.getDouble(0)+a[3*row+1]*n.getDouble(1)+a[3*row+2]*n.getDouble(2),3e-7);
    }
    @Test public void singleIlluminantUsesCompleteFirstProfileAndReportsIt()throws Exception{
        for(int n=0;n<4;n++){
            Fixture f=new Fixture(n,false);JSONObject d=new JSONObject();Object m=f.run(d);
            assertEquals(0.0,(Double)field(m,"interpolationFactor"),0.0);assertNeutral(f,m);
            assertEquals(1,d.getInt("sourceCalibrationIlluminantCount"));assertTrue(d.getBoolean("sourceSingleIlluminantFallbackApplied"));
            assertEquals("Camera2_single_illuminant_native_XYZ_D50",d.getString("sourceModel"));
        }
    }
    @Test public void unadvertisedSecondMatricesCannotAffectFirstProfile()throws Exception{
        Fixture first=new Fixture(1,false),stray=new Fixture(1,true);
        when(stray.c.get(CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT2)).thenReturn(null);
        ColorSpaceTransform unrelated=matrix(new JSONArray(new int[]{9,2,3,4,7,2,1,3,8}));when(stray.c.get(CameraCharacteristics.SENSOR_FORWARD_MATRIX2)).thenReturn(unrelated);
        Object a=first.run(new JSONObject()),b=stray.run(new JSONObject());
        assertArrayEquals((float[])field(a,"sensorToXyzD50"),(float[])field(b,"sensorToXyzD50"),0);
        assertArrayEquals((double[])field(a,"sceneXy"),(double[])field(b,"sceneXy"),0);
    }
    @Test public void advertisedButIncompleteSecondProfileIsRejected()throws Exception{
        for(int n=0;n<3;n++){
            Fixture f=new Fixture(1,true);
            if(n==0)when(f.c.get(CameraCharacteristics.SENSOR_CALIBRATION_TRANSFORM2)).thenReturn(null);
            if(n==1)when(f.c.get(CameraCharacteristics.SENSOR_COLOR_TRANSFORM2)).thenReturn(null);
            if(n==2)when(f.c.get(CameraCharacteristics.SENSOR_FORWARD_MATRIX2)).thenReturn(null);
            assertThrows(IllegalStateException.class,()->f.run(new JSONObject()));
        }
    }
    @Test public void singleIlluminantStillRequiresFirstProfileAndNeutral()throws Exception{
        for(int n=0;n<5;n++){
            Fixture f=new Fixture(1,false);
            if(n==0)when(f.c.get(CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT1)).thenReturn(null);
            if(n==1)when(f.c.get(CameraCharacteristics.SENSOR_CALIBRATION_TRANSFORM1)).thenReturn(null);
            if(n==2)when(f.c.get(CameraCharacteristics.SENSOR_COLOR_TRANSFORM1)).thenReturn(null);
            if(n==3)when(f.c.get(CameraCharacteristics.SENSOR_FORWARD_MATRIX1)).thenReturn(null);
            if(n==4)when(f.r.get(CaptureResult.SENSOR_NEUTRAL_COLOR_POINT)).thenReturn(null);
            assertThrows(IllegalStateException.class,()->f.run(new JSONObject()));
        }
    }
    @Test public void allRecordedDualIlluminantTransformsRemainExact()throws Exception{
        for(int n=0;n<3;n++){
            Fixture f=new Fixture(n,true);JSONObject d=new JSONObject(),ex=f.j.getJSONObject("expected");Object m=f.run(d);
            float[] a=(float[])field(m,"sensorToXyzD50");JSONArray expected=ex.getJSONArray("sourceSensorToXYZD50");
            for(int i=0;i<9;i++)assertEquals(expected.getJSONArray(i/3).getDouble(i%3),a[i],0.0);
            assertEquals(ex.getDouble("sourceInterpolationFactor"),(Double)field(m,"interpolationFactor"),0);
            assertArrayEquals(new double[]{ex.getDouble("sceneWhiteX"),ex.getDouble("sceneWhiteY")},(double[])field(m,"sceneXy"),0);
            assertEquals(ex.getDouble("sceneCctKelvinLeicaLocus"),(Double)field(m,"sceneKelvin"),0);
            assertEquals(2,d.getInt("sourceCalibrationIlluminantCount"));assertFalse(d.getBoolean("sourceSingleIlluminantFallbackApplied"));
        }
    }
}
