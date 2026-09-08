package com.m10r.diagnostic;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * RGB1G — firmware-YC chroma-preservation topology audit.
 *
 * Fixed upstream: CA9 C -> Leica ColorSpec -> linear sRGB.
 * Fixed nonlinear assets: coordinate scale 0.94, exact MEDIUM -> DG.
 *
 * Variants:
 *   CONTROL_REC709_SHARED_LINEAR
 *     RGB1D winner: scalar = OETF(linear Rec709 Y), mapped/scalar shared on
 *     linear RGB, then final sRGB OETF.
 *
 *   FW_COMPONENT_SHARED_LINEAR
 *     RGB1F control for reconstruction isolation: exact firmware Y row applied
 *     to individually encoded RGB, but mapped/input ratio still shared on
 *     linear RGB, then final sRGB OETF.
 *
 *   FW_YC_PRESERVE_CHROMA
 *     Encode linear RGB with standard sRGB OETF, convert encoded RGB with the
 *     exact recovered B2Y Q12 RGB->YC matrix, apply MEDIUM->DG to Y only,
 *     preserve signed Cb/Cr, invert that exact matrix mathematically, and write
 *     the reconstructed encoded RGB directly (no second OETF).
 *
 * The inverse is not a fitted camera matrix; it is the mathematical inverse of
 * record 0x0C's exact Q12 coefficients. This branch is research-only.
 */
public final class M10RTransferRgb1GRenderer {
    private M10RTransferRgb1GRenderer() {}
    static final int INPUT_MAX=0x3fff,TONE_ENTRIES=10240,DG_ENTRIES=32768,DG_OUT_MAX=0x3fff;
    static final double SCALE=0.94;
    static final double DEN=4096.0;
    static final int YR=1224,YG=2403,YB=469;
    static final int CBR=-691,CBG=-1357,CBB=2048;
    static final int CRR=2048,CRG=-1715,CRB=-333;

    // Mathematical inverse of the exact Q12 matrix above; no fit.
    static final double I00=1.000000000000000, I01=-0.001043337610782, I02=1.401991725444800;
    static final double I10=1.000000000000000, I11=-0.345114690198605, I12=-0.714098755335564;
    static final double I20=1.000000000000000, I21=1.770975790581759, I22=-0.000124867533205;

    public static final class Assets {
        final int[] tone,dg;
        private Assets(int[] t,int[] d){tone=t;dg=d;}
        public static Assets load(Path tp,Path dp)throws IOException{
            byte[] tb=Files.readAllBytes(tp),db=Files.readAllBytes(dp);
            if(tb.length!=TONE_ENTRIES*4||db.length!=DG_ENTRIES*2)throw new IllegalArgumentException("asset length");
            ByteBuffer t=ByteBuffer.wrap(tb).order(ByteOrder.LITTLE_ENDIAN),d=ByteBuffer.wrap(db).order(ByteOrder.LITTLE_ENDIAN);
            int[] ta=new int[TONE_ENTRIES],da=new int[DG_ENTRIES];
            for(int i=0;i<ta.length;i++)ta[i]=t.getInt();
            for(int i=0;i<da.length;i++)da[i]=d.getShort()&0xffff;
            return new Assets(ta,da);
        }
    }
    public static final class Result{
        public final int width,height,stride;
        public final int[] rec709SharedLinear,fwComponentSharedLinear,fwYcPreserveChroma;
        public final int[] ca9Gains;public final long[] neutralClips;
        Result(int w,int h,int s,int[] a,int[] b,int[] c,int[] g,long[] n){width=w;height=h;stride=s;rec709SharedLinear=a;fwComponentSharedLinear=b;fwYcPreserveChroma=c;ca9Gains=g;neutralClips=n;}
    }

    public static Result render(DngRawDecoder.RawImage raw,DngMetadataReader.DngInfo info,Assets assets,int maxDimension){
        M10RReferenceColorCore.CalibrationTemperatures ts=M10RReferenceColorCore.referenceTemperaturesForIlluminants(info.calibrationIlluminant1,info.calibrationIlluminant2);
        M10RReferenceColorCore.WhiteSolution white=M10RReferenceColorCore.solveNeutralToXy(info.asShotNeutral,info.colorMatrix1,info.colorMatrix2,ts.t1,ts.t2);
        int[] gains=M10RColorSpecCore.recoverCa9Gains(info.asShotNeutral);
        SensorPreviewCore.CfaPattern cfa=SensorPreviewCore.CfaPattern.fromDng(info.cfaRepeatPatternDim,info.cfaPattern);
        int stride=Math.max(1,ceilDiv(Math.max(raw.width,raw.height),maxDimension)),w=ceilDiv(raw.width,stride),h=ceilDiv(raw.height,stride),n=w*h;
        int[] a=new int[n],b=new int[n],c=new int[n];long[] clips=new long[3];
        for(int oy=0;oy<h;oy++){int sy=Math.min(oy*stride,raw.height-1);for(int ox=0;ox<w;ox++){int sx=Math.min(ox*stride,raw.width-1);
            double[] cam={
                interp(raw.samples,raw.width,raw.height,sx,sy,SensorPreviewCore.Channel.R,cfa,info.blackLevel,info.whiteLevel),
                interp(raw.samples,raw.width,raw.height,sx,sy,SensorPreviewCore.Channel.G,cfa,info.blackLevel,info.whiteLevel),
                interp(raw.samples,raw.width,raw.height,sx,sy,SensorPreviewCore.Channel.B,cfa,info.blackLevel,info.whiteLevel)};
            for(int ch=0;ch<3;ch++)if(cam[ch]*gains[ch]/M10RColorSpecCore.ASN_SCALE>1.0)clips[ch]++;
            double[] guarded=M10RNeutralClipReferenceRenderer.applyCa9NeutralSaturation(cam,gains);
            double[] lin=M10RColorSpecCore.matVecMul(white.cameraToSrgbLinear,guarded);

            // A: RGB1D global winner.
            double recLin=.2126*lin[0]+.7152*lin[1]+.0722*lin[2];
            double recScalar=oetf(recLin),recMapped=map(recScalar,assets);
            double recGain=recScalar>1e-12?recMapped/recScalar:0.0;

            // Encode once for the two firmware-Y variants.
            double er=oetf(lin[0]),eg=oetf(lin[1]),eb=oetf(lin[2]);
            double fy=(YR*er+YG*eg+YB*eb)/DEN;
            double fcb=(CBR*er+CBG*eg+CBB*eb)/DEN;
            double fcr=(CRR*er+CRG*eg+CRB*eb)/DEN;
            double mappedY=map(fy,assets);

            // B: same firmware component-Y scalar, old shared-linear reconstruction.
            double fwGain=fy>1e-12?mappedY/fy:0.0;

            // C: replace Y only, preserve signed Cb/Cr, reconstruct encoded RGB.
            double rr=I00*mappedY+I01*fcb+I02*fcr;
            double rg=I10*mappedY+I11*fcb+I12*fcr;
            double rb=I20*mappedY+I21*fcb+I22*fcr;

            int i=oy*w+ox;
            a[i]=argbLinearGain(lin,recGain);
            b[i]=argbLinearGain(lin,fwGain);
            c[i]=argbEncoded(rr,rg,rb);
        }}
        return new Result(w,h,stride,a,b,c,gains,clips);
    }

    private static double map(double y,Assets a){
        if(!Double.isFinite(y)||y<=0)y=0;
        double q=y*INPUT_MAX*SCALE;
        int x=q>=INPUT_MAX?INPUT_MAX:clamp((int)Math.round(q),0,INPUT_MAX);
        int m=medium(x,a.tone);
        return a.dg[clamp(m,0,a.dg.length-1)]/(double)DG_OUT_MAX;
    }
    static int medium(int x,int[] t){int xx=clamp(x,0,t.length*2-1);return(int)(((long)xx*t[xx>>1])>>15);}
    private static double oetf(double x){x=clamp01(x);return x<=.0031308?12.92*x:1.055*Math.pow(x,1.0/2.4)-.055;}
    private static int argbLinearGain(double[] l,double g){return 0xff000000|(SensorPreviewCore.toSrgb8(l[0]*g)<<16)|(SensorPreviewCore.toSrgb8(l[1]*g)<<8)|SensorPreviewCore.toSrgb8(l[2]*g);}
    private static int q8(double x){x=clamp01(x);return clamp((int)Math.round(255.0*x),0,255);}
    private static int argbEncoded(double r,double g,double b){return 0xff000000|(q8(r)<<16)|(q8(g)<<8)|q8(b);}
    private static double interp(short[] s,int w,int h,int x,int y,SensorPreviewCore.Channel want,SensorPreviewCore.CfaPattern c,double[] b,double[] wh){
        if(c.channelAt(x,y)==want)return SensorPreviewCore.normalized(s[y*w+x]&0xffff,x,y,b,wh);
        double sum=0;int n=0;
        for(int dy=-1;dy<=1;dy++){int yy=y+dy;if(yy<0||yy>=h)continue;for(int dx=-1;dx<=1;dx++){int xx=x+dx;if(xx<0||xx>=w||(dx==0&&dy==0)||c.channelAt(xx,yy)!=want)continue;sum+=SensorPreviewCore.normalized(s[yy*w+xx]&0xffff,xx,yy,b,wh);n++;}}
        if(n==0)throw new IllegalStateException();return sum/n;
    }
    private static int clamp(int v,int l,int h){return v<l?l:(v>h?h:v);}private static double clamp01(double x){return x<=0?0:(x>=1?1:x);}private static int ceilDiv(int a,int b){return(a+b-1)/b;}
}
