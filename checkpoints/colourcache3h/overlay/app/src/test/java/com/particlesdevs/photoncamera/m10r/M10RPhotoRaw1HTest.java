package com.particlesdevs.photoncamera.m10r;

import android.media.Image;
import android.media.ImageReader;
import com.particlesdevs.photoncamera.processing.ImageSaver;
import org.junit.Test;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

public class M10RPhotoRaw1HTest {
    private final ImageReader reader = mock(ImageReader.class);
    private final ImageSaver saver = mock(ImageSaver.class);
    private final M10RPhotoRaw1H raw = new M10RPhotoRaw1H(reader,saver);
    private Image image(long timestamp) {
        Image image = mock(Image.class); when(image.getTimestamp()).thenReturn(timestamp); return image;
    }
    private void succeeds() { when(saver.bufferSize()).thenReturn(1); }

    @Test public void metadataThenImageDeliversExactlyOnePhotographicRaw() {
        succeeds(); raw.started(200); Image image = image(200); raw.image(reader,image);
        assertTrue(raw.ready()); verify(saver).initOwnedRaw1C(reader,image);
        Image duplicate = image(200); raw.image(reader,duplicate); verify(duplicate).close();
        verify(saver,times(1)).initOwnedRaw1C(any(),any());
    }
    @Test public void imageBeforeMetadataWaitsForExactMatch() {
        succeeds(); Image image = image(200); raw.image(reader,image);
        assertFalse(raw.ready()); verify(saver,never()).initOwnedRaw1C(any(),any());
        raw.started(200); assertTrue(raw.ready()); verify(saver).initOwnedRaw1C(reader,image);
    }
    @Test public void delayedOldImageCannotDisplaceNewImageAwaitingMetadata() {
        succeeds(); Image current = image(200), old = image(100);
        raw.image(reader,current); raw.image(reader,old); raw.started(200);
        verify(old).close(); verify(saver).initOwnedRaw1C(reader,current); assertTrue(raw.ready());
    }
    @Test public void pendingOldImageIsReplacedAndClosedBeforeNewShotMetadata() {
        succeeds(); Image old = image(100), current = image(200);
        raw.image(reader,old); raw.image(reader,current); raw.started(200);
        verify(old).close(); verify(saver).initOwnedRaw1C(reader,current);
    }
    @Test public void wrongTimestampAndRetiredReaderAreClosed() {
        succeeds(); raw.started(200); Image old = image(100), otherReader = image(200);
        raw.image(reader,old); raw.image(mock(ImageReader.class),otherReader);
        verify(old).close(); verify(otherReader).close(); assertFalse(raw.ready());
        verify(saver,never()).initOwnedRaw1C(any(),any());
    }
    @Test public void sealClosesPendingAndRejectsAllLateDelivery() {
        Image pending = image(200), late = image(200); raw.image(reader,pending); raw.seal();
        raw.started(200); raw.image(reader,late);
        verify(pending).close(); verify(late).close(); verifyNoInteractions(saver);
    }
    @Test public void readFailureIsRecordedAndFurtherImagesAreClosed() {
        raw.started(200); Image broken = image(200);
        doThrow(new IllegalStateException("plane unavailable")).when(saver).initOwnedRaw1C(reader,broken);
        raw.image(reader,broken); assertFalse(raw.ready()); assertTrue(raw.failure().contains("plane unavailable"));
        Image late = image(200); raw.image(reader,late); verify(late).close();
    }
    @Test public void cameraRestartPreservesCopiedRawUntilWorkerDiscardsIt() {
        succeeds(); raw.started(200); raw.image(reader,image(200)); raw.retireCamera();
        assertTrue(raw.ready()); assertNull(raw.failure()); verify(saver,never()).discardRaw1H();
        raw.discard(); verify(saver).discardRaw1H();
    }
    @Test public void cameraRestartBeforeCopyClosesPendingAndReportsFailure() {
        Image pending = image(200); raw.image(reader,pending); raw.retireCamera();
        assertNotNull(raw.failure()); verify(pending).close(); assertFalse(raw.ready());
    }
    @Test public void deadlineIncludesLongExposureAndFrameDuration() {
        assertEquals(10_000, M10RPhotoRaw1H.acquisitionTimeoutMillis(null,null));
        assertEquals(40_000, M10RPhotoRaw1H.acquisitionTimeoutMillis(30_000_000_000L,1L));
        assertEquals(70_000, M10RPhotoRaw1H.acquisitionTimeoutMillis(1L,60_000_000_000L));
    }
}
