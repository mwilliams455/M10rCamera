package com.m10r.diagnostic;

import java.io.EOFException;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.channels.FileChannel;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/** Minimal classic-TIFF/DNG parser for the M10-R diagnostic path. */
public final class DngMetadataReader {
    private DngMetadataReader() {}

    private static final int TIFF_MAGIC = 42;
    private static final int MAX_IFDS = 16;
    private static final int MAX_ENTRIES_PER_IFD = 2048;
    private static final long MAX_VALUE_BYTES = 1L << 20;

    private static final int TAG_IMAGE_WIDTH = 256;
    private static final int TAG_IMAGE_LENGTH = 257;
    private static final int TAG_BITS_PER_SAMPLE = 258;
    private static final int TAG_COMPRESSION = 259;
    private static final int TAG_PHOTOMETRIC = 262;
    private static final int TAG_STRIP_OFFSETS = 273;
    private static final int TAG_STRIP_BYTE_COUNTS = 279;
    private static final int TAG_TILE_WIDTH = 322;
    private static final int TAG_TILE_LENGTH = 323;
    private static final int TAG_TILE_OFFSETS = 324;
    private static final int TAG_TILE_BYTE_COUNTS = 325;
    private static final int TAG_SUB_IFDS = 330;
    private static final int TAG_CFA_REPEAT_PATTERN_DIM = 33421;
    private static final int TAG_CFA_PATTERN = 33422;
    private static final int TAG_BLACK_LEVEL = 50714;
    private static final int TAG_WHITE_LEVEL = 50717;
    private static final int TAG_COLOR_MATRIX_1 = 50721;
    private static final int TAG_COLOR_MATRIX_2 = 50722;
    private static final int TAG_AS_SHOT_NEUTRAL = 50728;
    private static final int TAG_CALIBRATION_ILLUMINANT_1 = 50778;
    private static final int TAG_CALIBRATION_ILLUMINANT_2 = 50779;
    private static final int TAG_ACTIVE_AREA = 50829;

    public static final class DngInfo {
        public final ByteOrder byteOrder;
        public final int ifdCount;
        public final int width;
        public final int height;
        public final int bitsPerSample;
        public final int compression;
        public final int photometricInterpretation;
        public final long rawPayloadOffset;
        public final long rawPayloadByteCount;
        public final boolean tiled;
        public final int tileWidth;
        public final int tileLength;
        public final double[] asShotNeutral;
        public final double[][] colorMatrix1;
        public final double[][] colorMatrix2;
        public final int calibrationIlluminant1;
        public final int calibrationIlluminant2;
        public final double[] blackLevel;
        public final double[] whiteLevel;
        public final long[] activeArea;
        public final long[] cfaRepeatPatternDim;
        public final byte[] cfaPattern;

        DngInfo(ByteOrder byteOrder, int ifdCount, int width, int height, int bitsPerSample,
                int compression, int photometricInterpretation, long rawPayloadOffset,
                long rawPayloadByteCount, boolean tiled, int tileWidth, int tileLength,
                double[] asShotNeutral, double[][] colorMatrix1, double[][] colorMatrix2,
                int calibrationIlluminant1, int calibrationIlluminant2,
                double[] blackLevel, double[] whiteLevel, long[] activeArea,
                long[] cfaRepeatPatternDim, byte[] cfaPattern) {
            this.byteOrder = byteOrder;
            this.ifdCount = ifdCount;
            this.width = width;
            this.height = height;
            this.bitsPerSample = bitsPerSample;
            this.compression = compression;
            this.photometricInterpretation = photometricInterpretation;
            this.rawPayloadOffset = rawPayloadOffset;
            this.rawPayloadByteCount = rawPayloadByteCount;
            this.tiled = tiled;
            this.tileWidth = tileWidth;
            this.tileLength = tileLength;
            this.asShotNeutral = asShotNeutral;
            this.colorMatrix1 = colorMatrix1;
            this.colorMatrix2 = colorMatrix2;
            this.calibrationIlluminant1 = calibrationIlluminant1;
            this.calibrationIlluminant2 = calibrationIlluminant2;
            this.blackLevel = blackLevel;
            this.whiteLevel = whiteLevel;
            this.activeArea = activeArea;
            this.cfaRepeatPatternDim = cfaRepeatPatternDim;
            this.cfaPattern = cfaPattern;
        }

        public boolean isCfaRaw() { return photometricInterpretation == 32803; }
        public boolean isLosslessJpeg() { return compression == 7; }

        public String summary() {
            StringBuilder s = new StringBuilder();
            s.append("TIFF: ").append(byteOrder == ByteOrder.LITTLE_ENDIAN ? "little-endian" : "big-endian")
                    .append(", IFDs=").append(ifdCount).append('\n');
            s.append("RAW IFD: ").append(width).append('x').append(height)
                    .append(", bits=").append(bitsPerSample)
                    .append(", compression=").append(compressionName(compression))
                    .append(" (").append(compression).append(')')
                    .append(", photometric=").append(photometricInterpretation).append('\n');
            s.append(tiled ? "Tiles" : "Strips").append(": payload≈")
                    .append(rawPayloadByteCount).append(" bytes, firstOffset=").append(rawPayloadOffset);
            if (tiled) s.append(", tile=").append(tileWidth).append('x').append(tileLength);
            s.append('\n');
            s.append("AsShotNeutral: ").append(format(asShotNeutral)).append('\n');
            s.append("Illuminants: ").append(calibrationIlluminant1).append(" / ")
                    .append(calibrationIlluminant2).append('\n');
            s.append("BlackLevel: ").append(format(blackLevel)).append('\n');
            s.append("WhiteLevel: ").append(format(whiteLevel)).append('\n');
            s.append("ActiveArea: ").append(format(activeArea)).append('\n');
            s.append("CFA repeat: ").append(format(cfaRepeatPatternDim))
                    .append(", CFA pattern: ").append(format(cfaPattern)).append('\n');
            s.append("ColorMatrix1: ").append(formatMatrix(colorMatrix1)).append('\n');
            s.append("ColorMatrix2: ").append(formatMatrix(colorMatrix2));
            return s.toString();
        }
    }

    private static final class Entry {
        final int tag;
        final int type;
        final long count;
        final byte[] data;
        final ByteOrder order;

        Entry(int tag, int type, long count, byte[] data, ByteOrder order) {
            this.tag = tag; this.type = type; this.count = count; this.data = data; this.order = order;
        }

        long[] longs() {
            int n = (int) Math.min(count, Integer.MAX_VALUE);
            long[] out = new long[n];
            ByteBuffer b = ByteBuffer.wrap(data).order(order);
            for (int i = 0; i < n; i++) {
                switch (type) {
                    case 1: case 6: case 7: out[i] = b.get() & 0xffL; break;
                    case 3: out[i] = b.getShort() & 0xffffL; break;
                    case 4: out[i] = b.getInt() & 0xffffffffL; break;
                    case 8: out[i] = b.getShort(); break;
                    case 9: out[i] = b.getInt(); break;
                    default: throw new IllegalStateException("tag " + tag + " is not integer type " + type);
                }
            }
            return out;
        }

        double[] doubles() {
            int n = (int) Math.min(count, Integer.MAX_VALUE);
            double[] out = new double[n];
            ByteBuffer b = ByteBuffer.wrap(data).order(order);
            for (int i = 0; i < n; i++) {
                switch (type) {
                    case 1: case 7: out[i] = b.get() & 0xff; break;
                    case 3: out[i] = b.getShort() & 0xffff; break;
                    case 4: out[i] = b.getInt() & 0xffffffffL; break;
                    case 5: {
                        long num = b.getInt() & 0xffffffffL;
                        long den = b.getInt() & 0xffffffffL;
                        out[i] = den == 0 ? Double.NaN : (double) num / (double) den;
                        break;
                    }
                    case 8: out[i] = b.getShort(); break;
                    case 9: out[i] = b.getInt(); break;
                    case 10: {
                        int num = b.getInt();
                        int den = b.getInt();
                        out[i] = den == 0 ? Double.NaN : (double) num / (double) den;
                        break;
                    }
                    case 11: out[i] = b.getFloat(); break;
                    case 12: out[i] = b.getDouble(); break;
                    default: throw new IllegalStateException("tag " + tag + " is not numeric type " + type);
                }
            }
            return out;
        }
    }

    private static final class Ifd {
        final Map<Integer, Entry> tags = new HashMap<>();
    }

    public static DngInfo read(FileChannel channel) throws IOException {
        if (channel == null) throw new IllegalArgumentException("channel == null");
        byte[] header = readAt(channel, 0, 8);
        ByteOrder order;
        if (header[0] == 'I' && header[1] == 'I') order = ByteOrder.LITTLE_ENDIAN;
        else if (header[0] == 'M' && header[1] == 'M') order = ByteOrder.BIG_ENDIAN;
        else throw new IOException("not TIFF/DNG: bad byte-order marker");

        ByteBuffer h = ByteBuffer.wrap(header).order(order);
        h.position(2);
        if ((h.getShort() & 0xffff) != TIFF_MAGIC) {
            throw new IOException("unsupported TIFF variant (classic TIFF magic 42 required)");
        }
        long firstIfd = h.getInt() & 0xffffffffL;
        List<Ifd> ifds = new ArrayList<>();
        Set<Long> visited = new HashSet<>();
        parseIfdChain(channel, order, firstIfd, ifds, visited);
        if (ifds.isEmpty()) throw new IOException("DNG contains no readable IFDs");

        Ifd raw = chooseRawIfd(ifds);
        Entry widthE = raw.tags.get(TAG_IMAGE_WIDTH);
        Entry heightE = raw.tags.get(TAG_IMAGE_LENGTH);
        int width = firstInt(widthE, 0);
        int height = firstInt(heightE, 0);
        int bits = firstInt(raw.tags.get(TAG_BITS_PER_SAMPLE), 0);
        int compression = firstInt(raw.tags.get(TAG_COMPRESSION), 1);
        int photometric = firstInt(raw.tags.get(TAG_PHOTOMETRIC), 0);

        long[] tileOffsets = longs(raw.tags.get(TAG_TILE_OFFSETS));
        long[] tileCounts = longs(raw.tags.get(TAG_TILE_BYTE_COUNTS));
        long[] stripOffsets = longs(raw.tags.get(TAG_STRIP_OFFSETS));
        long[] stripCounts = longs(raw.tags.get(TAG_STRIP_BYTE_COUNTS));
        boolean tiled = tileOffsets != null && tileOffsets.length > 0;
        long[] offsets = tiled ? tileOffsets : stripOffsets;
        long[] counts = tiled ? tileCounts : stripCounts;
        long payloadOffset = offsets == null || offsets.length == 0 ? 0 : offsets[0];
        long payloadBytes = sum(counts);

        Entry asn = findFirst(ifds, TAG_AS_SHOT_NEUTRAL);
        Entry cm1 = findFirst(ifds, TAG_COLOR_MATRIX_1);
        Entry cm2 = findFirst(ifds, TAG_COLOR_MATRIX_2);
        Entry ill1 = findFirst(ifds, TAG_CALIBRATION_ILLUMINANT_1);
        Entry ill2 = findFirst(ifds, TAG_CALIBRATION_ILLUMINANT_2);
        Entry black = findFirst(ifds, TAG_BLACK_LEVEL);
        Entry white = findFirst(ifds, TAG_WHITE_LEVEL);
        Entry active = findFirst(ifds, TAG_ACTIVE_AREA);
        Entry cfaDim = raw.tags.get(TAG_CFA_REPEAT_PATTERN_DIM);
        Entry cfa = raw.tags.get(TAG_CFA_PATTERN);

        return new DngInfo(order, ifds.size(), width, height, bits, compression, photometric,
                payloadOffset, payloadBytes, tiled,
                firstInt(raw.tags.get(TAG_TILE_WIDTH), 0), firstInt(raw.tags.get(TAG_TILE_LENGTH), 0),
                doubles(asn), matrix3(cm1), matrix3(cm2), firstInt(ill1, 0), firstInt(ill2, 0),
                doubles(black), doubles(white), longs(active), longs(cfaDim), cfa == null ? null : cfa.data.clone());
    }

    private static void parseIfdChain(FileChannel ch, ByteOrder order, long offset,
                                      List<Ifd> out, Set<Long> visited) throws IOException {
        while (offset != 0 && out.size() < MAX_IFDS && visited.add(offset)) {
            Ifd ifd = parseOneIfd(ch, order, offset);
            out.add(ifd);
            Entry sub = ifd.tags.get(TAG_SUB_IFDS);
            if (sub != null) {
                long[] subs = sub.longs();
                for (long s : subs) {
                    if (s != 0 && out.size() < MAX_IFDS && !visited.contains(s)) {
                        parseIfdChain(ch, order, s, out, visited);
                    }
                }
            }
            byte[] countBytes = readAt(ch, offset, 2);
            int count = ByteBuffer.wrap(countBytes).order(order).getShort() & 0xffff;
            long nextPos = offset + 2L + 12L * count;
            offset = u32(readAt(ch, nextPos, 4), order);
        }
    }

    private static Ifd parseOneIfd(FileChannel ch, ByteOrder order, long offset) throws IOException {
        int count = ByteBuffer.wrap(readAt(ch, offset, 2)).order(order).getShort() & 0xffff;
        if (count > MAX_ENTRIES_PER_IFD) throw new IOException("IFD entry count too large: " + count);
        Ifd ifd = new Ifd();
        for (int i = 0; i < count; i++) {
            long p = offset + 2L + 12L * i;
            byte[] entryBytes = readAt(ch, p, 12);
            ByteBuffer e = ByteBuffer.wrap(entryBytes).order(order);
            int tag = e.getShort() & 0xffff;
            int type = e.getShort() & 0xffff;
            long n = e.getInt() & 0xffffffffL;
            int size = typeSize(type);
            if (size == 0) continue;
            long bytes = n * (long) size;
            if (bytes < 0 || bytes > MAX_VALUE_BYTES) continue;
            byte[] value;
            if (bytes <= 4) {
                value = new byte[(int) bytes];
                System.arraycopy(entryBytes, 8, value, 0, (int) bytes);
            } else {
                long valueOffset = e.getInt() & 0xffffffffL;
                value = readAt(ch, valueOffset, (int) bytes);
            }
            ifd.tags.put(tag, new Entry(tag, type, n, value, order));
        }
        return ifd;
    }

    private static Ifd chooseRawIfd(List<Ifd> ifds) {
        Ifd best = ifds.get(0);
        long bestPixels = -1;
        for (Ifd ifd : ifds) {
            int photo = firstInt(ifd.tags.get(TAG_PHOTOMETRIC), 0);
            long w = firstInt(ifd.tags.get(TAG_IMAGE_WIDTH), 0);
            long h = firstInt(ifd.tags.get(TAG_IMAGE_LENGTH), 0);
            long pixels = w * h;
            if (photo == 32803 && pixels >= bestPixels) {
                best = ifd; bestPixels = pixels;
            } else if (bestPixels < 0 && pixels > 0) {
                best = ifd;
            }
        }
        return best;
    }

    private static Entry findFirst(List<Ifd> ifds, int tag) {
        for (Ifd ifd : ifds) {
            Entry e = ifd.tags.get(tag);
            if (e != null) return e;
        }
        return null;
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

    private static byte[] readAt(FileChannel ch, long pos, int count) throws IOException {
        if (pos < 0 || count < 0) throw new IOException("invalid file range");
        ByteBuffer b = ByteBuffer.allocate(count);
        while (b.hasRemaining()) {
            int n = ch.read(b, pos + b.position());
            if (n < 0) throw new EOFException("unexpected EOF at " + pos + " + " + b.position());
            if (n == 0) throw new EOFException("zero-byte read at " + pos);
        }
        return b.array();
    }

    private static long u32(byte[] b, ByteOrder order) {
        return ByteBuffer.wrap(b).order(order).getInt() & 0xffffffffL;
    }

    private static int firstInt(Entry e, int fallback) {
        if (e == null) return fallback;
        try {
            long[] v = e.longs();
            return v.length == 0 ? fallback : (int) v[0];
        } catch (RuntimeException ex) {
            double[] v = e.doubles();
            return v.length == 0 ? fallback : (int) Math.round(v[0]);
        }
    }

    private static long[] longs(Entry e) {
        if (e == null) return null;
        try { return e.longs(); }
        catch (RuntimeException ex) {
            double[] d = e.doubles();
            long[] out = new long[d.length];
            for (int i = 0; i < d.length; i++) out[i] = Math.round(d[i]);
            return out;
        }
    }

    private static double[] doubles(Entry e) {
        return e == null ? null : e.doubles();
    }

    private static double[][] matrix3(Entry e) {
        if (e == null) return null;
        double[] v = e.doubles();
        if (v.length != 9) return null;
        return new double[][] {{v[0],v[1],v[2]},{v[3],v[4],v[5]},{v[6],v[7],v[8]}};
    }

    private static long sum(long[] v) {
        if (v == null) return 0;
        long s = 0;
        for (long x : v) {
            if (x > 0 && Long.MAX_VALUE - s >= x) s += x;
        }
        return s;
    }

    private static String compressionName(int c) {
        switch (c) {
            case 1: return "uncompressed";
            case 7: return "JPEG/lossless-JPEG";
            case 8: return "Deflate";
            case 34892: return "JPEG lossless (DNG variant)";
            default: return "other";
        }
    }

    private static String format(double[] v) {
        if (v == null) return "<missing>";
        StringBuilder s = new StringBuilder("[");
        for (int i = 0; i < v.length; i++) {
            if (i > 0) s.append(", ");
            s.append(String.format(Locale.US, "%.10g", v[i]));
        }
        return s.append(']').toString();
    }

    private static String format(long[] v) {
        if (v == null) return "<missing>";
        StringBuilder s = new StringBuilder("[");
        for (int i = 0; i < v.length; i++) {
            if (i > 0) s.append(", ");
            s.append(v[i]);
        }
        return s.append(']').toString();
    }

    private static String format(byte[] v) {
        if (v == null) return "<missing>";
        StringBuilder s = new StringBuilder("[");
        for (int i = 0; i < v.length; i++) {
            if (i > 0) s.append(", ");
            s.append(v[i] & 0xff);
        }
        return s.append(']').toString();
    }

    private static String formatMatrix(double[][] m) {
        if (m == null) return "<missing>";
        return String.format(Locale.US,
                "[[%.8f, %.8f, %.8f], [%.8f, %.8f, %.8f], [%.8f, %.8f, %.8f]]",
                m[0][0],m[0][1],m[0][2],m[1][0],m[1][1],m[1][2],m[2][0],m[2][1],m[2][2]);
    }
}
