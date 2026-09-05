package com.m10r.diagnostic;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.channels.FileChannel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;

import org.junit.Test;

public class DngMetadataReaderTest {
    @Test
    public void parsesSyntheticClassicDngAndFeedsCa9Path() throws Exception {
        byte[] fixture = buildFixture();
        Path p = Files.createTempFile("m10r-dng-fixture", ".dng");
        try {
            Files.write(p, fixture);
            try (FileChannel ch = FileChannel.open(p, StandardOpenOption.READ)) {
                DngMetadataReader.DngInfo info = DngMetadataReader.read(ch);
                assertEquals(9520, info.width);
                assertEquals(6336, info.height);
                assertEquals(14, info.bitsPerSample);
                assertEquals(7, info.compression);
                assertEquals(32803, info.photometricInterpretation);
                assertTrue(info.isCfaRaw());
                assertTrue(info.isLosslessJpeg());
                assertNotNull(info.asShotNeutral);
                assertEquals(3, info.asShotNeutral.length);
                assertArrayEquals(new int[] {897, 256, 390},
                        M10RColorSpecCore.recoverCa9Gains(info.asShotNeutral));
                assertNotNull(info.colorMatrix1);
                assertEquals(1.0, info.colorMatrix1[0][0], 0.0);
                assertEquals(1.0, info.colorMatrix1[1][1], 0.0);
                assertEquals(1.0, info.colorMatrix1[2][2], 0.0);
            }
        } finally {
            Files.deleteIfExists(p);
        }
    }

    private static byte[] buildFixture() {
        ByteBuffer b = ByteBuffer.allocate(512).order(ByteOrder.LITTLE_ENDIAN);
        b.put((byte) 'I').put((byte) 'I').putShort((short) 42).putInt(8);

        final int entries = 7;
        b.position(8);
        b.putShort((short) entries);
        putLongInline(b, 256, 9520);               // ImageWidth
        putLongInline(b, 257, 6336);               // ImageLength
        putShortInline(b, 258, 14);                // BitsPerSample
        putShortInline(b, 259, 7);                 // Compression
        putLongInline(b, 262, 32803);              // CFA photometric
        putOffsetEntry(b, 50728, 5, 3, 128);       // AsShotNeutral RATIONAL[3]
        putOffsetEntry(b, 50721, 10, 9, 160);      // ColorMatrix1 SRATIONAL[9]
        b.putInt(0);                               // next IFD

        b.position(128);
        putRational(b, 2_853_958, 10_000_000);
        putRational(b, 1, 1);
        putRational(b, 6_564_103, 10_000_000);

        b.position(160);
        for (int r = 0; r < 3; r++) {
            for (int c = 0; c < 3; c++) {
                putSignedRational(b, r == c ? 1 : 0, 1);
            }
        }
        return b.array();
    }

    private static void putLongInline(ByteBuffer b, int tag, long value) {
        b.putShort((short) tag).putShort((short) 4).putInt(1).putInt((int) value);
    }

    private static void putShortInline(ByteBuffer b, int tag, int value) {
        b.putShort((short) tag).putShort((short) 3).putInt(1).putShort((short) value).putShort((short) 0);
    }

    private static void putOffsetEntry(ByteBuffer b, int tag, int type, int count, int offset) {
        b.putShort((short) tag).putShort((short) type).putInt(count).putInt(offset);
    }

    private static void putRational(ByteBuffer b, long numerator, long denominator) {
        b.putInt((int) numerator).putInt((int) denominator);
    }

    private static void putSignedRational(ByteBuffer b, int numerator, int denominator) {
        b.putInt(numerator).putInt(denominator);
    }
}
