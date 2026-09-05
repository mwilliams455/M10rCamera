package com.m10r.diagnostic;

import java.io.FileInputStream;
import java.nio.channels.FileChannel;

/** CI harness that exercises the same DNG->SOF3 path used by the Android diagnostic. */
public final class M10RDngRawCli {
    public static void main(String[] args) throws Exception {
        if (args.length != 1) throw new IllegalArgumentException("usage: input.dng");
        try (FileInputStream in = new FileInputStream(args[0]); FileChannel ch = in.getChannel()) {
            DngRawDecoder.RawImage raw = DngRawDecoder.decode(ch);
            System.out.println(raw.diagnosticSummary());
        }
    }
}
