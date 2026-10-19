package com.particlesdevs.photoncamera.m10r;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;

/**
 * Portable fresh-state translation of the recovered CA9 A688 selector and 7B08 gain converter.
 *
 * <p>The caller supplies the complete packet, configuration and classification table. This
 * class defines no sensor adaptation, calibration defaults, illuminant names, exposure policy
 * or retained-state policy. Its input tuples are unsigned 32-bit words; they are not assumed
 * to have the semantics of Android sample counts or channel sums. All work and cell state is
 * freshly zeroed on each call. No caller-owned input is modified.</p>
 *
 * <p>Integer operations deliberately retain 32-bit wrap, signed 16-bit narrowing, unsigned
 * division and per-term truncation from the recovered stage models. Java float expressions
 * preserve each binary32 rounding point in the post-class penalties; the 0.9 multiplier is
 * deliberately binary64. These details are part of the numerical contract.</p>
 *
 * <p>Reference chain: full_selector_oracle3r.composed_model and its frozen coordinate, prior,
 * aggregation, control, postclass, final-coordinate and gain-conversion models. Complete
 * intermediate snapshots have the same labels and byte layouts as the original-instruction
 * 3R/3X fixtures. Successful arithmetic validation does not validate a phone-to-Leica adapter.</p>
 */
public final class M10RWbSelector3Y {
    public static final String REVISION = "M10R_WB_SELECTOR3Y";
    public static final int PACKET_BYTES = 0x5C;
    public static final int CONFIGURATION_BYTES = 0x310;
    public static final int TABLE_BYTES = 40000;
    public static final int WORK_BYTES = 0x284;
    public static final int MAX_CELLS = 352;

    private static final long UINT32_MASK = 0xFFFFFFFFL;
    private static final int[] PRIOR_CLASSES = {2, 3, 5, 6, 8, 12, 10, 9};
    private static final int[] PRIOR_DESTINATIONS = {0xA, 0xC, 0x10, 0x12, 0x16, 0x1C, 0x1A, 0x18};
    private static final int[] PRIOR_FIELDS = {0xBC, 0xDC, 0xFC, 0x11C, 0x13C, 0x15C, 0x17C, 0x19C};
    private static final int[] PERCENTAGE_WEIGHT_OFFSETS = {
            0x1E, 0x20, 0x22, 0x24, 0x26, 0x28, 0x2A, 0x2C,
            0x2E, 0x32, 0x34, 0x36, 0x38, 0x3A, 0x3C
    };
    private static final int[] INCLUDED_CLASSES = {2, 3, 5, 6, 8, 11, 12, 13, 14, 15, 16, 10, 9};
    private static final int[][] UPPER_PENALTIES = {
            {0x4A, 0x16, 0x2A, 0x68}, {0x4C, 0x18, 0x2C, 0x6A},
            {0x4E, 0x1A, 0x2E, 0x6C}, {0x50, 0x1C, 0x32, 0x6E},
            {0x52, 0x1C, 0x34, 0x70}, {0x54, 0x1C, 0x36, 0x72},
            {0x56, 0x1C, 0x38, 0x74}, {0x58, 0x1C, 0x3A, 0x76},
            {0x5A, 0x1C, 0x3C, 0x78}
    };
    private static final int[][] FINAL_WEIGHTS = {
            {0x7A, 0x0A, 0x1E, 0x3E, 0x5C}, {0x7C, 0x0C, 0x20, 0x40, 0x5E},
            {0x80, 0x10, 0x24, 0x44, 0x62}, {0x86, 0x16, 0x2A, 0x4A, 0x68},
            {0x88, 0x18, 0x2C, 0x4C, 0x6A}, {0x8A, 0x1A, 0x2E, 0x4E, 0x6C},
            {0x8C, 0x1C, 0x32, 0x50, 0x6E}, {0x8E, 0x1C, 0x34, 0x52, 0x70},
            {0x90, 0x1C, 0x36, 0x54, 0x72}, {0x92, 0x1C, 0x38, 0x56, 0x74},
            {0x94, 0x1C, 0x3A, 0x58, 0x76}, {0x96, 0x1C, 0x3C, 0x5A, 0x78}
    };

    private M10RWbSelector3Y() { }

    /** Numerical result and independent byte snapshots; no result field aliases an input. */
    public static final class Result {
        public final LinkedHashMap<String, byte[]> cellStages;
        public final LinkedHashMap<String, byte[]> workStages;
        public final int gateAcceptedCells;
        public final int[] selectedCoordinates;
        public final int[] selectedGainsRgb;
        public final int[] gainDenominators;
        public final int[][] cells;
        public final int[] tableReads;
        /** Aggregation buckets 1..16; tags other than 2..16 or 20 enter bucket 1. */
        public final int[] classCounts16;
        public final String selectionRoute;
        /** Reciprocal selected gains in the supplied calibration basis, or null if invalid. */
        public final double[] selectedTargetNeutral;

        private Result(LinkedHashMap<String, byte[]> cellStages,
                       LinkedHashMap<String, byte[]> workStages,
                       int accepted, int[][] cells, List<Integer> tableReads,
                       int[] classCounts, String selectionRoute, byte[] work) {
            this.cellStages = cellStages;
            this.workStages = workStages;
            this.gateAcceptedCells = accepted;
            this.cells = cells;
            this.classCounts16 = classCounts;
            this.selectionRoute = selectionRoute;
            this.tableReads = new int[tableReads.size()];
            for (int n = 0; n < this.tableReads.length; n++) {
                this.tableReads[n] = tableReads.get(n);
            }
            this.selectedCoordinates = new int[] {h(work, 0), h(work, 2)};
            this.selectedGainsRgb = new int[] {i(work, 0x274), i(work, 0x278), i(work, 0x27C)};
            this.gainDenominators = new int[] {i(work, 0x268), i(work, 0x26C)};
            this.selectedTargetNeutral = selectedGainsRgb[0] > 0 && selectedGainsRgb[2] > 0
                    ? new double[] {256.0 / selectedGainsRgb[0], 1.0, 256.0 / selectedGainsRgb[2]}
                    : null;
        }
    }

    /**
     * Evaluate fresh-state selector plus gain conversion with explicit recovered-format inputs.
     *
     * @param records rows of [D, R numerator, G numerator, B numerator], each 0..0xFFFFFFFF
     * @param packet exact 0x5C-byte header with its cell count/rows/columns and controls
     * @param configuration exact 0x310-byte configuration in recovered little-endian layout
     * @param classificationTable exact 200 by 200-byte class table in recovered row order
     * @throws IllegalArgumentException for a malformed input or unsupported control interval
     * @throws ArithmeticException for an unguarded zero denominator, as in the reference models
     */
    public static Result evaluate(long[][] records, byte[] packet, byte[] configuration,
                                  byte[] classificationTable) {
        requireLength(packet, PACKET_BYTES, "packet");
        requireLength(configuration, CONFIGURATION_BYTES, "configuration");
        requireLength(classificationTable, TABLE_BYTES, "classificationTable");
        if (records == null || records.length > MAX_CELLS || u(packet, 0) != records.length
                || u(packet, 8) > 22 || (long) u(packet, 4) * u(packet, 8) != records.length) {
            throw new IllegalArgumentException("Cell count and packet dimensions must agree within 352 cells / 22 columns");
        }
        for (long[] record : records) {
            if (record == null || record.length != 4) {
                throw new IllegalArgumentException("Each record must contain four unsigned32 words");
            }
            for (long value : record) {
                if (value < 0 || value > UINT32_MASK) {
                    throw new IllegalArgumentException("Record word outside unsigned32 range");
                }
            }
        }

        LinkedHashMap<String, byte[]> cellStages = new LinkedHashMap<>();
        LinkedHashMap<String, byte[]> workStages = new LinkedHashMap<>();
        int[][] cells = new int[records.length][7];
        int black = h(packet, 0x42);
        int gateOffset = i(packet, 0x14) == 2 ? 0x2FA : 0x2FE;
        int low = u(configuration, gateOffset);
        int high = u(configuration, gateOffset + 2);
        int accepted = 0;
        for (int index = 0; index < records.length; index++) {
            long[] record = records[index];
            int[] cell = cells[index];
            if (record[0] != 0) {
                cell[0] = (short) (record[1] / record[0]);
                cell[1] = (short) (record[2] / record[0]);
                cell[2] = cell[1];
                cell[3] = (short) (record[3] / record[0]);
            }
            boolean admitted = true;
            for (int channel = 0; channel < 4; channel++) {
                cell[channel] = Math.max(1, cell[channel] - black);
                admitted &= low <= cell[channel] && cell[channel] <= high;
            }
            cell[6] = admitted ? 0 : 20;
            if (admitted) accepted++;
        }
        cellStages.put("after_gate", recordsBytes(cells));

        int[] anchors = new int[8];
        int[] axes = new int[4];
        for (int n = 0; n < anchors.length; n++) anchors[n] = u(packet, 0x4C + 2 * n);
        for (int n = 0; n < axes.length; n++) axes[n] = h(configuration, 2 * n);
        coordinates(anchors, axes, cells);
        cellStages.put("after_coordinates", recordsBytes(cells));
        List<Integer> tableReads = new ArrayList<>();
        for (int[] cell : cells) {
            if (cell[6] != 0) continue;
            int x = (short) cell[4] / 5;
            int y = (short) cell[5] / 5;
            if (x >= 0 && x < 200 && y >= 0 && y < 200) {
                int index = 200 * y + x;
                tableReads.add(index);
                cell[6] = classificationTable[index] & 0xFF;
            } else {
                cell[6] = 1;
            }
        }
        cellStages.put("after_classification", recordsBytes(cells));

        byte[] work = new byte[WORK_BYTES];
        int scalar = h(packet, 0x36);
        for (int n = 0; n < PRIOR_CLASSES.length; n++) {
            put16(work, PRIOR_DESTINATIONS[n], prior(configuration, scalar, PRIOR_CLASSES[n]));
        }
        snapshot(workStages, "after_priors", work);
        int[] counts = aggregate(cells, configuration, work, workStages);
        control(packet, configuration, work);
        snapshot(workStages, "after_93a8", work);
        penalties(work);
        snapshot(workStages, "after_8c90", work);
        finalWeights(work);
        snapshot(workStages, "after_8930", work);
        String selectionRoute = mix(configuration, work);
        snapshot(workStages, "after_8738", work);
        tail(packet, configuration, work);
        snapshot(workStages, "after_a688", work);
        gains(anchors, axes, work);
        snapshot(workStages, "after_7b08", work);
        return new Result(cellStages, workStages, accepted, cells, tableReads, counts, selectionRoute, work);
    }

    private static int[][] anchorRatios(int[] anchors) {
        int greenA = anchors[1] + anchors[2];
        int greenB = anchors[5] + anchors[6];
        return new int[][] {
                {greenA == 0 ? 0 : (anchors[3] << 13) / greenA,
                 greenB == 0 ? 0 : (anchors[7] << 13) / greenB},
                {greenA == 0 ? 0 : (anchors[0] << 13) / greenA,
                 greenB == 0 ? 0 : (anchors[4] << 13) / greenB}
        };
    }

    private static void coordinates(int[] anchors, int[] axes, int[][] cells) {
        int[][] ratios = anchorRatios(anchors);
        int[] slopes = new int[2];
        for (int axis = 0; axis < 2; axis++) {
            int difference = ratios[axis][0] - ratios[axis][1];
            slopes[axis] = difference == 0 ? 0
                    : ((axes[2 * axis] - axes[2 * axis + 1]) << 12) / difference;
        }
        for (int[] cell : cells) {
            int greenSum = cell[1] + cell[2];
            int divisor = greenSum > 0 ? greenSum : 10;
            for (int axis = 0; axis < 2; axis++) {
                int ratio = (cell[axis == 0 ? 0 : 3] << 13) / divisor;
                int product = (ratio - ratios[axis][1]) * slopes[axis];
                cell[4 + axis] = axes[2 * axis + 1] + (product >> 12);
            }
        }
    }

    private static int priorIndex(int classId) {
        switch (classId) {
            case 3: return 1;
            case 5: return 2;
            case 6: return 3;
            case 8: return 4;
            case 9: return 7;
            case 10: return 6;
            case 11: case 12: case 13: case 14: case 15: case 16: return 5;
            default: return 0;
        }
    }

    private static int prior(byte[] config, int scalar, int classId) {
        int bank = 4 * priorIndex(classId);
        int[] fields = new int[8];
        for (int n = 0; n < fields.length; n++) fields[n] = i(config, PRIOR_FIELDS[n] + bank);
        int amplitude = fields[0], low = fields[1], rise = fields[2], fall = fields[3];
        int high = fields[4], low2 = fields[5], high2 = fields[6], amplitude2 = fields[7];
        int value;
        if (scalar <= low) value = 0;
        else if (scalar < rise) value = ((scalar - low) * amplitude) / (rise - low);
        else if (scalar <= fall) value = amplitude;
        else if (scalar <= high) value = (fall - scalar) * (amplitude / (high - fall)) + amplitude;
        else if (scalar <= low2) value = 0;
        else if (scalar > high2) value = amplitude2;
        else value = ((scalar - low2) * amplitude2) / (high2 - low2);
        return (short) (value >>> 8);
    }

    private static int blend(int tag, int mean, int defaultValue) {
        switch (tag) {
            case 1: return mean;
            case 5: case 6: case 9: return defaultValue;
            case 2: return (2 * mean + defaultValue) / 3;
            case 3: return (2 * mean + 3 * defaultValue) / 5;
            case 11: return (mean + 3 * defaultValue) / 4;
            default: return (mean + defaultValue) / 2;
        }
    }

    private static int percentageWeight(int percent, byte[] config) {
        int upper = h(config, 8), pivot = h(config, 10), knee = h(config, 12);
        if (upper <= pivot) return 0;
        int value;
        if (percent <= knee) value = (pivot * percent) / knee;
        else if (percent > 100) return 0;
        else {
            int slope = ((upper - pivot) << 8) / (100 - knee);
            value = pivot + ((slope * (percent - knee)) >>> 8);
        }
        return Math.max(0, (short) value);
    }

    private static int[] aggregate(int[][] cells, byte[] config, byte[] work,
                                   LinkedHashMap<String, byte[]> stages) {
        int[] xSums = new int[16], ySums = new int[16], counts = new int[16];
        for (int[] cell : cells) {
            int tag = cell[6];
            if (tag == 20) continue;
            int bucket = tag >= 2 && tag <= 16 ? tag - 1 : 0;
            xSums[bucket] += cell[4];
            ySums[bucket] += cell[5];
            counts[bucket]++;
        }
        int total = 0;
        for (int bucket = 0; bucket < 16; bucket++) {
            int count = counts[bucket];
            total += count;
            int dx = i(config, 0x20 + 4 * bucket), dy = i(config, 0x70 + 4 * bucket);
            int meanX = count > 9 ? xSums[bucket] / count : dx;
            int meanY = count > 9 ? ySums[bucket] / count : dy;
            put32(work, 0x9C + 4 * bucket, meanX);
            put32(work, 0xEC + 4 * bucket, meanY);
            put32(work, 0x13C + 4 * bucket, blend(bucket + 1, meanX, dx));
            put32(work, 0x18C + 4 * bucket, blend(bucket + 1, meanY, dy));
            put32(work, 0x1DC + 4 * bucket, count);
        }
        snapshot(stages, "after_9750", work);
        put32(work, 0x228, total);
        int[] percentages = new int[16];
        for (int bucket = 0; bucket < 16; bucket++) {
            percentages[bucket] = total == 0 ? 0 : (100 * counts[bucket]) / total;
            put16(work, 0x22E + 2 * bucket, percentages[bucket]);
        }
        snapshot(stages, "after_9678", work);
        int upperClassSum = 0;
        for (int n = 0; n < PERCENTAGE_WEIGHT_OFFSETS.length; n++) {
            int tag = n + 2;
            int value = percentageWeight(percentages[tag - 1], config);
            if (tag == 5 || tag == 6) value *= 2;
            put16(work, PERCENTAGE_WEIGHT_OFFSETS[n], value);
            if (n >= 9) upperClassSum += value & 0xFFFF;
        }
        put16(work, 0x30, upperClassSum);
        snapshot(stages, "after_9540", work);
        return counts;
    }

    private static void control(byte[] packet, byte[] config, byte[] work) {
        int delta = (short) (u(packet, 0x36) - u(packet, 0x34));
        int a = h(config, 0xE), b = h(config, 0x10), c = h(config, 0x12), d = h(config, 0x14);
        int right = h(config, 0x16), left = h(config, 0x18);
        if (!(a < b && b <= c && c < d)) {
            throw new IllegalArgumentException("Control intervals must satisfy a < b <= c < d, as in the validated reference domain");
        }
        int value;
        if (delta <= a) value = left;
        else if (delta < b) value = left + ((a - delta) * left) / (b - a);
        else if (delta <= c) value = 0;
        else if (delta >= d) value = right;
        else value = ((delta - c) * right) / (d - c);
        value = (short) value;
        int p36 = h(packet, 0x36);
        if (p36 < -80) value = 0;
        else if (p36 < 0) value = (short) (((p36 + 80) / 80) * (value & 0xFFFF));
        put16(work, 8, value);
        for (int offset = 0x6E; offset < 0x7A; offset += 2) {
            if (value < 0 && offset == 0x74) continue;
            put16(work, offset, value < 0 ? value : 0);
        }
        put16(work, 0x66, 0);
        int adjustment = -value / 25;
        put16(work, 0x5C, adjustment);
        put16(work, 0x5E, adjustment);
    }

    private static void penalties(byte[] work) {
        int total = h(work, 0x230) + h(work, 0x232) + h(work, 0x234) + h(work, 0x236);
        for (int offset = 0x3E; offset < 0x5C; offset += 2) put16(work, offset, 0);
        if (total > 10) {
            if (h(work, 0x10) < 0) put16(work, 0x44, h(work, 0x10));
        } else {
            float factor = 1.0f - (float) total / 10.0f;
            put16(work, 0x44, (int) (factor * (float) -(h(work, 0x10) + h(work, 0x62))));
            float product3 = factor * (float) -(h(work, 0xC) + h(work, 0x5E));
            float product2 = factor * (float) -(h(work, 0xA) + h(work, 0x5C));
            put16(work, 0x40, (int) ((double) product3 * 0.9));
            put16(work, 0x3E, (int) ((double) product2 * 0.9));
        }
        if (total > 30) {
            for (int[] fields : UPPER_PENALTIES) {
                put16(work, fields[0], -(u(work, fields[1]) + u(work, fields[2]) + u(work, fields[3])));
            }
        } else if (total >= 20) {
            float factor = (float) (total - 10) / 20.0f;
            for (int[] fields : UPPER_PENALTIES) {
                int negative = -(h(work, fields[1]) + h(work, fields[2]) + h(work, fields[3]));
                put16(work, fields[0], (int) (factor * (float) negative));
            }
        } else {
            for (int n = 0; n < 3; n++) {
                int percentage = h(work, 0x23C + 2 * n);
                if (percentage < 8) {
                    float factor = 1.0f - (float) percentage * 0.125f;
                    put16(work, 0x4A + 2 * n, (int) ((float) -h(work, 0x16 + 2 * n) * factor));
                }
            }
            for (int n = 0; n < 6; n++) {
                int percentage = h(work, 0x242 + 2 * n);
                if (percentage < 15) {
                    float factor = 1.0f - (float) percentage / 15.0f;
                    put16(work, 0x50 + 2 * n, (int) ((float) -h(work, 0x1C) * factor));
                }
            }
        }
        for (int offset = 0x3E; offset < 0x5C; offset += 2) {
            if (h(work, offset) > 0) put16(work, offset, 0);
        }
    }

    private static void finalWeights(byte[] work) {
        put16(work, 0x82, 0);
        for (int[] fields : FINAL_WEIGHTS) {
            int sum = u(work, fields[1]) + u(work, fields[2]) + u(work, fields[3]) + u(work, fields[4]);
            put16(work, fields[0], Math.max(0, (short) sum));
        }
    }

    private static String mix(byte[] config, byte[] work) {
        int totalWeight = 0;
        for (int tag : INCLUDED_CLASSES) totalWeight += h(work, 0x7A + 2 * (tag - 2));
        if (i(work, 0x228) == 0 || (totalWeight & UINT32_MASK) <= 2) {
            put16(work, 0x254, u(config, 0x24));
            put16(work, 0x256, u(config, 0x74));
            return "configured_fallback";
        }
        for (int axis = 0; axis < 2; axis++) {
            int numerator = 0;
            int base = axis == 0 ? 0x13C : 0x18C;
            for (int tag : INCLUDED_CLASSES) {
                numerator += i(work, base + 4 * (tag - 1)) * h(work, 0x7A + 2 * (tag - 2));
            }
            long quotient = (numerator & UINT32_MASK) / (totalWeight & UINT32_MASK);
            put16(work, 0x254 + 2 * axis, (int) quotient);
        }
        return "unsigned_weighted_mix";
    }

    private static void tail(byte[] packet, byte[] config, byte[] work) {
        int x = h(work, 0x254), y = h(work, 0x256);
        int firstCount = i(work, 0x1DC), total = i(work, 0x228);
        int denominator = firstCount + total;
        int p = firstCount != 0 && denominator != 0 ? (short) ((firstCount * 100) / denominator) : 0;
        int low = h(config, 0x2E4), high = h(config, 0x2E6), strength = h(config, 0x2E2);
        int background;
        if (p < low) background = 0;
        else if (high < p) background = strength;
        else {
            int slope = high == low ? 0 : (strength << 8) / (high - low);
            background = (short) (((p - low) * slope) >> 8);
        }
        put16(work, 0x25C, p);
        put16(work, 0x25E, background);
        int finalX, finalY;
        if ((packet[0x32] & 0xFF) == 1) {
            int delta = (short) (u(packet, 0x3C) + u(packet, 0x3E) - u(packet, 0x3A)
                    + u(packet, 0x40) - u(packet, 0x38));
            int low2 = h(config, 0x1BC), high2 = h(config, 0x1BE), strength2 = h(config, 0x1C0);
            int alpha;
            if (delta < low2) alpha = strength2 / 256;
            else if (high2 < delta) alpha = 0;
            else {
                int slope = high2 == low2 ? 0 : (strength2 << 8) / (high2 - low2);
                alpha = (strength2 - (((delta - low2) * slope) >> 8)) >> 8;
            }
            put16(work, 4, delta);
            put16(work, 6, 100 - alpha);
            finalX = (h(config, 0x1CA) * (100 - alpha) + x * alpha) / 100;
            finalY = (h(config, 0x1DA) * (100 - alpha) + y * alpha) / 100;
        } else {
            finalX = (i(work, 0x13C) * background) / 100 + (x * (100 - background)) / 100;
            finalY = (i(work, 0x18C) * background) / 100 + (y * (100 - background)) / 100;
        }
        put16(work, 0x258, finalX);
        put16(work, 0x25A, finalY);
        put16(work, 0, finalX);
        put16(work, 2, finalY);
    }

    private static void gains(int[] anchors, int[] axes, byte[] work) {
        int[][] ratios = anchorRatios(anchors);
        int[] selectedGains = {0, 256, 0};
        for (int axis = 0; axis < 2; axis++) {
            int c0 = axes[2 * axis], c1 = axes[2 * axis + 1];
            int slope = c0 == c1 ? 0 : ((ratios[axis][0] - ratios[axis][1]) << 2) / (c0 - c1);
            int denominator = ((h(work, 2 * axis) - c1) * slope + (ratios[axis][1] << 2)) >> 6;
            put32(work, 0x268 + 4 * axis, denominator);
            selectedGains[axis == 0 ? 0 : 2] = denominator == 0 ? 0 : Math.min(2000, 65536 / denominator);
        }
        for (int n = 0; n < selectedGains.length; n++) put32(work, 0x274 + 4 * n, selectedGains[n]);
    }

    private static void requireLength(byte[] bytes, int length, String label) {
        if (bytes == null || bytes.length != length) {
            throw new IllegalArgumentException(label + " must contain exactly " + length + " bytes");
        }
    }

    private static int u(byte[] data, int offset) {
        return (data[offset] & 0xFF) | ((data[offset + 1] & 0xFF) << 8);
    }

    private static int h(byte[] data, int offset) {
        return (short) u(data, offset);
    }

    private static int i(byte[] data, int offset) {
        return u(data, offset) | (u(data, offset + 2) << 16);
    }

    private static void put16(byte[] data, int offset, int value) {
        data[offset] = (byte) value;
        data[offset + 1] = (byte) (value >>> 8);
    }

    private static void put32(byte[] data, int offset, int value) {
        put16(data, offset, value);
        put16(data, offset + 2, value >>> 16);
    }

    private static byte[] recordsBytes(int[][] records) {
        byte[] bytes = new byte[records.length * 28];
        for (int index = 0; index < records.length; index++) {
            for (int field = 0; field < 7; field++) put32(bytes, 28 * index + 4 * field, records[index][field]);
        }
        return bytes;
    }

    private static void snapshot(LinkedHashMap<String, byte[]> stages, String label, byte[] work) {
        stages.put(label, work.clone());
    }
}
