package com.m10r.diagnostic;

import java.io.EOFException;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.channels.FileChannel;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/** Decodes classic-TIFF DNG CFA strips using the pixel-exact SOF3 decoder. */
public final class DngRawDecoder {
    private DngRawDecoder() {}

    private static final int MAX_IFDS = 32;
    private static final int MAX_ENTRIES = 2048;
    private static final int TAG_WIDTH = 256;
    private static final int TAG_HEIGHT = 257;
    private static final int TAG_COMPRESSION = 259;
    private static final int TAG_PHOTOMETRIC = 262;
    private static final int TAG_STRIP_OFFSETS = 273;
    private static final int TAG_ROWS_PER_STRIP = 278;
    private static final int TAG_STRIP_BYTE_COUNTS = 279;
    private static final int TAG_SUB_IFDS = 330;

    public static final class RawImage {
        public final int width;
        public final int height;
        public final short[] samples;
        public final int stripCount;
        public final int jpegPrecision;
        public final int jpegPredictor;
        public final int jpegPointTransform;

        RawImage(int width, int height, short[] samples, int stripCount,
                 int jpegPrecision, int jpegPredictor, int jpegPointTransform) {
            this.width = width;
            this.height = height;
            this.samples = samples;
            this.stripCount = stripCount;
            this.jpegPrecision = jpegPrecision;
            this.jpegPredictor = jpegPredictor;
            this.jpegPointTransform = jpegPointTransform;
        }

        public String diagnosticSummary() {
            int min = 0xffff, max = 0;
            long sum = 0;
            long[] planeSum = new long[4];
            long[] planeCount = new long[4];
            MessageDigest sha;
            try { sha = MessageDigest.getInstance("SHA-256"); }
            catch (Exception e) { throw new IllegalStateException(e); }
            byte[] pair = new byte[2];
            for (int y = 0, i = 0; y < height; y++) {
                for (int x = 0; x < width; x++, i++) {
                    int v = samples[i] & 0xffff;
                    if (v < min) min = v;
                    if (v > max) max = v;
                    sum += v;
                    int plane = ((y & 1) << 1) | (x & 1); // RGGB: R,G1,G2,B
                    planeSum[plane] += v;
                    planeCount[plane]++;
                    pair[0] = (byte) v;
                    pair[1] = (byte) (v >>> 8);
                    sha.update(pair);
                }
            }
            String[] names = {"R", "G1", "G2", "B"};
            StringBuilder planes = new StringBuilder();
            for (int p = 0; p < 4; p++) {
                if (p > 0) planes.append(", ");
                planes.append(names[p]).append('=')
                        .append(String.format(Locale.US, "%.3f", (double) planeSum[p] / planeCount[p]));
            }
            return String.format(Locale.US,
                    "Decoded CFA: %dx%d, strips=%d, samples=%d\n" +
                    "SOF3: precision=%d, predictor=%d, Pt=%d\n" +
                    "RAW stats: min=%d, max=%d, mean=%.6f\n" +
                    "RGGB plane means: %s\n" +
                    "CFA SHA-256 (LE u16): %s",
                    width, height, stripCount, samples.length,
                    jpegPrecision, jpegPredictor, jpegPointTransform,
                    min, max, (double) sum / samples.length,
                    planes, hex(sha.digest()));
        }
    }

    private static final class Ifd {
        long width;
        long height;
        int compression = 1;
        int photometric;
        long rowsPerStrip;
        long[] stripOffsets;
        long[] stripCounts;
    }

    private static final class Entry {
        final int type;
        final long count;
        final byte[] data;
        final ByteOrder order;
        Entry(int type, long count, byte[] data, ByteOrder order) {
            this.type = type; this.count = count; this.data = data; this.order = order;
        }
        long[] longs() throws IOException {
            if (count > Integer.MAX_VALUE) throw new IOException("TIFF value count too large");
            int n = (int) count;
            long[] out = new long[n];
            ByteBuffer b = ByteBuffer.wrap(data).order(order);
            for (int i = 0; i < n; i++) {
                switch (type) {
                    case 1: case 6: case 7: out[i] = b.get() & 0xffL; break;
                    case 3: out[i] = b.getShort() & 0xffffL; break;
                    case 4: out[i] = b.getInt() & 0xffffffffL; break;
                    case 8: out[i] = b.getShort(); break;
                    case 9: out[i] = b.getInt(); break;
                    default: throw new IOException("unsupported integer TIFF type " + type);
                }
            }
            return out;
        }
        long first(long fallback) throws IOException {
            long[] v = longs(); return v.length == 0 ? fallback : v[0];
        }
    }

    public static RawImage decode(FileChannel ch) throws IOException {
        if (ch == null) throw new IllegalArgumentException("channel == null");
        byte[] header = readAt(ch, 0, 8);
        ByteOrder order;
        if (header[0] == 'I' && header[1] == 'I') order = ByteOrder.LITTLE_ENDIAN;
        else if (header[0] == 'M' && header[1] == 'M') order = ByteOrder.BIG_ENDIAN;
        else throw new IOException("not a classic TIFF/DNG");
        ByteBuffer h = ByteBuffer.wrap(header).order(order);
        h.position(2);
        if ((h.getShort() & 0xffff) != 42) throw new IOException("classic TIFF magic 42 required");
        long firstIfd = h.getInt() & 0xffffffffL;

        List<Ifd> ifds = new ArrayList<>();
        parseChain(ch, order, firstIfd, new HashSet<>(), ifds);
        Ifd raw = null;
        long bestPixels = -1;
        for (Ifd x : ifds) {
            long px = x.width * x.height;
            if (x.photometric == 32803 && px > bestPixels) { raw = x; bestPixels = px; }
        }
        if (raw == null) throw new IOException("no CFA RAW IFD found");
        if (raw.compression != 7) throw new IOException("RAW compression " + raw.compression + " is not JPEG/lossless-JPEG (7)");
        if (raw.width <= 0 || raw.height <= 0 || raw.width > Integer.MAX_VALUE || raw.height > Integer.MAX_VALUE)
            throw new IOException("invalid RAW dimensions");
        if (raw.stripOffsets == null || raw.stripCounts == null || raw.stripOffsets.length == 0 || raw.stripOffsets.length != raw.stripCounts.length)
            throw new IOException("RAW strip arrays missing or inconsistent");

        int width = (int) raw.width;
        int height = (int) raw.height;
        long totalLong = (long) width * height;
        if (totalLong > Integer.MAX_VALUE) throw new IOException("RAW image too large for Java array");
        short[] result = null;
        int rowsWritten = 0;
        int precision = -1, predictor = -1, pt = -1;

        for (int s = 0; s < raw.stripOffsets.length; s++) {
            long off = raw.stripOffsets[s], count = raw.stripCounts[s];
            if (count <= 0 || count > Integer.MAX_VALUE) throw new IOException("invalid strip byte count");
            byte[] jpeg = readAt(ch, off, (int) count);
            LosslessJpegDecoder.DecodedImage decoded = LosslessJpegDecoder.decode(jpeg);
            int stripWidth = decoded.fullWidth();
            if (stripWidth != width) throw new IOException("JPEG strip full width " + stripWidth + " != DNG width " + width);
            if (precision < 0) { precision = decoded.precision; predictor = decoded.predictor; pt = decoded.pointTransform; }
            else if (precision != decoded.precision || predictor != decoded.predictor || pt != decoded.pointTransform)
                throw new IOException("lossless JPEG strip parameters changed mid-image");
            if (rowsWritten + decoded.height > height) throw new IOException("JPEG strips exceed DNG height");

            if (raw.stripOffsets.length == 1 && decoded.height == height && decoded.samples.length == resultLength(width, height)) {
                result = decoded.samples; // avoid a second full-frame allocation
                rowsWritten = height;
                break;
            }
            if (result == null) result = new short[resultLength(width, height)];
            System.arraycopy(decoded.samples, 0, result, rowsWritten * width, decoded.samples.length);
            rowsWritten += decoded.height;
        }
        if (result == null || rowsWritten != height) throw new IOException("decoded rows " + rowsWritten + " != DNG height " + height);
        return new RawImage(width, height, result, raw.stripOffsets.length, precision, predictor, pt);
    }

    private static int resultLength(int w, int h) throws IOException {
        long n = (long) w * h;
        if (n > Integer.MAX_VALUE) throw new IOException("RAW sample array too large");
        return (int) n;
    }

    private static void parseChain(FileChannel ch, ByteOrder order, long offset, Set<Long> seen, List<Ifd> out) throws IOException {
        while (offset != 0 && out.size() < MAX_IFDS && seen.add(offset)) {
            byte[] countBytes = readAt(ch, offset, 2);
            int n = ByteBuffer.wrap(countBytes).order(order).getShort() & 0xffff;
            if (n > MAX_ENTRIES) throw new IOException("IFD entry count too large");
            Ifd ifd = new Ifd();
            List<Long> subIfds = new ArrayList<>();
            for (int i = 0; i < n; i++) {
                long p = offset + 2L + 12L * i;
                byte[] ebytes = readAt(ch, p, 12);
                ByteBuffer e = ByteBuffer.wrap(ebytes).order(order);
                int tag = e.getShort() & 0xffff;
                int type = e.getShort() & 0xffff;
                long count = e.getInt() & 0xffffffffL;
                int size = typeSize(type);
                if (size == 0 || count > (1L << 20)) continue;
                long bytesLong = count * size;
                if (bytesLong < 0 || bytesLong > (1L << 24)) continue;
                int bytes = (int) bytesLong;
                byte[] value;
                if (bytes <= 4) {
                    value = new byte[bytes];
                    System.arraycopy(ebytes, 8, value, 0, bytes);
                } else {
                    long valueOffset = e.getInt() & 0xffffffffL;
                    value = readAt(ch, valueOffset, bytes);
                }
                Entry v = new Entry(type, count, value, order);
                switch (tag) {
                    case TAG_WIDTH: ifd.width = v.first(0); break;
                    case TAG_HEIGHT: ifd.height = v.first(0); break;
                    case TAG_COMPRESSION: ifd.compression = (int) v.first(1); break;
                    case TAG_PHOTOMETRIC: ifd.photometric = (int) v.first(0); break;
                    case TAG_ROWS_PER_STRIP: ifd.rowsPerStrip = v.first(0); break;
                    case TAG_STRIP_OFFSETS: ifd.stripOffsets = v.longs(); break;
                    case TAG_STRIP_BYTE_COUNTS: ifd.stripCounts = v.longs(); break;
                    case TAG_SUB_IFDS:
                        for (long x : v.longs()) if (x != 0) subIfds.add(x);
                        break;
                    default: break;
                }
            }
            out.add(ifd);
            for (long sub : subIfds) parseChain(ch, order, sub, seen, out);
            long nextPos = offset + 2L + 12L * n;
            offset = u32(readAt(ch, nextPos, 4), order);
        }
    }

    private static int typeSize(int type) {
        switch (type) {
            case 1: case 2: case 6: case 7: return 1;
            case 3: case 8: return 2;
            case 4: case 9: case 11: return 4;
            case 5: case 10: case 12: return 8;
            default: return 0;
        }
    }

    private static byte[] readAt(FileChannel ch, long offset, int length) throws IOException {
        if (offset < 0 || length < 0 || offset + (long) length > ch.size()) throw new EOFException("TIFF read outside file");
        ByteBuffer b = ByteBuffer.allocate(length);
        long p = offset;
        while (b.hasRemaining()) {
            int n = ch.read(b, p);
            if (n < 0) throw new EOFException("unexpected EOF");
            if (n == 0) continue;
            p += n;
        }
        return b.array();
    }

    private static long u32(byte[] bytes, ByteOrder order) {
        return ByteBuffer.wrap(bytes).order(order).getInt() & 0xffffffffL;
    }

    private static String hex(byte[] a) {
        StringBuilder s = new StringBuilder(a.length * 2);
        for (byte b : a) s.append(String.format(Locale.US, "%02x", b & 0xff));
        return s.toString();
    }
}
