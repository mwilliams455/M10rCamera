package com.particlesdevs.photoncamera.m10r;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Objects;

/**
 * Integer B2Y reference for Android/host parity experiments.
 *
 * This is NOT a recovered hardware pixel datapath. Input signal selection,
 * coordinate normalization, stage order, clamps, and rounding remain open.
 * In particular, a tone lookup coordinate need not be the multiplied component.
 * No floating-point normalization, RGB/luma assumption, or OETF is hidden here.
 * All arguments that select unproven behavior are mandatory.
 */
public final class M10RB2YScalarOracle {
    public static final int TONE_COORD_MAX = 20479;
    public static final int DG_COORD_MAX = 32767;
    public static final int LIMIT14 = 16383;
    public static final String TONE_SHA256 =
            "2fd6ca209f290c75aa96976b3d7692e55c41a55c0017a063aba9808da3b41a00";
    public static final String DG_SHA256 =
            "9e65de24d52271be0783f4e2728f20f482c0ba43b63159b75033b4a4fc75457d";

    public enum Rounding { TRUNCATE, HALF_UP, TIES_EVEN }
    public enum Order { TONE_DG, DG_TONE }
    public enum ClampPolicy { NONE, INPUT_14, EACH_STAGE_14, FINAL_14 }

    private final int[] medium;
    private final int[] dg;

    public M10RB2YScalarOracle(byte[] mediumU32LE, byte[] dgU16LE) {
        check(mediumU32LE, 10240 * 4, TONE_SHA256);
        check(dgU16LE, 32768 * 2, DG_SHA256);
        ByteBuffer t = ByteBuffer.wrap(mediumU32LE).order(ByteOrder.LITTLE_ENDIAN);
        ByteBuffer d = ByteBuffer.wrap(dgU16LE).order(ByteOrder.LITTLE_ENDIAN);
        medium = new int[10240];
        dg = new int[32768];
        for (int i = 0; i < medium.length; ++i) medium[i] = t.getInt();
        for (int i = 0; i < dg.length; ++i) dg[i] = d.getShort() & 0xffff;
    }

    /** Q15 candidates for NONNEGATIVE samples only; no implicit saturation. */
    public static int multiplyQ15(int sample, int gain, Rounding rounding) {
        Objects.requireNonNull(rounding, "rounding");
        if (sample < 0 || gain < 0 || gain > 0xffff) {
            throw new IllegalArgumentException("nonnegative sample and u16 Q15 gain required");
        }
        long product = (long) sample * gain;
        long quotient = product >>> 15;
        long remainder = product & 0x7fff;
        if (rounding == Rounding.HALF_UP && remainder >= 0x4000) {
            ++quotient;
        } else if (rounding == Rounding.TIES_EVEN
                && (remainder > 0x4000 || (remainder == 0x4000 && (quotient & 1) != 0))) {
            ++quotient;
        }
        if (quotient > Integer.MAX_VALUE) throw new ArithmeticException("Q15 result exceeds int");
        return (int) quotient;
    }

    /** idx=coordinate>>1 is the existing first-parity model, not proven RTL. */
    public int toneAt(int sample, int coordinate, Rounding rounding) {
        requireCoordinate(coordinate, TONE_COORD_MAX);
        return multiplyQ15(sample, medium[coordinate >>> 1], rounding);
    }

    /** Exact expanded table access. Out-of-domain coordinates fail explicitly. */
    public int dgAt(int coordinate) {
        requireCoordinate(coordinate, DG_COORD_MAX);
        return dg[coordinate];
    }

    /**
     * Candidate *scalar* composition, restricted to the common tone capacity.
     * The same integer serves as coordinate and sample in this explicit model.
     * This function does not imply that tone and DG share a source in hardware.
     */
    public int candidate(int coordinate, Order order, Rounding rounding, ClampPolicy clamps) {
        requireCoordinate(coordinate, TONE_COORD_MAX);
        Objects.requireNonNull(order, "order");
        Objects.requireNonNull(rounding, "rounding");
        Objects.requireNonNull(clamps, "clamps");
        int v = clamps == ClampPolicy.INPUT_14 ? Math.min(coordinate, LIMIT14) : coordinate;
        if (order == Order.TONE_DG) {
            v = toneAt(v, v, rounding);
            if (clamps == ClampPolicy.EACH_STAGE_14) v = Math.min(v, LIMIT14);
            v = dgAt(v);
        } else {
            v = dgAt(v);
            if (clamps == ClampPolicy.EACH_STAGE_14) v = Math.min(v, LIMIT14);
            v = toneAt(v, v, rounding);
        }
        if (clamps == ClampPolicy.EACH_STAGE_14 || clamps == ClampPolicy.FINAL_14) {
            v = Math.min(v, LIMIT14);
        }
        return v;
    }

    private static void requireCoordinate(int coordinate, int max) {
        if (coordinate < 0 || coordinate > max) {
            throw new IllegalArgumentException("coordinate outside explicit table capacity");
        }
    }

    private static void check(byte[] bytes, int size, String expected) {
        Objects.requireNonNull(bytes, "asset");
        if (bytes.length != size) throw new IllegalArgumentException("wrong asset size");
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(bytes);
            StringBuilder hex = new StringBuilder();
            for (byte b : digest) hex.append(String.format(java.util.Locale.ROOT, "%02x", b & 0xff));
            if (!expected.equals(hex.toString())) throw new IllegalArgumentException("asset hash mismatch");
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }
}
