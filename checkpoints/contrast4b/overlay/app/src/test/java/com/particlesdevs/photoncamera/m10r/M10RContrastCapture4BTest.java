package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.CaptureRequest;
import android.os.Handler;
import com.particlesdevs.photoncamera.capture.CaptureController;
import com.particlesdevs.photoncamera.processing.parameters.IsoExpoSelector;
import com.particlesdevs.photoncamera.settings.PreferenceKeys;
import com.particlesdevs.photoncamera.settings.SensorConfigInjector;
import org.json.JSONObject;
import org.junit.*;
import org.mockito.ArgumentCaptor;
import static com.particlesdevs.photoncamera.m10r.M10RContrast4B.Level.*;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/** Real shutter admission and probe/final request construction; camera work is mocked. */
public class M10RContrastCapture4BTest {
    @BeforeClass public static void keys() throws Exception {
        M10RContrastLifecycle4BTest.initializePreferenceResources();
        M10RCaptureMeterReference1ITest.keys();
    }
    @AfterClass public static void restoreKeys() throws Exception {M10RCaptureMeterReference1ITest.restoreKeys();}
    @Before public void setup(){M10RPreviewState1A.clear(null);CaptureController.isProcessing=false;}
    @After public void cleanup(){M10RPreviewState1A.clear(null);CaptureController.isProcessing=false;}

    void queueShot(M10RCaptureMeterReference1ITest.Fixture f,M10RContrast4B.Level level) throws Exception {
        if(f.gate.busy())f.gate.finish(f.gate.active());
        f.prefs.when(PreferenceKeys::getM10RContrastValue).thenReturn(level.preferenceValue);
        f.set("mBackgroundHandler",null);
        f.set("m10rBackgroundInput1A",mock(M10RExposureCamera1C.Input.class));
        f.controller.takePicture();assertTrue(f.gate.preparing());
    }
    void changeAndObserve(M10RCaptureMeterReference1ITest.Fixture f,M10RContrast4B.Level level) throws Exception {
        f.prefs.when(PreferenceKeys::getM10RContrastValue).thenReturn(level.preferenceValue);
        M10RPreviewState1A.clear(null);
        String controls=(String)f.call("m10rControls1C",new Class<?>[0]);
        var o=M10RPreviewMetadata1E.observe(f.session,"2:4096x3072:0",controls,f.chars,f.result,f.request,
                System.nanoTime(),0,true).withContrast(level);
        M10RPreviewState1A.observe(o);
    }
    M10RContrast4B.Level captured(M10RCaptureMeterReference1ITest.Fixture f) throws Exception {
        return (M10RContrast4B.Level)f.call("m10rCaptureContrast4B",new Class<?>[0]);
    }

    @Test public void shutterFreezesBeforeBackgroundQueueAndBusyPressCannotReplaceIt() throws Exception {
        try(var f=new M10RCaptureMeterReference1ITest.Fixture(0)){
            queueShot(f,LOW);long first=f.gate.active();
            f.prefs.when(PreferenceKeys::getM10RContrastValue).thenReturn("high");
            f.controller.takePicture();assertEquals(first,f.gate.active());assertEquals(LOW,captured(f));
            f.call("m10rFinishShot1G",new Class<?>[]{long.class,String.class},first,null);
            queueShot(f,HIGH);long second=f.gate.active();assertTrue(second>first);assertEquals(HIGH,captured(f));
            f.call("m10rFinishShot1G",new Class<?>[]{long.class,String.class},first,"late completion");
            assertTrue(f.gate.owns(second));assertEquals(HIGH,captured(f));
        }
    }

    @Test public void foregroundProbeUsesAdmittedContrastDespiteNewPreviewSelection() throws Exception {
        try(var f=new M10RCaptureMeterReference1ITest.Fixture(0)){
            queueShot(f,LOW);changeAndObserve(f,HIGH);
            f.set("m10rBackgroundInput1A",null);f.set("m10rQueuedShutter1A",false);
            f.set("mBackgroundHandler",mock(Handler.class));f.start(false);
            assertNotNull(f.admitted);assertEquals(LOW,f.admitted.contrast4B);
            assertTrue(f.admitted.controlsKey.endsWith(":contrast4b=low"));
            assertEquals(true,f.call("m10rCurrent1C",new Class<?>[]{M10RExposureCamera1C.Input.class},f.admitted));
            when(f.preview.get(CaptureRequest.CONTROL_AE_EXPOSURE_COMPENSATION)).thenReturn(3);
            assertEquals(false,f.call("m10rCurrent1C",new Class<?>[]{M10RExposureCamera1C.Input.class},f.admitted));
        }
    }

    @Test public void backgroundProbeCannotReturnAfterSelectionWasClearedAndRestored() throws Exception {
        try(var f=new M10RCaptureMeterReference1ITest.Fixture(0)){
            changeAndObserve(f,LOW);f.start(true);assertNotNull(f.admitted);
            assertEquals(LOW,f.admitted.contrast4B);
            assertEquals(true,f.call("m10rCurrent1C",new Class<?>[]{M10RExposureCamera1C.Input.class},f.admitted));
            changeAndObserve(f,HIGH);changeAndObserve(f,LOW);
            assertEquals(false,f.call("m10rCurrent1C",new Class<?>[]{M10RExposureCamera1C.Input.class},f.admitted));
        }
    }

    @Test public void manualPhotoRequestGetsFrozenReportBeforeOtherCaptureWork() throws Exception {
        try(var f=new M10RCaptureMeterReference1ITest.Fixture(0);
                var sensor=mockStatic(SensorConfigInjector.class);
                var iso=mockStatic(IsoExpoSelector.class);
                var live=mockStatic(M10RLiveMeterState.class);
                var area=mockStatic(M10RMeterArea1A.class)){
            queueShot(f,LOW);f.prefs.when(PreferenceKeys::getM10RContrastValue).thenReturn("high");
            f.set("m10rBackgroundInput1A",null);
            // Stop after the real controller has set the request tag. No HAL or save is run.
            iso.when(()->IsoExpoSelector.GenerateExpoPair(-1,f.controller))
                    .thenThrow(new IllegalStateException("test_after_request_tag"));
            f.call("captureStillPicturePrepared1C",new Class<?>[]{M10RExposureCapture1B.Selection.class,M10RExposureReport1C.class},null,null);
            ArgumentCaptor<Object> tags=ArgumentCaptor.forClass(Object.class);verify(f.meter).setTag(tags.capture());
            assertTrue(tags.getValue() instanceof M10RExposureReport1C);
            var report=(M10RExposureReport1C)tags.getValue();assertEquals(LOW,report.contrast4B);
            assertEquals("low",new JSONObject(report.json).getString("contrastSetting4B"));
        }
    }

    @Test public void reportForAnotherContrastCannotRelabelAdmittedPhoto() throws Exception {
        try(var f=new M10RCaptureMeterReference1ITest.Fixture(0)){
            queueShot(f,LOW);f.set("m10rBackgroundInput1A",null);
            f.call("captureStillPicturePrepared1C",new Class<?>[]{M10RExposureCapture1B.Selection.class,M10RExposureReport1C.class},
                    null,new M10RExposureReport1C(new JSONObject(),HIGH));
            verify(f.device,never()).createCaptureRequest(anyInt());
            verify(f.events).onProcessingError(contains("contrast selection differs"));assertFalse(f.gate.busy());
        }
    }
}
