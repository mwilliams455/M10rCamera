package com.particlesdevs.photoncamera.m10r;

/** Still-bound telemetry for generic MFM1D physical-camera source normalization. */
public final class M10RMfm1DSourceState {
    private M10RMfm1DSourceState() {}

    public static final class Snapshot {
        public final boolean valid;
        public final String profileId;
        public final String fingerprint;
        public final String canonicalDescriptor;
        public final double exponent;
        public final String calibrationStatus;
        public final String calibrationEvidenceId;
        public final String basis;
        public final int activeWidth;
        public final int activeHeight;
        public final int cfa;
        public final double sensorWidthMm;
        public final double physicalFocalMm;
        public final double aperture;
        public final int whiteLevel;
        public final int referenceIlluminant1;
        public final int referenceIlluminant2;
        public final long generation;

        Snapshot(boolean valid,String profileId,String fingerprint,String canonicalDescriptor,
                 double exponent,String calibrationStatus,String calibrationEvidenceId,String basis,
                 int activeWidth,int activeHeight,int cfa,double sensorWidthMm,
                 double physicalFocalMm,double aperture,int whiteLevel,
                 int referenceIlluminant1,int referenceIlluminant2,long generation) {
            this.valid=valid;
            this.profileId=profileId;
            this.fingerprint=fingerprint;
            this.canonicalDescriptor=canonicalDescriptor;
            this.exponent=exponent;
            this.calibrationStatus=calibrationStatus;
            this.calibrationEvidenceId=calibrationEvidenceId;
            this.basis=basis;
            this.activeWidth=activeWidth;
            this.activeHeight=activeHeight;
            this.cfa=cfa;
            this.sensorWidthMm=sensorWidthMm;
            this.physicalFocalMm=physicalFocalMm;
            this.aperture=aperture;
            this.whiteLevel=whiteLevel;
            this.referenceIlluminant1=referenceIlluminant1;
            this.referenceIlluminant2=referenceIlluminant2;
            this.generation=generation;
        }
    }

    private static Snapshot snapshot = new Snapshot(
            false,"UNSET","UNSET","UNSET",1.0,"unset","NONE","unset",
            -1,-1,-1,Double.NaN,Double.NaN,Double.NaN,-1,-1,-1,0);

    public static synchronized void record(M10RMfm1DSourceProxy.Profile p) {
        if (p == null) {
            snapshot=new Snapshot(false,"UNSET","UNSET","UNSET",1.0,
                    "unset","NONE","unset",-1,-1,-1,
                    Double.NaN,Double.NaN,Double.NaN,-1,-1,-1,
                    snapshot.generation+1);
            return;
        }
        snapshot=new Snapshot(true,p.id,p.fingerprint,p.canonicalDescriptor,p.exponent,
                p.calibrationStatus,p.calibrationEvidenceId,p.basis,
                p.activeWidth,p.activeHeight,p.cfa,p.sensorWidthMm,
                p.physicalFocalMm,p.aperture,p.whiteLevel,
                p.referenceIlluminant1,p.referenceIlluminant2,
                snapshot.generation+1);
    }

    public static synchronized Snapshot snapshot() { return snapshot; }
}
