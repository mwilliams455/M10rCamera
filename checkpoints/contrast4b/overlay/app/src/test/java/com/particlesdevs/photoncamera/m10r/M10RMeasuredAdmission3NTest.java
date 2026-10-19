package com.particlesdevs.photoncamera.m10r;

import android.media.ImageReader;
import com.particlesdevs.photoncamera.api.CameraEventsListener;
import com.particlesdevs.photoncamera.api.CameraMode;
import com.particlesdevs.photoncamera.api.Settings;
import com.particlesdevs.photoncamera.app.PhotonCamera;
import com.particlesdevs.photoncamera.capture.CaptureController;
import org.junit.After;
import org.junit.Test;

import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/** The measured transport and PHOTO/MOTION owner have mutually exclusive admission. */
public class M10RMeasuredAdmission3NTest {
    @After public void clean() { CaptureController.isProcessing = false; }

    @Test public void activeSpotCannotAdmitPhotoOrMotionShutter() throws Exception {
        for (CameraMode mode : new CameraMode[] {CameraMode.PHOTO, CameraMode.MOTION}) {
            try (var app = mockStatic(PhotonCamera.class)) {
                Settings settings = mock(Settings.class); settings.selectedMode = mode;
                app.when(PhotonCamera::getSettings).thenReturn(settings);
                CaptureController controller = mock(CaptureController.class, CALLS_REAL_METHODS);
                doReturn(false).when(controller).isZslMode();
                M10RCaptureLifecycle1G shot = new M10RCaptureLifecycle1G();
                M10RMeasuredRaw3N spot = mock(M10RMeasuredRaw3N.class); when(spot.busy()).thenReturn(true);
                CameraEventsListener events = mock(CameraEventsListener.class);
                M10RCaptureAdmission1GTest.field(controller, "m10rShot1G", shot);
                M10RCaptureAdmission1GTest.field(controller, "m10rMeasuredRaw3N", spot);
                M10RCaptureAdmission1GTest.field(controller, "m10rMeasuredAdmission3P", new M10RMeasuredAdmission3P());
                M10RCaptureAdmission1GTest.field(controller, "cameraEventsListener", events);
                for (int press = 0; press < 3; press++) controller.takePicture();
                assertFalse(shot.busy()); assertEquals(1, shot.begin());
                verifyNoInteractions(events);
            }
        }
    }

    @Test public void quarantinedReaderCannotAdmitShotAfterSpotOperationHasFailed() throws Exception {
        try (var app = mockStatic(PhotonCamera.class)) {
            Settings settings = mock(Settings.class); settings.selectedMode = CameraMode.PHOTO;
            app.when(PhotonCamera::getSettings).thenReturn(settings);
            CaptureController controller = mock(CaptureController.class, CALLS_REAL_METHODS);
            doReturn(false).when(controller).isZslMode();
            M10RCaptureLifecycle1G shot = new M10RCaptureLifecycle1G();
            ImageReader retiredReader = mock(ImageReader.class);
            CameraEventsListener events = mock(CameraEventsListener.class);
            M10RCaptureAdmission1GTest.field(controller, "m10rShot1G", shot);
            M10RCaptureAdmission1GTest.field(controller, "m10rMeasuredRaw3N", mock(M10RMeasuredRaw3N.class));
            M10RCaptureAdmission1GTest.field(controller, "m10rMeasuredAdmission3P", new M10RMeasuredAdmission3P());
            M10RCaptureAdmission1GTest.field(controller, "mImageReaderRaw", retiredReader);
            M10RCaptureAdmission1GTest.field(controller, "m10rRejectedRawReader1C", retiredReader);
            M10RCaptureAdmission1GTest.field(controller, "cameraEventsListener", events);
            controller.takePicture(); assertFalse(shot.busy()); assertEquals(1, shot.begin());
            verifyNoInteractions(events);
        }
    }

    @Test public void directBackgroundProbeEntryCannotCreateAnotherReaderOwner() throws Exception {
        CaptureController controller = mock(CaptureController.class, CALLS_REAL_METHODS);
        M10RMeasuredRaw3N spot = mock(M10RMeasuredRaw3N.class); when(spot.busy()).thenReturn(true);
        M10RExposureCamera1C exposure = mock(M10RExposureCamera1C.class);
        M10RCaptureAdmission1GTest.field(controller, "m10rMeasuredRaw3N", spot);
        M10RCaptureAdmission1GTest.field(controller, "m10rMeasuredAdmission3P", new M10RMeasuredAdmission3P());
        M10RCaptureAdmission1GTest.field(controller, "m10rExposure1C", exposure);
        var probe = CaptureController.class.getDeclaredMethod("m10rStartProbe1A", boolean.class);
        probe.setAccessible(true);
        probe.invoke(controller, true);
        verifyNoInteractions(exposure);
    }
}
