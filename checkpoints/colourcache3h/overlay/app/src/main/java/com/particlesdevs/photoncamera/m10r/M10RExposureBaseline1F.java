package com.particlesdevs.photoncamera.m10r;

/**
 * Bounded starting-exposure protection using the existing incremental loss predicates.
 * This inverse use of the donor predicates is new engineering policy, not a Leica
 * firmware target or a claim of recovered sensor information. Neutral-user evidence
 * owns this decision; explicit user EV is applied separately by the allocator.
 */
public final class M10RExposureBaseline1F {
    public static final String REVISION="M10R_EXPOSURE1F_NEUTRAL_BASELINE_HIGHLIGHTS";
    private M10RExposureBaseline1F() {}
    public static final class Decision {
        public final double correctionEv;
        public final int selectedStep; // 0 = neutral, 1 = -0.25, 2 = -0.50.
        public final String reason;
        public final M10RHighlightGuard1A.Stop recoveredLoss;
        private Decision(int step,String reason,M10RHighlightGuard1A.Stop loss) {
            selectedStep=step;correctionEv=-step*M10RHighlightGuard1A.STEP_EV;
            this.reason=reason;recoveredLoss=loss;
        }
    }
    /** Order: neutral, -0.25, -0.50 EV, all from the same reconstruction/colour context. */
    public static Decision evaluate(M10RHighlightGuard1A.Stats[] neutralAndLower) {
        if(neutralAndLower==null)return new Decision(0,"baseline_evidence_unavailable",M10RHighlightGuard1A.Stop.NONE);
        if(neutralAndLower.length!=3)throw new IllegalArgumentException("neutral and two lower candidates required");
        for(var s:neutralAndLower)if(s==null)throw new IllegalArgumentException("incomplete baseline evidence");
        for(int step=1;step<3;step++) {
            // A lower candidate must demonstrate the SAME substantial emerging loss
            // on returning to neutral. Persistent white lights/sky and tiny highlights
            // do not become a reason to darken the whole frame.
            var loss=M10RHighlightGuard1A.stopReason(neutralAndLower[step],neutralAndLower[0],
                    M10RHighlightGuard1A.SubjectProgress.none());
            if(loss!=M10RHighlightGuard1A.Stop.NONE)
                return new Decision(step,"measured_neutral_highlight_loss",loss);
        }
        return new Decision(0,"no_demonstrated_neutral_highlight_loss",M10RHighlightGuard1A.Stop.NONE);
    }
}
