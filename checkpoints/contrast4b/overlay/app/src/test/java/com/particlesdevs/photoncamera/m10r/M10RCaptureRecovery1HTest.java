package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.CameraCaptureSession;
import android.hardware.camera2.CaptureRequest;
import android.media.Image;
import android.media.ImageReader;
import android.os.Handler;
import com.particlesdevs.photoncamera.api.CameraEventsListener;
import com.particlesdevs.photoncamera.api.CameraMode;
import com.particlesdevs.photoncamera.api.Settings;
import com.particlesdevs.photoncamera.app.PhotonCamera;
import com.particlesdevs.photoncamera.capture.CaptureController;
import com.particlesdevs.photoncamera.processing.ImageSaver;
import org.junit.After;
import org.junit.Test;
import java.lang.reflect.Method;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

public class M10RCaptureRecovery1HTest {
    private final CaptureController controller = mock(CaptureController.class,CALLS_REAL_METHODS);
    private final M10RCaptureLifecycle1G gate = new M10RCaptureLifecycle1G();
    private final CameraEventsListener events = mock(CameraEventsListener.class);
    private final CameraCaptureSession session = mock(CameraCaptureSession.class);
    private final ImageReader reader = mock(ImageReader.class);
    private final ImageSaver saver = mock(ImageSaver.class);
    private final M10RPhotoRaw1H raw = new M10RPhotoRaw1H(reader,saver);
    private void set(String name,Object value) throws Exception { M10RCaptureAdmission1GTest.field(controller,name,value); }
    private Method method(String name,Class<?>... types) throws Exception {
        Method m = CaptureController.class.getDeclaredMethod(name,types); m.setAccessible(true); return m;
    }
    private long submitted() throws Exception {
        set("m10rMeasuredRaw3N",mock(M10RMeasuredRaw3N.class));
        set("m10rMeasuredAdmission3P", new M10RMeasuredAdmission3P());
        set("m10rShot1G",gate); set("cameraEventsListener",events); set("m10rPhotoRaw1H",raw);
        set("mCaptureSession",session); set("mImageReaderRaw",reader);
        doNothing().when(controller).unlockFocus(); doReturn(false).when(controller).isZslMode();
        long ticket = gate.begin(); gate.submitted(ticket); return ticket;
    }
    private void fail(long ticket) throws Exception {
        method("m10rFailShot1H",long.class,M10RPhotoRaw1H.class,CameraCaptureSession.class,String.class)
                .invoke(controller,ticket,raw,session,"RAW missing");
    }
    @After public void clean() { CaptureController.isProcessing = false; }

    @Test public void acquisitionFailureCleansRawAndRestoresPreviewBeforeNextAdmission() throws Exception {
        long ticket = submitted(); fail(ticket);
        assertFalse(gate.busy()); verify(saver).discardRaw1H(); verify(controller).unlockFocus();
        verify(events).onProcessingError(contains("RAW missing")); assertTrue(gate.begin() > ticket);
    }
    @Test public void failureDuringSavingDoesNotReleaseWorkerOwnership() throws Exception {
        long ticket = submitted(); gate.processing(ticket); CaptureController.isProcessing = true;
        fail(ticket); assertTrue(gate.owns(ticket)); assertTrue(CaptureController.isProcessing);
        verify(saver,never()).discardRaw1H(); verifyNoInteractions(events);
        assertNotNull(raw.failure());
    }
    @Test public void staleFailureCannotCancelNewerCapture() throws Exception {
        long old = submitted(); gate.finish(old); long next = gate.begin(); gate.submitted(next);
        fail(old); assertTrue(gate.owns(next)); assertNull(raw.failure()); verifyNoInteractions(events,saver);
    }
    @Test public void normalPhotoRouterRejectsLateOldFrameAndAcceptsMatchingNewFrame() throws Exception {
        try (var app = mockStatic(PhotonCamera.class)) {
            Settings settings = mock(Settings.class); settings.selectedMode = CameraMode.PHOTO;
            app.when(PhotonCamera::getSettings).thenReturn(settings);
            submitted(); raw.started(200); when(saver.bufferSize()).thenReturn(1);
            Image old = mock(Image.class), current = mock(Image.class);
            when(old.getTimestamp()).thenReturn(100L); when(current.getTimestamp()).thenReturn(200L);
            Method route = method("m10rDispatchRaw1C",ImageReader.class,Image.class);
            route.invoke(controller,reader,old); route.invoke(controller,reader,current);
            verify(old).close(); verify(saver).initOwnedRaw1C(reader,current); assertTrue(raw.ready());
        }
    }
    @Test public void acquisitionDeadlineReleasesStalledShotButNeverInterruptsSaving() throws Exception {
        long ticket = submitted(); Handler handler = mock(Handler.class); set("mBackgroundHandler",handler);
        final Runnable[] deadline = {null};
        when(handler.postDelayed(any(Runnable.class),anyLong())).thenAnswer(i -> { deadline[0] = i.getArgument(0); return true; });
        doNothing().when(controller).abortCaptures();
        Method watch = method("m10rWatchAcquisition1H",long.class,M10RPhotoRaw1H.class,CaptureRequest.class);
        watch.invoke(controller,ticket,raw,mock(CaptureRequest.class));
        deadline[0].run(); assertFalse(gate.busy()); verify(controller).abortCaptures(); verify(controller).unlockFocus();
        long next = gate.begin(); gate.submitted(next); set("m10rPhotoRaw1H",raw);
        watch.invoke(controller,next,raw,mock(CaptureRequest.class)); gate.processing(next);
        deadline[0].run(); assertTrue(gate.owns(next)); verify(controller,times(1)).abortCaptures();
    }

    @Test public void rawReadExceptionDoesNotEscapeRouterOrLeaveShutterBusy() throws Exception {
        try (var app = mockStatic(PhotonCamera.class)) {
            Settings settings = mock(Settings.class); settings.selectedMode = CameraMode.PHOTO;
            app.when(PhotonCamera::getSettings).thenReturn(settings);
            submitted(); raw.started(200);
            Image broken = mock(Image.class); when(broken.getTimestamp()).thenReturn(200L);
            doThrow(new IllegalStateException("RAW planes unavailable")).when(saver).initOwnedRaw1C(reader,broken);
            method("m10rDispatchRaw1C",ImageReader.class,Image.class).invoke(controller,reader,broken);
            assertFalse(gate.busy()); verify(saver).discardRaw1H(); verify(controller).unlockFocus();
            verify(events).onProcessingError(contains("RAW planes unavailable"));
        }
    }

    @Test public void queuedCallbackFromClosedReaderCannotFailCurrentShot() throws Exception {
        long ticket = submitted(); ImageReader retired = mock(ImageReader.class);
        when(retired.acquireNextImage()).thenThrow(new IllegalStateException("reader closed"));
        method("m10rReceivePhotoRaw1H",ImageReader.class).invoke(controller,retired);
        assertTrue(gate.owns(ticket)); verifyNoInteractions(events); verify(retired,never()).acquireNextImage();
    }

    @Test public void ordinaryReaderAcquisitionFailureReleasesCurrentShot() throws Exception {
        submitted(); when(reader.acquireNextImage()).thenThrow(new IllegalStateException("reader full"));
        method("m10rReceivePhotoRaw1H",ImageReader.class).invoke(controller,reader);
        assertFalse(gate.busy()); verify(saver).discardRaw1H(); verify(controller).unlockFocus();
    }

    @Test public void cameraCloseReleasesReadersWhileCopiedPhotoContinuesSaving() throws Exception {
        long ticket = submitted(); gate.processing(ticket); CaptureController.isProcessing = true;
        set("m10rExposure1C",mock(M10RExposureCamera1C.class));
        ImageReader preview = mock(ImageReader.class); set("mImageReaderPreview",preview);
        when(saver.bufferSize()).thenReturn(1); raw.started(200);
        Image image = mock(Image.class); when(image.getTimestamp()).thenReturn(200L); raw.image(reader,image);
        method("closeCameraResourcesLocked").invoke(controller);
        verify(reader).close(); verify(preview).close(); verify(session).close();
        assertTrue(gate.owns(ticket)); assertTrue(CaptureController.isProcessing);
        assertTrue(raw.ready()); assertNull(raw.failure()); verify(saver,never()).discardRaw1H();
    }

    @Test public void intentionalDualSessionTransitionKeepsAdmittedPhotoAndDeadline() throws Exception {
        long ticket = submitted(); controller.isDualSession = true;
        set("m10rExposure1C",mock(M10RExposureCamera1C.class));
        Handler handler = mock(Handler.class); Runnable deadline = mock(Runnable.class);
        set("m10rTimeoutHandler1H",handler); set("m10rAcquisitionTimeout1H",deadline);
        method("m10rRetireForSession1H",boolean.class).invoke(controller,true);
        assertTrue(gate.owns(ticket)); assertNull(raw.failure()); verifyNoInteractions(saver,handler);
        method("m10rRetireForSession1H",boolean.class).invoke(controller,false);
        assertFalse(gate.busy()); verify(saver).discardRaw1H(); verify(handler).removeCallbacks(deadline);
    }
}
