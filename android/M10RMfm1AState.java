package com.particlesdevs.photoncamera.m10r;

/** Still-bound MFM1A telemetry. */
public final class M10RMfm1AState {
    private M10RMfm1AState() {}

    public static final class Snapshot {
        public final boolean valid;
        public final long liveGridGeneration;
        public final double userExposureCorrectionEv;
        public final double mfmExposureCorrectionEv;
        public final double totalExposureCorrectionEv;
        public final M10RMfm1A.Decision decision;
        public final long generation;

        Snapshot(boolean valid,long liveGridGeneration,double userExposureCorrectionEv,
                 double mfmExposureCorrectionEv,double totalExposureCorrectionEv,
                 M10RMfm1A.Decision decision,long generation) {
            this.valid=valid; this.liveGridGeneration=liveGridGeneration;
            this.userExposureCorrectionEv=userExposureCorrectionEv;
            this.mfmExposureCorrectionEv=mfmExposureCorrectionEv;
            this.totalExposureCorrectionEv=totalExposureCorrectionEv;
            this.decision=decision; this.generation=generation;
        }
    }

    private static Snapshot snapshot = new Snapshot(false,0,0.0,0.0,0.0,null,0);

    public static synchronized void record(long liveGridGeneration,double userEv,
                                           double mfmEv,double totalEv,
                                           M10RMfm1A.Decision decision) {
        snapshot=new Snapshot(decision!=null && decision.valid,liveGridGeneration,userEv,mfmEv,totalEv,
                decision,snapshot.generation+1);
    }

    public static synchronized Snapshot snapshot() { return snapshot; }
}
