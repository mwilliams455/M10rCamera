package com.m10r.diagnostic;
import java.io.*;import java.nio.channels.FileChannel;import java.nio.charset.StandardCharsets;import java.nio.file.Path;
public final class M10RTransferRgb1FCli{
 public static void main(String[] a)throws Exception{
  if(a.length<6||a.length>7)throw new IllegalArgumentException("usage: <dng> <tone> <dg> <rec709.ppm> <fw601_oetfy.ppm> <fw601_component.ppm> [max]");
  M10RTransferRgb1FRenderer.Assets as=M10RTransferRgb1FRenderer.Assets.load(Path.of(a[1]),Path.of(a[2]));int max=a.length==7?Integer.parseInt(a[6]):2000;
  try(FileInputStream in=new FileInputStream(a[0]);FileChannel ch=in.getChannel()){
   DngMetadataReader.DngInfo i=DngMetadataReader.read(ch);DngRawDecoder.RawImage raw=DngRawDecoder.decode(ch);M10RTransferRgb1FRenderer.Result r=M10RTransferRgb1FRenderer.render(raw,i,as,max);
   wr(Path.of(a[3]),r.width,r.height,r.rec709OetfY);wr(Path.of(a[4]),r.width,r.height,r.fw601OetfY);wr(Path.of(a[5]),r.width,r.height,r.fw601ComponentY);
   System.out.println("RGB1F "+r.width+"x"+r.height+" stride="+r.stride+" scale=0.94; FW Y row=1224/2403/469 Q12; no fit");
  }
 }
 private static void wr(Path p,int w,int h,int[] v)throws Exception{try(OutputStream o=new BufferedOutputStream(new FileOutputStream(p.toFile()))){o.write(("P6\n"+w+" "+h+"\n255\n").getBytes(StandardCharsets.US_ASCII));byte[] row=new byte[w*3];for(int y=0;y<h;y++){int q=0;for(int x=0;x<w;x++){int z=v[y*w+x];row[q++]=(byte)(z>>>16);row[q++]=(byte)(z>>>8);row[q++]=(byte)z;}o.write(row);}}}
}
