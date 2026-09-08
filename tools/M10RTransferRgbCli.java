package com.m10r.diagnostic;

import java.io.BufferedOutputStream;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.OutputStream;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.Arrays;

/** Host-side RGB1A renderer. Writes transfer-ON and transfer-OFF PPMs from one frozen upstream path. */
public final class M10RTransferRgbCli {
    private M10RTransferRgbCli() {}

    public static void main(String[] args) throws Exception {
        if (args.length < 5 || args.length > 6) {
            throw new IllegalArgumentException(
                    "usage: M10RTransferRgbCli <dng> <tone_medium> <dg_expanded> <on.ppm> <off.ppm> [maxDimension]");
        }
        Path dng = Path.of(args[0]);
        M10RTransferRgbRenderer.Assets assets = M10RTransferRgbRenderer.Assets.load(
                Path.of(args[1]), Path.of(args[2]));
        int maxDimension = args.length == 6 ? Integer.parseInt(args[5]) : 2000;

        try (FileInputStream in = new FileInputStream(dng.toFile()); FileChannel channel = in.getChannel()) {
            DngMetadataReader.DngInfo info = DngMetadataReader.read(channel);
            DngRawDecoder.RawImage raw = DngRawDecoder.decode(channel);
            M10RTransferRgbRenderer.Result result =
                    M10RTransferRgbRenderer.render(raw, info, assets, maxDimension);
            writePpm(Path.of(args[3]), result.width, result.height, result.oetfOnArgb);
            writePpm(Path.of(args[4]), result.width, result.height, result.oetfOffArgb);

            System.out.println("RGB1A width=" + result.width + " height=" + result.height +
                    " stride=" + result.sourceStride + " maxDimension=" + maxDimension);
            System.out.println("CA9 gains=" + Arrays.toString(result.ca9Gains));
            System.out.println("CA9 neutral clips=" + Arrays.toString(result.neutralClipCounts));
            System.out.println("pre-transfer <0=" + Arrays.toString(result.preTransferBelowZero));
            System.out.println("pre-transfer >1=" + Arrays.toString(result.preTransferAboveOne));
            System.out.println("luma input clips low/high=" + result.lumaInputClipLow + "/" + result.lumaInputClipHigh);
            System.out.println("DG index clips low/high=" + result.dgIndexClipLow + "/" + result.dgIndexClipHigh);
            System.out.println("TRANSFER VARIABLE ONLY: ON=standard sRGB OETF; OFF=identity mapping");
        }
    }

    private static void writePpm(Path path, int width, int height, int[] argb) throws Exception {
        try (OutputStream out = new BufferedOutputStream(new FileOutputStream(path.toFile()))) {
            out.write(("P6\n" + width + " " + height + "\n255\n").getBytes(StandardCharsets.US_ASCII));
            byte[] row = new byte[Math.multiplyExact(width, 3)];
            for (int y = 0; y < height; y++) {
                int q = 0;
                for (int x = 0; x < width; x++) {
                    int p = argb[y * width + x];
                    row[q++] = (byte) (p >>> 16);
                    row[q++] = (byte) (p >>> 8);
                    row[q++] = (byte) p;
                }
                out.write(row);
            }
        }
    }
}
