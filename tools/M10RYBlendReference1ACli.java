package com.m10r.diagnostic;

import java.io.*;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.Arrays;

public final class M10RYBlendReference1ACli {
    private M10RYBlendReference1ACli(){}

    public static void main(String[] args)throws Exception{
        if(args.length<4||args.length>5)throw new IllegalArgumentException(
                "usage: M10RYBlendReference1ACli <dng> <tone> <dg> <outDir> [maxDimension]");
        int max=args.length==5?Integer.parseInt(args[4]):1000;
        Path out=Path.of(args[3]);Files.createDirectories(out);
        M10RYBlendReference1ARenderer.Assets assets=
                M10RYBlendReference1ARenderer.Assets.load(Path.of(args[1]),Path.of(args[2]));
        try(FileInputStream in=new FileInputStream(Path.of(args[0]).toFile());FileChannel ch=in.getChannel()){
            DngMetadataReader.DngInfo info=DngMetadataReader.read(ch);
            DngRawDecoder.RawImage raw=DngRawDecoder.decode(ch);
            M10RYBlendReference1ARenderer.Result r=
                    M10RYBlendReference1ARenderer.render(raw,info,assets,max);
            for(int i=0;i<M10RYBlendReference1ARenderer.K_VALUES.length;i++){
                int code=(int)Math.round(M10RYBlendReference1ARenderer.K_VALUES[i]*100.0);
                write(out.resolve(String.format("k_%03d.ppm",code)),r.width,r.height,r.argb[i]);
            }
            System.out.println("YBLEND_REFERENCE1A width="+r.width+" height="+r.height+" stride="+r.stride);
            System.out.println("CA9 gains="+Arrays.toString(r.ca9Gains));
            System.out.println("neutral clips="+Arrays.toString(r.neutralClips));
            System.out.println("k values="+Arrays.toString(M10RYBlendReference1ARenderer.K_VALUES));
        }
    }

    private static void write(Path p,int w,int h,int[] argb)throws Exception{
        try(OutputStream out=new BufferedOutputStream(new FileOutputStream(p.toFile()))){
            out.write(("P6\n"+w+" "+h+"\n255\n").getBytes(StandardCharsets.US_ASCII));
            byte[] row=new byte[Math.multiplyExact(w,3)];
            for(int y=0;y<h;y++){int q=0;for(int x=0;x<w;x++){
                int v=argb[y*w+x];row[q++]=(byte)(v>>>16);row[q++]=(byte)(v>>>8);row[q++]=(byte)v;
            }out.write(row);}
        }
    }
}
