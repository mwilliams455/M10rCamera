package com.particlesdevs.photoncamera.processing;

import android.graphics.ImageFormat;
import android.media.Image;
import android.media.ImageReader;
import com.particlesdevs.photoncamera.api.CameraMode;
import com.particlesdevs.photoncamera.api.Settings;
import com.particlesdevs.photoncamera.app.PhotonCamera;
import org.junit.After;
import org.junit.Test;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

public class M10RRawRecovery1HTest {
    @After public void clear() { SaverImplementation.IMAGE_BUFFER.clear(); }

    @Test public void rawPlaneReadFailureClosesImageWithoutPublishingFrame() {
        try (var app = mockStatic(PhotonCamera.class)) {
            Settings settings = mock(Settings.class); settings.selectedMode = CameraMode.PHOTO;
            app.when(PhotonCamera::getSettings).thenReturn(settings);
            RAW16Saver saver = mock(RAW16Saver.class, CALLS_REAL_METHODS);
            Image image = mock(Image.class);
            doThrow(new IllegalStateException("plane unavailable")).when(saver).getFrame(image);
            assertThrows(IllegalStateException.class, () -> saver.addImage(image));
            verify(image).close();
            assertTrue(SaverImplementation.IMAGE_BUFFER.isEmpty());
        }
    }

    @Test public void invalidRawCannotPublishNullAndPoisonTheNextSave() {
        try (var app = mockStatic(PhotonCamera.class)) {
            Settings settings = mock(Settings.class); settings.selectedMode = CameraMode.PHOTO;
            app.when(PhotonCamera::getSettings).thenReturn(settings);
            RAW16Saver saver = mock(RAW16Saver.class, CALLS_REAL_METHODS);
            Image image = mock(Image.class); doReturn(null).when(saver).getFrame(image);
            assertThrows(IllegalStateException.class, () -> saver.addImage(image));
            verify(image).close();
            assertTrue(SaverImplementation.IMAGE_BUFFER.isEmpty());
        }
    }

    @Test public void ownedImageClosesWhenFormatLookupFailsBeforeSaverReceivesIt() {
        ImageSaver saver = mock(ImageSaver.class, CALLS_REAL_METHODS); saver.setFrameCount(1);
        Image image = mock(Image.class); ImageReader reader = mock(ImageReader.class);
        when(image.getFormat()).thenThrow(new IllegalStateException("closed image"));
        assertThrows(IllegalStateException.class, () -> saver.initOwnedRaw1C(reader,image));
        verify(image).close();
    }

    @Test public void rejectedFrameClosesItsCopiedBufferEvenIfArrivalPackingFails() {
        try (var app = mockStatic(PhotonCamera.class); var packing = mockStatic(ImageFrame.class)) {
            Settings settings = mock(Settings.class); settings.selectedMode = CameraMode.PHOTO; settings.frameCount = 2;
            app.when(PhotonCamera::getSettings).thenReturn(settings);
            RAW16Saver saver = mock(RAW16Saver.class, CALLS_REAL_METHODS);
            Image image = mock(Image.class); ImageFrame frame = mock(ImageFrame.class);
            doReturn(frame).when(saver).getFrame(image);
            packing.when(() -> ImageFrame.packBurstAtArrival(eq(frame),anyInt(),anyBoolean()))
                    .thenThrow(new IllegalStateException("pack failed"));
            assertThrows(IllegalStateException.class, () -> saver.addImage(image));
            verify(frame).close(); verify(image).close(); assertTrue(SaverImplementation.IMAGE_BUFFER.isEmpty());
        }
    }

    @Test public void failedShotCleanupClosesEveryCopiedFrameBeforeClearing() {
        ImageSaver saver = mock(ImageSaver.class, CALLS_REAL_METHODS);
        ImageFrame first = mock(ImageFrame.class), second = mock(ImageFrame.class);
        SaverImplementation.IMAGE_BUFFER.add(first); SaverImplementation.IMAGE_BUFFER.add(second);
        doThrow(new IllegalStateException("already released")).when(first).close();
        saver.discardRaw1H(); verify(first).close(); verify(second).close();
        assertTrue(SaverImplementation.IMAGE_BUFFER.isEmpty());
    }
}
