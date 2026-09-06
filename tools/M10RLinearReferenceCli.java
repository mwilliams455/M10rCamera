package com.m10r.diagnostic;

import java.io.FileInputStream;
import java.nio.channels.FileChannel;
import java.nio.file.Path;
import java.security.MessageDigest;

/** Host-side real-DNG validator for the canonical RENDER_PARITY1A 2x2 experiment. */
public final class M10RLinearReferenceCli {
    private M10RLinearReferenceCli() {}

    public static void main(String[] args) throws Exception {
        if (args.length != 1) throw new IllegalArgumentException("usage: M10RLinearReferenceCli <m10r.dng>");
        try (FileInputStream in = new FileInputStream(Path.of(args[0]).toFile());
             FileChannel channel = in.getChannel()) {
            DngMetadataReader.DngInfo info = DngMetadataReader.read(channel);
            DngRawDecoder.RawImage raw = DngRawDecoder.decode(channel);
            SensorPreviewCore.PreviewResult sensor = SensorPreviewCore.render(raw, info);
            M10RHighlightFactorialRenderer.Result a = M10RHighlightFactorialRenderer.render(
                    raw, info, M10RHighlightFactorialRenderer.Mode.A_BASELINE);
            M10RHighlightFactorialRenderer.Result b = M10RHighlightFactorialRenderer.render(
                    raw, info, M10RHighlightFactorialRenderer.Mode.B_HEADROOM);
            M10RHighlightFactorialRenderer.Result c = M10RHighlightFactorialRenderer.render(
                    raw, info, M10RHighlightFactorialRenderer.Mode.C_CA9_CLIP);
            M10RHighlightFactorialRenderer.Result d = M10RHighlightFactorialRenderer.render(
                    raw, info, M10RHighlightFactorialRenderer.Mode.D_HEADROOM_CA9);

            System.out.println(info.summary());
            System.out.println(raw.diagnosticSummary());
            System.out.println(sensor.diagnosticSummary());
            System.out.println("Sensor ARGB8 SHA-256 (A,R,G,B byte order): " + argbSha(sensor.argb));
            System.out.println("A — " + a.diagnosticSummary());
            System.out.println("A ARGB8 SHA-256: " + argbSha(a.argb));
            System.out.println("B — " + b.diagnosticSummary());
            System.out.println("B ARGB8 SHA-256: " + argbSha(b.argb));
            System.out.println("C — " + c.diagnosticSummary());
            System.out.println("C ARGB8 SHA-256: " + argbSha(c.argb));
            System.out.println("D — " + d.diagnosticSummary());
            System.out.println("D ARGB8 SHA-256: " + argbSha(d.argb));
        }
    }

    private static String argbSha(int[] pixels) throws Exception {
        MessageDigest sha = MessageDigest.getInstance("SHA-256");
        byte[] p = new byte[4];
        for (int argb : pixels) {
            p[0] = (byte) (argb >>> 24);
            p[1] = (byte) (argb >>> 16);
            p[2] = (byte) (argb >>> 8);
            p[3] = (byte) argb;
            sha.update(p);
        }
        StringBuilder s = new StringBuilder();
        for (byte b : sha.digest()) s.append(String.format("%02x", b & 0xff));
        return s.toString();
    }
}
