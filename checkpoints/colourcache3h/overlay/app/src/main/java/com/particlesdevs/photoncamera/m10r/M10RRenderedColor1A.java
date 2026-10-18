package com.particlesdevs.photoncamera.m10r;

/**
 * Firmware-derived capture-state and rendered-coefficient preparation.
 * This preserves the current native pixel loop, not the ISP's MAC arithmetic.
 * Nominal 2856/6504 K is the validated fixture bridge, not a decoded enum parser.
 */
final class M10RRenderedColor1A {
    static final String REVISION = "M10R_RENDERED_COLOR1A_CAPTURE_CC0_CC1";
    private static final double[] D50 = {.3457, .3585};
    private static final double[] BRADFORD = {
        .8951,.2664,-.1614, -.7502,1.7135,.0367, .0389,-.0685,1.0296
    };
    // Stored firmware values, intentionally not inverse3(BRADFORD).
    private static final double[] BRADFORD_INV = {
        .9869929,-.1470543,.1599627, .4323053,.5183603,.0492912,
        -.0085287,.0400428,.9684867
    };
    private static final double[] PCS = {
        1.346,-.2556,-.0511, -.5446,1.5082,.0205, 0,0,1.2123
    };
    private final double[] profileA, profileD65;
    private final double[][] locus;

    M10RRenderedColor1A(double[] a, double[] d65, double[][] locus) {
        profileA = matrix(a); profileD65 = matrix(d65);
        for (int i=0;i<9;i++) {
            profileA[i] = Math.rint(profileA[i]*4096.0)/4096.0;
            profileD65[i] = Math.rint(profileD65[i]*4096.0)/4096.0;
        }
        if (locus==null || locus.length!=31) throw new IllegalArgumentException("locus");
        this.locus = new double[locus.length][];
        for (int i=0;i<locus.length;i++) {
            if (locus[i]==null || locus[i].length!=5) throw new IllegalArgumentException("locus_row");
            this.locus[i]=locus[i].clone();
            for (double x:this.locus[i]) finite(x);
        }
    }

    /** False is an exact baseline selection. Unvalidated states also retain both matrices. */
    Result select(boolean enabled, int[] gains, double[] baselineWork, double[] baselineOutput) {
        double[] bw=matrix(baselineWork), bo=matrix(baselineOutput);
        if (!enabled) return new Result(bw,bo,"disabled");
        try { return reconstruct(gains,bo); }
        catch (IllegalArgumentException e) {
            return new Result(bw,bo,"capture_state_rejected:"+e.getMessage());
        }
    }

    private Result reconstruct(int[] gains, double[] output) {
        if (gains==null || gains.length!=3) throw new IllegalArgumentException("gains_shape");
        double[] neutral=new double[3];
        for (int i=0;i<3;i++) {
            if (gains[i]<1 || gains[i]>2000) throw new IllegalArgumentException("gains_range");
            neutral[i]=256.0/gains[i];
        }
        double[] xy=D50.clone(); boolean converged=false; int passes=0;
        for (int p=0;p<15;p++) {
            double[] w=vec(inverse(profile(temperature(xy))),neutral);
            double sum=w[0]+w[1]+w[2];
            if (!(sum>0) || !Double.isFinite(sum)) throw new IllegalArgumentException("white_sum");
            double[] next={w[0]/sum,w[1]/sum};
            double delta=Math.abs(next[0]-xy[0])+Math.abs(next[1]-xy[1]);
            passes=p+1;
            if (delta<1e-7) { xy=next;converged=true;break; }
            xy=p==14 ? new double[]{(next[0]+xy[0])*.5,(next[1]+xy[1])*.5} : next;
        }
        if (!converged) throw new IllegalArgumentException("white_not_converged");
        double kelvin=temperature(xy);
        double[] adapted=mul(profile(kelvin),adapt(D50,xy));
        double[] work=mul(PCS,inverse(adapted));
        double[] cc0=new double[9];
        for (int i=0;i<9;i++) cc0[i]=work[i]*neutral[i%3];
        Quantized q0=quantize(cc0,-1),q1=quantize(output,0);
        if (q0.clipped!=0 || q1.clipped!=0) throw new IllegalArgumentException("coefficient_clipped");
        double[] effective=new double[9];
        for (int i=0;i<9;i++) effective[i]=q0.decoded[i]/neutral[i%3];
        return new Result(effective,q1.decoded,neutral,xy,kelvin,passes,q0,q1);
    }

    static final class Result {
        final double[] targetToWorking, workingToOutput, neutral, whiteXy;
        final boolean applied;
        final String reason;
        final double kelvin;
        final int passes;
        final Quantized cc0, cc1;
        Result(double[] work,double[] output,String reason) {
            targetToWorking=work;workingToOutput=output;this.reason=reason;applied=false;
            neutral=null;whiteXy=null;kelvin=Double.NaN;passes=0;cc0=null;cc1=null;
        }
        Result(double[] work,double[] output,double[] neutral,double[] xy,double kelvin,
               int passes,Quantized cc0,Quantized cc1) {
            targetToWorking=work;workingToOutput=output;this.neutral=neutral;whiteXy=xy;
            this.kelvin=kelvin;this.passes=passes;this.cc0=cc0;this.cc1=cc1;
            applied=true;reason="applied";
        }
    }
    static final class Quantized {
        final int scale, denominator, clipped;
        final int[] integers;
        final double[] decoded;
        Quantized(int scale,int clipped,int[] integers) {
            this.scale=scale;denominator=1<<(9-scale);this.clipped=clipped;this.integers=integers;
            decoded=new double[9];
            for (int i=0;i<9;i++) decoded[i]=integers[i]/(double)denominator;
        }
    }
    /** scale=-1 selects 0,1,2 then saturated 3; range testing follows rounding. */
    static Quantized quantize(double[] values,int scale) {
        double[] m=matrix(values);
        if (scale < -1 || scale > 3) throw new IllegalArgumentException("scale");
        for (int s=scale<0?0:scale;s<=3;s++) {
            int denominator=1<<(9-s),clipped=0;
            int[] q=new int[9];
            for (int i=0;i<9;i++) {
                double v=m[i]*denominator;
                double rounded=Math.copySign(Math.floor(Math.abs(v)+.5),v);
                if (rounded < -2048 || rounded > 2047) clipped++;
                q[i]=(int)Math.max(-2048,Math.min(2047,rounded));
            }
            if (scale>=0 || clipped==0 || s==3) return new Quantized(s,clipped,q);
        }
        throw new AssertionError("scale selection");
    }
    private double[] profile(double kelvin) {
        double f=Math.max(0,Math.min(1,(1/kelvin-1/6504.0)/(1/2856.0-1/6504.0)));
        double[] p=new double[9];
        for (int i=0;i<9;i++) p[i]=f*profileA[i]+(1-f)*profileD65[i];
        return p;
    }
    private double temperature(double[] xy) {
        double den=1.5-xy[0]+6*xy[1];
        if (!(den>0) || !Double.isFinite(xy[0]+xy[1])) throw new IllegalArgumentException("white_coordinate");
        double u=2*xy[0]/den,v=3*xy[1]/den,previous=Double.NaN;
        for (int i=1;i<locus.length;i++) {
            double[] r=locus[i];double distance=((v-r[2])-(u-r[1])*r[3])/r[4];
            if (distance<=0) {
                double current=-distance;
                double f=i==1?0:previous+current>0?current/(previous+current):.5;
                double mired=locus[i-1][0]*f+r[0]*(1-f);
                return mired>0?1e6/mired:100000;
            }
            previous=distance;
        }
        return 1e6/locus[locus.length-1][0];
    }
    private static double[] xyz(double[] xy) {
        if (!(xy[1]>0) || xy[0]<0 || xy[0]+xy[1]>1) throw new IllegalArgumentException("white_domain");
        return new double[]{xy[0]/xy[1],1,(1-xy[0]-xy[1])/xy[1]};
    }
    private static double[] adapt(double[] source,double[] dest) {
        double[] s=vec(BRADFORD,xyz(source)),d=vec(BRADFORD,xyz(dest));
        double[] diag={d[0]/s[0],0,0,0,d[1]/s[1],0,0,0,d[2]/s[2]};
        return mul(mul(BRADFORD_INV,diag),BRADFORD);
    }
    private static double[] matrix(double[] m) {
        if (m==null || m.length!=9) throw new IllegalArgumentException("matrix_shape");
        double[] copy=m.clone();for (double x:copy) finite(x);return copy;
    }
    private static void finite(double x) {
        if (!Double.isFinite(x)) throw new IllegalArgumentException("nonfinite");
    }
    private static double[] mul(double[] a,double[] b) {
        double[] o=new double[9];
        for (int r=0;r<3;r++) for (int c=0;c<3;c++)
            o[r*3+c]=a[r*3]*b[c]+a[r*3+1]*b[3+c]+a[r*3+2]*b[6+c];
        return o;
    }
    private static double[] vec(double[] m,double[] v) {
        return new double[]{m[0]*v[0]+m[1]*v[1]+m[2]*v[2],
                m[3]*v[0]+m[4]*v[1]+m[5]*v[2],m[6]*v[0]+m[7]*v[1]+m[8]*v[2]};
    }
    private static double[] inverse(double[] m) {
        double a=m[0],b=m[1],c=m[2],d=m[3],e=m[4],f=m[5],g=m[6],h=m[7],i=m[8];
        double det=a*(e*i-f*h)-b*(d*i-f*g)+c*(d*h-e*g);
        if (!Double.isFinite(det) || Math.abs(det)<1e-15) throw new IllegalArgumentException("singular_matrix");
        double s=1/det;
        return new double[]{(e*i-f*h)*s,(c*h-b*i)*s,(b*f-c*e)*s,
                (f*g-d*i)*s,(a*i-c*g)*s,(c*d-a*f)*s,
                (d*h-e*g)*s,(b*g-a*h)*s,(a*e-b*d)*s};
    }
}
