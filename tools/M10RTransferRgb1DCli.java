package com.m10r.diagnostic;
import java.io.*;import java.nio.channels.FileChannel;import java.nio.charset.StandardCharsets;import java.nio.file.Path;
public final class M10RTransferRgb1DCli{
 public static void main(String[] a)throws Exception{if(a.length<8||a.length>9)throw new IllegalArgumentException("usage: <dng> <tone> <dg> <ll> <component_ratio> <oetfy_ratio> <component_target> <oetfy_target> [max]");
  M10RTransferRgb1DRenderer.Assets as=M10RTransferRgb1DRenderer.Assets.load(Path.of(a[1]),Path.of(a[2]));int max=a.length==9?Integer.parseInt(a[8]):2000;
  try(FileInputStream in=new FileInputStream(a[0]);FileChannel ch=in.getChannel()){DngMetadataReader.DngInfo i=DngMetadataReader.read(ch);DngRawDecoder.RawImage raw=DngRawDecoder.decode(ch);M10RTransferRgb1DRenderer.Result r=M10RTransferRgb1DRenderer.render(raw,i,as,max);
   wr(Path.of(a[3]),r.width,r.height,r.llOetf);wr(Path.of(a[4]),r.width,r.height,r.componentCodeRatio);wr(Path.of(a[5]),r.width,r.height,r.oetfYCodeRatio);wr(Path.of(a[6]),r.width,r.height,r.componentLinearTarget);wr(Path.of(a[7]),r.width,r.height,r.oetfYLinearTarget);
   System.out.println("RGB1D "+r.width+"x"+r.height+" stride="+r.stride+" scale=0.94; encoded-input construction x mapped-Y interpretation");}}
 private static void wr(Path p,int w,int h,int[] v)throws Exception{try(OutputStream o=new BufferedOutputStream(new FileOutputStream(p.toFile()))){o.write(("P6\n"+w+" "+h+"\n255\n").getBytes(StandardCharsets.US_ASCII));byte[] row=new byte[w*3];for(int y=0;y<h;y++){int q=0;for(int x=0;x<w;x++){int z=v[y*w+x];row[q++]=(byte)(z>>>16);row[q++]=(byte)(z>>>8);row[q++]=(byte)z;}o.write(row);}}}
}
