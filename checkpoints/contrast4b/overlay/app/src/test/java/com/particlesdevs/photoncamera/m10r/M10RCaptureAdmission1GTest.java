package com.particlesdevs.photoncamera.m10r;

import com.particlesdevs.photoncamera.api.CameraEventsListener;
import com.particlesdevs.photoncamera.api.CameraMode;
import com.particlesdevs.photoncamera.api.Settings;
import com.particlesdevs.photoncamera.app.PhotonCamera;
import com.particlesdevs.photoncamera.capture.CaptureController;
import org.junit.After;
import org.junit.Test;
import java.lang.reflect.Field;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/** Exercises real controller admission/finish code without a Camera2 device. */
public class M10RCaptureAdmission1GTest {
    static void field(Object obj, String name, Object value) throws Exception {
        Field f = obj.getClass().getDeclaredField(name);f.setAccessible(true);f.set(obj, value);
    }
    @After public void clean() { CaptureController.isProcessing = false; }
    @Test public void cameraNotReadyDoesNotLeaveNextShutterBusy() throws Exception {
        try (var app = mockStatic(PhotonCamera.class)) {
            Settings settings = mock(Settings.class);settings.selectedMode = CameraMode.PHOTO;
            app.when(PhotonCamera::getSettings).thenReturn(settings);
            CaptureController controller = mock(CaptureController.class, CALLS_REAL_METHODS);
            field(controller,"m10rMeasuredRaw3N",mock(M10RMeasuredRaw3N.class));
            field(controller,"m10rMeasuredAdmission3P", new M10RMeasuredAdmission3P());
            doReturn(false).when(controller).isZslMode();
            var gate = new M10RCaptureLifecycle1G();var events = mock(CameraEventsListener.class);
            field(controller,"m10rShot1G",gate);
            field(controller,"m10rExposure1C",mock(M10RExposureCamera1C.class));
            field(controller,"cameraEventsListener",events);
            for (int i = 0; i < 3; i++) { controller.takePicture();assertFalse(gate.busy()); }
            verify(events,times(3)).onProcessingError(contains("Camera not ready"));
        }
    }
    @Test public void rejectedBusyShutterDoesNotCancelExistingSave() throws Exception {
        try (var app = mockStatic(PhotonCamera.class)) {
            Settings settings = mock(Settings.class);settings.selectedMode = CameraMode.PHOTO;
            app.when(PhotonCamera::getSettings).thenReturn(settings);
            CaptureController controller = mock(CaptureController.class, CALLS_REAL_METHODS);
            field(controller,"m10rMeasuredRaw3N",mock(M10RMeasuredRaw3N.class));
            field(controller,"m10rMeasuredAdmission3P", new M10RMeasuredAdmission3P());
            doReturn(false).when(controller).isZslMode();
            var gate = new M10RCaptureLifecycle1G();var events = mock(CameraEventsListener.class);
            field(controller,"m10rShot1G",gate);field(controller,"cameraEventsListener",events);
            long ticket = gate.begin();gate.submitted(ticket);gate.processing(ticket);
            controller.takePicture();assertTrue(gate.owns(ticket));verifyNoInteractions(events);
        }
    }
    @Test public void meterBusyRejectionReleasesAdmissionForRetry() throws Exception {
        try (var app = mockStatic(PhotonCamera.class)) {
            Settings settings = mock(Settings.class);settings.selectedMode = CameraMode.PHOTO;
            app.when(PhotonCamera::getSettings).thenReturn(settings);
            CaptureController controller = mock(CaptureController.class, CALLS_REAL_METHODS);
            field(controller,"m10rMeasuredRaw3N",mock(M10RMeasuredRaw3N.class));
            field(controller,"m10rMeasuredAdmission3P", new M10RMeasuredAdmission3P());
            doReturn(false).when(controller).isZslMode();
            var gate = new M10RCaptureLifecycle1G();var events = mock(CameraEventsListener.class);
            var meter = mock(M10RExposureCamera1C.class);when(meter.busy()).thenReturn(true);
            field(controller,"m10rShot1G",gate);field(controller,"m10rExposure1C",meter);
            field(controller,"cameraEventsListener",events);
            controller.takePicture();assertFalse(gate.busy());
            verify(events).onProcessingError(contains("Meter still busy"));
        }
    }
    @Test public void saverSuccessAndFailureBothReleaseRealControllerForNextCapture() throws Exception {
        CaptureController controller = mock(CaptureController.class, CALLS_REAL_METHODS);
        field(controller,"m10rMeasuredRaw3N",mock(M10RMeasuredRaw3N.class));
        field(controller,"m10rMeasuredAdmission3P", new M10RMeasuredAdmission3P());
        var gate = new M10RCaptureLifecycle1G();var events = mock(CameraEventsListener.class);
        field(controller,"m10rShot1G",gate);field(controller,"cameraEventsListener",events);
        var finish = CaptureController.class.getDeclaredMethod("m10rFinishShot1G",long.class,String.class);
        finish.setAccessible(true);
        for (String error : new String[]{null,"No RAW frame received","Save failed",null}) {
            long ticket = gate.begin();assertTrue(ticket > 0);
            gate.submitted(ticket);gate.processing(ticket);CaptureController.isProcessing = true;
            finish.invoke(controller,ticket,error);
            assertFalse(gate.busy());assertFalse(CaptureController.isProcessing);
        }
        verify(events,times(2)).onProcessingFinished(any());
        verify(events,times(2)).onProcessingError(any());
    }

}
