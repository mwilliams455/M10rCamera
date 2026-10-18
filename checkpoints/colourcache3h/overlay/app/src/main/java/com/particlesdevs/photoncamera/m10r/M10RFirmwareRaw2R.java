package com.particlesdevs.photoncamera.m10r;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;

/** Read-only phone-code evidence. The Leica still Q8 weights are a hypothesis
 * on this sensor, not a calibrated Leica live-view statistics producer. */
public final class M10RFirmwareRaw2R {
    private M10RFirmwareRaw2R() {}
    public static final class Sample {
        public final int width,height,cfa,white;
        private final double[] black;
        private final long[] codeSums,atWhite,aboveWhite,nearWhite,ySums;
        private final int[] counts;
        private final double[] correctedSums;
        Sample(int w,int h,int c,int white,double[] black,long[] codes,double[] corrected,
                long[] at,long[] above,long[] near,long[] y,int[] n) {
            width=w;height=h;cfa=c;this.white=white;this.black=black.clone();
            codeSums=codes;correctedSums=corrected;atWhite=at;aboveWhite=above;nearWhite=near;ySums=y;counts=n;
        }
        public double[] black(){return black.clone();}
        public long[] codeSums(){return codeSums.clone();}
        public double[] correctedSums(){return correctedSums.clone();}
        public long[] atWhite(){return atWhite.clone();}
        public long[] aboveWhite(){return aboveWhite.clone();}
        public long[] nearWhite(){return nearWhite.clone();}
        public int[] counts(){return counts.clone();}
        public long[] ySums(){return ySums.clone();}
        public long[] meanYCodes() {
            long[] out=new long[352];
            for(int i=0;i<352;i++)out[i]=ySums[i]/counts[i];
            return out;
        }
    }
    // Canonical [R, G on R row, G on B row, B], independently of Camera2 gain order.
    private static final int[][] CHANNEL={{0,1,2,3},{1,0,3,2},{2,3,0,1},{3,2,1,0}};
    public static Sample sample(ByteBuffer data,int offset,int stride,int width,int height,int cfa,
            double[] black,int white,M10RMetering1U.Config cfg) {
        if(data==null||cfg==null||width<208||height<160||width>8192||height>8192
                ||cfa<0||cfa>3||offset<0||stride<2L*width
                ||(long)offset+(height-1L)*stride+width*2L>data.limit()
                ||black==null||black.length!=4||white<2||white>65535)
            throw new IllegalArgumentException("shadow RAW16 layout");
        for(double b:black)if(!Double.isFinite(b)||b<0||b>=white)
            throw new IllegalArgumentException("shadow black/white");
        double l=Math.max(16,cfg.left*width),t=Math.max(16,cfg.top*height);
        double r=Math.min(width-16,cfg.right*width),b=Math.min(height-16,cfg.bottom*height);
        if(r<=l||b<=t)throw new IllegalArgumentException("shadow crop");
        long[] codes=new long[1408],at=new long[1408],above=new long[1408],near=new long[1408],ys=new long[352];
        double[] corrected=new double[1408],quad=new double[4];int[] counts=new int[352];
        ByteBuffer src=data.duplicate().order(ByteOrder.LITTLE_ENDIAN);
        for(int y=0;y<128;y++)for(int x=0;x<176;x++) {
            int px=M10RMetering1U.sampleCoordinate(x,176,width),py=M10RMetering1U.sampleCoordinate(y,128,height);
            // Match existing meter membership; read the enclosing even-origin CFA tile.
            if(px+.5<l||px+.5>=r||py+.5<t||py+.5>=b)continue;
            int cell=(int)((py+.5-t)/(b-t)*16)*22+(int)((px+.5-l)/(r-l)*22);
            int sx=px&~1,sy=py&~1;counts[cell]++;
            for(int p=0;p<4;p++) {
                int code=src.getShort(offset+(sy+(p>>1))*stride+(sx+(p&1))*2)&65535;
                int c=CHANNEL[cfa][p],i=cell*4+c;
                double v=Math.max(0,code-black[p]);quad[c]=v;
                codes[i]+=code;corrected[i]+=v;
                if(code==white)at[i]++;if(code>white)above[i]++;
                if(v>=.98*(white-black[p]))near[i]++;
            }
            // No white normalization, WB, LSC, gray target, hidden-sample repair or upper clamp.
            ys[cell]+=(long)Math.floor((83*quad[0]+45*quad[1]+45*quad[2]+83*quad[3]+128)/256);
        }
        for(int n:counts)if(n==0)throw new IllegalArgumentException("shadow incomplete crop grid");
        return new Sample(width,height,cfa,white,black,codes,corrected,at,above,near,ys,counts);
    }
}
