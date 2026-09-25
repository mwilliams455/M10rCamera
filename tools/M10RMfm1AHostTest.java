import com.particlesdevs.photoncamera.m10r.M10RMfm1A;

public final class M10RMfm1AHostTest {
    private static void near(double a,double b,double eps,String name){
        if(Math.abs(a-b)>eps) throw new AssertionError(name+" "+a+" vs "+b);
    }

    public static void main(String[] args){
        double[] flat=new double[16*22];
        for(int i=0;i<flat.length;i++) flat[i]=0.25;
        M10RMfm1A.Decision neutral=M10RMfm1A.evaluate(flat);
        if(!neutral.valid || neutral.wouldApply || neutral.recommendedEv!=0.0)
            throw new AssertionError("flat neutral");

        // Strong upper-bright / lower-dark synthetic backlight field.
        double[] backlit=new double[16*22];
        for(int r=0;r<16;r++) for(int c=0;c<22;c++) {
            double v=r<5 ? 0.90 : (r>9 ? 0.08 : 0.20);
            if(c<3 || c>18) v*=1.25;
            backlit[r*22+c]=v;
        }
        M10RMfm1A.Decision pos=M10RMfm1A.evaluate(backlit);
        if(!pos.valid) throw new AssertionError("backlit invalid");
        if(!(pos.recommendedEv>=0.0 && pos.recommendedEv<=M10RMfm1A.MAX_POSITIVE_EV))
            throw new AssertionError("positive bounds");
        if(pos.sceneSpreadEv<=0.5) throw new AssertionError("spread missing");

        // Bright center / dark edges may request bounded negative moderation.
        double[] centerBright=new double[16*22];
        for(int r=0;r<16;r++) for(int c=0;c<22;c++) {
            boolean center=r>=4&&r<12&&c>=5&&c<17;
            centerBright[r*22+c]=center?0.8:0.15;
        }
        M10RMfm1A.Decision neg=M10RMfm1A.evaluate(centerBright);
        if(!neg.valid) throw new AssertionError("negative invalid");
        if(neg.recommendedEv < -M10RMfm1A.MAX_NEGATIVE_EV || neg.recommendedEv > M10RMfm1A.MAX_POSITIVE_EV)
            throw new AssertionError("negative bounds");

        M10RMfm1A.Decision bad=M10RMfm1A.evaluate(new double[2]);
        if(bad.valid) throw new AssertionError("bad grid valid");

        System.out.println("M10RMfm1AHostTest PASS");
    }
}
