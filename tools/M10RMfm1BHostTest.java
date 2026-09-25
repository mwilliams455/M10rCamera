import com.particlesdevs.photoncamera.m10r.M10RMfm1B;

public final class M10RMfm1BHostTest {
    public static void main(String[] args){
        double[] flat=new double[16*22];
        for(int i=0;i<flat.length;i++) flat[i]=0.25;
        M10RMfm1B.Decision neutral=M10RMfm1B.evaluate(flat);
        if(!neutral.valid || neutral.wouldApply || neutral.recommendedEv!=0.0)
            throw new AssertionError("flat neutral");

        // Rotation-invariant side backlight: one side is very bright while
        // the broad inner field contains a much darker subject-like area.
        double[] sideBacklit=new double[16*22];
        for(int r=0;r<16;r++) for(int c=0;c<22;c++) {
            double v=0.10;
            if(c<6) v=0.85;
            if(c>=8 && c<=15 && r>=4 && r<12) v=0.055;
            sideBacklit[r*22+c]=v;
        }
        M10RMfm1B.Decision pos=M10RMfm1B.evaluate(sideBacklit);
        if(!pos.valid || !pos.wouldApply)
            throw new AssertionError("side backlight did not trigger");
        if(!(pos.recommendedEv>0.20 && pos.recommendedEv<=M10RMfm1B.MAX_POSITIVE_EV))
            throw new AssertionError("side backlight magnitude "+pos.recommendedEv);
        if(!(pos.brightestSideVsInnerEv>0.45))
            throw new AssertionError("side geometry missing");

        // The same geometry rotated by 180 degrees must still be recognized.
        double[] sideBacklitRotated=new double[16*22];
        for(int r=0;r<16;r++) for(int c=0;c<22;c++) {
            sideBacklitRotated[(15-r)*22+(21-c)]=sideBacklit[r*22+c];
        }
        M10RMfm1B.Decision posRot=M10RMfm1B.evaluate(sideBacklitRotated);
        if(!posRot.valid || !posRot.wouldApply || posRot.recommendedEv<=0.20)
            throw new AssertionError("rotated side backlight did not trigger");

        // Bright center / dark edges must never be interpreted as positive backlight.
        double[] centerBright=new double[16*22];
        for(int r=0;r<16;r++) for(int c=0;c<22;c++) {
            boolean center=r>=4&&r<12&&c>=5&&c<17;
            centerBright[r*22+c]=center?0.80:0.15;
        }
        M10RMfm1B.Decision center=M10RMfm1B.evaluate(centerBright);
        if(!center.valid) throw new AssertionError("center bright invalid");
        if(center.recommendedEv>0.0) throw new AssertionError("center bright positive assist");
        if(center.recommendedEv < -M10RMfm1B.MAX_NEGATIVE_EV)
            throw new AssertionError("negative bound");

        M10RMfm1B.Decision bad=M10RMfm1B.evaluate(new double[2]);
        if(bad.valid) throw new AssertionError("bad grid valid");

        System.out.println("M10RMfm1BHostTest PASS");
    }
}
