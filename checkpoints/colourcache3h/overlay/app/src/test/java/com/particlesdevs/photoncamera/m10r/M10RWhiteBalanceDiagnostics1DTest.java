package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.*;
import android.hardware.camera2.params.RggbChannelVector;
import android.util.Rational;
import org.json.JSONObject;
import org.junit.*;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

public class M10RWhiteBalanceDiagnostics1DTest {
    @BeforeClass public static void keys()throws Exception {
        M10RPreviewMetadata1ETest.installFrameworkKeyIdentities();
        var m=M10RPreviewMetadata1ETest.class.getDeclaredMethod("keys",Class.class,Class.class,String[].class);m.setAccessible(true);
        m.invoke(null,CaptureRequest.class,CaptureRequest.Key.class,new String[]{"CONTROL_AWB_MODE","CONTROL_AWB_LOCK","COLOR_CORRECTION_MODE","COLOR_CORRECTION_GAINS","COLOR_CORRECTION_TRANSFORM"});
        m.invoke(null,CaptureResult.class,CaptureResult.Key.class,new String[]{"CONTROL_AWB_MODE","CONTROL_AWB_STATE","CONTROL_AWB_LOCK","COLOR_CORRECTION_MODE","COLOR_CORRECTION_GAINS","COLOR_CORRECTION_TRANSFORM","SENSOR_NEUTRAL_COLOR_POINT","SENSOR_TIMESTAMP"});
        m.invoke(null,CameraCharacteristics.class,CameraCharacteristics.Key.class,new String[]{"SENSOR_REFERENCE_ILLUMINANT1","SENSOR_REFERENCE_ILLUMINANT2","SENSOR_CALIBRATION_TRANSFORM1","SENSOR_CALIBRATION_TRANSFORM2","SENSOR_COLOR_TRANSFORM1","SENSOR_COLOR_TRANSFORM2","SENSOR_FORWARD_MATRIX1","SENSOR_FORWARD_MATRIX2"});
    }
    @AfterClass public static void restore()throws Exception {M10RPreviewMetadata1ETest.restoreFrameworkKeys();}
    static Rational ratio(double v){Rational r=mock(Rational.class);when(r.doubleValue()).thenReturn(v);return r;}
    @Test public void actualStillControlsKeepRequestedAndDeliveredValuesSeparate()throws Exception {
        CameraCharacteristics c=mock(CameraCharacteristics.class);CaptureRequest q=mock(CaptureRequest.class);CaptureResult r=mock(CaptureResult.class);
        when(q.get(CaptureRequest.CONTROL_AWB_MODE)).thenReturn(0);when(q.get(CaptureRequest.CONTROL_AWB_LOCK)).thenReturn(true);
        when(r.get(CaptureResult.CONTROL_AWB_MODE)).thenReturn(1);when(r.get(CaptureResult.CONTROL_AWB_LOCK)).thenReturn(false);
        when(r.get(CaptureResult.CONTROL_AWB_STATE)).thenReturn(2);when(r.get(CaptureResult.SENSOR_TIMESTAMP)).thenReturn(123L);
        when(r.getFrameNumber()).thenReturn(456L);
        Rational[] neutral={ratio(.525390625),ratio(1),ratio(.498046875)};
        when(r.get(CaptureResult.SENSOR_NEUTRAL_COLOR_POINT)).thenReturn(neutral);
        RggbChannelVector g=mock(RggbChannelVector.class);when(g.getRed()).thenReturn(2f);when(g.getGreenEven()).thenReturn(1f);when(g.getGreenOdd()).thenReturn(1.1f);when(g.getBlue()).thenReturn(2.2f);
        when(r.get(CaptureResult.COLOR_CORRECTION_GAINS)).thenReturn(g);
        JSONObject destination=new JSONObject().put("existingCaptureValue",17);
        short[] raw=M10RWhiteBalanceProbe1DTest.scene(0,1,.2,(x,y)->M10RWhiteBalanceProbe1DTest.WHITE);
        M10RWhiteBalanceDiagnostics1D.append(destination,raw,256,192,0,1,4506,c,q,r);
        var d=destination.getJSONObject("m10rWhiteBalanceProbe1D");
        assertEquals(0,d.getJSONObject("requested").getInt("awbMode"));assertTrue(d.getJSONObject("requested").getBoolean("awbLock"));
        assertEquals(1,d.getJSONObject("delivered").getInt("awbMode"));assertFalse(d.getJSONObject("delivered").getBoolean("awbLock"));
        assertEquals(2,d.getJSONObject("delivered").getInt("awbState"));assertEquals(1.1,d.getJSONObject("delivered").getJSONArray("gainsRGGB").getDouble(2),1e-6);
        assertEquals(123,d.getLong("sourceFrameTimestampNs"));assertEquals(456,d.getLong("sourceFrameNumber"));
        assertTrue(d.getBoolean("hasProposal"));assertFalse(d.getBoolean("applied"));assertEquals(17,destination.getInt("existingCaptureValue"));
        assertTrue(d.getJSONObject("requested").isNull("gainsRGGB"));
    }
    @Test public void missingMetadataAndDiagnosticFailureCannotAlterExistingCaptureData()throws Exception {
        var c=mock(CameraCharacteristics.class);var r=mock(CaptureResult.class);JSONObject destination=new JSONObject().put("existing",7);
        M10RWhiteBalanceDiagnostics1D.append(destination,new short[256*192],256,192,0,1,4506,c,null,r);
        var d=destination.getJSONObject("m10rWhiteBalanceProbe1D");assertFalse(d.getBoolean("hasProposal"));assertFalse(d.getJSONObject("requested").getBoolean("available"));
        assertTrue(d.getJSONObject("delivered").isNull("awbMode"));
        when(r.get(CaptureResult.SENSOR_NEUTRAL_COLOR_POINT)).thenThrow(new IllegalStateException("fixture"));
        M10RWhiteBalanceDiagnostics1D.append(destination,new short[256*192],256,192,0,1,4506,c,null,r);
        assertEquals("diagnostic_error",destination.getJSONObject("m10rWhiteBalanceProbe1D").getString("reason"));assertEquals(7,destination.getInt("existing"));
    }
}
