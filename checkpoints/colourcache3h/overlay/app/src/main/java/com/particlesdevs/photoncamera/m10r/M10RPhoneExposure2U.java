package com.particlesdevs.photoncamera.m10r;

/**
 * Phone-domain exposure allocation. The firmware oracle remains untouched and
 * supplies an ISO preference, not a calibrated phone brightness measurement.
 * Time times reported ISO is a nominal control target, not measured sensor gain.
 */
public final class M10RPhoneExposure2U {
    public static final String REVISION="M10R_PHONE_EXPOSURE2U_NOMINAL_TARGET";
    private M10RPhoneExposure2U() {}

    public static final class Result {
        public final long exposureNs;
        public final int iso;
        public final boolean physicalClamped;
        public final double targetProduct,oracleProduct,targetMinusOracleEv,residualEv;
        private Result(long ns,int iso,boolean clamped,double target,double oracle){
            exposureNs=ns;this.iso=iso;physicalClamped=clamped;
            targetProduct=target;oracleProduct=oracle;
            targetMinusOracleEv=log2(target/oracle);
            residualEv=log2(((double)ns*iso)/target);
        }
    }

    private static double log2(double x){return Math.log(x)/Math.log(2);}
    private static long clampTime(double ns,long min,long max){
        return Math.max(min,Math.min(max,Math.round(ns)));
    }

    public static Result allocate(M10RAe1BPolicy.Decision d,long minNs,long maxNs,int minIso,int maxIso){
        if(d==null||!d.valid||d.oracle==null||minNs<=0||maxNs<minNs||minIso<=0||maxIso<minIso)
            throw new IllegalArgumentException("valid decision and physical ranges required");
        // Use the reference and its explicit delta, before any Leica SV correction,
        // Q8 rounding or firmware shutter clamp. Already-applied EV is removed by
        // the caller's reference binding; do not apply it a second time here.
        double target=(double)d.previewExposureNs*d.previewIso*Math.pow(2,d.exposureCorrectionEv);
        if(!(target>0)||!Double.isFinite(target))throw new IllegalArgumentException("invalid phone target");
        long oracleNs=Math.max(1,Math.round(d.oracle.shutterSeconds*1e9));
        double preferredNs=target/d.oracle.iso;
        long ns=clampTime(preferredNs,minNs,maxNs);
        // Clamp before narrowing to int: long shutter/ISO transfers must not wrap.
        long wantedIso=Math.round(target/ns);
        int iso=(int)Math.max(minIso,Math.min((long)maxIso,wantedIso));
        ns=clampTime(target/iso,minNs,maxNs);
        boolean clamped=preferredNs<minNs||preferredNs>maxNs
                ||d.oracle.iso<minIso||d.oracle.iso>maxIso;
        return new Result(ns,iso,clamped,target,(double)oracleNs*d.oracle.iso);
    }
}
