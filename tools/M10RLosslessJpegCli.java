package com.m10r.diagnostic;

import java.io.BufferedOutputStream;
import java.io.FileOutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;

/** CI-only command-line harness for pixel-exact SOF3 validation. */
public final class M10RLosslessJpegCli {
    private static String hex(byte[] a) {
        StringBuilder s = new StringBuilder(a.length * 2);
        for (byte b : a) s.append(String.format("%02x", b & 0xff));
        return s.toString();
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 2) throw new IllegalArgumentException("usage: input.jpg output.u16le");
        byte[] jpeg = Files.readAllBytes(Path.of(args[0]));
        LosslessJpegDecoder.DecodedImage image = LosslessJpegDecoder.decode(jpeg);
        MessageDigest sha = MessageDigest.getInstance("SHA-256");
        int min = 0xffff, max = 0;
        long sum = 0;
        try (BufferedOutputStream out = new BufferedOutputStream(new FileOutputStream(args[1]), 1 << 20)) {
            byte[] pair = new byte[2];
            for (short raw : image.samples) {
                int v = raw & 0xffff;
                if (v < min) min = v;
                if (v > max) max = v;
                sum += v;
                pair[0] = (byte) v;
                pair[1] = (byte) (v >>> 8);
                out.write(pair);
                sha.update(pair);
            }
        }
        System.out.println("jpeg_width=" + image.width);
        System.out.println("jpeg_height=" + image.height);
        System.out.println("components=" + image.components);
        System.out.println("full_width=" + image.fullWidth());
        System.out.println("precision=" + image.precision);
        System.out.println("predictor=" + image.predictor);
        System.out.println("point_transform=" + image.pointTransform);
        System.out.println("samples=" + image.samples.length);
        System.out.println("min=" + min);
        System.out.println("max=" + max);
        System.out.println("mean=" + ((double) sum / image.samples.length));
        System.out.println("sha256_le_u16=" + hex(sha.digest()));
        StringBuilder first = new StringBuilder();
        for (int i = 0; i < Math.min(32, image.samples.length); i++) {
            if (i > 0) first.append(',');
            first.append(image.samples[i] & 0xffff);
        }
        System.out.println("first32=[" + first + "]");
    }
}
