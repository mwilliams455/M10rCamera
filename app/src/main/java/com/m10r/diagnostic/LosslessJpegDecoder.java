package com.m10r.diagnostic;

import java.io.IOException;
import java.util.Arrays;

/**
 * Bounded ISO/IEC 10918-1 lossless JPEG (SOF3) decoder for DNG CFA payloads.
 *
 * The implementation deliberately supports the features observed in Leica M10-R
 * DNGs and rejects unsupported modes rather than silently approximating them:
 * SOF3, 1x1 component sampling, Huffman-coded differences, predictors 1..7,
 * point transform, byte stuffing, and optional restart markers.
 */
public final class LosslessJpegDecoder {
    private LosslessJpegDecoder() {}

    public static final class DecodedImage {
        public final int width;
        public final int height;
        public final int components;
        public final int precision;
        public final int predictor;
        public final int pointTransform;
        /** Pixel-major, component-interleaved unsigned sample values stored in Java shorts. */
        public final short[] samples;

        DecodedImage(int width, int height, int components, int precision,
                     int predictor, int pointTransform, short[] samples) {
            this.width = width;
            this.height = height;
            this.components = components;
            this.precision = precision;
            this.predictor = predictor;
            this.pointTransform = pointTransform;
            this.samples = samples;
        }

        public int fullWidth() {
            return width * components;
        }
    }

    private static final class Frame {
        int precision;
        int width;
        int height;
        int components;
        int[] ids;
    }

    private static final class Scan {
        int[] componentIds;
        int[] dcTableIds;
        int predictor;
        int pointTransform;
    }

    private static final class HuffmanTable {
        final int[] minCode = new int[17];
        final int[] maxCode = new int[17];
        final int[] valuePtr = new int[17];
        final int[] values;

        HuffmanTable(int[] counts, int[] values) throws IOException {
            this.values = values;
            Arrays.fill(maxCode, -1);
            int code = 0;
            int k = 0;
            for (int len = 1; len <= 16; len++) {
                int count = counts[len - 1];
                if (count > 0) {
                    minCode[len] = code;
                    valuePtr[len] = k;
                    code += count - 1;
                    maxCode[len] = code;
                    code++;
                    k += count;
                }
                code <<= 1;
            }
            if (k != values.length) throw new IOException("invalid DHT symbol count");
        }

        int decode(BitReader bits) throws IOException {
            int code = 0;
            for (int len = 1; len <= 16; len++) {
                code = (code << 1) | bits.readBit();
                if (maxCode[len] >= 0 && code >= minCode[len] && code <= maxCode[len]) {
                    int idx = valuePtr[len] + code - minCode[len];
                    if (idx < 0 || idx >= values.length) throw new IOException("bad Huffman index");
                    return values[idx];
                }
            }
            throw new IOException("invalid Huffman code");
        }
    }

    private static final class BitReader {
        final byte[] data;
        int pos;
        int current;
        int bitsLeft;
        int pendingMarker = -1;

        BitReader(byte[] data, int pos) {
            this.data = data;
            this.pos = pos;
        }

        int readBit() throws IOException {
            if (bitsLeft == 0) {
                current = nextEntropyByte();
                bitsLeft = 8;
            }
            int bit = (current >> 7) & 1;
            current = (current << 1) & 0xff;
            bitsLeft--;
            return bit;
        }

        int readBits(int n) throws IOException {
            int v = 0;
            for (int i = 0; i < n; i++) v = (v << 1) | readBit();
            return v;
        }

        void alignByte() {
            bitsLeft = 0;
        }

        int consumeRestartMarker() throws IOException {
            alignByte();
            int marker;
            if (pendingMarker >= 0) {
                marker = pendingMarker;
                pendingMarker = -1;
                return marker;
            }
            if (pos >= data.length || (data[pos] & 0xff) != 0xff) {
                throw new IOException("restart marker expected at entropy offset " + pos);
            }
            while (pos < data.length && (data[pos] & 0xff) == 0xff) pos++;
            if (pos >= data.length) throw new IOException("truncated restart marker");
            marker = data[pos++] & 0xff;
            return marker;
        }

        private int nextEntropyByte() throws IOException {
            if (pendingMarker >= 0) throw new IOException("unexpected JPEG marker in entropy stream");
            if (pos >= data.length) throw new IOException("truncated entropy stream");
            int b = data[pos++] & 0xff;
            if (b != 0xff) return b;
            if (pos >= data.length) throw new IOException("truncated JPEG marker escape");
            int next = data[pos++] & 0xff;
            while (next == 0xff) {
                if (pos >= data.length) throw new IOException("truncated JPEG fill bytes");
                next = data[pos++] & 0xff;
            }
            if (next == 0x00) return 0xff;
            pendingMarker = next;
            throw new IOException(String.format("unexpected marker FF%02X while decoding entropy", next));
        }
    }

    public static DecodedImage decode(byte[] jpeg) throws IOException {
        if (jpeg == null || jpeg.length < 4) throw new IOException("JPEG payload too short");
        if (u8(jpeg, 0) != 0xff || u8(jpeg, 1) != 0xd8) throw new IOException("missing JPEG SOI");

        Frame frame = null;
        HuffmanTable[] dcTables = new HuffmanTable[4];
        int restartInterval = 0;
        int pos = 2;

        while (pos < jpeg.length) {
            if (u8(jpeg, pos) != 0xff) throw new IOException("marker expected at offset " + pos);
            while (pos < jpeg.length && u8(jpeg, pos) == 0xff) pos++;
            if (pos >= jpeg.length) throw new IOException("truncated marker");
            int marker = u8(jpeg, pos++);
            if (marker == 0xd9) throw new IOException("EOI before SOS");
            if (marker >= 0xd0 && marker <= 0xd7) continue;
            if (pos + 2 > jpeg.length) throw new IOException("truncated segment length");
            int length = u16be(jpeg, pos);
            if (length < 2 || pos + length > jpeg.length) throw new IOException("invalid JPEG segment length");
            int start = pos + 2;
            int end = pos + length;

            if (marker == 0xc3) {
                frame = parseFrame(jpeg, start, end);
            } else if (marker == 0xc4) {
                parseDht(jpeg, start, end, dcTables);
            } else if (marker == 0xdd) {
                if (end - start != 2) throw new IOException("invalid DRI length");
                restartInterval = u16be(jpeg, start);
            } else if (marker == 0xda) {
                if (frame == null) throw new IOException("SOS before SOF3");
                Scan scan = parseScan(jpeg, start, end, frame);
                return decodeScan(jpeg, end, frame, scan, dcTables, restartInterval);
            } else if (marker == 0xc0 || marker == 0xc1 || marker == 0xc2) {
                throw new IOException(String.format("unsupported JPEG SOF marker FF%02X; SOF3 required", marker));
            }
            pos = end;
        }
        throw new IOException("JPEG SOS not found");
    }

    private static Frame parseFrame(byte[] data, int start, int end) throws IOException {
        if (end - start < 6) throw new IOException("truncated SOF3");
        Frame f = new Frame();
        f.precision = u8(data, start);
        f.height = u16be(data, start + 1);
        f.width = u16be(data, start + 3);
        f.components = u8(data, start + 5);
        if (f.precision < 2 || f.precision > 16) throw new IOException("unsupported lossless precision " + f.precision);
        if (f.width <= 0 || f.height <= 0 || f.components <= 0 || f.components > 4) throw new IOException("invalid SOF3 dimensions/components");
        if (end - start != 6 + 3 * f.components) throw new IOException("unexpected SOF3 component record length");
        f.ids = new int[f.components];
        for (int c = 0; c < f.components; c++) {
            int p = start + 6 + 3 * c;
            f.ids[c] = u8(data, p);
            int sampling = u8(data, p + 1);
            if (sampling != 0x11) throw new IOException("subsampled lossless JPEG components are unsupported");
        }
        return f;
    }

    private static void parseDht(byte[] data, int start, int end, HuffmanTable[] dcTables) throws IOException {
        int p = start;
        while (p < end) {
            if (p + 17 > end) throw new IOException("truncated DHT");
            int tcTh = u8(data, p++);
            int tableClass = tcTh >> 4;
            int id = tcTh & 0x0f;
            int[] counts = new int[16];
            int total = 0;
            for (int i = 0; i < 16; i++) { counts[i] = u8(data, p++); total += counts[i]; }
            if (p + total > end) throw new IOException("truncated DHT values");
            int[] values = new int[total];
            for (int i = 0; i < total; i++) values[i] = u8(data, p++);
            if (tableClass != 0) continue;
            if (id >= dcTables.length) throw new IOException("unsupported DC Huffman table id " + id);
            dcTables[id] = new HuffmanTable(counts, values);
        }
    }

    private static Scan parseScan(byte[] data, int start, int end, Frame frame) throws IOException {
        if (start >= end) throw new IOException("truncated SOS");
        int count = u8(data, start);
        if (count != frame.components) throw new IOException("multi-scan lossless JPEG is unsupported");
        if (end - start != 1 + 2 * count + 3) throw new IOException("unexpected SOS length");
        Scan s = new Scan();
        s.componentIds = new int[count];
        s.dcTableIds = new int[count];
        int p = start + 1;
        for (int i = 0; i < count; i++) {
            s.componentIds[i] = u8(data, p++);
            int selectors = u8(data, p++);
            s.dcTableIds[i] = selectors >> 4;
            if ((selectors & 0x0f) != 0) throw new IOException("unexpected AC table selector in lossless scan");
        }
        s.predictor = u8(data, p++);
        int se = u8(data, p++);
        int ahAl = u8(data, p);
        if (s.predictor < 1 || s.predictor > 7) throw new IOException("invalid lossless predictor " + s.predictor);
        if (se != 0 || (ahAl >> 4) != 0) throw new IOException("unsupported lossless SOS parameters");
        s.pointTransform = ahAl & 0x0f;
        if (s.pointTransform >= frame.precision) throw new IOException("invalid point transform");
        for (int i = 0; i < count; i++) {
            if (s.componentIds[i] != frame.ids[i]) throw new IOException("scan/frame component ordering mismatch");
        }
        return s;
    }

    private static DecodedImage decodeScan(byte[] data, int entropyStart, Frame f, Scan s,
                                           HuffmanTable[] dcTables, int restartInterval) throws IOException {
        for (int id : s.dcTableIds) {
            if (id < 0 || id >= dcTables.length || dcTables[id] == null) throw new IOException("missing DC Huffman table " + id);
        }
        long sampleCountLong = (long) f.width * f.height * f.components;
        if (sampleCountLong > Integer.MAX_VALUE) throw new IOException("decoded image too large for Java array");
        short[] out = new short[(int) sampleCountLong];
        int reducedPrecision = f.precision - s.pointTransform;
        int initialPredictor = 1 << (reducedPrecision - 1);
        int maxReduced = (1 << reducedPrecision) - 1;
        BitReader bits = new BitReader(data, entropyStart);
        long mcu = 0;
        int expectedRestart = 0;
        boolean restartReset = false;

        for (int y = 0; y < f.height; y++) {
            for (int x = 0; x < f.width; x++) {
                if (restartInterval > 0 && mcu > 0 && mcu % restartInterval == 0) {
                    int marker = bits.consumeRestartMarker();
                    int wanted = 0xd0 + (expectedRestart & 7);
                    if (marker != wanted) throw new IOException(String.format("expected restart FF%02X, got FF%02X", wanted, marker));
                    expectedRestart++;
                    restartReset = true;
                }
                for (int c = 0; c < f.components; c++) {
                    HuffmanTable table = dcTables[s.dcTableIds[c]];
                    int category = table.decode(bits);
                    if (category < 0 || category > 16) throw new IOException("invalid lossless difference category " + category);
                    int diff = receiveExtend(bits, category);
                    int predictor;
                    if (restartReset || (x == 0 && y == 0)) {
                        predictor = initialPredictor;
                    } else if (y == 0) {
                        predictor = reducedAt(out, f, x - 1, y, c, s.pointTransform);
                    } else if (x == 0) {
                        predictor = reducedAt(out, f, x, y - 1, c, s.pointTransform);
                    } else {
                        int ra = reducedAt(out, f, x - 1, y, c, s.pointTransform);
                        int rb = reducedAt(out, f, x, y - 1, c, s.pointTransform);
                        int rc = reducedAt(out, f, x - 1, y - 1, c, s.pointTransform);
                        predictor = predictor(s.predictor, ra, rb, rc);
                    }
                    int value = predictor + diff;
                    if (value < 0 || value > maxReduced) throw new IOException("decoded sample outside precision range");
                    int index = ((y * f.width + x) * f.components) + c;
                    out[index] = (short) (value << s.pointTransform);
                }
                restartReset = false;
                mcu++;
            }
        }
        return new DecodedImage(f.width, f.height, f.components, f.precision, s.predictor, s.pointTransform, out);
    }

    private static int reducedAt(short[] out, Frame f, int x, int y, int c, int pt) {
        int index = ((y * f.width + x) * f.components) + c;
        return (out[index] & 0xffff) >> pt;
    }

    private static int predictor(int selection, int ra, int rb, int rc) {
        switch (selection) {
            case 1: return ra;
            case 2: return rb;
            case 3: return rc;
            case 4: return ra + rb - rc;
            case 5: return ra + ((rb - rc) >> 1);
            case 6: return rb + ((ra - rc) >> 1);
            case 7: return (ra + rb) >> 1;
            default: throw new IllegalArgumentException("predictor");
        }
    }

    private static int receiveExtend(BitReader bits, int size) throws IOException {
        if (size == 0) return 0;
        int v = bits.readBits(size);
        int threshold = 1 << (size - 1);
        if (v < threshold) v -= (1 << size) - 1;
        return v;
    }

    private static int u8(byte[] a, int p) { return a[p] & 0xff; }
    private static int u16be(byte[] a, int p) { return (u8(a, p) << 8) | u8(a, p + 1); }
}
