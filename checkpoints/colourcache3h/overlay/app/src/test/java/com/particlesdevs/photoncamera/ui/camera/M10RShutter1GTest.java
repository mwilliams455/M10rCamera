package com.particlesdevs.photoncamera.ui.camera;

import android.view.View;
import com.particlesdevs.photoncamera.api.CameraMode;
import com.particlesdevs.photoncamera.api.Settings;
import com.particlesdevs.photoncamera.app.PhotonCamera;
import com.particlesdevs.photoncamera.capture.CaptureController;
import org.junit.Test;
import static org.mockito.Mockito.*;

public class M10RShutter1GTest {
    @Test public void rejectedPhotoShutterDoesNotRequireGalleryToBecomeClickable() throws Exception {
        try (var app = mockStatic(PhotonCamera.class)) {
            Settings settings = mock(Settings.class);settings.selectedMode = CameraMode.PHOTO;
            app.when(PhotonCamera::getSettings).thenReturn(settings);
            CameraFragment fragment = mock(CameraFragment.class);
            fragment.captureController = mock(CaptureController.class); // busy/not-ready no-op
            CameraUIController ui = new CameraUIController(fragment);
            View shutter = mock(View.class);
            var field = CameraUIController.class.getDeclaredField("shutterButton");
            field.setAccessible(true);field.set(ui, shutter);
            var finish = CameraUIController.class.getDeclaredMethod("onTimerFinished");
            finish.setAccessible(true);
            for (int i = 0; i < 3; i++) finish.invoke(ui);
            verify(shutter,never()).setClickable(false);
            verify(shutter,never()).setActivated(false);
            verify(fragment.captureController,times(3)).takePicture();
        }
    }
    @Test public void otherStillModesRetainTheirExistingShutterBehaviour() throws Exception {
        try (var app = mockStatic(PhotonCamera.class)) {
            Settings settings = mock(Settings.class);settings.selectedMode = CameraMode.NIGHT;
            app.when(PhotonCamera::getSettings).thenReturn(settings);
            CameraFragment fragment = mock(CameraFragment.class);
            fragment.captureController = mock(CaptureController.class);
            CameraUIController ui = new CameraUIController(fragment);View shutter = mock(View.class);
            var field = CameraUIController.class.getDeclaredField("shutterButton");
            field.setAccessible(true);field.set(ui, shutter);
            var finish = CameraUIController.class.getDeclaredMethod("onTimerFinished");
            finish.setAccessible(true);finish.invoke(ui);
            verify(shutter).setClickable(false);verify(shutter).setActivated(false);
        }
    }
}
