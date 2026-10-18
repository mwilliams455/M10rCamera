package com.particlesdevs.photoncamera.m10r;

/** E1G renderer-specific experimental adapter. All thresholds are engineering policy.
 * Uses the existing request-owned RAW regions and rendered lattice; no extra capture,
 * reconstruction, tone manipulation, object detector, or device-specific calibration.
 */
public final class M10RMultiField1G {
    public static final String REVISION="M10R_FOREGROUND1Q_QUALIFIED_NEGATIVE_CONFLICT";
    public static final String GEOMETRY_REVISION="M10R_MIDGAP1S_BOUNDED_FOREGROUND";
    public static final double MAX_ASSIST_EV=.50;
    private M10RMultiField1G() {}

    public static final class Decision {
        public final MultiFieldScene1G.Scene scene;
        public final double legacyRequestedEv,requestedEv,positiveRequestLimitEv;
        public final double neutralForegroundQ90;
        public final String reason;
        private final M10RHighlightGuard1A.SubjectProgress[] progress;
        private final double[] foregroundQ90;
        private Decision(MultiFieldScene1G.Scene scene,double legacy,double requested,
                double neutralQ90,String reason,M10RHighlightGuard1A.SubjectProgress[] progress,double[] q90) {
            this(scene,legacy,requested,neutralQ90,reason,progress,q90,M10RExposureRange1H.MAX_POSITIVE_EV);
        }
        private Decision(MultiFieldScene1G.Scene scene,double legacy,double requested,
                double neutralQ90,String reason,M10RHighlightGuard1A.SubjectProgress[] progress,double[] q90,
                double positiveLimit) {
            this.scene=scene;legacyRequestedEv=legacy;requestedEv=requested;
            positiveRequestLimitEv=positiveLimit;
            neutralForegroundQ90=neutralQ90;this.reason=reason;
            this.progress=progress.clone();foregroundQ90=q90.clone();
        }
        public M10RHighlightGuard1A.SubjectProgress[] progress(){return progress.clone();}
        public double foregroundQ90(int step){return foregroundQ90[step];}
    }

    public static Decision evaluate(M10RMfm1B.Decision legacy,M10RHighlightGuard1A.Stats neutral,
            M10RHighlightGuard1A.Stats[] candidates,M10RHighlightGuard1A.SubjectProgress[] original) {
        return evaluate(legacy.regions4x6,legacy.wouldApply?legacy.recommendedEv:0,neutral,candidates,original);
    }
    // Also permits exact decision replay from the recorded regional evidence.
    static Decision evaluate(double[] rawRegions,double previous,M10RHighlightGuard1A.Stats neutral,
            M10RHighlightGuard1A.Stats[] candidates,M10RHighlightGuard1A.SubjectProgress[] original) {
        if(!Double.isFinite(previous)||candidates==null||!M10RExposureRange1H.completeLattice(candidates.length)
                ||original==null||original.length!=candidates.length)
            throw new IllegalArgumentException("complete multi-field evidence required");
        for(int i=0;i<candidates.length;i++)if(candidates[i]==null||original[i]==null)
            throw new IllegalArgumentException("missing candidate");
        int dark=0,bright=0,midtone=0;
        if(neutral!=null)for(int f=0;f<24;f++) {
            // q90 describes most of a field, resisting a few holes/bright leaves.
            // Mixed sky/leaf fields remain unclassified rather than becoming the
            // foreground brightness target merely because most pixels are dark.
            if(neutral.q90(f)<=96&&neutral.bright(f)<.01&&neutral.clipped(f)<.02)dark|=1<<f;
            if(neutral.q90(f)>=192)bright|=1<<f;
            if(neutral.q90(f)>96&&neutral.q90(f)<192)midtone|=1<<f;
        }
        MultiFieldScene1G.Scene scene=MultiFieldScene1G.evaluate(rawRegions,dark,bright,midtone);
        double[] q=new double[candidates.length];
        for(int i=0;i<q.length;i++)q[i]=meanQ90(candidates[i],scene.foregroundMask);
        double neutralQ=neutral==null?0:meanQ90(neutral,scene.foregroundMask);
        M10RHighlightGuard1A.SubjectProgress[] progress=original.clone();
        if(previous<0&&!scene.qualified)return new Decision(scene,previous,previous,neutralQ,
                "legacy_negative_preserved",progress,q);
        // SCENEQUAL1O: relative RAW contrast alone cannot authorize a lift. A
        // bright wall beside dark material can satisfy the legacy meter without
        // a rendered foreground that needs help. Require the same neutral-user
        // qualification for inherited positive demand as for regional assistance.
        // This gate does not alter user EV or introduce a negative offset.
        if(!scene.qualified)return new Decision(scene,previous,0,neutralQ,
                previous>0?(neutral==null?"positive_assist_missing_neutral_evidence"
                        :"positive_assist_unqualified_foreground"):scene.reason,progress,q);
        // Smoothly enter between two and four stops of regional separation.
        double t=Math.max(0,Math.min(1,(scene.separationEv-2)/2));
        double assist=MAX_ASSIST_EV*t*t*(3-2*t);
        if(assist<M10RMfm1B.DEAD_BAND_EV)assist=0;
        if(previous<0) {
            // FOREGROUND1Q: contrast-only negative demand cannot bypass a
            // qualified dark foreground with measured progress and highlight
            // headroom. Use the bounded path without background exceptions.
            double requested=Math.min(assist,foregroundLimit(candidates,q,scene.foregroundMask));
            requested=Math.min(requested,M10RHighlightGuard1A.limit(candidates,progress).maxPositiveEv);
            if(requested<=0)return new Decision(scene,previous,previous,neutralQ,
                    "legacy_negative_no_safe_foreground_assist",progress,q);
            return new Decision(scene,previous,requested,neutralQ,
                    "qualified_foreground_overrides_negative_meter",progress,q,requested);
        }
        if(scene.splitBackground||scene.midtoneBridge) {
            // A new geometry path gets only the measured, bounded regional
            // assist, never the legacy contrast demand or its wider range.
            // The existing 96/128 code boundaries define dark/too-open fields;
            // these are engineering bounds, not skin or M9 brightness targets.
            double limit=foregroundLimit(candidates,q,scene.foregroundMask);
            double requested=Math.min(assist,limit);
            // No new background highlight exception is granted by this branch.
            String kind=scene.midtoneBridge?"midtone_bridge":"split_background";
            return new Decision(scene,previous,requested,neutralQ,
                    kind+(requested>0?"_bounded_assist":"_no_foreground_progress"),
                    progress,q,requested);
        }
        double requested=Math.max(previous,assist);
        for(int i=1;i<candidates.length;i++) {
            boolean safe=true;
            for(int f=0;f<24;f++)if((scene.foregroundMask&(1<<f))!=0)
                safe&=candidates[i].clipped(f)<.02&&candidates[i].bright(f)<.02&&candidates[i].q90(f)<=128;
            // The user-EV candidate must still be dark and actually improve.
            // Never extend this exception beyond the half-stop experiment.
            boolean supported=i*M10RHighlightGuard1A.STEP_EV<=MAX_ASSIST_EV
                    &&q[0]<96&&q[i]-q[i-1]>=2&&safe&&assist>0;
            if(supported)progress[i]=M10RHighlightGuard1A.SubjectProgress.forNearWhiteBackground(
                    scene.foregroundMask,scene.backgroundMask);
        }
        return new Decision(scene,previous,requested,neutralQ,"regional_foreground_assist",progress,q);
    }
    private static double foregroundLimit(M10RHighlightGuard1A.Stats[] candidates,double[] q,int mask) {
        double limit=0;
        if(q[0]<96&&safeForeground(candidates[0],mask)) {
            for(int i=1;i<candidates.length&&i*M10RHighlightGuard1A.STEP_EV<=MAX_ASSIST_EV;i++) {
                if(q[i-1]>=96||q[i]-q[i-1]<2||!safeForeground(candidates[i],mask))break;
                limit=i*M10RHighlightGuard1A.STEP_EV;
            }
        }
        return limit;
    }
    private static double meanQ90(M10RHighlightGuard1A.Stats stats,int mask) {
        if(mask==0)return 0;
        double sum=0;for(int f=0;f<24;f++)if((mask&(1<<f))!=0)sum+=stats.q90(f);
        return sum/Integer.bitCount(mask);
    }
    private static boolean safeForeground(M10RHighlightGuard1A.Stats stats,int mask) {
        for(int f=0;f<24;f++)if((mask&(1<<f))!=0)
            if(stats.q90(f)>128||stats.bright(f)>=.02||stats.clipped(f)>=.02)return false;
        return mask!=0;
    }
}
