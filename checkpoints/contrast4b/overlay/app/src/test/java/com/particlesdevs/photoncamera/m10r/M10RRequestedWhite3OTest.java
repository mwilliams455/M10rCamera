package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.CaptureResult;
import android.hardware.camera2.params.RggbChannelVector;
import android.util.Rational;
import org.junit.AfterClass;
import org.junit.BeforeClass;
import org.junit.Test;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/** Request authority, immutable copies, rejection and bounded reconstruction without JNI. */
public class M10RRequestedWhite3OTest {
    @BeforeClass public static void keys() throws Exception { M10RCaptureMeterReference1ITest.keys(); }
    @AfterClass public static void restore() throws Exception { M10RCaptureMeterReference1ITest.restoreKeys(); }

    static RggbChannelVector gains(float r,float ge,float go,float b) {
        RggbChannelVector gains=mock(RggbChannelVector.class);
        when(gains.getRed()).thenReturn(r);when(gains.getGreenEven()).thenReturn(ge);
        when(gains.getGreenOdd()).thenReturn(go);when(gains.getBlue()).thenReturn(b);
        return gains;
    }
    static CaptureRequest request(float r,float ge,float go,float b) {
        CaptureRequest request=mock(CaptureRequest.class);
        RggbChannelVector gains=gains(r,ge,go,b);
        when(request.get(CaptureRequest.CONTROL_AWB_MODE)).thenReturn(CaptureRequest.CONTROL_AWB_MODE_OFF);
        when(request.get(CaptureRequest.COLOR_CORRECTION_GAINS)).thenReturn(gains);
        return request;
    }
    static CaptureRequest autoRequest() {
        CaptureRequest request=mock(CaptureRequest.class);
        when(request.get(CaptureRequest.CONTROL_AWB_MODE)).thenReturn(CaptureRequest.CONTROL_AWB_MODE_AUTO);
        return request;
    }

    @Test public void autoIgnoresUnusedManualGainsAndKeepsOriginalFloatImport() {
        CaptureResult result=mock(CaptureResult.class);
        float[] values={.73123455f,1.73125f,.41987652f};
        Rational[] neutral={M10RSourceCalibration3CTest.number(values[0]),
                M10RSourceCalibration3CTest.number(values[1]),M10RSourceCalibration3CTest.number(values[2])};
        when(result.get(CaptureResult.SENSOR_NEUTRAL_COLOR_POINT)).thenReturn(neutral);
        when(result.getFrameNumber()).thenReturn(73L);
        CaptureRequest auto=autoRequest();RggbChannelVector leftover=gains(Float.NaN,0,0,-1);
        when(auto.get(CaptureRequest.COLOR_CORRECTION_GAINS)).thenReturn(leftover);
        var selected=M10RSourceWhite3N.select(result,auto);
        assertArrayEquals(values,selected.copySourceNeutral(),0);
        assertEquals(M10RSourceWhite3N.Authority.VENDOR_CAPTURE_RESULT,selected.authority());
        assertNull(selected.sensorTimestampNs());assertEquals(73L,selected.frameNumber());
        assertNull(M10RSourceWhite3N.manualNeutral(auto));
        assertEquals(M10RSourceWhite3N.requestKey(null),M10RSourceWhite3N.requestKey(auto));
        verifyNoInteractions(leftover);
        for(Rational component:neutral)verify(component,never()).doubleValue();
    }

    @Test public void manualUsesFrozenRequestEvenWithoutVendorNeutralAndDefensivelyCopiesValues() {
        CaptureResult result=mock(CaptureResult.class);
        when(result.get(CaptureResult.SENSOR_TIMESTAMP)).thenReturn(1234L);
        when(result.getFrameNumber()).thenReturn(19L);
        CaptureRequest request=request(2.7f,1.15f,1.25f,3.3f);
        float green=(1.15f+1.25f)/2f;
        float[] expected={green/2.7f,1,green/3.3f};
        var selected=M10RSourceWhite3N.select(result,request);
        float[] first=M10RSourceWhite3N.manualNeutral(request),second=M10RSourceWhite3N.manualNeutral(request);
        assertNotSame(first,second);assertArrayEquals(expected,first,0);first[0]=99;
        assertArrayEquals(expected,second,0);
        selected.copySourceNeutral()[0]=99;selected.copyRequestedGains()[0]=99;
        RggbChannelVector later=gains(10,1,1,10);
        when(request.get(CaptureRequest.COLOR_CORRECTION_GAINS)).thenReturn(later);
        when(result.get(CaptureResult.SENSOR_TIMESTAMP)).thenReturn(9999L);
        assertArrayEquals(expected,selected.copySourceNeutral(),0);
        assertArrayEquals(new float[]{2.7f,1.15f,1.25f,3.3f},selected.copyRequestedGains(),0);
        assertEquals(Long.valueOf(1234),selected.sensorTimestampNs());assertEquals(19,selected.frameNumber());
        assertEquals(M10RSourceWhite3N.Authority.MANUAL_CAPTURE_REQUEST_GAINS,selected.authority());
        verify(result,never()).get(CaptureResult.SENSOR_NEUTRAL_COLOR_POINT);
    }

    @Test public void invalidExplicitManualControlsRejectWithoutVendorFallback() {
        CaptureResult result=mock(CaptureResult.class);
        CaptureRequest missing=request(2,1,1,2);
        when(missing.get(CaptureRequest.COLOR_CORRECTION_GAINS)).thenReturn(null);
        assertEquals("manual_WB_request_gains_missing",assertThrows(IllegalArgumentException.class,
                ()->M10RSourceWhite3N.manualNeutral(missing)).getMessage());
        for(float invalid:new float[]{0,-1,Float.NaN,Float.POSITIVE_INFINITY}) {
            for(int channel=0;channel<4;channel++) {
                float[] values={2,1,1,2};values[channel]=invalid;
                CaptureRequest request=request(values[0],values[1],values[2],values[3]);
                assertThrows(IllegalArgumentException.class,()->M10RSourceWhite3N.select(result,request));
                assertThrows(IllegalArgumentException.class,()->M10RSourceWhite3N.manualNeutral(request));
            }
        }
        CaptureRequest overflow=request(Float.MIN_VALUE,1,1,1);
        assertEquals("manual_WB_request_neutral_invalid",assertThrows(IllegalArgumentException.class,
                ()->M10RSourceWhite3N.manualNeutral(overflow)).getMessage());
        verify(result,never()).get(CaptureResult.SENSOR_NEUTRAL_COLOR_POINT);
    }

    @Test public void gainTwentyOnlyBoundsTemporaryAmazeConditioningNotSelectedWhite() {
        CaptureResult result=mock(CaptureResult.class);
        var selected=M10RSourceWhite3N.select(result,request(20,1,1,.1f));
        assertArrayEquals(new float[]{.05f,1,10},selected.copySourceNeutral(),0);
        double[] conditioned=selected.copyManualAmazeNeutral();
        assertArrayEquals(new double[]{.0625,10},conditioned,0);
        conditioned[0]=12;
        assertArrayEquals(new double[]{.0625,10},selected.copyManualAmazeNeutral(),0);
        assertArrayEquals(new float[]{.05f,1,10},selected.copySourceNeutral(),0);
        var large=M10RSourceWhite3N.select(result,request(.01f,1,1,1));
        assertEquals(100f,large.copySourceNeutral()[0],0);
        assertEquals(16,large.copyManualAmazeNeutral()[0],0);
    }
}
