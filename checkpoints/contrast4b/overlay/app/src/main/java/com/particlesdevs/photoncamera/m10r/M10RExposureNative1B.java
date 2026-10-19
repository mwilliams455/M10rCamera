package com.particlesdevs.photoncamera.m10r;

/** Shared native pixel renderer; exposure metering retains PREVIEW1L matrix preparation. */
public final class M10RExposureNative1B {
    public static final String TARGET_REVISION = "YA_TOPOLOGY1A_GAMUT1A_TONECAL1A_EDGE0A";
    static { System.loadLibrary("dngCreator"); }
    private M10RExposureNative1B() {}
    private static native void nativeRender(short[] rgb, int pixels, double inverseScale,
            double[] sourceToTarget, int[] ca9, double[] targetToWorking, double[] workingToOutput,
            int[] tone, int[] dg, int[] out, long[] counts, boolean cc1BeforeDg);

    /** Constructed once from the exact probe frame's Camera2 colour state. */
    public static final class Context {
        private final double[] sourceToTarget, targetToWorking, workingToOutput;
        private final int[] ca9;
        private final boolean cc1BeforeDg;
        private final String matrixRevision;
        public final M10RContrast4B.Level contrast4B;
        final M10RSourceWhite3N sourceWhite;
        public final String revision, cameraKey;
        public final long frameTimestampNs;
        Context(double[] sourceToTarget, int[] ca9, double[] targetToWorking, double[] workingToOutput,
                String cameraKey, long frameTimestampNs) {
            this(sourceToTarget,ca9,targetToWorking,workingToOutput,cameraKey,frameTimestampNs,null);
        }
        Context(double[] sourceToTarget, int[] ca9, double[] targetToWorking, double[] workingToOutput,
                String cameraKey, long frameTimestampNs, M10RSourceWhite3N sourceWhite) {
            this(sourceToTarget,ca9,targetToWorking,workingToOutput,cameraKey,frameTimestampNs,TARGET_REVISION,false,sourceWhite,
                    M10RContrast4B.Level.STANDARD);
        }
        private Context(double[] sourceToTarget, int[] ca9, double[] targetToWorking, double[] workingToOutput,
                String cameraKey, long frameTimestampNs,String matrixRevision,boolean cc1BeforeDg,
                M10RSourceWhite3N sourceWhite, M10RContrast4B.Level contrast4B) {
            if(cameraKey==null||cameraKey.isEmpty()||frameTimestampNs<=0)throw new IllegalArgumentException("frame colour binding");
            this.cameraKey=cameraKey;this.frameTimestampNs=frameTimestampNs;
            this.sourceToTarget = matrix(sourceToTarget);
            this.targetToWorking = matrix(targetToWorking);
            this.workingToOutput = matrix(workingToOutput);
            if (ca9 == null || ca9.length != 3) throw new IllegalArgumentException("CA9 gains");
            this.ca9 = ca9.clone();
            for (int v : this.ca9) if (v < 1 || v > 2000) throw new IllegalArgumentException("CA9 range");
            this.matrixRevision = matrixRevision;
            this.contrast4B = M10RContrast4B.normalized(contrast4B);
            revision = M10RContrast4B.rendererRevision(matrixRevision, this.contrast4B);
            this.cc1BeforeDg = cc1BeforeDg;
            this.sourceWhite = sourceWhite;
        }
        Context withRenderedColor(M10RRenderedColor1A preparation,boolean enabled) {
            return withRenderedColor(preparation,enabled,false);
        }
        Context withRenderedColor(M10RRenderedColor1A preparation,boolean enabled,boolean orderRequested) {
            M10RRenderedColor1A.Result r=preparation.select(enabled,ca9,targetToWorking,workingToOutput);
            boolean orderApplied=orderRequested && r.applied;
            String name=r.applied ? M10RRenderedColor1A.REVISION : TARGET_REVISION;
            if(orderApplied) name += ":M10R_COLORORDER1A_CC1_BEFORE_DG";
            return new Context(sourceToTarget,ca9,r.targetToWorking,r.workingToOutput,cameraKey,
                    frameTimestampNs,name,orderApplied,sourceWhite,contrast4B);
        }
        Context withContrast(M10RContrast4B.Level level) {
            if (M10RContrast4B.normalized(level) == contrast4B) return this;
            return new Context(sourceToTarget,ca9,targetToWorking,workingToOutput,cameraKey,
                    frameTimestampNs,matrixRevision,cc1BeforeDg,sourceWhite,level);
        }
        public int[] render(short[] normalizedRgb, double inverseScale) {
            if (normalizedRgb == null || normalizedRgb.length == 0 || normalizedRgb.length % 3 != 0
                    || normalizedRgb.length > 3 * 65536 || !Double.isFinite(inverseScale) || inverseScale <= 0)
                throw new IllegalArgumentException("bounded RGB probe and finite scale required");
            int pixels = normalizedRgb.length / 3;
            int[] out = new int[pixels];
            long[] counts = new long[24];
            nativeRender(normalizedRgb, pixels, inverseScale, sourceToTarget, ca9, targetToWorking,
                    workingToOutput, M10RContrast4B.nativeToneTable(contrast4B), M10RToneDg1A.nativeDgTable(), out, counts, cc1BeforeDg);
            // The inherited native routine can return early on allocation/shape failure.
            // Never turn unfilled output into an apparently highlight-safe black frame.
            if (counts[8] != pixels) throw new IllegalStateException("incomplete native colour probe");
            for (int v : out) if ((v >>> 24) != 255) throw new IllegalStateException("invalid native alpha");
            return out;
        }
        private static double[] matrix(double[] a) {
            if (a == null || a.length != 9) throw new IllegalArgumentException("3x3 matrix required");
            double[] out = a.clone();
            for (double x : out) if (!Double.isFinite(x)) throw new IllegalArgumentException("nonfinite matrix");
            return out;
        }
    }
}
