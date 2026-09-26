package com.m10r.diagnostic;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * Host-only YBLEND_REFERENCE1A falsification renderer.
 *
 * Fixed pipeline:
 * camera -> CA9 neutral guard -> Leica internal RGB -> exact YC record 0x0C
 * -> MEDIUM tone -> DG on Y -> constant-k chroma carrier family
 * -> exact YC inverse -> corrected factory sRGB CC1 -> sRGB publication.
 *
 * The k sweep is diagnostic only. It does not claim record 0x0D uses this equation.
 */
public final class M10RYBlendReference1ARenderer {
    private M10RYBlendReference1ARenderer() {}

    static final int INPUT_MAX=0x3fff;
    static final int TONE_ENTRIES=10240;
    static final int DG_ENTRIES=32768;
    static final int DG_OUT_MAX=0x3fff;
    public static final double[] K_VALUES = {
        0.00,0.05,0.10,0.15,0.20,0.25,0.30,0.35,0.40,0.45,0.50,
        0.55,0.60,0.65,0.70,0.75,0.80,0.85,0.90,0.95,1.00
    };

    // Corrected factory STILL sRGB row (CC1MAP1A / CA9 mode 0).
    static final double[][] WORKING_TO_SRGB = {
        { 2.0341, -0.7273, -0.3067},
        {-0.2288,  1.2317, -0.0029},
        {-0.0086, -0.1533,  1.1619}
    };

    public static final class Assets {
        final int[] tone,dg;
        private Assets(int[] tone,int[] dg){this.tone=tone;this.dg=dg;}
        public static Assets load(Path tp,Path dp)throws IOException{
            byte[] tb=Files.readAllBytes(tp),db=Files.readAllBytes(dp);
            if(tb.length!=TONE_ENTRIES*4||db.length!=DG_ENTRIES*2)throw new IllegalArgumentException("asset length");
            ByteBuffer t=ByteBuffer.wrap(tb).order(ByteOrder.LITTLE_ENDIAN);
            ByteBuffer d=ByteBuffer.wrap(db).order(ByteOrder.LITTLE_ENDIAN);
            int[] ta=new int[TONE_ENTRIES],da=new int[DG_ENTRIES];
            for(int i=0;i<ta.length;i++)ta[i]=t.getInt();
            for(int i=0;i<da.length;i++)da[i]=d.getShort()&0xffff;
            return new Assets(ta,da);
        }
    }

    public static final class Result {
        public final int width,height,stride;
        public final int[][] argb;
        public final int[] ca9Gains;
        public final long[] neutralClips;
        Result(int w,int h,int s,int[][] a,int[] g,long[] c){
            width=w;height=h;stride=s;argb=a;ca9Gains=g;neutralClips=c;
        }
    }

    public static Result render(DngRawDecoder.RawImage raw,DngMetadataReader.DngInfo info,Assets assets,int maxDimension){
        M10RReferenceColorCore.CalibrationTemperatures ts=
                M10RReferenceColorCore.referenceTemperaturesForIlluminants(
                        info.calibrationIlluminant1,info.calibrationIlluminant2);
        M10RReferenceColorCore.WhiteSolution white=
                M10RReferenceColorCore.solveNeutralToXy(
                        info.asShotNeutral,info.colorMatrix1,info.colorMatrix2,ts.t1,ts.t2);
        double[][] cameraToWorking=white.cameraToInternal;
        int[] gains=M10RColorSpecCore.recoverCa9Gains(info.asShotNeutral);
        SensorPreviewCore.CfaPattern cfa=SensorPreviewCore.CfaPattern.fromDng(
                info.cfaRepeatPatternDim,info.cfaPattern);

        int stride=Math.max(1,ceilDiv(Math.max(raw.width,raw.height),maxDimension));
        int w=ceilDiv(raw.width,stride),h=ceilDiv(raw.height,stride),n=w*h;
        int[][] out=new int[K_VALUES.length][n];
        long[] clips=new long[3];

        for(int oy=0;oy<h;oy++){
            int sy=Math.min(oy*stride,raw.height-1);
            for(int ox=0;ox<w;ox++){
                int sx=Math.min(ox*stride,raw.width-1);
                double[] cam={
                    interp(raw.samples,raw.width,raw.height,sx,sy,SensorPreviewCore.Channel.R,cfa,info.blackLevel,info.whiteLevel),
                    interp(raw.samples,raw.width,raw.height,sx,sy,SensorPreviewCore.Channel.G,cfa,info.blackLevel,info.whiteLevel),
                    interp(raw.samples,raw.width,raw.height,sx,sy,SensorPreviewCore.Channel.B,cfa,info.blackLevel,info.whiteLevel)
                };
                for(int c=0;c<3;c++) if(cam[c]*gains[c]/M10RColorSpecCore.ASN_SCALE>1.0) clips[c]++;
                double[] guarded=M10RNeutralClipReferenceRenderer.applyCa9NeutralSaturation(cam,gains);
                double[] wrgb=M10RColorSpecCore.matVecMul(cameraToWorking,guarded);

                double y=(1224.0*wrgb[0]+2403.0*wrgb[1]+469.0*wrgb[2])/4096.0;
                double cb=(-691.0*wrgb[0]-1357.0*wrgb[1]+2048.0*wrgb[2])/4096.0;
                double cr=(2048.0*wrgb[0]-1715.0*wrgb[1]-333.0*wrgb[2])/4096.0;
                double mappedY=mapY(y,assets);
                double ratio=y>1.0e-12?mappedY/y:0.0;
                int q=oy*w+ox;

                for(int ki=0;ki<K_VALUES.length;ki++){
                    double k=K_VALUES[ki];
                    double cs=y>1.0e-12?1.0+k*(ratio-1.0):0.0;
                    double mcb=cb*cs,mcr=cr*cs;
                    double nr=mappedY-0.001043337611*mcb+1.401991725445*mcr;
                    double ng=mappedY-0.345114690199*mcb-0.714098755336*mcr;
                    double nb=mappedY+1.770975790582*mcb-0.000124867533*mcr;
                    double sr=WORKING_TO_SRGB[0][0]*nr+WORKING_TO_SRGB[0][1]*ng+WORKING_TO_SRGB[0][2]*nb;
                    double sg=WORKING_TO_SRGB[1][0]*nr+WORKING_TO_SRGB[1][1]*ng+WORKING_TO_SRGB[1][2]*nb;
                    double sb=WORKING_TO_SRGB[2][0]*nr+WORKING_TO_SRGB[2][1]*ng+WORKING_TO_SRGB[2][2]*nb;
                    out[ki][q]=0xff000000|
                            (SensorPreviewCore.toSrgb8(sr)<<16)|
                            (SensorPreviewCore.toSrgb8(sg)<<8)|
                            SensorPreviewCore.toSrgb8(sb);
                }
            }
        }
        return new Result(w,h,stride,out,gains,clips);
    }

    static double mapY(double y,Assets a){
        if(!Double.isFinite(y)||y<=0.0)y=0.0;
        int x=y>=1.0?INPUT_MAX:clamp((int)Math.round(y*INPUT_MAX),0,INPUT_MAX);
        int m=medium(x,a.tone);
        return a.dg[clamp(m,0,a.dg.length-1)]/(double)DG_OUT_MAX;
    }

    static int medium(int x,int[] t){
        int xx=clamp(x,0,t.length*2-1);
        return (int)(((long)xx*t[xx>>1])>>15);
    }

    private static double interp(short[] s,int w,int h,int x,int y,SensorPreviewCore.Channel want,
                                 SensorPreviewCore.CfaPattern c,double[] b,double[] wh){
        if(c.channelAt(x,y)==want)return SensorPreviewCore.normalized(s[y*w+x]&0xffff,x,y,b,wh);
        double sum=0;int n=0;
        for(int dy=-1;dy<=1;dy++){int yy=y+dy;if(yy<0||yy>=h)continue;
            for(int dx=-1;dx<=1;dx++){int xx=x+dx;
                if(xx<0||xx>=w||(dx==0&&dy==0)||c.channelAt(xx,yy)!=want)continue;
                sum+=SensorPreviewCore.normalized(s[yy*w+xx]&0xffff,xx,yy,b,wh);n++;
            }}
        if(n==0)throw new IllegalStateException();
        return sum/n;
    }
    static int clamp(int v,int l,int h){return v<l?l:(v>h?h:v);}
    static int ceilDiv(int a,int b){return(a+b-1)/b;}
}
