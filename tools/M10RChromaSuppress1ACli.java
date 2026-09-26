package com.m10r.diagnostic;

import java.io.*;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;

/** CLI for the CHROMASUPPRESS1A offline reference screen. */
public final class M10RChromaSuppress1ACli {
    public static void main(String[] a)throws Exception{
        if(a.length<4||a.length>5)
            throw new IllegalArgumentException("usage: <dng> <tone> <dg> <out_prefix> [max]");
        M10RChromaSuppress1ARenderer.Assets as=
            M10RChromaSuppress1ARenderer.Assets.load(Path.of(a[1]),Path.of(a[2]));
        int max=a.length==5?Integer.parseInt(a[4]):2000;
        try(FileInputStream in=new FileInputStream(a[0]);FileChannel ch=in.getChannel()){
            DngMetadataReader.DngInfo info=DngMetadataReader.read(ch);
            DngRawDecoder.RawImage raw=DngRawDecoder.decode(ch);
            M10RChromaSuppress1ARenderer.Result r=
                M10RChromaSuppress1ARenderer.render(raw,info,as,max);
            for(int i=0;i<M10RChromaSuppress1ARenderer.MODE_NAMES.length;i++){
                wr(Path.of(a[3]+"_"+M10RChromaSuppress1ARenderer.MODE_NAMES[i]+".ppm"),
                   r.width,r.height,r.modes[i]);
            }
            StringBuilder s=new StringBuilder();
            s.append("CHROMASUPPRESS1A ").append(r.width).append("x").append(r.height)
             .append(" stride=").append(r.stride)
             .append(" csumScale=").append(M10RChromaSuppress1ARenderer.CHROMA_CODE_SCALE);
            for(int i=0;i<r.suppressedPixelCounts.length;i++){
                s.append(" ").append(M10RChromaSuppress1ARenderer.MODE_NAMES[i+1])
                 .append("{suppressed=").append(r.suppressedPixelCounts[i])
                 .append(",meanGain=").append(String.format(java.util.Locale.ROOT,"%.8f",r.meanAppliedGains[i]))
                 .append("}");
            }
            System.out.println(s);
        }
    }

    private static void wr(Path p,int w,int h,int[] v)throws Exception{
        try(OutputStream o=new BufferedOutputStream(new FileOutputStream(p.toFile()))){
            o.write(("P6\n"+w+" "+h+"\n255\n").getBytes(StandardCharsets.US_ASCII));
            byte[] row=new byte[w*3];
            for(int y=0;y<h;y++){
                int q=0;
                for(int x=0;x<w;x++){
                    int z=v[y*w+x];
                    row[q++]=(byte)(z>>>16);
                    row[q++]=(byte)(z>>>8);
                    row[q++]=(byte)z;
                }
                o.write(row);
            }
        }
    }
}
