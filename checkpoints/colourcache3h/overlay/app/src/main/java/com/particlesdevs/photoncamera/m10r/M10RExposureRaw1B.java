package com.particlesdevs.photoncamera.m10r;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;

/** Frame-local RAW16 preparation. Source normalisation mirrors the frozen September 30 renderer. */
public final class M10RExposureRaw1B {
    private M10RExposureRaw1B() {}
    static final int[][] GAIN_CHANNELS = {{0,1,2,3},{1,0,3,2},{1,3,0,2},{3,1,2,0}};
    public static final class Prepared {
        final short[] normalized;
        private final double[] rawGreen;
        double[] meterGreen1U;
        String firmwareShadow2R;
        private final long[] phaseAtWhite, phaseAboveWhite, phaseNearWhite;
        public final int width, height, cfa;
        public final double storageScale;
        Prepared(short[] normalized, double[] green, long[] at, long[] above, long[] near,
                int width, int height, int cfa, double scale) {
            this.normalized=normalized;this.rawGreen=green;this.phaseAtWhite=at;
            this.phaseAboveWhite=above;this.phaseNearWhite=near;
            this.width=width;this.height=height;this.cfa=cfa;this.storageScale=scale;
        }
        public double[] neutralGreen(double referenceIntentEv) {
            if (!Double.isFinite(referenceIntentEv) || Math.abs(referenceIntentEv)>32)
                throw new IllegalArgumentException("reference intent");
            double gain=Math.pow(2,-referenceIntentEv);
            double[] result=rawGreen.clone();
            for(int i=0;i<result.length;i++) result[i]=Math.min(1,result[i]*gain);
            return result;
        }
        public long[] atWhiteByCfaPhase(){return phaseAtWhite.clone();}
        public long[] aboveWhiteByCfaPhase(){return phaseAboveWhite.clone();}
        public long[] nearWhiteByCfaPhase(){return phaseNearWhite.clone();}
        public short[] normalizedCopy(){return normalized.clone();}
    }
    /**
     * Buffer offset is explicit; position/limit/order of the caller are never changed.
     * This phase supports only full RAW origin (0,0), matching the current JPEG path.
     * Crop origins are rejected, NOT silently treated as RGGB or a full sensor.
     * Shading channel order is Camera2 [R, G_even, G_odd, B].
     */
    public static Prepared prepare(ByteBuffer data,int offset,int rowStride,int pixelStride,
            int width,int height,int originX,int originY,int cfa,double[] black,int white,
            float[] shading,int cols,int rows) {
        if(data==null || width<64 || height<64 || width>8192 || height>8192 || cfa<0 || cfa>3
                || originX!=0 || originY!=0 || pixelStride!=2 || rowStride<(long)width*2 || offset<0
                || (long)offset+(long)(height-1)*rowStride+(long)width*2>data.limit()
                || black==null || black.length!=4 || white<2 || white>65535)
            throw new IllegalArgumentException("full-origin valid RAW16 layout required");
        black=black.clone();
        for(double v:black) if(!Double.isFinite(v)||v<0||v>=white)throw new IllegalArgumentException("black/white");
        if(shading!=null) {
            if(cols<2||rows<2||cols>256||rows>256||shading.length!=(long)cols*rows*4)
                throw new IllegalArgumentException("shading shape");
            shading=shading.clone();
            for(float v:shading)if(!Float.isFinite(v)||v<=0||v>64)throw new IllegalArgumentException("shading values");
        } else if(cols!=0||rows!=0)throw new IllegalArgumentException("absent shading dimensions");
        double max=1;
        if(shading!=null)for(float g:shading)if(g>max)max=g;
        double scale=1/max;
        short[] normalized=new short[Math.multiplyExact(width,height)];
        double[] green=new double[352];long[] count=new long[352];
        long[] at=new long[4],above=new long[4],near=new long[4];
        ByteBuffer src=data.duplicate().order(ByteOrder.LITTLE_ENDIAN);
        for(int y=0;y<height;y++) for(int x=0;x<width;x++) {
            int phase=((y&1)<<1)|(x&1), code=src.getShort(offset+y*rowStride+x*2)&65535;
            double den=Math.max(1,white-black[phase]);
            double unit=Math.max(0,(code-black[phase])/den);
            if(code==white)at[phase]++;
            if(code>white)above[phase]++;
            if(unit>=.98)near[phase]++;
            unit=Math.min(1,unit);
            int channel=GAIN_CHANNELS[cfa][phase];
            double gain=shading==null?1:Math.max(1,bilinear(shading,cols,rows,channel,
                    x/(double)(width-1),y/(double)(height-1)));
            normalized[y*width+x]=(short)Math.round(Math.max(0,Math.min(1,unit*gain*scale))*65535);
            // Same CFA-aware 8x8 sample lattice as METERAREA1A. No OEM luma proxy.
            if((channel==1||channel==2)&&(x&7)<2&&(y&7)<2) {
                int cell=Math.min(15,(int)((long)y*16/height))*22+Math.min(21,(int)((long)x*22/width));
                green[cell]+=unit;count[cell]++;
            }
        }
        for(int i=0;i<352;i++){
            if(count[i]==0)throw new IllegalArgumentException("RAW too small for complete meter lattice");
            green[i]/=count[i];
        }
        return new Prepared(normalized,green,at,above,near,width,height,cfa,scale);
    }
    static double bilinear(float[] m,int cols,int rows,int c,double u,double v){
        double gx=Math.max(0,Math.min(1,u))*(cols-1), gy=Math.max(0,Math.min(1,v))*(rows-1);
        int x0=(int)Math.floor(gx),y0=(int)Math.floor(gy),x1=Math.min(cols-1,x0+1),y1=Math.min(rows-1,y0+1);
        double fx=gx-x0,fy=gy-y0;
        double a=m[(y0*cols+x0)*4+c],b=m[(y0*cols+x1)*4+c],d=m[(y1*cols+x0)*4+c],e=m[(y1*cols+x1)*4+c];
        return (a*(1-fx)+b*fx)*(1-fy)+(d*(1-fx)+e*fx)*fy;
    }
}
