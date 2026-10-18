package com.particlesdevs.photoncamera.m10r;

/** Thread-safe live-preview Leica metering probe.
 * The preview pixels are sampled from the GL camera texture into a 22x16 grid.
 * Two domains are retained:
 * - code-space RGB luma from the preview texture;
 * - approximate linear-light luma after inverse sRGB on each channel.
 *
 * This is diagnostic only in METER1A. It does not alter exposure.
 */
public final class M10RLiveMeterState {
    private M10RLiveMeterState() {}

    public static final class Snapshot {
        public final boolean valid;
        public final long generation;
        public final long timestampNs;
        public final long previewExposureNs;
        public final int previewIso;
        public final double codeWholeMean;
        public final double codeIntegralMean;
        public final double codeIntegralVsWholeEv;
        public final double linearWholeMean;
        public final double linearIntegralMean;
        public final double linearIntegralVsWholeEv;
        public final double[] linearGrid;

        Snapshot(boolean valid,long generation,long timestampNs,long previewExposureNs,int previewIso,
                 double codeWholeMean,double codeIntegralMean,double codeIntegralVsWholeEv,
                 double linearWholeMean,double linearIntegralMean,double linearIntegralVsWholeEv,
                 double[] linearGrid) {
            this.valid=valid; this.generation=generation; this.timestampNs=timestampNs;
            this.previewExposureNs=previewExposureNs; this.previewIso=previewIso;
            this.codeWholeMean=codeWholeMean; this.codeIntegralMean=codeIntegralMean;
            this.codeIntegralVsWholeEv=codeIntegralVsWholeEv;
            this.linearWholeMean=linearWholeMean; this.linearIntegralMean=linearIntegralMean;
            this.linearIntegralVsWholeEv=linearIntegralVsWholeEv;
            this.linearGrid=linearGrid != null ? linearGrid.clone() : null;
        }
    }

    private static Snapshot snapshot = new Snapshot(false,0,0,0,0,
            Double.NaN,Double.NaN,Double.NaN,Double.NaN,Double.NaN,Double.NaN,null);
    private static Snapshot frozen = new Snapshot(false,0,0,0,0,
            Double.NaN,Double.NaN,Double.NaN,Double.NaN,Double.NaN,Double.NaN,null);

    public static synchronized void publish(long timestampNs,long previewExposureNs,int previewIso,
                                            double codeWholeMean,double codeIntegralMean,
                                            double linearWholeMean,double linearIntegralMean,
                                            double[] linearGrid) {
        long gen=snapshot.generation+1;
        double codeEv=(codeWholeMean>0.0 && codeIntegralMean>0.0)
                ? log2(codeIntegralMean/codeWholeMean) : Double.NaN;
        double linearEv=(linearWholeMean>0.0 && linearIntegralMean>0.0)
                ? log2(linearIntegralMean/linearWholeMean) : Double.NaN;
        snapshot=new Snapshot(true,gen,timestampNs,previewExposureNs,previewIso,
                codeWholeMean,codeIntegralMean,codeEv,
                linearWholeMean,linearIntegralMean,linearEv,linearGrid);
    }

    public static synchronized Snapshot snapshot() {
        return copy(snapshot);
    }

    public static synchronized void freezeCapture() {
        frozen = copy(snapshot);
    }

    public static synchronized Snapshot frozenSnapshot() {
        return copy(frozen);
    }

    private static Snapshot copy(Snapshot s) {
        return new Snapshot(s.valid,s.generation,s.timestampNs,s.previewExposureNs,s.previewIso,
                s.codeWholeMean,s.codeIntegralMean,s.codeIntegralVsWholeEv,
                s.linearWholeMean,s.linearIntegralMean,s.linearIntegralVsWholeEv,s.linearGrid);
    }

    private static double log2(double x) { return Math.log(x)/Math.log(2.0); }
}
