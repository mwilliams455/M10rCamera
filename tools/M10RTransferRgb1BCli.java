package com.m10r.diagnostic;

import java.io.BufferedOutputStream;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.OutputStream;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.Arrays;

/** Host-side RGB1B renderer. Writes all five fixed domain-placement candidates from one upstream path. */
public final class M10RTransferRgb1BCli {
    private M10RTransferRgb1BCli() {}

    public static void main(String[] args) throws Exception {
        if (args.length < 8 || args.length > 9) {
            throw new IllegalArgumentException(
                    "usage: M10RTransferRgb1BCli <dng> <tone_medium> <dg_expanded> " +
                    "<ll_oetf.ppm> <ll_identity.ppm> <le_identity.ppm> <el_oetf.ppm> <ee_identity.ppm> [maxDimension]");
        }
        Path dng = Path.of(args[0]);
        M10RTransferRgb1BRenderer.Assets assets = M10RTransferRgb1BRenderer.Assets.load(
                Path.of(args[1]), Path.of(args[2]));
        int maxDimension = args.length == 9 ? Integer.parseInt(args[8]) : 2000;

        try (FileInputStream in = new FileInputStream(dng.toFile()); FileChannel channel = in.getChannel()) {
            DngMetadataReader.DngInfo info = DngMetadataReader.read(channel);
            DngRawDecoder.RawImage raw = DngRawDecoder.decode(channel);
            M10RTransferRgb1BRenderer.Result result =
                    M10RTransferRgb1BRenderer.render(raw, info, assets, maxDimension);
            writePpm(Path.of(args[3]), result.width, result.height, result.llOetfArgb);
            writePpm(Path.of(args[4]), result.width, result.height, result.llIdentityArgb);
            writePpm(Path.of(args[5]), result.width, result.height, result.leIdentityArgb);
            writePpm(Path.of(args[6]), result.width, result.height, result.elOetfArgb);
            writePpm(Path.of(args[7]), result.width, result.height, result.eeIdentityArgb);

            System.out.println("RGB1B width=" + result.width + " height=" + result.height +
                    " stride=" + result.sourceStride + " maxDimension=" + maxDimension);
            System.out.println("CA9 gains=" + Arrays.toString(result.ca9Gains));
            System.out.println("CA9 neutral clips=" + Arrays.toString(result.neutralClipCounts));
            System.out.println("linear-luma input clips low/high/nonfinite=" +
                    result.linearLumaInputLow + "/" + result.linearLumaInputHigh + "/" + result.linearLumaInputNonFinite);
            System.out.println("linear-luma DG index clips low/high=" +
                    result.linearDgIndexLow + "/" + result.linearDgIndexHigh);
            System.out.println("encoded-luma input clips low/high/nonfinite=" +
                    result.encodedLumaInputLow + "/" + result.encodedLumaInputHigh + "/" + result.encodedLumaInputNonFinite);
            System.out.println("encoded-luma DG index clips low/high=" +
                    result.encodedDgIndexLow + "/" + result.encodedDgIndexHigh);
            System.out.println("RGB1B MODES: LL_OETF, LL_IDENTITY, LE_IDENTITY, EL_OETF, EE_IDENTITY; no fitted terms");
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
