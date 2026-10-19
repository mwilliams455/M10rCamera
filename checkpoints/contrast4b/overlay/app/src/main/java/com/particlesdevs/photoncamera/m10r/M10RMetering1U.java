package com.particlesdevs.photoncamera.m10r;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.Arrays;

/** Live View phone adapter. Recovered masks/EV ratios, NOT absolute Leica Y calibration.
 * The phone's full-field AE is the physical exposure anchor for all three modes.
 * No fixed middle-gray target or scene/subject classifier is introduced here.
 */
public final class M10RMetering1U {
    public static final String REVISION="M10R_MFMSTATS1X_FIRMWARE_REGION_GEOMETRY";
    public enum Mode { CENTRE_WEIGHTED, MULTI_FIELD, SPOT }
    public static final int W=176,H=128,BORDER=16;
    public static final double MAX_SPATIAL_EV=2.0;
    private M10RMetering1U() {}
    public static Mode mode(int preference) {
        return preference==0?Mode.CENTRE_WEIGHTED:preference==2?Mode.SPOT:Mode.MULTI_FIELD;
    }
    /** Crop is in unrotated, full-buffer normalized sensor coordinates. Spot is
     * normalized within that crop. The 2.5% spot area is an adapter parameter;
     * Leica's boundary-cell softening is not yet ported.
     */
    public static final class Config {
        public final Mode mode;
        public final double left,top,right,bottom,spotX,spotY;
        public Config(Mode mode,double left,double top,double right,double bottom,double sx,double sy) {
            if(mode==null||!unit(left)||!unit(top)||!unit(right)||!unit(bottom)
                    ||right<=left||bottom<=top||!unit(sx)||!unit(sy))
                throw new IllegalArgumentException("meter mode/crop/spot");
            this.mode=mode;this.left=left;this.top=top;this.right=right;this.bottom=bottom;
            spotX=sx;spotY=sy;
        }
        public Config(Mode mode) {this(mode,0,0,1,1,.5,.5);}
        public String key() {return mode+":"+left+":"+top+":"+right+":"+bottom+":"+spotX+":"+spotY;}
    }
    public static int sampleCoordinate(int i,int n,int extent) {
        return BORDER+(int)((2L*i+1)*(extent-2*BORDER)/(2L*n));
    }
    /** Both greens of a CFA cell, before LSC/WB, at the same sparse sample sites
     * used by the rendered candidates. Does not alter the caller's buffer cursor.
     */
    public static double[] sampleGreen(ByteBuffer data,int offset,int stride,int width,int height,
            int cfa,double[] black,int white) {
        if(width<W+2*BORDER||height<H+2*BORDER)return null;
        ByteBuffer b=data.duplicate().order(ByteOrder.LITTLE_ENDIAN);
        double[] out=new double[W*H];
        for(int y=0;y<H;y++)for(int x=0;x<W;x++) {
            int sx=sampleCoordinate(x,W,width)&~1,sy=sampleCoordinate(y,H,height)&~1;
            double sum=0;
            for(int p=0;p<4;p++)if(M10RExposureRaw1B.GAIN_CHANNELS[cfa][p]==1
                    ||M10RExposureRaw1B.GAIN_CHANNELS[cfa][p]==2) {
                int code=b.getShort(offset+(sy+(p>>1))*stride+(sx+(p&1))*2)&65535;
                sum+=Math.max(0,Math.min(1,(code-black[p])/(white-black[p])));
            }
            out[y*W+x]=sum*.5;
        }
        return out;
    }
    public static final class Measurement {
        public final Config config;
        public final double mean,integral,spot,spatialEv;
        private final double[] cells,regions;
        private final int[] fields;
        Measurement(Config config,double mean,double integral,double spot,double[] cells,double[] regions,int[] fields) {
            this.config=config;this.mean=mean;this.integral=integral;this.spot=spot;
            this.cells=cells.clone();this.regions=regions.clone();this.fields=fields.clone();
            double selected=config.mode==Mode.SPOT?spot:integral;
            // A floor prevents an empty/black spot from requesting unbounded gain.
            spatialEv=mean<=1e-6?0:Math.max(-MAX_SPATIAL_EV,Math.min(MAX_SPATIAL_EV,
                    Math.log(mean/Math.max(selected,1e-6))/Math.log(2)));
        }
        public double[] cells(){return cells.clone();}
        public double[] regions(){return regions.clone();}
        public int[] fields(){return fields.clone();}
    }
    public static Measurement measure(double[] green,int rawWidth,int rawHeight,Config cfg) {
        if(green==null||green.length!=W*H||cfg==null||rawWidth<W+32||rawHeight<H+32)
            throw new IllegalArgumentException("shared RAW measurement unavailable");
        // One ROI for RAW cells, RAW regions and every rendered candidate.
        double l=Math.max(BORDER,cfg.left*rawWidth),t=Math.max(BORDER,cfg.top*rawHeight);
        double r=Math.min(rawWidth-BORDER,cfg.right*rawWidth),b=Math.min(rawHeight-BORDER,cfg.bottom*rawHeight);
        if(r<=l||b<=t)throw new IllegalArgumentException("empty meter crop");
        double[] cells=new double[352];
        int[] nc=new int[352],fields=new int[W*H];Arrays.fill(fields,-1);
        for(int y=0;y<H;y++)for(int x=0;x<W;x++) {
            int i=y*W+x;double g=green[i];
            if(!unit(g))throw new IllegalArgumentException("invalid RAW sample");
            double px=sampleCoordinate(x,W,rawWidth)+.5,py=sampleCoordinate(y,H,rawHeight)+.5;
            if(px<l||px>=r||py<t||py>=b)continue;
            double u=(px-l)/(r-l),v=(py-t)/(b-t);
            int cell=(int)(v*16)*22+(int)(u*22);
            cells[cell]+=g;nc[cell]++;fields[i]=M10RMeteringGeometry1X.fieldForCell(cell);
        }
        double sum=0,weighted=0,spotSum=0;int sw=0,ns=0;
        double half=Math.sqrt(.025)*.5;
        double cx=Math.max(half,Math.min(1-half,cfg.spotX)),cy=Math.max(half,Math.min(1-half,cfg.spotY));
        for(int i=0;i<352;i++) {
            if(nc[i]==0)throw new IllegalArgumentException("crop too small for complete meter grid");
            cells[i]/=nc[i];sum+=cells[i];
            int weight=M10RIntegralMask.weight(i/22,i%22);weighted+=cells[i]*weight;sw+=weight;
            if(Math.abs((i%22+.5)/22-cx)<=half&&Math.abs((i/22+.5)/16-cy)<=half){spotSum+=cells[i];ns++;}
        }
        double[] regions=M10RMeteringGeometry1X.regionMeans(cells);
        if(ns==0)throw new IllegalArgumentException("empty spot mask");
        return new Measurement(cfg,sum/352,weighted/sw,spotSum/ns,cells,regions,fields);
    }
    private static boolean unit(double v){return Double.isFinite(v)&&v>=0&&v<=1;}
}
