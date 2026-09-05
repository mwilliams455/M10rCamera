package com.m10r.diagnostic;

import java.io.FileInputStream;
import java.nio.channels.FileChannel;
import java.nio.file.Path;
import java.security.MessageDigest;

/** Host-side real-DNG validator for the v0.5.3 2x2 highlight-boundary experiment. */
public final class M10RLinearReferenceCli {
    private M10RLinearReferenceCli() {}

    public static void main(String[] args) throws Exception {
        if (args.length != 1) throw new IllegalArgumentException("usage: M10RLinearReferenceCli <m10r.dng>");
        try (FileInputStream in = new FileInputStream(Path.of(args[0]).toFile());
             FileChannel channel = in.getChannel()) {
            DngMetadataReader.DngInfo info = DngMetadataReader.read(channel);
            DngRawDecoder.RawImage raw = DngRawDecoder.decode(channel);
            SensorPreviewCore.PreviewResult sensor = SensorPreviewCore.render(raw, info);
            M10RLinearReferenceRenderer.Result a = M10RLinearReferenceRenderer.render(raw, info);
            M10RHighlightFactorialRenderer.Result b = M10RHighlightFactorialRenderer.render(
                    raw, info, M10RHighlightFactorialRenderer.Mode.WHITELEVEL_CLAMP_ONLY);
            M10RHighlightFactorialRenderer.Result c = M10RHighlightFactorialRenderer.render(
                    raw, info, M10RHighlightFactorialRenderer.Mode.HEADROOM_NEUTRAL_CLIP_ONLY);
            M10RNeutralClipReferenceRenderer.Result d = M10RNeutralClipReferenceRenderer.render(raw, info);

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
