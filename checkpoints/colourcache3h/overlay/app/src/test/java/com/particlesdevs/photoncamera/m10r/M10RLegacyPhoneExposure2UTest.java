package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.*;
import com.particlesdevs.photoncamera.capture.CaptureController;
import com.particlesdevs.photoncamera.processing.parameters.*;
import com.particlesdevs.photoncamera.processing.parameters.IsoExpoSelector.ExpoPair;
import java.lang.reflect.*;
import org.junit.*;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/** Ensure the remaining legacy entry point cannot reintroduce Leica gain. */
public class M10RLegacyPhoneExposure2UTest {
    @BeforeClass public static void keys()throws Exception{M10RCaptureMeterReference1ITest.keys();}
    @AfterClass public static void restore()throws Exception{M10RCaptureMeterReference1ITest.restoreKeys();}
    private static Object field(Object o,String n)throws Exception{
        Field f=o.getClass().getDeclaredField(n);f.setAccessible(true);return f.get(o);
    }
    private static Object select(M10RCaptureMeterReference1ITest.Fixture f)throws Exception{
        Method m=IsoExpoSelector.class.getDeclaredMethod("m10rAe1BSelect",CaptureController.class,M10RLiveMeterState.Snapshot.class);
        m.setAccessible(true);return m.invoke(null,f.controller,null);
    }
    @Test public void legacyEntryConservesPhoneTargetWithoutChangingOracle()throws Exception{
        CaptureResult previous=CaptureController.mPreviewCaptureResult;
        try(var f=new M10RCaptureMeterReference1ITest.Fixture(0)){
            CaptureController.mPreviewCaptureResult=f.result;
            f.controller.mPreviewExposureTime=5_524_044;f.controller.mPreviewIso=50;
            Object s=select(f);assertNotNull(s);
            ExpoPair pair=(ExpoPair)field(s,"pair");
            assertEquals(100,pair.iso,0);assertEquals(2_762_022L,pair.exposure);
            assertTrue((Long)field(s,"oracleExposureNs")>pair.exposure);
            assertEquals(false,field(s,"sensorClampApplied"));
        }finally{CaptureController.mPreviewCaptureResult=previous;}
    }
    @Test public void legacyPreviewCannotAuthorizeIsoAboveAdvertisedAnalogCeiling()throws Exception{
        CaptureResult previous=CaptureController.mPreviewCaptureResult;
        try(var f=new M10RCaptureMeterReference1ITest.Fixture(0)){
            CaptureController.mPreviewCaptureResult=f.result;
            f.controller.mPreviewExposureTime=30_000_000;f.controller.mPreviewIso=6402;
            when(f.chars.get(CameraCharacteristics.SENSOR_MAX_ANALOG_SENSITIVITY)).thenReturn(3200);
            Object s=select(f);assertNotNull(s);ExpoPair pair=(ExpoPair)field(s,"pair");
            assertEquals(3200,pair.iso,0);assertEquals(60_018_750L,pair.exposure);
            assertEquals(true,field(s,"sensorClampApplied"));
        }finally{CaptureController.mPreviewCaptureResult=previous;}
    }
}
