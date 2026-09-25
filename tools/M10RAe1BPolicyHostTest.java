import com.particlesdevs.photoncamera.m10r.M10RAe1BPolicy;

public final class M10RAe1BPolicyHostTest {
    private static void near(double got,double expected,double eps,String name) {
        if(Math.abs(got-expected)>eps) throw new AssertionError(name+" got="+got+" expected="+expected);
    }
    public static void main(String[] args) {
        M10RAe1BPolicy.Decision d=M10RAe1BPolicy.solve(
                66440677L,59,1.63,23.950196650949387,0.0,100,50000);
        if(!d.valid) throw new AssertionError("decision invalid");
        near(d.previewBvEv,1.0827464768840445,1e-7,"preview Bv");
        near(d.tvIsoEv,4.5,1e-12,"1/f TV");
        if(d.oracle.iso!=100) throw new AssertionError("actual-Bv ISO");
        near(d.oracle.shutterSeconds,0.04220605362162608,1e-12,"actual-Bv shutter");

        M10RAe1BPolicy.Decision center=M10RAe1BPolicy.solve(
                66440677L,59,1.63,23.950196650949387,2.76459421221579,100,50000);
        // Positive exposure correction is deliberately brighter: it lowers target Tv.
        if(center.oracle.iso < 100) throw new AssertionError("invalid ISO");
        if(!(center.oracle.shutterSeconds*center.oracle.iso
                > d.oracle.shutterSeconds*d.oracle.iso)) throw new AssertionError("positive EC not brighter");

        near(M10RAe1BPolicy.oneOverFTv(23.950196650949387),4.5,1e-12,"half-stop 1/f");
        System.out.println("M10RAe1BPolicyHostTest PASS");
    }
}
