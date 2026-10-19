package com.particlesdevs.photoncamera.m10r;

import android.graphics.ImageFormat;
import android.graphics.Rect;
import android.media.Image;
import com.particlesdevs.photoncamera.processing.ImageFrame;
import org.junit.Test;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;

import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/** Exercises descriptor extraction against a padded, read-only buffer with a live cursor. */
public class M10RRawImage4ATest {
    @Test public void capturingDeliveryAndConversionEvidencePreservesAllRawBufferState() throws Exception {
        final int width = 32, height = 24, rowStride = width * 2 + 8;
        byte[] pixels = new byte[rowStride * height];
        for (int i = 0; i < pixels.length; i++) pixels[i] = (byte) (i * 37 + 11);
        ByteBuffer input = ByteBuffer.wrap(pixels.clone()).asReadOnlyBuffer()
                .order(ByteOrder.BIG_ENDIAN);
        input.position(7);
        input.mark();
        input.limit(input.capacity() - 2);

        Image image = mock(Image.class);
        Image.Plane plane = mock(Image.Plane.class);
        Rect crop = mock(Rect.class);
        crop.left = 0; crop.top = 0; crop.right = width; crop.bottom = height;
        when(image.getFormat()).thenReturn(ImageFormat.RAW_SENSOR);
        when(image.getWidth()).thenReturn(width);
        when(image.getHeight()).thenReturn(height);
        when(image.getTimestamp()).thenReturn(76437411047298L);
        when(image.getCropRect()).thenReturn(crop);
        when(image.getPlanes()).thenReturn(new Image.Plane[]{plane});
        when(plane.getRowStride()).thenReturn(rowStride);
        when(plane.getPixelStride()).thenReturn(2);
        when(plane.getBuffer()).thenReturn(input);

        M10RRawBinding4A.ImageEvidence evidence =
                M10RRawBinding4A.ImageEvidence.captureOriginal(image);
        assertNotNull(evidence);

        var constructor = ImageFrame.class.getDeclaredConstructor();
        constructor.setAccessible(true);
        ImageFrame frame = constructor.newInstance();
        frame.width = rowStride / 2; // Mirrors the existing padding-inclusive copy contract.
        frame.height = height;
        frame.timestamp = 76437411047298L;
        frame.buffer = input;
        assertNotNull(evidence.withConversion(frame, false, "full_buffer_copy", crop));

        assertEquals(7, input.position());
        assertEquals(pixels.length - 2, input.limit());
        assertEquals(ByteOrder.BIG_ENDIAN, input.order());
        assertTrue(input.isReadOnly());
        input.reset();
        assertEquals(7, input.position());
        ByteBuffer view = input.duplicate();
        view.clear();
        byte[] after = new byte[view.remaining()];
        view.get(after);
        assertArrayEquals(pixels, after);
        assertSame(input, frame.buffer);
        verify(image, never()).close();
    }
}
