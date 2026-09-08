package com.m10r.diagnostic;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * RGB1F — exact firmware YC_CONVERSION Y-row audit.
 *
 * Frozen from RGB1D winner:
 *   CA9 C -> Leica ColorSpec -> linear sRGB -> encoded-like scalar
 *   -> coordinate scale 0.94 -> exact MEDIUM -> DG -> code ratio shared on linear RGB
 *   -> standard sRGB OETF.
 *
 * Variable only:
 *   REC709_OETFY       Ylin=0.2126R+0.7152G+0.0722B; scalar=OETF(Ylin) [RGB1D control]
 *   FW601_OETFY        Ylin=(1224R+2403G+469B)/4096; scalar=OETF(Ylin)
 *   FW601_COMPONENT_Y  scalar=(1224 OETF(R)+2403 OETF(G)+469 OETF(B))/4096
 *
 * The 1224/2403/469 coefficients are copied exactly from recovered B2Y record 0x0C.
 * No exposure/gamma/WB/colour/coordinate parameter is fitted here.
 */
public final class M10RTransferRgb1FRenderer {
    private M10RTransferRgb1FRenderer() {}
    static final int INPUT_MAX=0x3fff,TONE_ENTRIES=10240,DG_ENTRIES=32768,DG_OUT_MAX=0x3fff;
    static final double SCALE=0.94;
    static final int FW_R=1224,FW_G=2403,FW_B=469,FW_DEN=4096;

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
        public final int[] rec709OetfY,fw601OetfY,fw601ComponentY;
        public final int[] ca9Gains;public final long[] neutralClips;
        Result(int w,int h,int s,int[] a,int[] b,int[] c,int[] g,long[] n){width=w;height=h;stride=s;rec709OetfY=a;fw601OetfY=b;fw601ComponentY=c;ca9Gains=g;neutralClips=n;}
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

            double recLin=.2126*lin[0]+.7152*lin[1]+.0722*lin[2];
            double fwLin=fwY(lin[0],lin[1],lin[2]);
            double recScalar=oetf(recLin);
            double fwScalar=oetf(fwLin);
            double fwCompScalar=fwY(oetf(lin[0]),oetf(lin[1]),oetf(lin[2]));
            double recMapped=map(recScalar,assets),fwMapped=map(fwScalar,assets),fwCompMapped=map(fwCompScalar,assets);
            double gr=recScalar>1e-12?recMapped/recScalar:0.0;
            double gf=fwScalar>1e-12?fwMapped/fwScalar:0.0;
            double gc=fwCompScalar>1e-12?fwCompMapped/fwCompScalar:0.0;
            int i=oy*w+ox;
            a[i]=argb(lin,gr);b[i]=argb(lin,gf);c[i]=argb(lin,gc);
        }}
        return new Result(w,h,stride,a,b,c,gains,clips);
    }

    private static double fwY(double r,double g,double b){return (FW_R*r+FW_G*g+FW_B*b)/(double)FW_DEN;}
    private static double map(double y,Assets a){
        if(!Double.isFinite(y)||y<=0)y=0;
        double q=y*INPUT_MAX*SCALE;
        int x=q>=INPUT_MAX?INPUT_MAX:clamp((int)Math.round(q),0,INPUT_MAX);
        int m=medium(x,a.tone);
        return a.dg[clamp(m,0,a.dg.length-1)]/(double)DG_OUT_MAX;
    }
    static int medium(int x,int[] t){int xx=clamp(x,0,t.length*2-1);return(int)(((long)xx*t[xx>>1])>>15);}
    private static double oetf(double x){x=clamp01(x);return x<=.0031308?12.92*x:1.055*Math.pow(x,1.0/2.4)-.055;}
    private static int argb(double[] l,double g){return 0xff000000|(SensorPreviewCore.toSrgb8(l[0]*g)<<16)|(SensorPreviewCore.toSrgb8(l[1]*g)<<8)|SensorPreviewCore.toSrgb8(l[2]*g);}
    private static double interp(short[] s,int w,int h,int x,int y,SensorPreviewCore.Channel want,SensorPreviewCore.CfaPattern c,double[] b,double[] wh){
        if(c.channelAt(x,y)==want)return SensorPreviewCore.normalized(s[y*w+x]&0xffff,x,y,b,wh);
        double sum=0;int n=0;
        for(int dy=-1;dy<=1;dy++){int yy=y+dy;if(yy<0||yy>=h)continue;for(int dx=-1;dx<=1;dx++){int xx=x+dx;if(xx<0||xx>=w||(dx==0&&dy==0)||c.channelAt(xx,yy)!=want)continue;sum+=SensorPreviewCore.normalized(s[yy*w+xx]&0xffff,xx,yy,b,wh);n++;}}
        if(n==0)throw new IllegalStateException();return sum/n;
    }
    private static int clamp(int v,int l,int h){return v<l?l:(v>h?h:v);}private static double clamp01(double x){return x<=0?0:(x>=1?1:x);}private static int ceilDiv(int a,int b){return(a+b-1)/b;}
}
