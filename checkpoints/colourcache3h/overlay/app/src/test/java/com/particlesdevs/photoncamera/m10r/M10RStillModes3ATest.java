package com.particlesdevs.photoncamera.m10r;

import android.graphics.Bitmap;
import android.graphics.ImageFormat;
import android.hardware.camera2.*;
import android.media.*;
import com.particlesdevs.photoncamera.api.*;
import com.particlesdevs.photoncamera.app.PhotonCamera;
import com.particlesdevs.photoncamera.capture.CaptureController;
import com.particlesdevs.photoncamera.manual.ParamController;
import com.particlesdevs.photoncamera.processing.*;
import com.particlesdevs.photoncamera.processing.parameters.*;
import java.nio.ByteBuffer;
import java.nio.file.Path;
import java.util.*;
import org.json.JSONObject;
import org.junit.*;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/** Mode routing regression checks; camera hardware and native rendering are mocked. */
public class M10RStillModes3ATest {
    @BeforeClass public static void keys() throws Exception { M10RCaptureMeterReference1ITest.keys(); }
    @AfterClass public static void restore() throws Exception { M10RCaptureMeterReference1ITest.restoreKeys(); }
    @After public void clean() { CaptureController.isProcessing=false;M10RPreviewState1A.clear(null);SaverImplementation.IMAGE_BUFFER.clear(); }

    @Test public void photoAndMotionAlwaysUseOneRawAndNeverEnterBufferedBurst() {
        boolean hdr=IsoExpoSelector.HDR;
        try(var app=mockStatic(PhotonCamera.class)) {
            Settings s=mock(Settings.class);s.frameCount=37;s.DebugData=true;
            app.when(PhotonCamera::getSettings).thenReturn(s);
            CaptureController c=mock(CaptureController.class,CALLS_REAL_METHODS);
            for(CameraMode mode:new CameraMode[]{CameraMode.PHOTO,CameraMode.MOTION}) {
                s.selectedMode=mode;
                for(boolean h:new boolean[]{false,true})for(boolean dual:new boolean[]{false,true}) {
                    IsoExpoSelector.HDR=h;c.isDualSession=dual;
                    assertEquals(1,FrameNumberSelector.getFrames());assertEquals(0,FrameNumberSelector.throwCount);
                    assertFalse(c.isZslMode());
                }
            }
            assertEquals(CameraMode.MOTION,CameraMode.valueOf(2));assertEquals(CameraMode.PHOTO,CameraMode.valueOf(3));
            for(CameraMode mode:new CameraMode[]{CameraMode.NIGHT,CameraMode.VIDEO,CameraMode.RAWVIDEO,CameraMode.UNLIMITED})
                assertFalse(CameraMode.usesM10RStillPipeline(mode));
        } finally {IsoExpoSelector.HDR=hdr;}
    }
    @Test public void bothModesEnableM10rAutoPreviewAndRetainManualBypass() throws Exception {
        try(var f=new M10RCaptureMeterReference1ITest.Fixture(0)) {
            Settings s=PhotonCamera.getSettings();ParamController p=f.controller.getParamController();
            for(CameraMode mode:CameraMode.values()) {
                s.selectedMode=mode;when(p.getCurrentISOValue()).thenReturn(0.0);when(p.getCurrentExposureValue()).thenReturn(0.0);
                assertEquals(mode==CameraMode.PHOTO||mode==CameraMode.MOTION,f.controller.isM10RLiveViewAuto1U());
                when(p.getCurrentISOValue()).thenReturn(100.0);assertFalse(f.controller.isM10RLiveViewAuto1U());
                when(p.getCurrentISOValue()).thenReturn(0.0);when(p.getCurrentExposureValue()).thenReturn(1000000.0);
                assertFalse(f.controller.isM10RLiveViewAuto1U());
            }
        }
    }
    static void motionReference(M10RCaptureMeterReference1ITest.Fixture f) throws Exception {
        PhotonCamera.getSettings().selectedMode=CameraMode.MOTION;
        String controls=(String)f.call("m10rControls1C",new Class<?>[0]);
        M10RPreviewState1A.clear(null);
        M10RPreviewState1A.observe(M10RPreviewMetadata1E.observe(f.session,"2:4096x3072:0",controls,
                f.chars,f.result,f.request,System.nanoTime(),0,
                M10RPreviewMetadata1E.requestMatchesCurrentControls(f.request,f.preview)));
    }
    @Test public void motionMetersAndConsumesTheFrozenM10rExposure() throws Exception {
        CaptureResult previous=CaptureController.mPreviewCaptureResult;
        try(var f=new M10RCaptureMeterReference1ITest.Fixture(0);var logging=mockStatic(com.particlesdevs.photoncamera.util.Log.class)) {
            motionReference(f);M10RPreviewBackgroundMeter1LTest.liveControls(f);
            f.start(true);assertNotNull(f.admitted);assertTrue(f.admitted.controlsKey.startsWith("MOTION:"));
            f.finish(M10RPreviewBackgroundMeter1LTest.measured(f,System.nanoTime()));
            var plan=M10RPreviewState1A.plan();assertNotNull(plan);assertTrue(plan.selection.apply);
            CaptureController.mPreviewCaptureResult=f.result;
            IsoExpoSelector.prepareM10rExposure1CCapture(f.controller,plan.selection);
            var pending=IsoExpoSelector.GenerateExpoPair(-1,f.controller);
            assertEquals(plan.selection.exposureNs,pending.exposure);assertEquals(plan.selection.iso,pending.iso,0);
            CaptureRequest.Builder still=mock(CaptureRequest.Builder.class);
            IsoExpoSelector.setExpo(still,0,f.controller);
            verify(still).set(CaptureRequest.SENSOR_EXPOSURE_TIME,plan.selection.exposureNs);
            verify(still).set(CaptureRequest.SENSOR_SENSITIVITY,plan.selection.iso);
            verify(f.device).createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW);
            verify(f.meter,never()).set(CaptureRequest.CONTROL_AE_MODE,CaptureRequest.CONTROL_AE_MODE_OFF);
        } finally {CaptureController.mPreviewCaptureResult=previous;}
    }
    @Test public void changingTabsRejectsThePreviousModesMeterBinding() throws Exception {
        try(var f=new M10RCaptureMeterReference1ITest.Fixture(0)) {
            f.start(true);assertNotNull(f.admitted);
            assertEquals(true,f.call("m10rCurrent1C",new Class<?>[]{M10RExposureCamera1C.Input.class},f.admitted));
            PhotonCamera.getSettings().selectedMode=CameraMode.MOTION;
            assertEquals(false,f.call("m10rCurrent1C",new Class<?>[]{M10RExposureCamera1C.Input.class},f.admitted));
            f.finish(M10RPreviewBackgroundMeter1LTest.measured(f,System.nanoTime()));
            assertNull(M10RPreviewState1A.plan());
        }
    }
    @Test public void motionShutterRejectionReleasesAdmissionForAnotherPress() throws Exception {
        try(var app=mockStatic(PhotonCamera.class)) {
            Settings s=mock(Settings.class);s.selectedMode=CameraMode.MOTION;app.when(PhotonCamera::getSettings).thenReturn(s);
            CaptureController c=mock(CaptureController.class,CALLS_REAL_METHODS);
            var gate=new M10RCaptureLifecycle1G();var events=mock(CameraEventsListener.class);
            M10RCaptureAdmission1GTest.field(c,"m10rShot1G",gate);
            M10RCaptureAdmission1GTest.field(c,"m10rExposure1C",mock(M10RExposureCamera1C.class));
            M10RCaptureAdmission1GTest.field(c,"cameraEventsListener",events);
            for(int i=0;i<3;i++){c.takePicture();assertFalse(gate.busy());}
            verify(events,times(3)).onProcessingError(contains("Camera not ready"));
        }
    }
    @Test public void motionRawRouterRejectsLateFramesAndKeepsTheRequestMatchedFrame() throws Exception {
        try(var f=new M10RCaptureMeterReference1ITest.Fixture(0)) {
            PhotonCamera.getSettings().selectedMode=CameraMode.MOTION;
            ImageSaver saver=mock(ImageSaver.class);when(saver.bufferSize()).thenReturn(1);
            var raw=new M10RPhotoRaw1H(f.reader,saver);raw.started(200);
            f.set("m10rPhotoRaw1H",raw);f.gate.submitted(f.gate.active());
            Image old=mock(Image.class),current=mock(Image.class);
            when(old.getTimestamp()).thenReturn(100L);when(current.getTimestamp()).thenReturn(200L);
            f.call("m10rDispatchRaw1C",new Class<?>[]{ImageReader.class,Image.class},f.reader,old);
            f.call("m10rDispatchRaw1C",new Class<?>[]{ImageReader.class,Image.class},f.reader,current);
            verify(old).close();verify(saver).initOwnedRaw1C(f.reader,current);assertTrue(raw.ready());
        }
    }
    @Test public void photoAndMotionSaversKeepM10rRenderingWhenTabsChangeDuringSave() throws Exception {
        for(CameraMode mode:new CameraMode[]{CameraMode.PHOTO,CameraMode.MOTION})
        try(var app=mockStatic(PhotonCamera.class);var logging=mockStatic(com.particlesdevs.photoncamera.util.Log.class);
            var nativeRender=mockStatic(M10RNativeRenderer.class);
            var rawVideo=mockConstruction(com.particlesdevs.photoncamera.processing.processor.RawVideoProcessor.class);
            var paths=mockStatic(ImagePath.class);var saves=mockStatic(ImageSaver.Util.class);var exif=mockStatic(ParseExif.class)) {
            Settings s=mock(Settings.class);s.selectedMode=mode;app.when(PhotonCamera::getSettings).thenReturn(s);
            var events=mock(ProcessingEventsListener.class);DefaultSaver saver=new DefaultSaver(events);
            // The capture owns its renderer even after the UI moves to another mode.
            s.selectedMode=CameraMode.NIGHT;
            Path dng=Path.of("/tmp/m10r-mode-test.dng"),jpg=Path.of("/tmp/m10r-mode-test.jpg");
            paths.when(ImagePath::newDNGFilePath).thenReturn(dng);
            var chars=mock(CameraCharacteristics.class);var result=mock(CaptureResult.class);var request=mock(CaptureRequest.class);
            var frame=mock(ImageFrame.class);frame.buffer=ByteBuffer.allocate(32);
            var bitmap=mock(Bitmap.class);var output=new M10RNativeRenderer.Result(bitmap,new JSONObject());
            var exifData=mock(ParseExif.ExifData.class);exif.when(()->ParseExif.parse(result,request)).thenReturn(exifData);
            nativeRender.when(()->M10RNativeRenderer.render(frame,chars,result,request,0)).thenReturn(output);
            saves.when(()->ImageSaver.Util.saveBitmapAsJPGM10R(jpg,bitmap,95,exifData)).thenReturn(true);
            saves.when(()->ImageSaver.Util.saveSingleRawM10RPhysicalCfa(dng,frame,chars,result,0)).thenReturn(true);
            SaverImplementation.IMAGE_BUFFER.add(frame);saver.bufferLock=false;
            saver.runRaw(ImageFormat.RAW_SENSOR,chars,result,request,new ArrayList<>(),0,new HashMap<>());
            nativeRender.verify(()->M10RNativeRenderer.render(frame,chars,result,request,0));
            assertEquals(mode.name(),output.diagnostics.getJSONObject("stillModes3A").getString("captureMode"));
            assertEquals(1,output.diagnostics.getJSONObject("stillModes3A").getInt("photographicRawFrames"));
            assertTrue(output.diagnostics.getBoolean("jpegSaved"));assertTrue(output.diagnostics.getBoolean("dngSaved"));
            verify(frame).close();assertTrue(SaverImplementation.IMAGE_BUFFER.isEmpty());assertFalse(saver.bufferLock);
            verify(events).onProcessingFinished("M10-R JPEG saved");
        }
    }
}
