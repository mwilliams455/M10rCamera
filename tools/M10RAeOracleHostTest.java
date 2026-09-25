import com.particlesdevs.photoncamera.m10r.M10RAeOracle;

public final class M10RAeOracleHostTest {
    private static void near(double got, double expected, double eps, String name) {
        if (Math.abs(got - expected) > eps) {
            throw new AssertionError(name + " got=" + got + " expected=" + expected);
        }
    }

    public static void main(String[] args) {
        if (M10RAeOracle.isoToSvQ8(100) != 0x0500) throw new AssertionError("ISO100 SV");
        if (M10RAeOracle.isoToSvQ8(200) != 0x0600) throw new AssertionError("ISO200 SV");
        if (M10RAeOracle.svToIso(0x0800) != 800) throw new AssertionError("SV8 ISO");

        M10RAeOracle.Result bright = M10RAeOracle.solveAMode(4.0, 1.4, 5.0, 100, 50000);
        near(bright.tvEv(), 7.49609375, 1e-12, "bright tv");
        if (bright.iso != 100 || bright.autoIsoSteps != 0) throw new AssertionError("bright allocation");

        M10RAeOracle.Result dark = M10RAeOracle.solveAMode(0.0, 2.0, 6.0, 100, 6400);
        near(dark.tvEv(), 6.21484375, 1e-12, "dark tv");
        near(dark.svEv(), 8.33203125, 1e-12, "dark sv");
        if (dark.iso != 1000 || dark.autoIsoSteps != 10) throw new AssertionError("dark allocation");
        if (!"sv_raised_to_tv_iso".equals(dark.constraintReason)) throw new AssertionError("dark reason");

        if (M10RAeOracle.evToQ8(-0.5) != -128) throw new AssertionError("negative half rounding");
        System.out.println("M10RAeOracleHostTest PASS");
    }
}
