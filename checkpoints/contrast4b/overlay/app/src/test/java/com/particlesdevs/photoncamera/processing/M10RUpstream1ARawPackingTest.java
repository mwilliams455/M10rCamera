package com.particlesdevs.photoncamera.processing;

import com.particlesdevs.photoncamera.m10r.M10RUpstream1A;
import org.junit.Test;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.security.MessageDigest;
import org.mockito.MockMakers;
import static org.junit.Assert.*;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.CALLS_REAL_METHODS;
import static org.mockito.Mockito.withSettings;

/** Exercises the real shared arrival method; native allocation must never run for M10-R. */
public class M10RUpstream1ARawPackingTest {
    private ImageFrame emptyFrame() {
        return mock(ImageFrame.class, withSettings().mockMaker(MockMakers.SUBCLASS)
                .defaultAnswer(CALLS_REAL_METHODS));
    }
    private void preservesRaw16(int width, int height, int whiteLevel, boolean verify)
            throws Exception {
        assertTrue("This test targets the M10-R build route", M10RUpstream1A.isM10rBuild());
        // Avoid a native constructor; all fields consumed by the real static method
        // are populated. No method on ImageFrame or Allocator is stubbed.
        ImageFrame frame = emptyFrame();
        ByteBuffer raw = ByteBuffer.allocateDirect(width * height * 2)
                .order(ByteOrder.LITTLE_ENDIAN);
        for (int i = 0; i < width * height; i++) {
            raw.putShort(i * 2, (short) ((i * 37 + 63) & whiteLevel));
        }
        frame.buffer = raw;
        frame.width = width;
        frame.height = height;
        byte[] before = digest(raw);
        raw.position(6);
        raw.mark();
        raw.limit(raw.capacity() - 2);

        // Both RAW16Saver and the ZSL caller enter this real method.
        ImageFrame.packBurstAtArrival(frame, whiteLevel, verify);

        assertSame("M10-R retains the original owned buffer", raw, frame.buffer);
        assertEquals(0, frame.packedBits);
        assertEquals(width * height * 2, frame.buffer.capacity());
        assertArrayEquals("No sensor sample may change", before, digest(frame.buffer));
        assertEquals(6, raw.position());
        assertEquals(raw.capacity() - 2, raw.limit());
        assertEquals(ByteOrder.LITTLE_ENDIAN, raw.order());
        raw.reset();
        assertEquals(6, raw.position());
        raw.clear();
        frame.requireM10rRaw16();
    }

    private static byte[] digest(ByteBuffer buffer) throws Exception {
        ByteBuffer view = buffer.duplicate();
        view.clear();
        MessageDigest hash = MessageDigest.getInstance("SHA-256");
        hash.update(view);
        return hash.digest();
    }

    @Test public void preservesFull12MpTenBitSensor() throws Exception {
        preservesRaw16(4096, 3072, 1023, true);
    }
    @Test public void preservesTwelveBitSensor() throws Exception {
        preservesRaw16(64, 48, 4095, true);
    }
    @Test public void preservesFourteenBitSensor() throws Exception {
        preservesRaw16(64, 48, 16383, false);
    }
    @Test public void preservesSixteenBitSensor() throws Exception {
        preservesRaw16(64, 48, 65535, false);
    }
    @Test public void preservesWithoutDebugVerification() throws Exception {
        preservesRaw16(64, 48, 1023, false);
    }
    @Test public void toleratesMissingFrame() {
        ImageFrame.packBurstAtArrival(null, 1023, false);
        ImageFrame.packBurstAtArrival(emptyFrame(), 1023, true);
    }

    private ImageFrame frame(int bytes, int packedBits, boolean fp16) {
        ImageFrame frame = emptyFrame();
        frame.width = 4096;
        frame.height = 3072;
        frame.buffer = ByteBuffer.allocateDirect(bytes);
        frame.packedBits = packedBits;
        frame.fp16 = fp16;
        return frame;
    }

    @Test public void rejectsExactReportedPackedLayoutBeforeNativeDngWrite() {
        assertThrows(IllegalArgumentException.class,
                () -> frame(15728640, 10, false).requireM10rRaw16());
    }
    @Test public void rejectsTruncatedRawEvenWithoutPackingFlag() {
        assertThrows(IllegalArgumentException.class,
                () -> frame(25165823, 0, false).requireM10rRaw16());
    }
    @Test public void rejectsFloatBufferOfCorrectSize() {
        assertThrows(IllegalArgumentException.class,
                () -> frame(25165824, 0, true).requireM10rRaw16());
    }
    @Test public void rejectsPackedFlagEvenWithRaw16Capacity() {
        assertThrows(IllegalArgumentException.class,
                () -> frame(25165824, 10, false).requireM10rRaw16());
    }
    @Test public void rejectsTruncatedBufferLimit() {
        ImageFrame f = frame(25165824, 0, false);
        f.buffer.limit(25165823);
        assertThrows(IllegalArgumentException.class, f::requireM10rRaw16);
    }
    @Test public void rejectsDimensionsThatOverflowIntByteCount() {
        ImageFrame f = frame(2, 0, false);
        f.width = 65536;
        f.height = 65536;
        assertThrows(IllegalArgumentException.class, f::requireM10rRaw16);
    }
    @Test public void acceptsRaw16WithExtraNativeCapacity() {
        frame(25165824 + 8, 0, false).requireM10rRaw16();
    }

    @Test public void preservesProvidedCaptureWhenConfigured() throws Exception {
        String fixture = System.getenv("M10R_RAW16_FIXTURE");
        org.junit.Assume.assumeTrue("Optional private capture fixture", fixture != null);
        byte[] pixels = java.nio.file.Files.readAllBytes(java.nio.file.Path.of(fixture));
        assertEquals(25165824, pixels.length);
        ImageFrame f = frame(pixels.length, 0, false);
        f.buffer.put(pixels).clear();
        byte[] before = digest(f.buffer);
        ByteBuffer owned = f.buffer;
        ImageFrame.packBurstAtArrival(f, 1023, true);
        f.requireM10rRaw16();
        assertSame(owned, f.buffer);
        assertEquals(0, f.packedBits);
        assertArrayEquals(before, digest(f.buffer));
    }
}
