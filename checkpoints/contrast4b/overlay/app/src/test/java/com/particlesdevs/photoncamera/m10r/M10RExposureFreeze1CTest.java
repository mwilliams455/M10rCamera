package com.particlesdevs.photoncamera.m10r;
import android.hardware.camera2.CaptureRequest;
import com.particlesdevs.photoncamera.api.CameraMode;
import com.particlesdevs.photoncamera.api.Settings;
import com.particlesdevs.photoncamera.app.PhotonCamera;
import com.particlesdevs.photoncamera.capture.CaptureController;
import com.particlesdevs.photoncamera.manual.ParamController;
import com.particlesdevs.photoncamera.processing.parameters.IsoExpoSelector;
import org.junit.Test;
import org.mockito.MockedStatic;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;
public class M10RExposureFreeze1CTest {
    M10RExposureCapture1B.Selection selection(){
        var r=new M10RExposure1A.Request("camera",1,"renderer",1000,1,2,24,100,50000,true);
        return M10RExposureCapture1B.select(null,r,new M10RExposureCapture1B.Reference("camera",1,990,10000000,200,0,0),
                new M10RExposureCapture1B.Limits(100000,1000000000,100,3200));
    }
    @Test public void actualSetExpoConsumesFrozenPairDespiteLaterPreviewChanges(){
        try(MockedStatic<PhotonCamera> app=mockStatic(PhotonCamera.class);
                MockedStatic<com.particlesdevs.photoncamera.util.Log> logging=mockStatic(com.particlesdevs.photoncamera.util.Log.class)){
            Settings settings=mock(Settings.class);settings.selectedMode=CameraMode.PHOTO;app.when(PhotonCamera::getSettings).thenReturn(settings);
            CaptureController c=mock(CaptureController.class);ParamController p=mock(ParamController.class);when(c.getParamController()).thenReturn(p);
            CaptureController.mCameraCharacteristics=null;CaptureController.mPreviewCaptureResult=null;
            var s=selection();assertTrue(s.apply);assertTrue(s.fallback);assertEquals(0,s.appliedAutoEv,0);
            IsoExpoSelector.prepareM10rExposure1CCapture(c,s);
            c.mPreviewExposureTime=500000000;c.mPreviewIso=3200;
            var display=IsoExpoSelector.GenerateExpoPair(-1,c);assertEquals(s.exposureNs,display.exposure);assertEquals(s.iso,display.iso);
            CaptureRequest.Builder builder=mock(CaptureRequest.Builder.class);IsoExpoSelector.setExpo(builder,0,c);
            verify(builder).set(CaptureRequest.SENSOR_EXPOSURE_TIME,s.exposureNs);
            verify(builder).set(CaptureRequest.SENSOR_SENSITIVITY,s.iso);
            assertEquals(1,IsoExpoSelector.fullpairs.size());assertEquals(s.exposureNs,IsoExpoSelector.lastSelectedExposure);
        }
    }
    @Test public void explicitManualOrWrongModeRejectsAutomaticFreeze(){
        try(MockedStatic<PhotonCamera> app=mockStatic(PhotonCamera.class);
                MockedStatic<com.particlesdevs.photoncamera.util.Log> logging=mockStatic(com.particlesdevs.photoncamera.util.Log.class)){
            Settings settings=mock(Settings.class);settings.selectedMode=CameraMode.PHOTO;app.when(PhotonCamera::getSettings).thenReturn(settings);
            CaptureController c=mock(CaptureController.class);ParamController p=mock(ParamController.class);when(c.getParamController()).thenReturn(p);
            when(p.getCurrentISOValue()).thenReturn(400.0);assertThrows(IllegalStateException.class,()->IsoExpoSelector.prepareM10rExposure1CCapture(c,selection()));
            when(p.getCurrentISOValue()).thenReturn(0.0);when(p.getCurrentExposureValue()).thenReturn(10000000.0);
            assertThrows(IllegalStateException.class,()->IsoExpoSelector.prepareM10rExposure1CCapture(c,selection()));
            // Motion now supports M10R automatic capture; Night remains outside it.
            when(p.getCurrentExposureValue()).thenReturn(0.0);settings.selectedMode=CameraMode.NIGHT;
            assertThrows(IllegalStateException.class,()->IsoExpoSelector.prepareM10rExposure1CCapture(c,selection()));
        }
    }
}
