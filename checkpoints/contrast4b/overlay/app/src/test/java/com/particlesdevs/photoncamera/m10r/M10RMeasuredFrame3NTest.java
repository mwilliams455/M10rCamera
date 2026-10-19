package com.particlesdevs.photoncamera.m10r;

import android.graphics.ImageFormat;
import android.graphics.Rect;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CaptureResult;
import android.media.Image;
import org.junit.BeforeClass;
import org.junit.AfterClass;
import org.junit.Test;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.ReadOnlyBufferException;

import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

public class M10RMeasuredFrame3NTest {
    @BeforeClass public static void keys() throws Exception { M10RCaptureMeterReference1ITest.keys(); }
    @AfterClass public static void restoreKeys() throws Exception { M10RCaptureMeterReference1ITest.restoreKeys(); }
    static final int WIDTH = 640, HEIGHT = 480, ORIGIN = 7;
    static final M10RMeasuredFrame3N.View CENTER = new M10RMeasuredFrame3N.View(50, 50, 100, 100, 0);
    CameraCharacteristics characteristics() {
        CameraCharacteristics c = mock(CameraCharacteristics.class);
        when(c.get(CameraCharacteristics.SENSOR_ORIENTATION)).thenReturn(90);
        when(c.get(CameraCharacteristics.LENS_FACING)).thenReturn(CameraCharacteristics.LENS_FACING_BACK);
        return c;
    }
    static int value(int x, int y, int format) {
        int mask = format == ImageFormat.RAW10 ? 1023 : format == ImageFormat.RAW12 ? 4095 : 65535;
        return (83 + x * 17 + y * 31) & mask;
    }
    Image image(int format, int padding, int pixelStride) {
        Image image = mock(Image.class); Image.Plane plane = mock(Image.Plane.class);
        int payload = format == ImageFormat.RAW10 ? WIDTH / 4 * 5
                : format == ImageFormat.RAW12 ? WIDTH / 2 * 3 : (WIDTH - 1) * pixelStride + 2;
        int row = payload + padding;
        ByteBuffer bytes = ByteBuffer.allocate(ORIGIN + (HEIGHT - 1) * row + payload).order(ByteOrder.LITTLE_ENDIAN);
        for (int y = 0; y < HEIGHT; y++) for (int x = 0; x < WIDTH; x++) {
            int v = value(x, y, format), offset;
            if (format == ImageFormat.RAW10) {
                offset = ORIGIN + y * row + x / 4 * 5;
                bytes.put(offset + x % 4, (byte) (v >>> 2));
                bytes.put(offset + 4, (byte) ((bytes.get(offset + 4) & 255) | ((v & 3) << (x % 4 * 2))));
            } else if (format == ImageFormat.RAW12) {
                offset = ORIGIN + y * row + x / 2 * 3;
                bytes.put(offset + x % 2, (byte) (v >>> 4));
                bytes.put(offset + 2, (byte) ((bytes.get(offset + 2) & 255) | ((v & 15) << (x % 2 * 4))));
            } else bytes.putShort(ORIGIN + y * row + x * pixelStride, (short) v);
        }
        bytes.position(ORIGIN);
        Rect crop = new Rect(); crop.right = WIDTH; crop.bottom = HEIGHT;
        when(image.getWidth()).thenReturn(WIDTH); when(image.getHeight()).thenReturn(HEIGHT);
        when(image.getTimestamp()).thenReturn(100L); when(image.getFormat()).thenReturn(format);
        when(image.getCropRect()).thenReturn(crop); when(image.getPlanes()).thenReturn(new Image.Plane[] {plane});
        when(plane.getRowStride()).thenReturn(row); when(plane.getPixelStride()).thenReturn(pixelStride);
        when(plane.getBuffer()).thenReturn(bytes);
        return image;
    }
    void assertPatch(M10RMeasuredFrame3N copy, int format) {
        var g = copy.geometry;
        assertEquals(WIDTH, g.sensorWidth); assertEquals(HEIGHT, g.sensorHeight);
        assertEquals(320, g.centerX); assertEquals(240, g.centerY);
        assertEquals(24, g.boxSide); assertEquals(308, g.startX); assertEquals(228, g.startY);
        assertEquals(332, g.endX); assertEquals(252, g.endY);
        assertEquals(0, g.startX & 1); assertEquals(0, g.startY & 1);
        assertEquals(24 * 24 * 2, copy.pixels().remaining());
        for (int y = g.startY; y < g.endY; y++) for (int x = g.startX; x < g.endX; x++)
            assertEquals(value(x, y, format), copy.pixels().getShort(
                    (y - g.startY) * copy.rowStride + (x - g.startX) * 2) & 65535);
    }

    @Test public void raw16CopiesOnlyBayerPatchAcrossPaddingPixelStrideAndBufferOrigin() {
        for (int padding : new int[] {0, 2, 16, 127}) for (int stride : new int[] {2, 4}) {
            Image image = image(ImageFormat.RAW_SENSOR, padding, stride);
            ByteBuffer borrowed = image.getPlanes()[0].getBuffer();
            M10RMeasuredFrame3N copy = M10RMeasuredFrame3N.copyAndClose(image, 100, characteristics(), null, CENTER);
            assertPatch(copy, ImageFormat.RAW_SENSOR); assertEquals(ORIGIN, borrowed.position());
            verify(image, times(1)).close();
        }
    }

    @Test public void packedRaw10And12RetainEveryIntegerSensel() {
        for (int format : new int[] {ImageFormat.RAW10, ImageFormat.RAW12}) {
            Image image = image(format, 17, 0);
            M10RMeasuredFrame3N copy = M10RMeasuredFrame3N.copyAndClose(image, 100, characteristics(), null, CENTER);
            assertPatch(copy, format); verify(image, times(1)).close();
            assertEquals(ORIGIN, image.getPlanes()[0].getBuffer().position());
        }
    }

    @Test public void payloadIsDetachedReadOnlyAndHasIndependentCursors() {
        Image image = image(ImageFormat.RAW_SENSOR, 4, 2);
        M10RMeasuredFrame3N copy = M10RMeasuredFrame3N.copyAndClose(image, 100, characteristics(), null, CENTER);
        ByteBuffer original = image.getPlanes()[0].getBuffer();
        int offset = ORIGIN + copy.geometry.startY * image.getPlanes()[0].getRowStride() + copy.geometry.startX * 2;
        original.putShort(offset, (short) 0);
        assertEquals(value(copy.geometry.startX, copy.geometry.startY, ImageFormat.RAW_SENSOR), copy.pixels().getShort(0) & 65535);
        assertThrows(ReadOnlyBufferException.class, () -> copy.pixels().put(0, (byte) 0));
        copy.pixels().position(10); assertEquals(0, copy.pixels().position());
        verify(image, times(1)).close();
    }

    @Test public void fullSensorCenterAndEvenOriginSurviveFrontMirrorAndEdgeTouches() {
        CameraCharacteristics c = characteristics();
        var right = new M10RMeasuredFrame3N.View(75, 50, 100, 100, 0);
        var back = M10RMeasuredFrame3N.geometry(WIDTH, HEIGHT, c, null, right);
        assertEquals(480, back.centerX); assertEquals(468, back.startX);
        when(c.get(CameraCharacteristics.LENS_FACING)).thenReturn(CameraCharacteristics.LENS_FACING_FRONT);
        var front = M10RMeasuredFrame3N.geometry(WIDTH, HEIGHT, c, null, right);
        assertEquals(160, front.centerX); assertEquals(148, front.startX);
        when(c.get(CameraCharacteristics.LENS_FACING)).thenReturn(CameraCharacteristics.LENS_FACING_BACK);
        var edge = M10RMeasuredFrame3N.geometry(WIDTH, HEIGHT, c, null,
                new M10RMeasuredFrame3N.View(100, 100, 100, 100, 0));
        assertEquals(639, edge.centerX); assertEquals(479, edge.centerY);
        assertEquals(616, edge.startX); assertEquals(456, edge.startY);
        assertEquals(WIDTH, edge.endX); assertEquals(HEIGHT, edge.endY);
    }

    @Test public void resultCropUsesCapturedSensorCoordinates() {
        CaptureResult result = mock(CaptureResult.class); Rect crop = mock(Rect.class);
        crop.left = 100; crop.top = 40; crop.right = 500; crop.bottom = 440;
        when(crop.width()).thenReturn(400); when(crop.height()).thenReturn(400);
        when(result.get(CaptureResult.SCALER_CROP_REGION)).thenReturn(crop);
        var g = M10RMeasuredFrame3N.geometry(WIDTH, HEIGHT, characteristics(), result, CENTER);
        assertEquals(300, g.centerX); assertEquals(240, g.centerY); assertEquals(20, g.boxSide);
        assertEquals(290, g.startX); assertEquals(230, g.startY);
    }

    @Test public void malformedRawAlwaysClosesExactlyOnce() {
        for (int kind = 0; kind < 8; kind++) {
            Image image = image(ImageFormat.RAW_SENSOR, 0, 2);
            if (kind == 0) when(image.getTimestamp()).thenReturn(101L);
            if (kind == 1) when(image.getFormat()).thenReturn(ImageFormat.JPEG);
            if (kind == 2) image.getCropRect().left = 1;
            if (kind == 3) when(image.getPlanes()).thenReturn(new Image.Plane[0]);
            if (kind == 4) when(image.getPlanes()[0].getPixelStride()).thenReturn(1);
            if (kind == 5) when(image.getPlanes()[0].getRowStride()).thenReturn(WIDTH * 2 - 1);
            if (kind == 6) image.getPlanes()[0].getBuffer().limit(100);
            if (kind == 7) when(image.getWidth()).thenReturn(0);
            assertThrows(IllegalArgumentException.class, () -> M10RMeasuredFrame3N.copyAndClose(image, 100, characteristics(), null, CENTER));
            verify(image, times(1)).close();
        }
    }

    @Test public void patchAllocationHasHardLimitBeforeReadingOrAllocatingSensorPlane() {
        Image image = mock(Image.class); Rect crop = new Rect(); crop.right = crop.bottom = 32768;
        when(image.getWidth()).thenReturn(32768); when(image.getHeight()).thenReturn(32768);
        when(image.getTimestamp()).thenReturn(100L); when(image.getFormat()).thenReturn(ImageFormat.RAW_SENSOR);
        when(image.getCropRect()).thenReturn(crop);
        assertThrows(IllegalArgumentException.class, () -> M10RMeasuredFrame3N.copyAndClose(image, 100, characteristics(), null, CENTER));
        verify(image, never()).getPlanes(); verify(image, times(1)).close();
    }

    @Test public void allocationOrBufferAccessFailureStillClosesImage() {
        Image image = image(ImageFormat.RAW_SENSOR, 0, 2);
        when(image.getPlanes()[0].getBuffer()).thenThrow(new OutOfMemoryError("injected"));
        assertThrows(OutOfMemoryError.class, () -> M10RMeasuredFrame3N.copyAndClose(image, 100, characteristics(), null, CENTER));
        verify(image, times(1)).close();
    }
}
