package com.m10r.diagnostic;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * REFERENCE_TRANSFER_RGB1D.
 *
 * Freeze RGB1C's supported 0.94 coordinate scale and the EL family (Tone/DG fed by an
 * encoded-like scalar, shared gain applied to linear RGB, final sRGB OETF). Cross two
 * remaining definitions:
 *   encoded-input construction:
 *     COMPONENT_Y = Rec709 Y of individually sRGB-encoded RGB channels
 *     OETF_Y      = sRGB OETF applied once to linear Rec709 Y
 *   mapped-Y interpretation:
 *     CODE_RATIO  = mappedCode/inputCode used directly as the linear-RGB shared gain
 *     LINEAR_TARGET = sRGB EOTF(mappedCode) / original linear Y used as shared gain
 *
 * No parameters are fitted on RGB1D. This is a research renderer only.
 */
public final class M10RTransferRgb1DRenderer {
    private M10RTransferRgb1DRenderer() {}
    static final int INPUT_MAX=0x3fff,TONE_ENTRIES=10240,DG_ENTRIES=32768,DG_OUT_MAX=0x3fff;
    static final double SCALE=0.94;

    public static final class Assets {
        final int[] tone,dg;
        private Assets(int[] t,int[] d){tone=t;dg=d;}
        public static Assets load(Path tp,Path dp)throws IOException{
            byte[] tb=Files.readAllBytes(tp),db=Files.readAllBytes(dp);
            if(tb.length!=TONE_ENTRIES*4||db.length!=DG_ENTRIES*2)throw new IllegalArgumentException("asset length");
            ByteBuffer t=ByteBuffer.wrap(tb).order(ByteOrder.LITTLE_ENDIAN),d=ByteBuffer.wrap(db).order(ByteOrder.LITTLE_ENDIAN);
            int[] ta=new int[TONE_ENTRIES],da=new int[DG_ENTRIES];for(int i=0;i<ta.length;i++)ta[i]=t.getInt();for(int i=0;i<da.length;i++)da[i]=d.getShort()&0xffff;
            return new Assets(ta,da);
        }
    }
    public static final class Result{
        public final int width,height,stride;public final int[] llOetf,componentCodeRatio,oetfYCodeRatio,componentLinearTarget,oetfYLinearTarget;
        public final int[] ca9Gains;public final long[] neutralClips;
        Result(int w,int h,int s,int[] ll,int[] a,int[] b,int[] c,int[] d,int[] g,long[] n){width=w;height=h;stride=s;llOetf=ll;componentCodeRatio=a;oetfYCodeRatio=b;componentLinearTarget=c;oetfYLinearTarget=d;ca9Gains=g;neutralClips=n;}
    }
    public static Result render(DngRawDecoder.RawImage raw,DngMetadataReader.DngInfo info,Assets assets,int maxDimension){
        M10RReferenceColorCore.CalibrationTemperatures ts=M10RReferenceColorCore.referenceTemperaturesForIlluminants(info.calibrationIlluminant1,info.calibrationIlluminant2);
        M10RReferenceColorCore.WhiteSolution white=M10RReferenceColorCore.solveNeutralToXy(info.asShotNeutral,info.colorMatrix1,info.colorMatrix2,ts.t1,ts.t2);
        int[] gains=M10RColorSpecCore.recoverCa9Gains(info.asShotNeutral);SensorPreviewCore.CfaPattern cfa=SensorPreviewCore.CfaPattern.fromDng(info.cfaRepeatPatternDim,info.cfaPattern);
        int stride=Math.max(1,ceilDiv(Math.max(raw.width,raw.height),maxDimension)),w=ceilDiv(raw.width,stride),h=ceilDiv(raw.height,stride),n=w*h;
        int[] ll=new int[n],cr=new int[n],or=new int[n],ct=new int[n],ot=new int[n];long[] clips=new long[3];
        for(int oy=0;oy<h;oy++){int sy=Math.min(oy*stride,raw.height-1);for(int ox=0;ox<w;ox++){int sx=Math.min(ox*stride,raw.width-1);
            double[] cam={interp(raw.samples,raw.width,raw.height,sx,sy,SensorPreviewCore.Channel.R,cfa,info.blackLevel,info.whiteLevel),interp(raw.samples,raw.width,raw.height,sx,sy,SensorPreviewCore.Channel.G,cfa,info.blackLevel,info.whiteLevel),interp(raw.samples,raw.width,raw.height,sx,sy,SensorPreviewCore.Channel.B,cfa,info.blackLevel,info.whiteLevel)};
            for(int c=0;c<3;c++)if(cam[c]*gains[c]/M10RColorSpecCore.ASN_SCALE>1)clips[c]++;
            double[] guarded=M10RNeutralClipReferenceRenderer.applyCa9NeutralSaturation(cam,gains),lin=M10RColorSpecCore.matVecMul(white.cameraToSrgbLinear,guarded);
            double yLin=luma(lin);double mappedLin=map(yLin,1.0,assets),gLin=yLin>1e-12?mappedLin/yLin:0;
            int i=oy*w+ox;ll[i]=argb(lin,gLin);
            double compY=.2126*oetf(lin[0])+.7152*oetf(lin[1])+.0722*oetf(lin[2]);double scalarY=oetf(yLin);
            double mc=map(compY,SCALE,assets),ms=map(scalarY,SCALE,assets);
            double gc=compY>1e-12?mc/compY:0,gs=scalarY>1e-12?ms/scalarY:0;
            cr[i]=argb(lin,gc);or[i]=argb(lin,gs);
            double targetC=eotf(mc),targetS=eotf(ms);double gct=yLin>1e-12?targetC/yLin:0,gst=yLin>1e-12?targetS/yLin:0;
            ct[i]=argb(lin,gct);ot[i]=argb(lin,gst);
        }}return new Result(w,h,stride,ll,cr,or,ct,ot,gains,clips);
    }
    private static double map(double y,double scale,Assets a){if(!Double.isFinite(y)||y<=0)y=0;double q=y*INPUT_MAX*scale;int x=q>=INPUT_MAX?INPUT_MAX:clamp((int)Math.round(q),0,INPUT_MAX);int m=medium(x,a.tone);return a.dg[clamp(m,0,a.dg.length-1)]/(double)DG_OUT_MAX;}
    static int medium(int x,int[] t){int xx=clamp(x,0,t.length*2-1);return(int)(((long)xx*t[xx>>1])>>15);}
    private static double oetf(double x){x=clamp01(x);return x<=.0031308?12.92*x:1.055*Math.pow(x,1.0/2.4)-.055;}
    private static double eotf(double x){x=clamp01(x);return x<=.04045?x/12.92:Math.pow((x+.055)/1.055,2.4);}
    private static double luma(double[] x){return .2126*x[0]+.7152*x[1]+.0722*x[2];}
    private static int argb(double[] l,double g){return 0xff000000|(SensorPreviewCore.toSrgb8(l[0]*g)<<16)|(SensorPreviewCore.toSrgb8(l[1]*g)<<8)|SensorPreviewCore.toSrgb8(l[2]*g);}
    private static double interp(short[] s,int w,int h,int x,int y,SensorPreviewCore.Channel want,SensorPreviewCore.CfaPattern c,double[] b,double[] wh){if(c.channelAt(x,y)==want)return SensorPreviewCore.normalized(s[y*w+x]&0xffff,x,y,b,wh);double sum=0;int n=0;for(int dy=-1;dy<=1;dy++){int yy=y+dy;if(yy<0||yy>=h)continue;for(int dx=-1;dx<=1;dx++){int xx=x+dx;if(xx<0||xx>=w||(dx==0&&dy==0)||c.channelAt(xx,yy)!=want)continue;sum+=SensorPreviewCore.normalized(s[yy*w+xx]&0xffff,xx,yy,b,wh);n++;}}if(n==0)throw new IllegalStateException();return sum/n;}
    private static int clamp(int v,int l,int h){return v<l?l:(v>h?h:v);}private static double clamp01(double x){return x<=0?0:(x>=1?1:x);}private static int ceilDiv(int a,int b){return(a+b-1)/b;}
}
