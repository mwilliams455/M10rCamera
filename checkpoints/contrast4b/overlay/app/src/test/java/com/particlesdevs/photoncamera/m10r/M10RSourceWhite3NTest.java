package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.CaptureResult;
import android.util.Rational;
import org.junit.AfterClass;
import org.junit.BeforeClass;
import org.junit.Test;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/** The compatibility adapter owns its input, while preserving its original representation. */
public class M10RSourceWhite3NTest {
    @BeforeClass public static void keys() throws Exception { M10RSourceCalibration3CTest.keys(); }
    @AfterClass public static void restore() throws Exception { M10RSourceCalibration3CTest.restore(); }

    @Test public void exactFloatValuesAndProvenanceSurviveInputAndCopyMutation() {
        CaptureResult result=mock(CaptureResult.class);
        float[] values={.73123455f,1.73125f,.41987652f};
        Rational[] rationals={M10RSourceCalibration3CTest.number(values[0]),
                M10RSourceCalibration3CTest.number(values[1]),M10RSourceCalibration3CTest.number(values[2])};
        Rational originalRed=rationals[0];
        when(result.get(CaptureResult.SENSOR_NEUTRAL_COLOR_POINT)).thenReturn(rationals);
        when(result.get(CaptureResult.SENSOR_TIMESTAMP)).thenReturn(4321L);
        when(result.getFrameNumber()).thenReturn(71L);
        M10RSourceWhite3N white=M10RSourceWhite3N.fromCaptureResult(result);

        rationals[0]=M10RSourceCalibration3CTest.number(9);
        when(result.get(CaptureResult.SENSOR_TIMESTAMP)).thenReturn(9876L);
        when(result.getFrameNumber()).thenReturn(72L);
        white.copySourceNeutral()[1]=0;

        assertArrayEquals(values,white.copySourceNeutral(),0);
        for(int i=0;i<3;i++)assertEquals(Float.floatToRawIntBits(values[i]),
                Float.floatToRawIntBits(white.copySourceNeutral()[i]));
        assertEquals(Long.valueOf(4321),white.sensorTimestampNs());
        assertEquals(71L,white.frameNumber());
        assertEquals(M10RSourceWhite3N.Authority.VENDOR_CAPTURE_RESULT,white.authority());
        verify(originalRed,never()).doubleValue();
    }

    @Test public void missingNeutralIsNotReplacedWithInventedWhite() {
        CaptureResult result=mock(CaptureResult.class);
        assertNull(M10RSourceWhite3N.fromCaptureResult(result));
        Rational[] shortNeutral={M10RSourceCalibration3CTest.number(1),M10RSourceCalibration3CTest.number(1)};
        when(result.get(CaptureResult.SENSOR_NEUTRAL_COLOR_POINT)).thenReturn(shortNeutral);
        assertNull(M10RSourceWhite3N.fromCaptureResult(result));
    }

    @Test public void optionalTimestampAddsNoAdmissionRequirement() {
        CaptureResult result=mock(CaptureResult.class);
        Rational[] neutral={
                M10RSourceCalibration3CTest.number(.4),M10RSourceCalibration3CTest.number(2),
                M10RSourceCalibration3CTest.number(.6)};
        when(result.get(CaptureResult.SENSOR_NEUTRAL_COLOR_POINT)).thenReturn(neutral);
        M10RSourceWhite3N white=M10RSourceWhite3N.fromCaptureResult(result);
        assertNotNull(white);
        assertNull(white.sensorTimestampNs());
        assertEquals(0L,white.frameNumber());
        assertArrayEquals(new float[]{.4f,2,.6f},white.copySourceNeutral(),0);
    }
}
