package com.m10r.diagnostic;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * CHROMASUPPRESS1A — constrained offline screen for the M10-R B2Y
 * color_dif_suppression block.
 *
 * Fixed upstream and nonlinear path are copied from RGB1G:
 *   CA9 C -> Leica ColorSpec -> linear sRGB -> one sRGB OETF ->
 *   exact recovered B2Y Q12 RGB->YC -> MEDIUM->DG on Y only.
 *
 * Baseline preserves signed Cb/Cr exactly.
 *
 * Six research candidates apply one Fujitsu-family low-chroma suppression
 * topology to Cb/Cr before the exact mathematical YC inverse. No threshold is
 * fitted: inner/outer values are chosen only from the M10-R record-0x18
 * MEDIUM calibration values {20000,30000,40000,50000}.
 *
 * Normalization hypothesis under test:
 *   csumCode = (abs(Cb)+abs(Cr)) * 65536
 * This corresponds to normalized signed chroma being represented on roughly
 * a signed-16-bit scale. This normalization is NOT yet proven Leica hardware
 * arithmetic and is deliberately isolated as the thing being falsified/tested.
 */
public final class M10RChromaSuppress1ARenderer {
    private M10RChromaSuppress1ARenderer() {}

    static final int INPUT_MAX=0x3fff,TONE_ENTRIES=10240,DG_ENTRIES=32768,DG_OUT_MAX=0x3fff;
    static final double SCALE=0.94;
    static final double DEN=4096.0;
    static final int YR=1224,YG=2403,YB=469;
    static final int CBR=-691,CBG=-1357,CBB=2048;
    static final int CRR=2048,CRG=-1715,CRB=-333;
    static final double CHROMA_CODE_SCALE=65536.0;

    static final double I00=1.000000000000000, I01=-0.001043337610782, I02=1.401991725444800;
    static final double I10=1.000000000000000, I11=-0.345114690198605, I12=-0.714098755335564;
    static final double I20=1.000000000000000, I21=1.770975790581759, I22=-0.000124867533205;

    public static final int[][] THRESHOLD_PAIRS = {
        {20000,30000},{20000,40000},{20000,50000},
        {30000,40000},{30000,50000},{40000,50000}
    };
    public static final String[] MODE_NAMES = {
        "baseline",
        "cs_20000_30000","cs_20000_40000","cs_20000_50000",
        "cs_30000_40000","cs_30000_50000","cs_40000_50000"
    };

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
        public final int[][] modes;
        public final int[] ca9Gains;
        public final long[] neutralClips;
        public final long[] suppressedPixelCounts;
        public final double[] meanAppliedGains;
        Result(int w,int h,int s,int[][] m,int[] g,long[] n,long[] sp,double[] mg){
            width=w;height=h;stride=s;modes=m;ca9Gains=g;neutralClips=n;
            suppressedPixelCounts=sp;meanAppliedGains=mg;
        }
    }

    public static Result render(DngRawDecoder.RawImage raw,DngMetadataReader.DngInfo info,Assets assets,int maxDimension){
        M10RReferenceColorCore.CalibrationTemperatures ts=M10RReferenceColorCore.referenceTemperaturesForIlluminants(info.calibrationIlluminant1,info.calibrationIlluminant2);
        M10RReferenceColorCore.WhiteSolution white=M10RReferenceColorCore.solveNeutralToXy(info.asShotNeutral,info.colorMatrix1,info.colorMatrix2,ts.t1,ts.t2);
        int[] gains=M10RColorSpecCore.recoverCa9Gains(info.asShotNeutral);
        SensorPreviewCore.CfaPattern cfa=SensorPreviewCore.CfaPattern.fromDng(info.cfaRepeatPatternDim,info.cfaPattern);
        int stride=Math.max(1,ceilDiv(Math.max(raw.width,raw.height),maxDimension));
        int w=ceilDiv(raw.width,stride),h=ceilDiv(raw.height,stride),n=w*h;
        int[][] out=new int[MODE_NAMES.length][n];
        long[] clips=new long[3];
        long[] suppressed=new long[THRESHOLD_PAIRS.length];
        double[] gainSum=new double[THRESHOLD_PAIRS.length];

        for(int oy=0;oy<h;oy++){
            int sy=Math.min(oy*stride,raw.height-1);
            for(int ox=0;ox<w;ox++){
                int sx=Math.min(ox*stride,raw.width-1);
                double[] cam={
                    interp(raw.samples,raw.width,raw.height,sx,sy,SensorPreviewCore.Channel.R,cfa,info.blackLevel,info.whiteLevel),
                    interp(raw.samples,raw.width,raw.height,sx,sy,SensorPreviewCore.Channel.G,cfa,info.blackLevel,info.whiteLevel),
                    interp(raw.samples,raw.width,raw.height,sx,sy,SensorPreviewCore.Channel.B,cfa,info.blackLevel,info.whiteLevel)};
                for(int ch=0;ch<3;ch++)if(cam[ch]*gains[ch]/M10RColorSpecCore.ASN_SCALE>1.0)clips[ch]++;
                double[] guarded=M10RNeutralClipReferenceRenderer.applyCa9NeutralSaturation(cam,gains);
                double[] lin=M10RColorSpecCore.matVecMul(white.cameraToSrgbLinear,guarded);

                double er=oetf(lin[0]),eg=oetf(lin[1]),eb=oetf(lin[2]);
                double fy=(YR*er+YG*eg+YB*eb)/DEN;
                double fcb=(CBR*er+CBG*eg+CBB*eb)/DEN;
                double fcr=(CRR*er+CRG*eg+CRB*eb)/DEN;
                double mappedY=map(fy,assets);

                int pos=oy*w+ox;
                out[0][pos]=inverseToArgb(mappedY,fcb,fcr);

                double csumCode=(Math.abs(fcb)+Math.abs(fcr))*CHROMA_CODE_SCALE;
                for(int k=0;k<THRESHOLD_PAIRS.length;k++){
                    int inner=THRESHOLD_PAIRS[k][0],outer=THRESHOLD_PAIRS[k][1];
                    double cg=chromaGain(csumCode,inner,outer);
                    gainSum[k]+=cg;
                    if(cg<0.999999999)suppressed[k]++;
                    out[k+1][pos]=inverseToArgb(mappedY,fcb*cg,fcr*cg);
                }
            }
        }
        double[] meanGain=new double[THRESHOLD_PAIRS.length];
        for(int k=0;k<meanGain.length;k++)meanGain[k]=gainSum[k]/Math.max(1,n);
        return new Result(w,h,stride,out,gains,clips,suppressed,meanGain);
    }

    static double chromaGain(double csumCode,double inner,double outer){
        if(!Double.isFinite(csumCode)||csumCode<=inner)return 0.0;
        if(csumCode>=outer)return 1.0;
        return (csumCode-inner)/(outer-inner);
    }

    private static int inverseToArgb(double y,double cb,double cr){
        double r=I00*y+I01*cb+I02*cr;
        double g=I10*y+I11*cb+I12*cr;
        double b=I20*y+I21*cb+I22*cr;
        return argbEncoded(r,g,b);
    }

    private static double map(double y,Assets a){
        if(!Double.isFinite(y)||y<=0)y=0;
        double q=y*INPUT_MAX*SCALE;
        int x=q>=INPUT_MAX?INPUT_MAX:clamp((int)Math.round(q),0,INPUT_MAX);
        int m=medium(x,a.tone);
        return a.dg[clamp(m,0,a.dg.length-1)]/(double)DG_OUT_MAX;
    }
    static int medium(int x,int[] t){
        int xx=clamp(x,0,t.length*2-1);
        return(int)(((long)xx*t[xx>>1])>>15);
    }
    private static double oetf(double x){
        x=clamp01(x);
        return x<=.0031308?12.92*x:1.055*Math.pow(x,1.0/2.4)-.055;
    }
    private static int q8(double x){x=clamp01(x);return clamp((int)Math.round(255.0*x),0,255);}
    private static int argbEncoded(double r,double g,double b){return 0xff000000|(q8(r)<<16)|(q8(g)<<8)|q8(b);}
    private static double interp(short[] s,int w,int h,int x,int y,SensorPreviewCore.Channel want,SensorPreviewCore.CfaPattern c,double[] bl,double[] wh){
        if(c.channelAt(x,y)==want)return SensorPreviewCore.normalized(s[y*w+x]&0xffff,x,y,bl,wh);
        double sum=0;int n=0;
        for(int dy=-1;dy<=1;dy++){
            int yy=y+dy;if(yy<0||yy>=h)continue;
            for(int dx=-1;dx<=1;dx++){
                int xx=x+dx;
                if(xx<0||xx>=w||(dx==0&&dy==0)||c.channelAt(xx,yy)!=want)continue;
                sum+=SensorPreviewCore.normalized(s[yy*w+xx]&0xffff,xx,yy,bl,wh);n++;
            }
        }
        if(n==0)throw new IllegalStateException();
        return sum/n;
    }
    private static int clamp(int v,int l,int h){return v<l?l:(v>h?h:v);}
    private static double clamp01(double x){return x<=0?0:(x>=1?1:x);}
    private static int ceilDiv(int a,int b){return(a+b-1)/b;}
}
