package com.particlesdevs.photoncamera.m10r;

import java.util.Arrays;

/**
 * E1A: an incremental, rendered-output highlight ceiling, not a brightness target.
 * Donor: M9 FINISH1N HIGHLIGHTRET1C, upstream2r source SHA-256
 * df6b82ecf84762aeafe0a9b151ed921247833a47c2ff9d1e61353100d3cd8448.
 * The loss predicates and code thresholds are a port of that engineering policy,
 * NOT claimed to be M10-R firmware constants or a RAW saturation detector.
 * Only actual M10-R-rendered candidate RGB may feed this class in production.
 */
public final class M10RHighlightGuard1A {
    public static final String REVISION = "M10R_E1A_INCREMENTAL_HIGHLIGHT_GUARD";
    public static final String POSITIVE_REVISION = "M10R_CLIPGROWTH1R_EXISTING_CLIP_LIMIT";
    public static final double POSITIVE_CLIP_GROWTH_BUDGET = .035;
    public static final int ROWS = 4, COLS = 6, FIELDS = ROWS * COLS;
    public static final double STEP_EV = 0.25;
    private static final int PREEXISTING_Q90 = 220;
    private M10RHighlightGuard1A() {}

    public enum Stop {
        NONE, GLOBAL_CHANNEL_CLIP_GROWTH, GLOBAL_NEARWHITE_GROWTH,
        REGIONAL_NEARWHITE_GROWTH, REGIONAL_CHANNEL_CLIP_GROWTH,
        GLOBAL_EXISTING_CHANNEL_CLIP_GROWTH
    }

    /** Immutable output-domain statistics. Original source-RAW clipping is separate. */
    public static final class Stats {
        public final double bright, clipped;
        private final int[] q90;
        private final double[] fieldBright, fieldClipped;
        public Stats(double bright, double clipped, int[] q90,
                     double[] fieldBright, double[] fieldClipped) {
            if (!fraction(bright) || !fraction(clipped) || q90 == null || fieldBright == null
                    || fieldClipped == null || q90.length != FIELDS
                    || fieldBright.length != FIELDS || fieldClipped.length != FIELDS)
                throw new IllegalArgumentException("complete 4x6 rendered highlight statistics required");
            this.bright = bright; this.clipped = clipped;
            this.q90 = q90.clone(); this.fieldBright = fieldBright.clone();
            this.fieldClipped = fieldClipped.clone();
            for (int f = 0; f < FIELDS; f++)
                if (this.q90[f] < 0 || this.q90[f] > 255 || !fraction(this.fieldBright[f])
                        || !fraction(this.fieldClipped[f]))
                    throw new IllegalArgumentException("invalid field " + f);
        }
        public int q90(int field) { return q90[field]; }
        public double bright(int field) { return fieldBright[field]; }
        public double clipped(int field) { return fieldClipped[field]; }
    }

    /**
     * Evidence supplied by a separate M10-R subject decision, for THIS candidate step.
     * No M9 body luminance target, mask detector or scene target is copied here.
     * Until an M10-R producer supplies these facts, use none().
     */
    public static final class SubjectProgress {
        public final int mask;
        public final boolean canDeferBackgroundChannelClip;
        public final int nearWhiteBackgroundMask;
        private SubjectProgress(int mask, boolean defer) {
            this(mask,defer,0);
        }
        private SubjectProgress(int mask, boolean defer,int background) {
            if ((mask & ~((1 << FIELDS) - 1)) != 0 || (defer && mask == 0))
                throw new IllegalArgumentException("invalid subject mask");
            if((background&~((1<<FIELDS)-1))!=0||(background&mask)!=0||(background!=0&&mask==0))
                throw new IllegalArgumentException("invalid background mask");
            this.mask = mask; this.canDeferBackgroundChannelClip = defer;
            nearWhiteBackgroundMask=background;
        }
        // Package-private: only the frame-bound E1G adapter produces this evidence.
        static SubjectProgress forNearWhiteBackground(int foreground,int background) {
            return new SubjectProgress(foreground,false,background);
        }
        public static SubjectProgress none() { return new SubjectProgress(0, false); }
        public static SubjectProgress fromEvidence(int mask, boolean sameFrameConfirmed,
                boolean strongBacklightQualified, boolean previousBelowM10rTarget,
                boolean currentImprovesSubject, boolean subjectSafe) {
            return new SubjectProgress(mask, sameFrameConfirmed && strongBacklightQualified
                    && previousBelowM10rTarget && currentImprovesSubject && subjectSafe);
        }
    }

    public static final class Limit {
        public final double maxPositiveEv;
        public final Stop stop;
        public final int firstRejectedStep; // -1 means every supplied step was safe.
        private Limit(double ev, Stop stop, int firstRejectedStep) {
            this.maxPositiveEv = ev; this.stop = stop; this.firstRejectedStep = firstRejectedStep;
        }
    }

    /** Original FINISH1N predicates when no E1G evidence is supplied. E1G can
     * defer only near-white growth in a qualified background; clipping rules stay intact. */
    public static Stop stopReason(Stats base, Stats current, SubjectProgress subject) {
        if (base == null || current == null || subject == null)
            throw new IllegalArgumentException("missing highlight input");
        double clipGrowth = current.clipped - base.clipped;
        double brightGrowth = current.bright - base.bright;
        boolean deferNearWhite=qualifiedBackgroundGrowth(base,current,subject);
        if (base.clipped < .04 && current.clipped >= .08 && clipGrowth >= .035)
            return Stop.GLOBAL_CHANNEL_CLIP_GROWTH;
        if (base.bright < .12 && current.bright >= .22 && brightGrowth >= .14 && !deferNearWhite)
            return Stop.GLOBAL_NEARWHITE_GROWTH;
        int near = 0, clips = 0;
        for (int f = 0; f < FIELDS; f++) {
            if (base.q90[f] >= PREEXISTING_Q90) continue;
            if (base.fieldBright[f] < .20 && current.fieldBright[f] >= .55
                    && current.fieldBright[f] - base.fieldBright[f] >= .30
                    && (!deferNearWhite||(subject.nearWhiteBackgroundMask&(1<<f))==0)) near++;
            boolean subjectField = (subject.mask & (1 << f)) != 0;
            if (base.fieldClipped[f] < .04 && current.fieldClipped[f] >= .08
                    && current.fieldClipped[f] - base.fieldClipped[f] >= .04
                    && (!subject.canDeferBackgroundChannelClip || subjectField)) clips++;
        }
        if (near >= 2) return Stop.REGIONAL_NEARWHITE_GROWTH;
        if (clips >= 2) return Stop.REGIONAL_CHANNEL_CLIP_GROWTH;
        return Stop.NONE;
    }

    /** E1G exception affects only near-white growth, never channel-clipping predicates.
     * At least 95% of regional growth must be in the qualified bright background;
     * outside growth is limited in every field. Global clipping must stay below 3%.
     * Equal field weighting is only a concentration test, not a pixel clipping count.
     */
    private static boolean qualifiedBackgroundGrowth(Stats base,Stats current,SubjectProgress subject) {
        if(subject.nearWhiteBackgroundMask==0||current.clipped>.03||current.clipped-base.clipped>.025)return false;
        double total=0,background=0;
        for(int f=0;f<FIELDS;f++) {
            double growth=Math.max(0,current.bright(f)-base.bright(f));total+=growth;
            if((subject.nearWhiteBackgroundMask&(1<<f))!=0)background+=growth;
            else if(growth>.03)return false;
            if((subject.mask&(1<<f))!=0&&(current.clipped(f)>=.02||current.bright(f)>=.02))return false;
        }
        return total>0&&background>=.95*total;
    }

    /** Search from one neutral, intent-removed frame; never jump past a failed step. */
    public static Limit limit(Stats[] candidates, SubjectProgress[] progress) {
        if (candidates == null || candidates.length < 2 || candidates.length > 11
                || progress == null || progress.length != candidates.length)
            throw new IllegalArgumentException("invalid exposure lattice");
        for (int i = 0; i < candidates.length; i++)
            if (candidates[i] == null || progress[i] == null)
                throw new IllegalArgumentException("incomplete candidate " + i);
        for (int i = 1; i < candidates.length; i++) {
            Stop stop = stopReason(candidates[0], candidates[i], progress[i]);
            // CLIPGROWTH1R: already-clipped windows must not disable the
            // existing 3.5 percentage-point global growth budget. This check
            // applies only to positive assistance, leaving the inverse baseline
            // test in stopReason unchanged. Existing clipping alone cannot
            // darken a scene, and foreground exceptions cannot waive new loss.
            if (stop == Stop.NONE && candidates[0].clipped >= .04
                    && candidates[i].clipped >= .08
                    && candidates[i].clipped - candidates[0].clipped >= POSITIVE_CLIP_GROWTH_BUDGET)
                stop = Stop.GLOBAL_EXISTING_CHANNEL_CLIP_GROWTH;
            if (stop != Stop.NONE) return new Limit((i - 1) * STEP_EV, stop, i);
        }
        return new Limit((candidates.length - 1) * STEP_EV, Stop.NONE, -1);
    }

    public static SubjectProgress[] noSubject(int count) {
        if (count < 2 || count > 11) throw new IllegalArgumentException("candidate count");
        SubjectProgress[] out = new SubjectProgress[count];
        Arrays.fill(out, SubjectProgress.none()); return out;
    }

    /**
     * Measure rendered ARGB, with the same luma quantizer and unweighted highlight
     * fractions as the donor. Orientation/crop must match across ALL candidates.
     * No resampling, luma-to-RGB expansion, gamma guess or gain simulation occurs here.
     */
    public static Stats measureArgb(int[] pixels, int width, int height) {
        return measureArgb(pixels,width,height,null);
    }
    public static Stats measureArgb(int[] pixels,int width,int height,int[] sharedFields) {
        if (pixels == null || width < COLS || height < ROWS || width > 8192 || height > 8192
                || pixels.length != (long) width * height)
            throw new IllegalArgumentException("invalid rendered probe dimensions");
        int[] hist = new int[FIELDS * 256], counts = new int[FIELDS];
        int[] brightCount = new int[FIELDS], clipCount = new int[FIELDS];
        if(sharedFields!=null&&sharedFields.length!=pixels.length)throw new IllegalArgumentException("field map shape");
        int bright = 0, clipped = 0, included=0;
        for (int y = 0; y < height; y++) for (int x = 0; x < width; x++) {
            int rgb = pixels[y * width + x];
            if ((rgb >>> 24) != 255) throw new IllegalArgumentException("non-opaque rendered probe");
            int r = (rgb >>> 16) & 255, g = (rgb >>> 8) & 255, b = rgb & 255;
            int l = (77 * r + 150 * g + 29 * b + 128) >> 8;
            int field = sharedFields==null?(y * ROWS / height) * COLS + x * COLS / width:sharedFields[y*width+x];
            if(field<0)continue;
            if(field>=FIELDS)throw new IllegalArgumentException("field map index");
            included++;
            hist[field * 256 + l]++; counts[field]++;
            if (l >= 224) { bright++; brightCount[field]++; }
            if (Math.max(r, Math.max(g, b)) >= 253) { clipped++; clipCount[field]++; }
        }
        int[] q90 = new int[FIELDS]; double[] fb = new double[FIELDS], fc = new double[FIELDS];
        for (int f = 0; f < FIELDS; f++) {
            if(counts[f]==0)throw new IllegalArgumentException("empty meter field");
            int need = Math.max(1, (int) Math.ceil(counts[f] * .90)), sum = 0;
            for (int v = 0; v < 256; v++) {
                sum += hist[f * 256 + v]; if (sum >= need) { q90[f] = v; break; }
            }
            fb[f] = brightCount[f] / (double) counts[f];
            fc[f] = clipCount[f] / (double) counts[f];
        }
        return new Stats(bright / (double) included, clipped / (double) included, q90, fb, fc);
    }

    private static boolean fraction(double value) {
        return Double.isFinite(value) && value >= 0 && value <= 1;
    }
}
