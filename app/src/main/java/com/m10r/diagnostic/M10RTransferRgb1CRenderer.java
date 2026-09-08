package com.m10r.diagnostic;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * REFERENCE_TRANSFER_RGB1C: isolate the remaining EL_OETF bright-end ambiguity.
 *
 * Frozen through Leica ColorSpec -> linear sRGB and exact MEDIUM -> DG arithmetic.
 * Controls retain RGB1A LL_OETF and LL_IDENTITY. The four EL candidates vary only:
 *   encoded luma source: BOUNDED per-channel standard sRGB code vs EXTENDED code before output clamp
 *   coordinate scale: 1.00 vs 0.94, with scale applied before the 14-bit coordinate clamp.
 *
 * 0.94 is pre-declared from the earlier scalar identity-transfer fits (nearest-rounding median),
 * not fitted on the RGB1C images. Shared gain remains on linear RGB and final output uses sRGB OETF.
 */
public final class M10RTransferRgb1CRenderer {
    private M10RTransferRgb1CRenderer() {}

    public static final int INPUT_MAX = 0x3fff;
    public static final int TONE_ENTRIES = 10240;
    public static final int DG_ENTRIES = 32768;
    public static final int DG_OUT_MAX = 0x3fff;
    public static final double SCALE_094 = 0.94;

    public static final class Assets {
        final int[] tone;
        final int[] dg;
        private Assets(int[] tone, int[] dg) { this.tone = tone; this.dg = dg; }
        public static Assets load(Path tonePath, Path dgPath) throws IOException {
            byte[] tb = Files.readAllBytes(tonePath);
            byte[] db = Files.readAllBytes(dgPath);
            if (tb.length != TONE_ENTRIES * 4) throw new IllegalArgumentException("MEDIUM asset byte length=" + tb.length);
            if (db.length != DG_ENTRIES * 2) throw new IllegalArgumentException("DG asset byte length=" + db.length);
            ByteBuffer tbuf = ByteBuffer.wrap(tb).order(ByteOrder.LITTLE_ENDIAN);
            ByteBuffer dbuf = ByteBuffer.wrap(db).order(ByteOrder.LITTLE_ENDIAN);
            int[] tone = new int[TONE_ENTRIES];
            int[] dg = new int[DG_ENTRIES];
            for (int i=0;i<tone.length;i++) tone[i]=tbuf.getInt();
            for (int i=0;i<dg.length;i++) dg[i]=dbuf.getShort() & 0xffff;
            return new Assets(tone,dg);
        }
    }

    public static final class Result {
        public final int width,height,sourceStride;
        public final int[] llOetf,llIdentity,elBounded100,elBounded094,elExtended100,elExtended094;
        public final int[] ca9Gains;
        public final long[] neutralClipCounts;
        Result(int width,int height,int sourceStride,
               int[] llOetf,int[] llIdentity,int[] elBounded100,int[] elBounded094,
               int[] elExtended100,int[] elExtended094,int[] ca9Gains,long[] neutralClipCounts) {
            this.width=width;this.height=height;this.sourceStride=sourceStride;
            this.llOetf=llOetf;this.llIdentity=llIdentity;this.elBounded100=elBounded100;
            this.elBounded094=elBounded094;this.elExtended100=elExtended100;this.elExtended094=elExtended094;
            this.ca9Gains=ca9Gains;this.neutralClipCounts=neutralClipCounts;
        }
    }

    public static Result render(DngRawDecoder.RawImage raw,DngMetadataReader.DngInfo info,Assets assets,int maxDimension) {
        if(raw==null||info==null||assets==null) throw new IllegalArgumentException("raw/info/assets must not be null");
        if(raw.width!=info.width||raw.height!=info.height) throw new IllegalArgumentException("decoded RAW dimensions do not match DNG metadata");
        if(info.colorMatrix1==null||info.colorMatrix2==null) throw new IllegalArgumentException("ColorMatrix1/2 are required");
        if(info.asShotNeutral==null||info.asShotNeutral.length!=3) throw new IllegalArgumentException("AsShotNeutral is required");
        if(maxDimension<=0) throw new IllegalArgumentException("maxDimension must be > 0");

        M10RReferenceColorCore.CalibrationTemperatures temperatures=
                M10RReferenceColorCore.referenceTemperaturesForIlluminants(info.calibrationIlluminant1,info.calibrationIlluminant2);
        M10RReferenceColorCore.WhiteSolution white=M10RReferenceColorCore.solveNeutralToXy(
                info.asShotNeutral,info.colorMatrix1,info.colorMatrix2,temperatures.t1,temperatures.t2);
        int[] gains=M10RColorSpecCore.recoverCa9Gains(info.asShotNeutral);
        SensorPreviewCore.CfaPattern cfa=SensorPreviewCore.CfaPattern.fromDng(info.cfaRepeatPatternDim,info.cfaPattern);

        int stride=Math.max(1,ceilDiv(Math.max(raw.width,raw.height),maxDimension));
        int outWidth=ceilDiv(raw.width,stride),outHeight=ceilDiv(raw.height,stride);
        int n=Math.multiplyExact(outWidth,outHeight);
        int[] llOn=new int[n],llId=new int[n],b100=new int[n],b094=new int[n],x100=new int[n],x094=new int[n];
        long[] neutralClips=new long[3];

        for(int oy=0;oy<outHeight;oy++){
            int sy=Math.min(oy*stride,raw.height-1);
            for(int ox=0;ox<outWidth;ox++){
                int sx=Math.min(ox*stride,raw.width-1);
                double[] camera={
                        interpolate(raw.samples,raw.width,raw.height,sx,sy,SensorPreviewCore.Channel.R,cfa,info.blackLevel,info.whiteLevel),
                        interpolate(raw.samples,raw.width,raw.height,sx,sy,SensorPreviewCore.Channel.G,cfa,info.blackLevel,info.whiteLevel),
                        interpolate(raw.samples,raw.width,raw.height,sx,sy,SensorPreviewCore.Channel.B,cfa,info.blackLevel,info.whiteLevel)};
                for(int c=0;c<3;c++) if(camera[c]*gains[c]/M10RColorSpecCore.ASN_SCALE>1.0) neutralClips[c]++;
                double[] guarded=M10RNeutralClipReferenceRenderer.applyCa9NeutralSaturation(camera,gains);
                double[] linear=M10RColorSpecCore.matVecMul(white.cameraToSrgbLinear,guarded);

                double yLinear=luma(linear);
                double mappedLinear=mapY(yLinear,1.0,assets);
                double gLinear=yLinear>1e-12?mappedLinear/yLinear:0.0;
                int i=oy*outWidth+ox;
                llOn[i]=argbSrgb(linear[0]*gLinear,linear[1]*gLinear,linear[2]*gLinear);
                llId[i]=argbIdentity(linear[0]*gLinear,linear[1]*gLinear,linear[2]*gLinear);

                double[] bounded={srgbBounded(linear[0]),srgbBounded(linear[1]),srgbBounded(linear[2])};
                double[] extended={srgbExtended(linear[0]),srgbExtended(linear[1]),srgbExtended(linear[2])};
                double yB=luma(bounded),yX=luma(extended);
                b100[i]=el(linear,yB,1.0,assets);
                b094[i]=el(linear,yB,SCALE_094,assets);
                x100[i]=el(linear,yX,1.0,assets);
                x094[i]=el(linear,yX,SCALE_094,assets);
            }
        }
        return new Result(outWidth,outHeight,stride,llOn,llId,b100,b094,x100,x094,gains,neutralClips);
    }

    private static int el(double[] linear,double encodedY,double scale,Assets assets){
        double mapped=mapY(encodedY,scale,assets);
        double gain=encodedY>1e-12?mapped/encodedY:0.0;
        return argbSrgb(linear[0]*gain,linear[1]*gain,linear[2]*gain);
    }

    private static double mapY(double y,double scale,Assets assets){
        if(!Double.isFinite(y)||y<=0.0) return assets.dg[Math.max(0,medium(0,assets.tone))]/(double)DG_OUT_MAX;
        double raw=y*INPUT_MAX*scale;
        int x=raw>=INPUT_MAX?INPUT_MAX:clamp((int)Math.round(raw),0,INPUT_MAX);
        int m=medium(x,assets.tone);
        int di=clamp(m,0,assets.dg.length-1);
        return assets.dg[di]/(double)DG_OUT_MAX;
    }

    static int medium(int x,int[] tone){int xx=clamp(x,0,tone.length*2-1);return (int)(((long)xx*(long)tone[xx>>1])>>15);}
    private static double luma(double[] rgb){return .2126*rgb[0]+.7152*rgb[1]+.0722*rgb[2];}
    private static double srgbBounded(double linear){double c=clamp01(linear);return c<=.0031308?12.92*c:1.055*Math.pow(c,1.0/2.4)-.055;}
    private static double srgbExtended(double linear){
        if(!Double.isFinite(linear)) return 0.0;
        if(linear<=.0031308) return 12.92*linear;
        return 1.055*Math.pow(linear,1.0/2.4)-.055;
    }
    private static int argbSrgb(double r,double g,double b){return 0xff000000|(SensorPreviewCore.toSrgb8(r)<<16)|(SensorPreviewCore.toSrgb8(g)<<8)|SensorPreviewCore.toSrgb8(b);}
    private static int argbIdentity(double r,double g,double b){return 0xff000000|(toIdentity8(r)<<16)|(toIdentity8(g)<<8)|toIdentity8(b);}
    private static int toIdentity8(double x){return (int)Math.round(clamp01(x)*255.0);}

    private static double interpolate(short[] samples,int width,int height,int x,int y,SensorPreviewCore.Channel wanted,
                                      SensorPreviewCore.CfaPattern cfa,double[] black,double[] white){
        if(cfa.channelAt(x,y)==wanted) return SensorPreviewCore.normalized(samples[y*width+x]&0xffff,x,y,black,white);
        double sum=0;int count=0;
        for(int dy=-1;dy<=1;dy++){int yy=y+dy;if(yy<0||yy>=height)continue;
            for(int dx=-1;dx<=1;dx++){int xx=x+dx;if(xx<0||xx>=width||(dx==0&&dy==0))continue;
                if(cfa.channelAt(xx,yy)!=wanted)continue;sum+=SensorPreviewCore.normalized(samples[yy*width+xx]&0xffff,xx,yy,black,white);count++;}}
        if(count==0)throw new IllegalStateException("no Bayer neighbour for "+wanted);return sum/count;
    }
    private static int ceilDiv(int a,int b){return(a+b-1)/b;}
    private static int clamp(int v,int lo,int hi){return v<lo?lo:(v>hi?hi:v);}
    private static double clamp01(double x){return x<=0?0:(x>=1?1:x);}
}
