package com.particlesdevs.photoncamera.m10r;

/** Still-bound telemetry for MFM1D SOURCEPROXY1A selection. */
public final class M10RMfm1DSourceState {
    private M10RMfm1DSourceState() {}

    public static final class Snapshot {
        public final boolean valid;
        public final String profileId;
        public final double exponent;
        public final String calibrationStatus;
        public final String basis;
        public final double sensorWidthMm;
        public final double physicalFocalMm;
        public final double aperture;
        public final int cfa;
        public final long generation;

        Snapshot(boolean valid,String profileId,double exponent,String calibrationStatus,
                 String basis,double sensorWidthMm,double physicalFocalMm,double aperture,
                 int cfa,long generation) {
            this.valid=valid;
            this.profileId=profileId;
            this.exponent=exponent;
            this.calibrationStatus=calibrationStatus;
            this.basis=basis;
            this.sensorWidthMm=sensorWidthMm;
            this.physicalFocalMm=physicalFocalMm;
            this.aperture=aperture;
            this.cfa=cfa;
            this.generation=generation;
        }
    }

    private static Snapshot snapshot = new Snapshot(
            false,"UNSET",1.0,"unset","unset",
            Double.NaN,Double.NaN,Double.NaN,-1,0);

    public static synchronized void record(M10RMfm1DSourceProxy.Profile p) {
        if (p == null) {
            snapshot=new Snapshot(false,"UNSET",1.0,"unset","unset",
                    Double.NaN,Double.NaN,Double.NaN,-1,snapshot.generation+1);
            return;
        }
        snapshot=new Snapshot(true,p.id,p.exponent,p.calibrationStatus,p.basis,
                p.sensorWidthMm,p.physicalFocalMm,p.aperture,p.cfa,snapshot.generation+1);
    }

    public static synchronized Snapshot snapshot() { return snapshot; }
}
