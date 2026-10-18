package com.particlesdevs.photoncamera.m10r;

import java.util.Arrays;

/**
 * Bounded M10-R multi-field architecture proxy.
 *
 * Uses:
 * - exact recovered 16x22 Integral mask,
 * - recovered MFM 4x6 / 24-region topology,
 * - hand-authored proxy blending already field-tested in the M9 cross-generation work.
 *
 * Does NOT claim numerical parity with Leica's unresolved 13-feature CA9 generator.
 */
public final class M10RMfm1A {
    public static final int GRID_R = 16;
    public static final int GRID_C = 22;
    public static final int REG_R = 4;
    public static final int REG_C = 6;

    public static final double DEAD_BAND_EV = 0.08;
    public static final double MAX_POSITIVE_EV = 0.75;
    public static final double MAX_NEGATIVE_EV = 0.50;

    private M10RMfm1A() {}

    public static final class Decision {
        public final boolean valid;
        public final boolean wouldApply;
        public final double recommendedEv;
        public final double integralY;
        public final double regionalMedianY;
        public final double regionalLowQuarterY;
        public final double regionalHighQuarterY;
        public final double sceneSpreadEv;
        public final double center8Y;
        public final double lower12Y;
        public final double upper6Y;
        public final double edge16Y;
        public final double inner8Y;
        public final double integralVsMedianEv;
        public final double integralVsCenterEv;
        public final double integralVsLowerEv;
        public final double edgeVsInnerEv;
        public final double upperVsLowerEv;
        public final double centerOverIntegralEv;
        public final double innerVsEdgeEv;
        public final double positiveCandidateEv;
        public final double negativeCandidateEv;
        public final double rawBlendEv;
        public final int brightRegionCount;
        public final int darkRegionCount;
        public final double brightRegionFraction;
        public final double darkRegionFraction;
        public final double positiveGeometryConfidence;
        public final double positiveConfidence;
        public final double negativeGeometryConfidence;
        public final double negativeConfidence;
        public final double[] regions4x6;
        public final String reason;

        Decision(boolean valid, boolean wouldApply, double recommendedEv,
                 double integralY, double regionalMedianY,
                 double regionalLowQuarterY, double regionalHighQuarterY,
                 double sceneSpreadEv, double center8Y, double lower12Y, double upper6Y,
                 double edge16Y, double inner8Y,
                 double integralVsMedianEv, double integralVsCenterEv, double integralVsLowerEv,
                 double edgeVsInnerEv, double upperVsLowerEv,
                 double centerOverIntegralEv, double innerVsEdgeEv,
                 double positiveCandidateEv, double negativeCandidateEv, double rawBlendEv,
                 int brightRegionCount, int darkRegionCount,
                 double brightRegionFraction, double darkRegionFraction,
                 double positiveGeometryConfidence, double positiveConfidence,
                 double negativeGeometryConfidence, double negativeConfidence,
                 double[] regions4x6, String reason) {
            this.valid=valid; this.wouldApply=wouldApply; this.recommendedEv=recommendedEv;
            this.integralY=integralY; this.regionalMedianY=regionalMedianY;
            this.regionalLowQuarterY=regionalLowQuarterY;
            this.regionalHighQuarterY=regionalHighQuarterY;
            this.sceneSpreadEv=sceneSpreadEv; this.center8Y=center8Y;
            this.lower12Y=lower12Y; this.upper6Y=upper6Y; this.edge16Y=edge16Y; this.inner8Y=inner8Y;
            this.integralVsMedianEv=integralVsMedianEv;
            this.integralVsCenterEv=integralVsCenterEv;
            this.integralVsLowerEv=integralVsLowerEv;
            this.edgeVsInnerEv=edgeVsInnerEv;
            this.upperVsLowerEv=upperVsLowerEv;
            this.centerOverIntegralEv=centerOverIntegralEv;
            this.innerVsEdgeEv=innerVsEdgeEv;
            this.positiveCandidateEv=positiveCandidateEv;
            this.negativeCandidateEv=negativeCandidateEv;
            this.rawBlendEv=rawBlendEv;
            this.brightRegionCount=brightRegionCount;
            this.darkRegionCount=darkRegionCount;
            this.brightRegionFraction=brightRegionFraction;
            this.darkRegionFraction=darkRegionFraction;
            this.positiveGeometryConfidence=positiveGeometryConfidence;
            this.positiveConfidence=positiveConfidence;
            this.negativeGeometryConfidence=negativeGeometryConfidence;
            this.negativeConfidence=negativeConfidence;
            this.regions4x6=regions4x6 != null ? regions4x6.clone() : null;
            this.reason=reason;
        }
    }

    public static Decision evaluate(double[] cell) {
        if (cell == null || cell.length != GRID_R * GRID_C) {
            return invalid("grid_shape_invalid");
        }
        for (double v : cell) {
            if (!finite(v) || v < 0.0) return invalid("grid_value_invalid");
        }

        int[] mask = M10RIntegralMask.copyWeights();
        double integralY = weightedMean(cell, mask);
        double[] regions = regions4x6(cell);
        double[] sorted = regions.clone();
        Arrays.sort(sorted);

        double regionalMedianY = 0.5 * (sorted[11] + sorted[12]);
        double regionalLowY = meanRange(sorted, 0, 6);
        double regionalHighY = meanRange(sorted, 18, 24);
        double sceneSpreadEv = log2(safe(regionalHighY) / safe(regionalLowY));

        double center8Y = regionRectMean(regions, 1, 3, 1, 5);
        double lower12Y = regionRectMean(regions, 2, 4, 0, 6);
        double upper6Y = regionRectMean(regions, 0, 1, 0, 6);
        double edge16Y = regionEdgeMean(regions, true);
        double inner8Y = regionEdgeMean(regions, false);

        double integralVsMedianEv = log2(safe(integralY) / safe(regionalMedianY));
        double integralVsCenterEv = log2(safe(integralY) / safe(center8Y));
        double integralVsLowerEv = log2(safe(integralY) / safe(lower12Y));
        double edgeVsInnerEv = log2(safe(edge16Y) / safe(inner8Y));
        double upperVsLowerEv = log2(safe(upper6Y) / safe(lower12Y));
        double centerOverIntegralEv = log2(safe(center8Y) / safe(integralY));
        double innerVsEdgeEv = log2(safe(inner8Y) / safe(edge16Y));

        int brightRegions=0, darkRegions=0;
        double brightThreshold = regionalMedianY * Math.pow(2.0, 0.50);
        double darkThreshold = regionalMedianY / Math.pow(2.0, 0.50);
        for (double v : regions) {
            if (v >= brightThreshold) brightRegions++;
            if (v <= darkThreshold) darkRegions++;
        }
        double brightRegionFraction = brightRegions / 24.0;
        double darkRegionFraction = darkRegions / 24.0;

        double rawPositiveEv = Math.max(0.0,
                0.55 * integralVsMedianEv
                + 0.25 * integralVsCenterEv
                + 0.20 * integralVsLowerEv);
        double edgeBacklightGeometry = smoothstep(edgeVsInnerEv, 0.05, 0.65);
        double upperBacklightGeometry = smoothstep(upperVsLowerEv, 0.15, 1.00);
        double positiveGeometryConfidence = Math.max(edgeBacklightGeometry, upperBacklightGeometry);
        double positiveConfidence = smoothstep(sceneSpreadEv, 0.70, 2.20)
                * smoothstep(brightRegionFraction, 0.08, 0.30)
                * positiveGeometryConfidence;
        double positiveCandidateEv = rawPositiveEv * positiveConfidence;

        double negativeGeometryConfidence = Math.max(
                smoothstep(innerVsEdgeEv, 0.05, 0.65),
                smoothstep(centerOverIntegralEv, 0.15, 0.65));
        double negativeConfidence = smoothstep(sceneSpreadEv, 0.45, 1.60)
                * negativeGeometryConfidence;
        double negativeCandidateEv = -0.70
                * Math.max(0.0, centerOverIntegralEv - 0.10)
                * negativeConfidence;

        double rawBlendEv = positiveCandidateEv + negativeCandidateEv;
        double candidateEv = clamp(rawBlendEv, -MAX_NEGATIVE_EV, MAX_POSITIVE_EV);
        if (Math.abs(candidateEv) < DEAD_BAND_EV) candidateEv = 0.0;

        boolean valid = finite(candidateEv) && finite(integralY) && finite(regionalMedianY);
        boolean wouldApply = valid && Math.abs(candidateEv) >= DEAD_BAND_EV;
        String reason = !valid ? "mfm_invalid"
                : !wouldApply ? "mfm_neutral_deadband"
                : candidateEv > 0.0 ? "mfm_positive_capture_assist"
                : "mfm_negative_capture_moderation";

        return new Decision(valid, wouldApply, valid ? candidateEv : 0.0,
                integralY, regionalMedianY, regionalLowY, regionalHighY,
                sceneSpreadEv, center8Y, lower12Y, upper6Y, edge16Y, inner8Y,
                integralVsMedianEv, integralVsCenterEv, integralVsLowerEv,
                edgeVsInnerEv, upperVsLowerEv, centerOverIntegralEv, innerVsEdgeEv,
                positiveCandidateEv, negativeCandidateEv, rawBlendEv,
                brightRegions, darkRegions, brightRegionFraction, darkRegionFraction,
                positiveGeometryConfidence, positiveConfidence,
                negativeGeometryConfidence, negativeConfidence,
                regions, reason);
    }

    private static Decision invalid(String reason) {
        return new Decision(false,false,0.0,
                Double.NaN,Double.NaN,Double.NaN,Double.NaN,Double.NaN,
                Double.NaN,Double.NaN,Double.NaN,Double.NaN,Double.NaN,
                Double.NaN,Double.NaN,Double.NaN,Double.NaN,Double.NaN,
                Double.NaN,Double.NaN,Double.NaN,Double.NaN,Double.NaN,
                0,0,0.0,0.0,0.0,0.0,0.0,0.0,null,reason);
    }

    private static double weightedMean(double[] v,int[] w) {
        double s=0.0, sw=0.0;
        for(int i=0;i<v.length && i<w.length;i++) {
            if(w[i]<=0) continue;
            s += v[i]*w[i];
            sw += w[i];
        }
        return sw>0.0 ? s/sw : 0.0;
    }

    private static double[] regions4x6(double[] cell) {
        double[] out=new double[24];
        for(int rr=0;rr<REG_R;rr++) {
            int r0=rr*GRID_R/REG_R, r1=(rr+1)*GRID_R/REG_R;
            for(int cc=0;cc<REG_C;cc++) {
                int c0=cc*GRID_C/REG_C, c1=(cc+1)*GRID_C/REG_C;
                double s=0.0; int n=0;
                for(int r=r0;r<r1;r++) {
                    for(int c=c0;c<c1;c++) {
                        s += cell[r*GRID_C+c];
                        n++;
                    }
                }
                out[rr*REG_C+cc]=n>0?s/n:0.0;
            }
        }
        return out;
    }

    private static double regionRectMean(double[] r,int r0,int r1,int c0,int c1) {
        double s=0.0; int n=0;
        for(int y=r0;y<r1;y++) for(int x=c0;x<c1;x++) {
            s += r[y*REG_C+x]; n++;
        }
        return n>0?s/n:0.0;
    }

    private static double regionEdgeMean(double[] r,boolean edge) {
        double s=0.0; int n=0;
        for(int y=0;y<REG_R;y++) for(int x=0;x<REG_C;x++) {
            boolean isEdge=y==0||y==REG_R-1||x==0||x==REG_C-1;
            if(isEdge==edge) { s += r[y*REG_C+x]; n++; }
        }
        return n>0?s/n:0.0;
    }

    private static double meanRange(double[] v,int from,int to) {
        double s=0.0; int n=0;
        for(int i=Math.max(0,from);i<Math.min(v.length,to);i++) { s+=v[i]; n++; }
        return n>0?s/n:0.0;
    }

    private static double smoothstep(double x,double lo,double hi) {
        if(!finite(x)) return 0.0;
        if(hi<=lo) return x>=hi?1.0:0.0;
        double t=clamp((x-lo)/(hi-lo),0.0,1.0);
        return t*t*(3.0-2.0*t);
    }

    private static double safe(double v) { return Math.max(v,1.0e-6); }
    private static double log2(double v) { return Math.log(Math.max(v,1.0e-12))/Math.log(2.0); }
    private static double clamp(double v,double lo,double hi) { return Math.max(lo,Math.min(hi,v)); }
    private static boolean finite(double v) { return !Double.isNaN(v) && !Double.isInfinite(v); }
}
