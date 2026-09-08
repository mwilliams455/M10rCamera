package com.m10r.diagnostic;

import java.io.*;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.Arrays;

/** Host-side RGB1C six-way bright-end boundary renderer. */
public final class M10RTransferRgb1CCli {
    private M10RTransferRgb1CCli() {}
    public static void main(String[] args) throws Exception {
        if(args.length<9||args.length>10) throw new IllegalArgumentException(
                "usage: M10RTransferRgb1CCli <dng> <tone> <dg> <ll_on> <ll_id> <b100> <b094> <x100> <x094> [maxDimension]");
        M10RTransferRgb1CRenderer.Assets assets=M10RTransferRgb1CRenderer.Assets.load(Path.of(args[1]),Path.of(args[2]));
        int maxDimension=args.length==10?Integer.parseInt(args[9]):2000;
        try(FileInputStream in=new FileInputStream(Path.of(args[0]).toFile());FileChannel ch=in.getChannel()){
            DngMetadataReader.DngInfo info=DngMetadataReader.read(ch);DngRawDecoder.RawImage raw=DngRawDecoder.decode(ch);
            M10RTransferRgb1CRenderer.Result r=M10RTransferRgb1CRenderer.render(raw,info,assets,maxDimension);
            write(Path.of(args[3]),r.width,r.height,r.llOetf);write(Path.of(args[4]),r.width,r.height,r.llIdentity);
            write(Path.of(args[5]),r.width,r.height,r.elBounded100);write(Path.of(args[6]),r.width,r.height,r.elBounded094);
            write(Path.of(args[7]),r.width,r.height,r.elExtended100);write(Path.of(args[8]),r.width,r.height,r.elExtended094);
            System.out.println("RGB1C width="+r.width+" height="+r.height+" stride="+r.sourceStride+" maxDimension="+maxDimension);
            System.out.println("CA9 gains="+Arrays.toString(r.ca9Gains));System.out.println("CA9 neutral clips="+Arrays.toString(r.neutralClipCounts));
            System.out.println("RGB1C fixed scale candidates: 1.00 and 0.94; encoded luma bounded vs extended; scale-before-coordinate-clamp");
        }
    }
    private static void write(Path p,int w,int h,int[] argb)throws Exception{
        try(OutputStream out=new BufferedOutputStream(new FileOutputStream(p.toFile()))){
            out.write(("P6\n"+w+" "+h+"\n255\n").getBytes(StandardCharsets.US_ASCII));byte[] row=new byte[w*3];
            for(int y=0;y<h;y++){int q=0;for(int x=0;x<w;x++){int v=argb[y*w+x];row[q++]=(byte)(v>>>16);row[q++]=(byte)(v>>>8);row[q++]=(byte)v;}out.write(row);}
        }
    }
}
