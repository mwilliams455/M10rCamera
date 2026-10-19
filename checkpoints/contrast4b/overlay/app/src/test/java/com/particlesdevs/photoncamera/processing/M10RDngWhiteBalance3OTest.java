package com.particlesdevs.photoncamera.processing;

import android.graphics.Point;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.CaptureResult;
import android.hardware.camera2.params.RggbChannelVector;
import android.util.Rational;

import com.particlesdevs.photoncamera.m10r.M10RCaptureMeterReference1ITest;
import com.particlesdevs.photoncamera.processing.render.Parameters;
import com.particlesdevs.photoncamera.util.Log;

import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;

import org.junit.AfterClass;
import org.junit.BeforeClass;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;
import org.mockito.ArgumentCaptor;
import org.mockito.MockedConstruction;
import org.mockito.MockedStatic;

import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/** Real ImageSaver routing, with phone-parameter population and native I/O isolated. */
public class M10RDngWhiteBalance3OTest {
    @Rule public final TemporaryFolder temporary = new TemporaryFolder();

    @BeforeClass public static void keys() throws Exception {
        M10RCaptureMeterReference1ITest.keys();
    }

    @AfterClass public static void restoreKeys() throws Exception {
        M10RCaptureMeterReference1ITest.restoreKeys();
    }

    @Test public void explicitManualRequestSurvivesWithoutHalNeutral() throws Exception {
        CaptureRequest selected = request(CaptureRequest.CONTROL_AWB_MODE_OFF, gains(4, 2, 2, 8));
        try (Boundary b = new Boundary(null)) {
            // The explicit still request wins even if a different request is exposed elsewhere.
            CaptureRequest unrelatedAuto = request(CaptureRequest.CONTROL_AWB_MODE_AUTO, null);
            when(b.result.getRequest()).thenReturn(unrelatedAuto);
            Path path = destination("manual.dng");
            assertTrue(ImageSaver.Util.saveSingleRawM10RPhysicalCfa(
                    path, b.frame, b.characteristics, b.result, selected, 270));

            Parameters written = b.written();
            verify(written).FillDynamicParameters(b.result, selected, 320);
            assertNull(b.result.get(CaptureResult.SENSOR_NEUTRAL_COLOR_POINT));
            assertArrayEquals(new float[]{0.5f, 1.0f, 0.25f}, written.whitePoint, 0.0f);
            b.assertPhoneMetadataAndRawUnchanged(written);
            assertTrue(Files.exists(path));
        }
    }

    @Test public void autoKeepsHistoricalNeutralAndPhoneMetadata() throws Exception {
        float[] vendor = {0.43000004f, 0.9800001f, 0.71000004f};
        // Gains on an Auto request do not claim authority over the vendor neutral.
        CaptureRequest selected = request(CaptureRequest.CONTROL_AWB_MODE_AUTO, gains(4, 2, 2, 8));
        try (Boundary b = new Boundary(vendor)) {
            assertTrue(ImageSaver.Util.saveSingleRawM10RPhysicalCfa(
                    destination("auto.dng"), b.frame, b.characteristics, b.result, selected, 270));

            Parameters written = b.written();
            verify(written).FillDynamicParameters(b.result, null, 320);
            assertSame("Auto must retain the population result, without normalizing or replacing it",
                    b.populatedNeutral, written.whitePoint);
            assertArrayEquals(vendor, written.whitePoint, 0.0f);
            b.assertPhoneMetadataAndRawUnchanged(written);
        }
    }

    @Test public void compatibilityOverloadUsesTheResultAssociatedRequest() throws Exception {
        CaptureRequest selected = request(CaptureRequest.CONTROL_AWB_MODE_OFF, gains(4, 2, 2, 8));
        try (Boundary b = new Boundary(null)) {
            when(b.result.getRequest()).thenReturn(selected);
            assertTrue(ImageSaver.Util.saveSingleRawM10RPhysicalCfa(
                    destination("associated.dng"), b.frame, b.characteristics, b.result, 270));
            Parameters written = b.written();
            verify(written).FillDynamicParameters(b.result, selected, 320);
            assertArrayEquals(new float[]{0.5f, 1.0f, 0.25f}, written.whitePoint, 0.0f);
            b.assertPhoneMetadataAndRawUnchanged(written);
        }
    }

    @Test public void invalidManualRequestCannotWriteOrFallBackToVendorWhite() throws Exception {
        RggbChannelVector[] invalid = {null, gains(0, 1, 1, 2)};
        for (int i = 0; i < invalid.length; i++) {
            CaptureRequest selected = request(CaptureRequest.CONTROL_AWB_MODE_OFF, invalid[i]);
            try (Boundary b = new Boundary(new float[]{0.6f, 1.0f, 0.8f})) {
                Path path = destination("invalid-" + i + ".dng");
                assertThrows(IllegalArgumentException.class, () ->
                        ImageSaver.Util.saveSingleRawM10RPhysicalCfa(
                                path, b.frame, b.characteristics, b.result, selected, 270));
                assertTrue(b.writers.constructed().isEmpty());
                assertFalse(Files.exists(path));
                Parameters populated = b.parameters.constructed().get(0);
                verify(populated, never()).FillDynamicParameters(any(), nullable(CaptureRequest.class), anyInt());
                assertNull("A rejected manual selection must not invent a white point", populated.whitePoint);
            }
        }
    }

    private Path destination(String name) { return temporary.getRoot().toPath().resolve(name); }

    private static CaptureRequest request(int mode, RggbChannelVector gains) {
        CaptureRequest request = mock(CaptureRequest.class);
        when(request.get(CaptureRequest.CONTROL_AWB_MODE)).thenReturn(mode);
        when(request.get(CaptureRequest.COLOR_CORRECTION_GAINS)).thenReturn(gains);
        return request;
    }

    private static RggbChannelVector gains(float red, float greenEven, float greenOdd, float blue) {
        RggbChannelVector gains = mock(RggbChannelVector.class);
        when(gains.getRed()).thenReturn(red);
        when(gains.getGreenEven()).thenReturn(greenEven);
        when(gains.getGreenOdd()).thenReturn(greenOdd);
        when(gains.getBlue()).thenReturn(blue);
        return gains;
    }

    private static final class Boundary implements AutoCloseable {
        final CameraCharacteristics characteristics = mock(CameraCharacteristics.class);
        final CaptureResult result = mock(CaptureResult.class);
        final ImageFrame frame;
        final byte[] raw = new byte[32];
        final float[] populatedNeutral;
        final float[][] profile = {
                {1, 2, 3, 4, 5, 6, 7, 8, 9}, {9, 8, 7, 6, 5, 4, 3, 2, 1},
                {1, 0, 0, 0, 2, 0, 0, 0, 3}, {3, 0, 0, 0, 2, 0, 0, 0, 1},
                {2, 1, 0, 0, 2, 1, 1, 0, 2}, {4, 0, 1, 1, 4, 0, 0, 1, 4}
        };
        final float[][] originalProfile = Arrays.stream(profile).map(matrix -> matrix.clone()).toArray(float[][]::new);
        final MockedStatic<Log> logging;
        final MockedConstruction<Parameters> parameters;
        final MockedConstruction<DngCreator> writers;

        Boundary(float[] vendorNeutral) throws Exception {
            var constructor = ImageFrame.class.getDeclaredConstructor();
            constructor.setAccessible(true);
            frame = constructor.newInstance();
            for (int i = 0; i < raw.length; i++) raw[i] = (byte) (i * 7 + 3);
            frame.buffer = ByteBuffer.allocateDirect(raw.length);
            frame.buffer.put(raw).flip();
            frame.width = 4; frame.height = 4;
            frame.cropOriginX = 2; frame.cropOriginY = 4;
            frame.fullWidth = 12; frame.fullHeight = 16;
            when(characteristics.get(CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT)).thenReturn(3);
            when(result.get(CaptureResult.SENSOR_SENSITIVITY)).thenReturn(320);
            if (vendorNeutral != null) {
                Rational[] neutral = new Rational[3];
                for (int i = 0; i < 3; i++) {
                    neutral[i] = mock(Rational.class);
                    when(neutral[i].floatValue()).thenReturn(vendorNeutral[i]);
                }
                when(result.get(CaptureResult.SENSOR_NEUTRAL_COLOR_POINT)).thenReturn(neutral);
            }
            populatedNeutral = vendorNeutral == null ? new float[]{9, 1, 7} : vendorNeutral.clone();
            Point size = mock(Point.class); size.x = 4; size.y = 4;
            logging = mockStatic(Log.class);
            parameters = mockConstruction(Parameters.class, (p, context) -> {
                doAnswer(call -> {
                    p.rawSize = size;
                    // Simulate phone metadata population, including a CFA setting that the
                    // physical Camera2 CFA must override before publication.
                    p.cfaPattern = 0;
                    p.ColorMatrix1 = profile[0]; p.ColorMatrix2 = profile[1];
                    p.ForwardTransform1 = profile[2]; p.ForwardTransform2 = profile[3];
                    p.calibrationTransform1 = profile[4]; p.calibrationTransform2 = profile[5];
                    p.calibrationIlluminant1 = 17; p.calibrationIlluminant2 = 21;
                    p.whiteLevel = 4095; p.blackLevel = new float[]{64, 65, 66, 67};
                    p.cameraID = "physical-phone-camera";
                    return null;
                }).when(p).FillConstParameters(any(), any(Point.class));
                doAnswer(call -> {
                    // The real Parameters manual branch needs the exact request when
                    // SENSOR_NEUTRAL_COLOR_POINT is absent. An accidentally dropped request
                    // must fail this boundary test rather than silently passing the fixture.
                    if (vendorNeutral == null && call.getArgument(1) == null)
                        throw new IllegalStateException("Manual request discarded before Parameters");
                    p.whitePoint = populatedNeutral;
                    p.iso = call.getArgument(2);
                    return null;
                }).when(p).FillDynamicParameters(any(), nullable(CaptureRequest.class), anyInt());
            });
            writers = mockConstruction(DngCreator.class);
        }

        Parameters written() throws Exception {
            assertEquals(1, parameters.constructed().size());
            assertEquals(1, writers.constructed().size());
            DngCreator writer = writers.constructed().get(0);
            ArgumentCaptor<Parameters> captured = ArgumentCaptor.forClass(Parameters.class);
            verify(writer).setParameters(captured.capture());
            verify(writer).setCompression(false);
            verify(writer).writeBuffer(any(), same(frame.buffer), eq(4), eq(4));
            verify(writer).close();
            assertSame(parameters.constructed().get(0), captured.getValue());
            return captured.getValue();
        }

        void assertPhoneMetadataAndRawUnchanged(Parameters written) {
            assertSame(profile[0], written.ColorMatrix1); assertSame(profile[1], written.ColorMatrix2);
            assertSame(profile[2], written.ForwardTransform1); assertSame(profile[3], written.ForwardTransform2);
            assertSame(profile[4], written.calibrationTransform1); assertSame(profile[5], written.calibrationTransform2);
            for (int i = 0; i < profile.length; i++) assertArrayEquals(originalProfile[i], profile[i], 0.0f);
            assertEquals(17, written.calibrationIlluminant1); assertEquals(21, written.calibrationIlluminant2);
            assertEquals(3, written.cfaPattern); assertEquals(4095, written.whiteLevel);
            assertArrayEquals(new float[]{64, 65, 66, 67}, written.blackLevel, 0.0f);
            assertEquals("physical-phone-camera", written.cameraID);
            assertEquals(320, written.iso); assertEquals(270, written.cameraRotation);
            verify(written).FillConstParameters(same(characteristics), any(Point.class));
            verify(written).setCropDetails(2, 4); verify(written).setFullRawSize(12, 16);
            assertTrue(frame.buffer.isDirect());
            byte[] retainedRaw = new byte[raw.length];
            frame.buffer.duplicate().get(retainedRaw);
            assertArrayEquals(raw, retainedRaw);
            assertEquals(0, frame.buffer.position()); assertEquals(32, frame.buffer.limit());
        }

        @Override public void close() {
            writers.close(); parameters.close(); logging.close();
        }
    }
}
