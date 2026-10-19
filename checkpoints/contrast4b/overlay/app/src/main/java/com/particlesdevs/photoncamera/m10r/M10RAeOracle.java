package com.particlesdevs.photoncamera.m10r;

/** Pure-Java port of the recovered M10-R production A-mode allocator.
 * Q8.8 APEX arithmetic and ISO/SV tables mirror tools/m10r_ae_oracle.py.
 */
public final class M10RAeOracle {
    public static final int Q8 = 256;
    public static final int SV_STEP_Q8 = 0x0055;
    public static final int TV_MIN_Q8 = -0x0700;
    public static final int TV_MAX_Q8 = 0x0C00;

    private static final int[] ISO_STATES = {
        3,4,5,6,8,10,12,16,20,25,32,40,50,64,80,100,125,160,200,250,320,400,500,640,
        800,1000,1250,1600,2000,2500,3200,4000,5000,6400,8000,10000,12500,16000,20000,
        25000,32000,40000,50000,64000,80000,100000,125000,160000,200000,250000,320000,400000
    };
    private static final int[] SV_STATES_Q8 = {
        0x0000,0x0055,0x00AE,0x0100,0x0155,0x01AE,0x0200,0x0255,0x02AE,0x0300,0x0355,0x03AE,
        0x0400,0x0455,0x04AE,0x0500,0x0555,0x05AE,0x0600,0x0655,0x06AE,0x0700,0x0755,0x07AE,
        0x0800,0x0855,0x08AE,0x0900,0x0955,0x09AE,0x0A00,0x0A55,0x0AAE,0x0B00,0x0B55,0x0BAE,
        0x0C00,0x0C55,0x0CAE,0x0D00,0x0D55,0x0DAE,0x0E00,0x0E55,0x0EAE,0x0F00,0x0F55,0x0FAE,
        0x1000,0x1055,0x10AE,0x1100
    };
    private static final int[] SV_CORRECTIONS_Q8 = {
        0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,27,37,39,29,31,39,47,28,40,42,29,32,37,36,31,
        44,39,33,31,24,15,6,0,6,39,48,39,39,48,39,39,0,0,0,0,0,0
    };

    private M10RAeOracle() {}

    public static final class Result {
        public final int tvQ8, avQ8, svQ8, dEvQ8, iso, targetEvQ8;
        public final double shutterSeconds;
        public final boolean autoIsoActivated, tvIsoReached, svUpperBoundHit;
        public final int autoIsoSteps;
        public final String constraintReason;
        Result(int tvQ8,int avQ8,int svQ8,int dEvQ8,int iso,double shutterSeconds,int targetEvQ8,
               boolean autoIsoActivated,int autoIsoSteps,boolean tvIsoReached,boolean svUpperBoundHit,
               String constraintReason) {
            this.tvQ8=tvQ8; this.avQ8=avQ8; this.svQ8=svQ8; this.dEvQ8=dEvQ8; this.iso=iso;
            this.shutterSeconds=shutterSeconds; this.targetEvQ8=targetEvQ8;
            this.autoIsoActivated=autoIsoActivated; this.autoIsoSteps=autoIsoSteps;
            this.tvIsoReached=tvIsoReached; this.svUpperBoundHit=svUpperBoundHit;
            this.constraintReason=constraintReason;
        }
        public double tvEv(){ return q8ToEv(tvQ8); }
        public double avEv(){ return q8ToEv(avQ8); }
        public double svEv(){ return q8ToEv(svQ8); }
        public double dEv(){ return q8ToEv(dEvQ8); }
        public double targetEv(){ return q8ToEv(targetEvQ8); }
    }

    public static int s16(int value) {
        int v=value & 0xffff;
        return (v & 0x8000)!=0 ? v-0x10000 : v;
    }
    public static int evToQ8(double ev) {
        double scaled=ev*Q8;
        long rounded=scaled>=0.0 ? (long)Math.floor(scaled+0.5) : (long)Math.ceil(scaled-0.5);
        return s16((int)rounded);
    }
    public static double q8ToEv(int q8) { return s16(q8)/(double)Q8; }
    public static int isoToSvQ8(int iso) {
        if (iso<=0) throw new IllegalArgumentException("ISO must be positive");
        for(int i=0;i<ISO_STATES.length;i++) if(ISO_STATES[i]>=iso) return SV_STATES_Q8[i];
        return SV_STATES_Q8[SV_STATES_Q8.length-1];
    }
    public static int svIndex(int svQ8) {
        int sv=s16(svQ8);
        if(sv<0 || sv>0x1100) return 0;
        int index=(int)((sv/(double)Q8)/0.333);
        return Math.min(index,ISO_STATES.length-1);
    }
    public static int svToIso(int svQ8) { return ISO_STATES[svIndex(svQ8)]; }
    public static int svCorrectionQ8(int svQ8) { return SV_CORRECTIONS_Q8[svIndex(svQ8)]; }
    public static int roundQ8ToStep(int valueQ8,int stepQ8) {
        int value=s16(valueQ8), step=s16(stepQ8);
        if(step<=0) throw new IllegalArgumentException("step must be positive");
        boolean negative=value<0;
        int v=negative ? -value : value;
        if(step>Q8) step%=Q8;
        if(step>=0x81 && step<=0xff) step%=0x80;
        if(step==0) return s16(negative ? -v : v);
        int remainder=v%Q8;
        if(remainder==0xff) v+=1;
        else if((remainder%step)!=0) {
            if((remainder%step)<(step>>1)) while(((v%Q8)%step)!=0) v-=1;
            else while(((v%Q8)%step)!=0) v+=1;
        }
        return s16(negative ? -v : v);
    }
    private static int clamp(int value,int lower,int upper) {
        int v=s16(value),lo=s16(lower),hi=s16(upper);
        if(lo>hi) throw new IllegalArgumentException("lower exceeds upper");
        return Math.min(Math.max(v,lo),hi);
    }

    public static Result solveAMode(double bvEv,double avEv,double tvIsoEv,
                                    int svMinIso,int svMaxIso) {
        return solveAModeQ8(evToQ8(bvEv),evToQ8(avEv),0,0,evToQ8(tvIsoEv),
                isoToSvQ8(svMinIso),isoToSvQ8(svMaxIso),TV_MIN_Q8,TV_MAX_Q8);
    }

    public static Result solveAModeQ8(int bvQ8,int avQ8,int overrideQ8,int exposureCorrectionQ8,
                                      int tvIsoQ8,int svMinQ8,int svMaxQ8,int tvMinQ8,int tvMaxQ8) {
        int av=clamp(avQ8,0,0x0c00);
        int svMin=s16(svMinQ8), svMax=s16(svMaxQ8);
        if(svMin>svMax) throw new IllegalArgumentException("SV minimum exceeds maximum");
        int selectedSv=clamp(svMin,svMin,svMax);
        int initialCorrection=svCorrectionQ8(selectedSv);
        int target=s16(s16(bvQ8)+selectedSv-s16(overrideQ8)-s16(exposureCorrectionQ8)-initialCorrection);
        int requestedTv=s16(target-av);
        int finalTv=requestedTv;
        int finalSv=roundQ8ToStep(selectedSv,SV_STEP_Q8);
        int moves=0;
        while(requestedTv<s16(tvIsoQ8) && finalSv<=s16(svMax-SV_STEP_Q8)) {
            finalSv=roundQ8ToStep(finalSv+SV_STEP_Q8,SV_STEP_Q8);
            finalTv=s16(finalTv+SV_STEP_Q8);
            requestedTv=s16(requestedTv+SV_STEP_Q8);
            moves++;
        }
        finalTv=clamp(finalTv,tvMinQ8,tvMaxQ8);
        int finalCorrection=svCorrectionQ8(finalSv);
        int dEv=s16(s16(bvQ8)+finalSv-finalTv-av-s16(overrideQ8)-s16(exposureCorrectionQ8)-finalCorrection);
        boolean tvIsoReached=requestedTv>=s16(tvIsoQ8);
        boolean svUpper=requestedTv<s16(tvIsoQ8);
        String reason;
        if(moves==0 && tvIsoReached) reason="tv_iso_already_satisfied";
        else if(svUpper) reason="sv_max_before_tv_iso";
        else reason="sv_raised_to_tv_iso";
        return new Result(finalTv,av,finalSv,dEv,svToIso(finalSv),Math.pow(2.0,-q8ToEv(finalTv)),target,
                moves>0,moves,tvIsoReached,svUpper,reason);
    }
}
