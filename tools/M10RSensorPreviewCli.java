package com.m10r.diagnostic;

import java.io.FileInputStream;
import java.nio.channels.FileChannel;
import java.security.MessageDigest;

/** Host-side validator for the v0.4 sensor-sanity path. */
public final class M10RSensorPreviewCli {
    private M10RSensorPreviewCli() {}

    public static void main(String[] args) throws Exception {
        if (args.length != 1) {
            System.err.println("usage: M10RSensorPreviewCli <m10r.dng>");
            System.exit(2);
        }

        try (FileInputStream in = new FileInputStream(args[0]);
             FileChannel channel = in.getChannel()) {
            DngMetadataReader.DngInfo info = DngMetadataReader.read(channel);
            if (!info.isCfaRaw()) {
                throw new IllegalStateException("selected DNG is not CFA RAW");
            }
            if (!info.isLosslessJpeg()) {
                throw new IllegalStateException("selected DNG is not compression=7 lossless JPEG");
            }

            DngRawDecoder.RawImage raw = DngRawDecoder.decode(channel);
            SensorPreviewCore.PreviewResult preview = SensorPreviewCore.render(raw, info);

            System.out.println(info.summary());
            System.out.println();
            System.out.println(raw.diagnosticSummary());
            System.out.println();
            System.out.println(preview.diagnosticSummary());
            System.out.println("Preview ARGB8 SHA-256 (A,R,G,B byte order): " + shaArgb(preview.argb));
        }
    }

    private static String shaArgb(int[] pixels) throws Exception {
        MessageDigest sha = MessageDigest.getInstance("SHA-256");
        for (int p : pixels) {
            sha.update((byte) (p >>> 24));
            sha.update((byte) (p >>> 16));
            sha.update((byte) (p >>> 8));
            sha.update((byte) p);
        }
        byte[] digest = sha.digest();
        StringBuilder out = new StringBuilder(digest.length * 2);
        for (byte b : digest) out.append(String.format("%02x", b & 0xff));
        return out.toString();
    }
}
