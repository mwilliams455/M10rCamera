package com.particlesdevs.photoncamera.m10r;

import java.io.BufferedOutputStream;
import java.nio.file.Files;
import java.nio.file.Paths;

/** Host-only driver; stdout is an ordered stream of little-endian u16 values. */
public final class B2YScalarProbe {
    private static void rejected(Runnable call) {
        try { call.run(); } catch (IllegalArgumentException expected) { return; }
        throw new AssertionError("invalid input accepted");
    }

    private static void put16(BufferedOutputStream out, int value) throws Exception {
        if (value < 0 || value > 65535) throw new AssertionError("not u16");
        out.write(value & 255);
        out.write(value >>> 8);
    }

    public static void main(String[] args) throws Exception {
        byte[] tone = Files.readAllBytes(Paths.get(args[0], "tone_medium_q15.u32le"));
        byte[] dg = Files.readAllBytes(Paths.get(args[0], "dg_expanded_u16le.bin"));
        M10RB2YScalarOracle o = new M10RB2YScalarOracle(tone, dg);
        byte[] corrupt = tone.clone(); corrupt[0] ^= 1;
        rejected(() -> new M10RB2YScalarOracle(corrupt, dg));
        rejected(() -> o.dgAt(-1));
        rejected(() -> o.dgAt(32768));
        rejected(() -> o.toneAt(1, 20480, M10RB2YScalarOracle.Rounding.TRUNCATE));
        rejected(() -> M10RB2YScalarOracle.multiplyQ15(-1, 32768, M10RB2YScalarOracle.Rounding.TRUNCATE));
        BufferedOutputStream out = new BufferedOutputStream(System.out);
        for (int x = 0; x < 32768; ++x) put16(out, o.dgAt(x));
        for (M10RB2YScalarOracle.Rounding r : M10RB2YScalarOracle.Rounding.values()) {
            for (int x = 0; x <= 20479; ++x) put16(out, o.toneAt(x, x, r));
            for (M10RB2YScalarOracle.Order order : M10RB2YScalarOracle.Order.values()) {
                for (M10RB2YScalarOracle.ClampPolicy c : M10RB2YScalarOracle.ClampPolicy.values()) {
                    for (int x = 0; x <= 20479; ++x) put16(out, o.candidate(x, order, r, c));
                }
            }
            // This matters for a shared tone gain acting on separate components.
            for (int sample : new int[] {0, 1, 127, 1024, 16383, 32767}) {
                for (int coordinate : new int[] {0, 1, 4095, 8192, 14710, 20479}) {
                    put16(out, o.toneAt(sample, coordinate, r));
                }
            }
            for (int gain : new int[] {0, 1, 16384, 32768, 65535}) {
                for (int sample : new int[] {0, 1, 2, 3, 16383, 32767}) {
                    put16(out, M10RB2YScalarOracle.multiplyQ15(sample, gain, r));
                }
            }
        }
        out.flush();
    }
}
