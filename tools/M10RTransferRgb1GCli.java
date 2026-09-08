package com.m10r.diagnostic;
import java.io.*;import java.nio.channels.FileChannel;import java.nio.charset.StandardCharsets;import java.nio.file.Path;
public final class M10RTransferRgb1GCli{
 public static void main(String[] a)throws Exception{
  if(a.length<6||a.length>7)throw new IllegalArgumentException("usage: <dng> <tone> <dg> <control> <fw_shared> <fw_yc_preserve> [max]");
  M10RTransferRgb1GRenderer.Assets as=M10RTransferRgb1GRenderer.Assets.load(Path.of(a[1]),Path.of(a[2]));int max=a.length==7?Integer.parseInt(a[6]):2000;
  try(FileInputStream in=new FileInputStream(a[0]);FileChannel ch=in.getChannel()){
   DngMetadataReader.DngInfo i=DngMetadataReader.read(ch);DngRawDecoder.RawImage raw=DngRawDecoder.decode(ch);M10RTransferRgb1GRenderer.Result r=M10RTransferRgb1GRenderer.render(raw,i,as,max);
   wr(Path.of(a[3]),r.width,r.height,r.rec709SharedLinear);wr(Path.of(a[4]),r.width,r.height,r.fwComponentSharedLinear);wr(Path.of(a[5]),r.width,r.height,r.fwYcPreserveChroma);
   System.out.println("RGB1G "+r.width+"x"+r.height+" stride="+r.stride+" scale=0.94; exact FW YC matrix; Y-only MEDIUM->DG; Cb/Cr preserve candidate");
  }
 }
 private static void wr(Path p,int w,int h,int[] v)throws Exception{try(OutputStream o=new BufferedOutputStream(new FileOutputStream(p.toFile()))){o.write(("P6\n"+w+" "+h+"\n255\n").getBytes(StandardCharsets.US_ASCII));byte[] row=new byte[w*3];for(int y=0;y<h;y++){int q=0;for(int x=0;x<w;x++){int z=v[y*w+x];row[q++]=(byte)(z>>>16);row[q++]=(byte)(z>>>8);row[q++]=(byte)z;}o.write(row);}}}
}
