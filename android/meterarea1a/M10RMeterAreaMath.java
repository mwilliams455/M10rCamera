package com.particlesdevs.photoncamera.m10r;

import java.nio.ByteBuffer;

/** Pure host-testable stratified area reducer. Not an exact full-resolution box filter. */
public final class M10RMeterAreaMath {
    public static final int ROWS=16, COLS=22, SUB=8;
    public static final int WIDTH=ROWS*SUB, HEIGHT=COLS*SUB;
    private static final double[] LINEAR=new double[256];
    static {
        for (int i=0;i<256;i++) {
            double c=i/255.0;
            LINEAR[i]=c<=0.04045 ? c/12.92 : Math.pow((c+0.055)/1.055,2.4);
        }
    }
    private M10RMeterAreaMath() {}
    public static final class Grid {
        public final double[] code=new double[ROWS*COLS];
        public final double[] linear=new double[ROWS*COLS];
        public final double[] green=new double[ROWS*COLS];
        public final double[] proxyBeforeAverage=new double[ROWS*COLS];
        public final double[][] linearPhases=new double[4][ROWS*COLS];
        public final double exponent;
        Grid(double exponent) { this.exponent=exponent; }
    }
    public static double decode(int code) { return LINEAR[code]; }
    public static Grid reduce(ByteBuffer rgba, double exponent) {
        if (rgba==null || rgba.remaining()!=WIDTH*HEIGHT*4
                || !Double.isFinite(exponent) || exponent<=0)
            throw new IllegalArgumentException("invalid area buffer/exponent");
        Grid out=new Grid(exponent);
        ByteBuffer b=rgba.duplicate();
        for (int fy=0;fy<HEIGHT;fy++) {
            int col=fy/SUB;
            for (int fx=0;fx<WIDTH;fx++) {
                int row=fx/SUB, i=row*COLS+col;
                int r=b.get()&255, g=b.get()&255, bl=b.get()&255;
                b.get();
                double y=0.2126*LINEAR[r]+0.7152*LINEAR[g]+0.0722*LINEAR[bl];
                out.code[i]+=(0.2126*r+0.7152*g+0.0722*bl)/255.0;
                out.linear[i]+=y;
                out.green[i]+=LINEAR[g];
                out.proxyBeforeAverage[i]+=Math.pow(Math.max(0,Math.min(1,y)),exponent);
                out.linearPhases[(fy&1)*2+(fx&1)][i]+=y;
            }
        }
        for (int i=0;i<ROWS*COLS;i++) {
            out.code[i]/=SUB*SUB; out.linear[i]/=SUB*SUB;
            out.green[i]/=SUB*SUB; out.proxyBeforeAverage[i]/=SUB*SUB;
            for (int p=0;p<4;p++) out.linearPhases[p][i]/=(SUB*SUB/4);
        }
        return out;
    }
    public static double[] proxyAfterAverage(double[] grid,double exponent) {
        double[] out=grid.clone();
        for(int i=0;i<out.length;i++) out[i]=Math.pow(Math.max(0,Math.min(1,out[i])),exponent);
        return out;
    }
}
