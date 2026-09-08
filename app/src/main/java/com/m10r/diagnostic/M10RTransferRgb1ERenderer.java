package com.m10r.diagnostic;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * REFERENCE_TRANSFER_RGB1E — firmware-topology discriminator.
 *
 * Hypothesis A from the firmware handoff is tested literally as far as the current
 * reference colour boundary allows:
 *
 *   linear RGB/components
 *     -> weighted scalar coordinate
 *     -> MEDIUM Q15 gain lookup
 *     -> the same tone gain applied to each RGB component coordinate
 *     -> Differential Gamma independently per component
 *     -> identity output OR standard sRGB OETF
 *
 * Two pre-declared scalar weight sets are crossed with the two final transfers:
 *   REC709:   0.2126 / 0.7152 / 0.0722 (existing diagnostic control)
 *   FW_TONE:  1024 / 2661 / 410, normalized by 4095 (firmware tone-related triplet)
 *
 * Current RGB1D winner is retained as BASELINE_OETFY_CODE_RATIO:
 *   OETF(linear Rec709 Y) -> MEDIUM -> DG scalar -> code-ratio shared gain on
 *   linear RGB -> final sRGB OETF.
 *
 * Important boundary: the per-component topology is evaluated after the current
 * Leica ColorSpec transform into linear sRGB. Firmware evidence does not yet prove
 * that this is the literal B2Y working RGB basis. No live capture code is changed.
 */
public final class M10RTransferRgb1ERenderer {
    private M10RTransferRgb1ERenderer() {}

    static final int INPUT_MAX = 0x3fff;
    static final int TONE_ENTRIES = 10240;
    static final int DG_ENTRIES = 32768;
    static final int DG_OUT_MAX = 0x3fff;
    static final double BASELINE_SCALE = 0.94;

    private static final double[] REC709 = {0.2126, 0.7152, 0.0722};
    private static final double[] FW_TONE = {1024.0/4095.0, 2661.0/4095.0, 410.0/4095.0};

    public static final class Assets {
        final int[] tone;
        final int[] dg;
        private Assets(int[] tone, int[] dg) { this.tone = tone; this.dg = dg; }

        public static Assets load(Path tonePath, Path dgPath) throws IOException {
            byte[] tb = Files.readAllBytes(tonePath);
            byte[] db = Files.readAllBytes(dgPath);
            if (tb.length != TONE_ENTRIES * 4) throw new IllegalArgumentException("MEDIUM asset byte length=" + tb.length);
            if (db.length != DG_ENTRIES * 2) throw new IllegalArgumentException("DG asset byte length=" + db.length);
            ByteBuffer t = ByteBuffer.wrap(tb).order(ByteOrder.LITTLE_ENDIAN);
            ByteBuffer d = ByteBuffer.wrap(db).order(ByteOrder.LITTLE_ENDIAN);
            int[] tone = new int[TONE_ENTRIES];
            int[] dg = new int[DG_ENTRIES];
            for (int i=0;i<tone.length;i++) tone[i]=t.getInt();
            for (int i=0;i<dg.length;i++) dg[i]=d.getShort() & 0xffff;
            return new Assets(tone,dg);
        }
    }

    public static final class Result {
        public final int width, height, stride;
        public final int[] baselineOetfyCodeRatio;
        public final int[] rec709ComponentDgIdentity;
        public final int[] rec709ComponentDgOetf;
        public final int[] fwToneComponentDgIdentity;
        public final int[] fwToneComponentDgOetf;
        public final int[] ca9Gains;
        public final long[] neutralClips;
        public final long[] rec709DgInputClips;
        public final long[] fwToneDgInputClips;

        Result(int width,int height,int stride,
               int[] baseline,int[] recId,int[] recOetf,int[] fwId,int[] fwOetf,
               int[] gains,long[] neutralClips,long[] recDgClips,long[] fwDgClips) {
            this.width=width;this.height=height;this.stride=stride;
            this.baselineOetfyCodeRatio=baseline;
            this.rec709ComponentDgIdentity=recId;
            this.rec709ComponentDgOetf=recOetf;
            this.fwToneComponentDgIdentity=fwId;
            this.fwToneComponentDgOetf=fwOetf;
            this.ca9Gains=gains;this.neutralClips=neutralClips;
            this.rec709DgInputClips=recDgClips;this.fwToneDgInputClips=fwDgClips;
        }
    }

    public static Result render(DngRawDecoder.RawImage raw,
                                DngMetadataReader.DngInfo info,
                                Assets assets,
                                int maxDimension) {
        if(raw==null||info==null||assets==null) throw new IllegalArgumentException("raw/info/assets must not be null");
        if(raw.width!=info.width||raw.height!=info.height) throw new IllegalArgumentException("decoded RAW dimensions do not match DNG metadata");
        if(info.colorMatrix1==null||info.colorMatrix2==null) throw new IllegalArgumentException("ColorMatrix1/2 are required");
        if(info.asShotNeutral==null||info.asShotNeutral.length!=3) throw new IllegalArgumentException("AsShotNeutral is required");
        if(maxDimension<=0) throw new IllegalArgumentException("maxDimension must be >0");

        M10RReferenceColorCore.CalibrationTemperatures ts =
                M10RReferenceColorCore.referenceTemperaturesForIlluminants(
                        info.calibrationIlluminant1, info.calibrationIlluminant2);
        M10RReferenceColorCore.WhiteSolution white = M10RReferenceColorCore.solveNeutralToXy(
                info.asShotNeutral, info.colorMatrix1, info.colorMatrix2, ts.t1, ts.t2);
        int[] gains = M10RColorSpecCore.recoverCa9Gains(info.asShotNeutral);
        SensorPreviewCore.CfaPattern cfa = SensorPreviewCore.CfaPattern.fromDng(
                info.cfaRepeatPatternDim, info.cfaPattern);

        int stride=Math.max(1,ceilDiv(Math.max(raw.width,raw.height),maxDimension));
        int w=ceilDiv(raw.width,stride), h=ceilDiv(raw.height,stride), n=Math.multiplyExact(w,h);
        int[] baseline=new int[n],recId=new int[n],recOetf=new int[n],fwId=new int[n],fwOetf=new int[n];
        long[] neutralClips=new long[3], recDgClips=new long[3], fwDgClips=new long[3];

        for(int oy=0;oy<h;oy++) {
            int sy=Math.min(oy*stride,raw.height-1);
            for(int ox=0;ox<w;ox++) {
                int sx=Math.min(ox*stride,raw.width-1);
                double[] camera={
                        interpolate(raw.samples,raw.width,raw.height,sx,sy,SensorPreviewCore.Channel.R,cfa,info.blackLevel,info.whiteLevel),
                        interpolate(raw.samples,raw.width,raw.height,sx,sy,SensorPreviewCore.Channel.G,cfa,info.blackLevel,info.whiteLevel),
                        interpolate(raw.samples,raw.width,raw.height,sx,sy,SensorPreviewCore.Channel.B,cfa,info.blackLevel,info.whiteLevel)};
                for(int c=0;c<3;c++) if(camera[c]*gains[c]/M10RColorSpecCore.ASN_SCALE>1.0) neutralClips[c]++;
                double[] guarded=M10RNeutralClipReferenceRenderer.applyCa9NeutralSaturation(camera,gains);
                double[] linear=M10RColorSpecCore.matVecMul(white.cameraToSrgbLinear,guarded);
                int i=oy*w+ox;

                baseline[i]=baselineOetfyCodeRatio(linear,assets);
                double[] rec=componentDg(linear,REC709,assets,recDgClips);
                double[] fw=componentDg(linear,FW_TONE,assets,fwDgClips);
                recId[i]=argbIdentity(rec); recOetf[i]=argbSrgb(rec);
                fwId[i]=argbIdentity(fw); fwOetf[i]=argbSrgb(fw);
            }
        }
        return new Result(w,h,stride,baseline,recId,recOetf,fwId,fwOetf,gains,neutralClips,recDgClips,fwDgClips);
    }

    private static double[] componentDg(double[] linear,double[] weights,Assets assets,long[] dgInputClips) {
        double scalar = weights[0]*linear[0] + weights[1]*linear[1] + weights[2]*linear[2];
        int scalarX=to14(scalar);
        int toneIndex=clamp(scalarX>>1,0,assets.tone.length-1);
        long toneGainQ15=assets.tone[toneIndex] & 0xffffffffL;
        double[] out=new double[3];
        for(int c=0;c<3;c++) {
            int componentX=to14(linear[c]);
            long toned=((long)componentX*toneGainQ15)>>15;
            int dgIndex;
            if(toned<0) { dgIndex=0; dgInputClips[c]++; }
            else if(toned>=assets.dg.length) { dgIndex=assets.dg.length-1; dgInputClips[c]++; }
            else dgIndex=(int)toned;
            out[c]=assets.dg[dgIndex]/(double)DG_OUT_MAX;
        }
        return out;
    }

    private static int baselineOetfyCodeRatio(double[] linear,Assets assets) {
        double y=.2126*linear[0]+.7152*linear[1]+.0722*linear[2];
        double encodedY=srgbOetf(clamp01(y));
        int x=to14Scaled(encodedY,BASELINE_SCALE);
        int m=mediumMappedCoordinate(x,assets.tone);
        int d=assets.dg[clamp(m,0,assets.dg.length-1)];
        double mapped=d/(double)DG_OUT_MAX;
        double gain=encodedY>1e-12?mapped/encodedY:0.0;
        return argbSrgb(new double[]{linear[0]*gain,linear[1]*gain,linear[2]*gain});
    }

    private static int mediumMappedCoordinate(int x,int[] tone) {
        int xx=clamp(x,0,tone.length*2-1);
        return (int)(((long)xx*(long)tone[xx>>1])>>15);
    }

    private static int to14(double v) {
        if(!Double.isFinite(v)||v<=0.0) return 0;
        if(v>=1.0) return INPUT_MAX;
        return clamp((int)Math.round(v*INPUT_MAX),0,INPUT_MAX);
    }
    private static int to14Scaled(double v,double scale) {
        if(!Double.isFinite(v)||v<=0.0) return 0;
        double q=v*INPUT_MAX*scale;
        if(q>=INPUT_MAX) return INPUT_MAX;
        return clamp((int)Math.round(q),0,INPUT_MAX);
    }

    private static double srgbOetf(double x) {
        return x<=0.0031308?12.92*x:1.055*Math.pow(x,1.0/2.4)-0.055;
    }
    private static int argbIdentity(double[] rgb) {
        return 0xff000000|(toIdentity8(rgb[0])<<16)|(toIdentity8(rgb[1])<<8)|toIdentity8(rgb[2]);
    }
    private static int argbSrgb(double[] rgb) {
        return 0xff000000|(SensorPreviewCore.toSrgb8(rgb[0])<<16)|(SensorPreviewCore.toSrgb8(rgb[1])<<8)|SensorPreviewCore.toSrgb8(rgb[2]);
    }
    private static int toIdentity8(double x){return(int)Math.round(clamp01(x)*255.0);}

    private static double interpolate(short[] s,int w,int h,int x,int y,SensorPreviewCore.Channel wanted,
                                      SensorPreviewCore.CfaPattern cfa,double[] black,double[] white) {
        if(cfa.channelAt(x,y)==wanted) return SensorPreviewCore.normalized(s[y*w+x]&0xffff,x,y,black,white);
        double sum=0.0; int count=0;
        for(int dy=-1;dy<=1;dy++){int yy=y+dy;if(yy<0||yy>=h)continue;
            for(int dx=-1;dx<=1;dx++){int xx=x+dx;if(xx<0||xx>=w||(dx==0&&dy==0)||cfa.channelAt(xx,yy)!=wanted)continue;
                sum+=SensorPreviewCore.normalized(s[yy*w+xx]&0xffff,xx,yy,black,white);count++;}}
        if(count==0)throw new IllegalStateException("no Bayer neighbour for "+wanted);return sum/count;
    }
    private static int ceilDiv(int a,int b){return(a+b-1)/b;}
    private static int clamp(int v,int lo,int hi){return v<lo?lo:(v>hi?hi:v);}
    private static double clamp01(double x){return x<=0.0?0.0:(x>=1.0?1.0:x);}
}
