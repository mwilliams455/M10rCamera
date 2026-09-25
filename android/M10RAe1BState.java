package com.particlesdevs.photoncamera.m10r;

/** Thread-safe telemetry handoff from capture selection to the saved-image sidecar. */
public final class M10RAe1BState {
    private M10RAe1BState() {}

    public static final class Snapshot {
        public final boolean valid, sensorClampApplied;
        public final long previewExposureNs, oracleExposureNs, appliedExposureNs;
        public final int previewIso, oracleIso, appliedIso;
        public final double aperture, focalLengthMm, focalLength35mm;
        public final double previewTvEv, previewAvEv, previewSvEv, previewBvEv;
        public final double tvIsoEv, exposureCorrectionEv, predictedDEv;
        public final String constraintReason;
        public final long generation;

        Snapshot(boolean valid,boolean sensorClampApplied,long previewExposureNs,int previewIso,
                 double aperture,double focalLengthMm,double focalLength35mm,
                 double previewTvEv,double previewAvEv,double previewSvEv,double previewBvEv,
                 double tvIsoEv,double exposureCorrectionEv,long oracleExposureNs,int oracleIso,
                 long appliedExposureNs,int appliedIso,double predictedDEv,String constraintReason,
                 long generation) {
            this.valid=valid; this.sensorClampApplied=sensorClampApplied;
            this.previewExposureNs=previewExposureNs; this.previewIso=previewIso;
            this.aperture=aperture; this.focalLengthMm=focalLengthMm; this.focalLength35mm=focalLength35mm;
            this.previewTvEv=previewTvEv; this.previewAvEv=previewAvEv; this.previewSvEv=previewSvEv;
            this.previewBvEv=previewBvEv; this.tvIsoEv=tvIsoEv; this.exposureCorrectionEv=exposureCorrectionEv;
            this.oracleExposureNs=oracleExposureNs; this.oracleIso=oracleIso;
            this.appliedExposureNs=appliedExposureNs; this.appliedIso=appliedIso;
            this.predictedDEv=predictedDEv; this.constraintReason=constraintReason; this.generation=generation;
        }
    }

    private static Snapshot snapshot = new Snapshot(false,false,0,0,Double.NaN,Double.NaN,Double.NaN,
            Double.NaN,Double.NaN,Double.NaN,Double.NaN,Double.NaN,0.0,0,0,0,0,
            Double.NaN,"not_recorded",0);

    public static synchronized void record(M10RAe1BPolicy.Decision d, double focalLengthMm,
                                           long oracleExposureNs,int oracleIso,
                                           long appliedExposureNs,int appliedIso,
                                           boolean sensorClampApplied) {
        long generation=snapshot.generation+1;
        if(d==null || !d.valid || d.oracle==null) {
            snapshot=new Snapshot(false,sensorClampApplied,0,0,Double.NaN,focalLengthMm,Double.NaN,
                    Double.NaN,Double.NaN,Double.NaN,Double.NaN,Double.NaN,0.0,
                    oracleExposureNs,oracleIso,appliedExposureNs,appliedIso,Double.NaN,
                    "invalid_input",generation);
            return;
        }
        snapshot=new Snapshot(true,sensorClampApplied,d.previewExposureNs,d.previewIso,d.aperture,
                focalLengthMm,d.focalLength35mm,d.previewTvEv,d.previewAvEv,d.previewSvEv,d.previewBvEv,
                d.tvIsoEv,d.exposureCorrectionEv,oracleExposureNs,oracleIso,appliedExposureNs,appliedIso,
                d.oracle.dEv(),d.oracle.constraintReason,generation);
    }

    public static synchronized Snapshot snapshot() { return snapshot; }
}
