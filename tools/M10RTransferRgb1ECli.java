package com.m10r.diagnostic;

import java.io.*;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.Arrays;

/** Host-side RGB1E topology renderer. */
public final class M10RTransferRgb1ECli {
    private M10RTransferRgb1ECli() {}

    public static void main(String[] args) throws Exception {
        if(args.length<8||args.length>9) throw new IllegalArgumentException(
                "usage: M10RTransferRgb1ECli <dng> <tone> <dg> <baseline.ppm> <rec_id.ppm> <rec_oetf.ppm> <fw_id.ppm> <fw_oetf.ppm> [maxDimension]");
        M10RTransferRgb1ERenderer.Assets assets=M10RTransferRgb1ERenderer.Assets.load(Path.of(args[1]),Path.of(args[2]));
        int max=args.length==9?Integer.parseInt(args[8]):2000;
        try(FileInputStream in=new FileInputStream(Path.of(args[0]).toFile());FileChannel ch=in.getChannel()) {
            DngMetadataReader.DngInfo info=DngMetadataReader.read(ch);
            DngRawDecoder.RawImage raw=DngRawDecoder.decode(ch);
            M10RTransferRgb1ERenderer.Result r=M10RTransferRgb1ERenderer.render(raw,info,assets,max);
            write(Path.of(args[3]),r.width,r.height,r.baselineOetfyCodeRatio);
            write(Path.of(args[4]),r.width,r.height,r.rec709ComponentDgIdentity);
            write(Path.of(args[5]),r.width,r.height,r.rec709ComponentDgOetf);
            write(Path.of(args[6]),r.width,r.height,r.fwToneComponentDgIdentity);
            write(Path.of(args[7]),r.width,r.height,r.fwToneComponentDgOetf);
            System.out.println("RGB1E width="+r.width+" height="+r.height+" stride="+r.stride+" maxDimension="+max);
            System.out.println("CA9 gains="+Arrays.toString(r.ca9Gains));
            System.out.println("CA9 neutral clips="+Arrays.toString(r.neutralClips));
            System.out.println("REC709 component-DG index clips="+Arrays.toString(r.rec709DgInputClips));
            System.out.println("FW_TONE component-DG index clips="+Arrays.toString(r.fwToneDgInputClips));
            System.out.println("RGB1E: shared MEDIUM Q15 gain -> component-wise DG; weights REC709 vs 1024/2661/410; output identity vs sRGB OETF");
        }
    }

    private static void write(Path p,int w,int h,int[] argb)throws Exception {
        try(OutputStream out=new BufferedOutputStream(new FileOutputStream(p.toFile()))) {
            out.write(("P6\n"+w+" "+h+"\n255\n").getBytes(StandardCharsets.US_ASCII));
            byte[] row=new byte[Math.multiplyExact(w,3)];
            for(int y=0;y<h;y++) {int q=0;for(int x=0;x<w;x++){int v=argb[y*w+x];row[q++]=(byte)(v>>>16);row[q++]=(byte)(v>>>8);row[q++]=(byte)v;}out.write(row);}
        }
    }
}
