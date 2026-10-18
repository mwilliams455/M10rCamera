package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.*;
import android.opengl.GLES20;
import org.junit.After;
import org.junit.BeforeClass;
import org.junit.AfterClass;
import org.junit.Test;
import java.util.ArrayList;
import java.util.concurrent.atomic.AtomicLong;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

public class M10RPreviewMetadata1ETest {
    // Local Android unit-test stubs leave framework key constants null. Give each
    // key a distinct identity so mocked get() calls cannot silently alias keys.
    private static final ArrayList<java.lang.reflect.Field> keyFields=new ArrayList<>();
    private static final ArrayList<Object> oldKeys=new ArrayList<>();
    private static Object unsafe;
    private static Class<?> unsafeClass;
    @BeforeClass public static void installFrameworkKeyIdentities()throws Exception {
        unsafeClass=Class.forName("sun.misc.Unsafe");
        var f=unsafeClass.getDeclaredField("theUnsafe");f.setAccessible(true);
        unsafe=f.get(null);
        keys(CaptureResult.class,CaptureResult.Key.class,"SENSOR_TIMESTAMP","SENSOR_EXPOSURE_TIME",
                "SENSOR_SENSITIVITY","CONTROL_AE_EXPOSURE_COMPENSATION");
        keys(CaptureRequest.class,CaptureRequest.Key.class,"CONTROL_AE_EXPOSURE_COMPENSATION","CONTROL_AE_MODE");
        keys(CameraCharacteristics.class,CameraCharacteristics.Key.class,"CONTROL_AE_COMPENSATION_STEP");
    }
    private static void keys(Class<?> owner,Class<?> type,String...names)throws Exception {
        for(String name:names){
            var f=owner.getField(name);Object old=f.get(null);keyFields.add(f);oldKeys.add(old);
            putKey(f,mock(type));
        }
    }
    private static void putKey(java.lang.reflect.Field field,Object value)throws Exception {
        Object base=unsafeClass.getMethod("staticFieldBase",java.lang.reflect.Field.class).invoke(unsafe,field);
        long offset=(Long)unsafeClass.getMethod("staticFieldOffset",java.lang.reflect.Field.class).invoke(unsafe,field);
        unsafeClass.getMethod("putObjectVolatile",Object.class,long.class,Object.class).invoke(unsafe,base,offset,value);
    }
    @AfterClass public static void restoreFrameworkKeys()throws Exception {
        for(int i=0;i<keyFields.size();i++){
            putKey(keyFields.get(i),oldKeys.get(i));
        }
    }
    static final long START=1_100_000_000L, TS=9_000_000_000L, MS=1_000_000L;
    final M10RPreviewPlan1ATest fixture=new M10RPreviewPlan1ATest();
    final CameraCharacteristics chars=mock(CameraCharacteristics.class);
    final CaptureRequest request=mock(CaptureRequest.class);
    CaptureResult result(long timestamp,Integer compensation){
        CaptureResult r=mock(CaptureResult.class);
        when(r.get(CaptureResult.SENSOR_TIMESTAMP)).thenReturn(timestamp);
        when(r.get(CaptureResult.SENSOR_EXPOSURE_TIME)).thenReturn(10_000_000L);
        when(r.get(CaptureResult.SENSOR_SENSITIVITY)).thenReturn(200);
        when(r.get(CaptureResult.CONTROL_AE_EXPOSURE_COMPENSATION)).thenReturn(compensation);
        return r;
    }
    M10RPreviewState1A.Observation observe(CaptureResult r,long now){
        return M10RPreviewMetadata1E.observe(fixture.owner,"cam","controls",chars,r,request,now,0);
    }
    @After public void cleanup(){M10RPreviewState1A.clear(null);}
    private void requestEv(int steps){
        when(request.get(CaptureRequest.CONTROL_AE_EXPOSURE_COMPENSATION)).thenReturn(steps);
        when(request.get(CaptureRequest.CONTROL_AE_MODE)).thenReturn(CaptureRequest.CONTROL_AE_MODE_ON);
    }
    private void compensationUnit(double value){
        android.util.Rational unit=mock(android.util.Rational.class);
        when(unit.doubleValue()).thenReturn(value);
        when(chars.get(CameraCharacteristics.CONTROL_AE_COMPENSATION_STEP)).thenReturn(unit);
    }
    @Test public void reportedControlTakesPrecedenceOverRequest(){
        requestEv(-3);compensationUnit(1.0/3);
        var o=observe(result(TS,6),START);
        assertTrue(o.captureEvidence);assertEquals(2,o.referenceEv,1e-12);
        assertEquals(TS,o.timestamp);assertEquals(10_000_000L,o.exposureNs);assertEquals(200,o.iso);
    }
    @Test public void requestControlUsesCalibratedEvOnlyForDisplay(){
        requestEv(3);compensationUnit(1.0/3);
        var o=observe(result(TS,null),START);
        assertFalse(o.captureEvidence);assertEquals(1,o.referenceEv,1e-12);
        assertEquals(10_000_000L,o.exposureNs);assertEquals(200,o.iso);
    }
    @Test public void missingOrUnsafeRequestIsNeverAssumedToBeZeroEv(){
        CaptureResult r=result(TS,null);
        assertThrows(IllegalArgumentException.class,()->observe(r,START));
        requestEv(0);
        for(Integer mode:new Integer[]{null,CaptureRequest.CONTROL_AE_MODE_OFF,
                CaptureRequest.CONTROL_AE_MODE_ON_AUTO_FLASH}){
            when(request.get(CaptureRequest.CONTROL_AE_MODE)).thenReturn(mode);
            assertThrows(IllegalArgumentException.class,()->observe(r,START));
        }
        assertThrows(IllegalArgumentException.class,()->M10RPreviewMetadata1E.observe(
                fixture.owner,"cam","controls",chars,r,null,START,0));
    }
    @Test public void nonzeroCompensationRequiresValidUnit(){
        requestEv(1);
        assertThrows(IllegalArgumentException.class,()->observe(result(TS,null),START));
        for(double unit:new double[]{0,-1,Double.NaN,Double.POSITIVE_INFINITY}){
            compensationUnit(unit);
            assertThrows(IllegalArgumentException.class,()->observe(result(TS,null),START));
        }
    }
    @Test public void missingSensorFieldsStillRejectWithSpecificReasons(){
        requestEv(0);
        CaptureResult r=result(TS,null);
        when(r.get(CaptureResult.SENSOR_TIMESTAMP)).thenReturn(null);
        assertEquals("preview_sensor_timestamp_missing",assertThrows(IllegalArgumentException.class,()->observe(r,START)).getMessage());
        when(r.get(CaptureResult.SENSOR_TIMESTAMP)).thenReturn(TS);
        when(r.get(CaptureResult.SENSOR_EXPOSURE_TIME)).thenReturn(null);
        assertEquals("preview_sensor_exposure_missing",assertThrows(IllegalArgumentException.class,()->observe(r,START)).getMessage());
        when(r.get(CaptureResult.SENSOR_EXPOSURE_TIME)).thenReturn(10_000_000L);
        when(r.get(CaptureResult.SENSOR_SENSITIVITY)).thenReturn(null);
        assertEquals("preview_sensor_ISO_missing",assertThrows(IllegalArgumentException.class,()->observe(r,START)).getMessage());
        when(r.get(CaptureResult.SENSOR_SENSITIVITY)).thenReturn(0);
        assertThrows(IllegalArgumentException.class,()->observe(r,START));
    }
    @Test public void displayOnlyObservationCannotAcknowledgeCaptureEvenWithMatchingPlan(){
        requestEv(0);
        var o=observe(result(TS,null),START);
        M10RPreviewState1A.observe(o);var p=fixture.plan(0,false);M10RPreviewState1A.publish(p);
        M10RPreviewState1A.displayed(o,p,START,"display_only_request_EV");
        assertEquals(0,M10RPreviewState1A.display().planId);
        assertSame(o,M10RPreviewState1A.forTexture(TS,START+250*MS));
        assertNull(M10RPreviewState1A.forTexture(TS,START+250*MS+1));
        assertNull(M10RPreviewState1A.recentForDisplay(TS-1,START));
        M10RPreviewState1A.rejectObservation(fixture.owner,"other_camera","controls","source_changed");
        assertNull(M10RPreviewState1A.forTexture(TS,START));assertNull(M10RPreviewState1A.plan());
    }
    @Test public void displayOnlyResultCannotExtendOriginalColourDeadline(){
        requestEv(0);
        var full=observe(result(TS,0),START);
        var good=new M10RPreviewColour1A.Frame(full,true,"ready",new byte[4],new byte[4],new float[9]);
        var sparse=observe(result(TS+900*MS,null),START+900*MS);
        assertSame(good,M10RPreviewColour1A.available(good,null,sparse,START+1000*MS));
        assertNull(M10RPreviewColour1A.available(good,null,sparse,START+1000*MS+1));
    }
    @Test public void rejectionDiagnosticRetainsSpecificMissingField(){
        requestEv(0);var o=observe(result(TS,0),START);M10RPreviewState1A.observe(o);
        M10RPreviewState1A.rejectObservation(fixture.owner,"cam","controls","preview_sensor_ISO_missing");
        assertTrue(M10RPreviewState1A.debugReason().contains("rejected=preview_sensor_ISO_missing"));
        assertSame(o,M10RPreviewState1A.forTexture(TS,START+MS));
        assertNull(M10RPreviewState1A.forTexture(TS,START+251*MS));
    }
    @Test public void intermittentMissingAeEchoDoesNotRepeatedlyDisableColourAfterCapture(){
        when(request.get(CaptureRequest.CONTROL_AE_EXPOSURE_COMPENSATION)).thenReturn(0);
        when(request.get(CaptureRequest.CONTROL_AE_MODE)).thenReturn(CaptureRequest.CONTROL_AE_MODE_ON);
        AtomicLong clock=new AtomicLong(START);ArrayList<Integer> enabled=new ArrayList<>();
        try(var gl=mockStatic(GLES20.class);var lut=mockStatic(M10RPreviewColour1A.class)){
            gl.when(()->GLES20.glGetUniformLocation(1,"m10rEnabled")).thenReturn(17);
            gl.when(()->GLES20.glUniform1i(eq(17),anyInt())).thenAnswer(i->{enabled.add(i.getArgument(1));return null;});
            // Colour remains available: this regression isolates admission of camera metadata.
            lut.when(()->M10RPreviewColour1A.request(any(),anyLong())).thenAnswer(i->{
                var o=(M10RPreviewState1A.Observation)i.getArgument(0);
                return new M10RPreviewColour1A.Frame(o,true,"ready",new byte[4],new byte[4],new float[9]);});
            var preview=new M10RPreviewGl1A(clock::get);
            for(int i=0;i<60;i++){
                long ts=TS+i*33*MS;clock.set(START+i*33*MS);
                CaptureResult r=result(ts,i%6==0?Integer.valueOf(0):null);
                try {M10RPreviewState1A.observe(observe(r,clock.get()));}
                catch(IllegalArgumentException e){M10RPreviewState1A.rejectObservation(fixture.owner,"cam","controls");}
                if(i==0)M10RPreviewState1A.publish(fixture.plan(0,false));
                preview.bind(1,ts);preview.drawn();
                assertEquals("sparse callback frame "+i,Integer.valueOf(1),enabled.get(enabled.size()-1));
                if(i%6!=0)assertEquals(0,M10RPreviewState1A.display().planId);
            }
        }
    }
}
