package com.particlesdevs.photoncamera.m10r;

/**
 * E1A capture-intent core. No Android state, camera requests or rendering mutations.
 * E1G adds a bounded regional foreground adapter; AE1B/Oracle remain the allocator.
 * E1F adds bounded, neutral-user baseline highlight protection to the positive ceiling.
 * MFM input is intent-removed. E1B colour candidates start at the explicitly bound user EV.
 */
public final class M10RExposure1A {
    public static final String REVISION = "M10R_E1H_EXTENDED_MEASURED_RANGE_AND_USER_REFERENCE_HIGHLIGHTS";
    // Same freshness budget as the M9 donor, engineering policy, not Leica firmware.
    public static final long MAX_AGE_NS = 1_200_000_000L;
    public enum ProbeDomain { M10R_RENDERED_NEUTRAL_REFERENCE, M10R_RENDERED_USER_EV_REFERENCE, OEM_PREVIEW_RGB, LUMA_ONLY, UNKNOWN }
    public enum Status { READY, BYPASS_MANUAL, NO_PROBE, SOURCE_MISMATCH, SESSION_MISMATCH,
        RENDERER_MISMATCH, WRONG_DOMAIN, TIMESTAMP_MISMATCH, STALE_OR_FUTURE, INCOMPLETE_LATTICE,
        INVALID_MFM, ALLOCATOR_REJECTED, USER_EV_MISMATCH, METERING_MISMATCH }
    private M10RExposure1A() {}

    /** Immutable, frame-bound input. Exposure/ISO must come from this frame's metadata. */
    public static final class Probe {
        public final String cameraKey, rendererRevision;
        // Legacy field name: textureTimestampNs carries Image.getTimestamp() for E1B RAW probes.
        public final long session, generation, textureTimestampNs, resultTimestampNs;
        public final long observedAtNs, completedAtNs, referenceExposureNs;
        public final int referenceIso;
        public final double referenceUserEv, referenceAutoEv, candidateUserEv;
        public final ProbeDomain domain;
        public final M10RMetering1U.Measurement metering;
        private final double[] rawProxyGrid;
        private final M10RHighlightGuard1A.Stats[] candidates;
        private final M10RHighlightGuard1A.SubjectProgress[] progress;
        private final M10RHighlightGuard1A.Stats[] baselineCandidates;
        public Probe(String cameraKey, long session, long generation, String rendererRevision,
                long textureTimestampNs, long resultTimestampNs, long observedAtNs, long completedAtNs,
                long referenceExposureNs, int referenceIso, double referenceUserEv, double referenceAutoEv,
                ProbeDomain domain, double[] rawProxyGrid, M10RHighlightGuard1A.Stats[] candidates,
                M10RHighlightGuard1A.SubjectProgress[] progress) {
            this(cameraKey,session,generation,rendererRevision,textureTimestampNs,resultTimestampNs,
                    observedAtNs,completedAtNs,referenceExposureNs,referenceIso,referenceUserEv,referenceAutoEv,
                    domain,rawProxyGrid,candidates,progress,0.0);
        }
        public Probe(String cameraKey, long session, long generation, String rendererRevision,
                long textureTimestampNs, long resultTimestampNs, long observedAtNs, long completedAtNs,
                long referenceExposureNs, int referenceIso, double referenceUserEv, double referenceAutoEv,
                ProbeDomain domain, double[] rawProxyGrid, M10RHighlightGuard1A.Stats[] candidates,
                M10RHighlightGuard1A.SubjectProgress[] progress, double candidateUserEv) {
            this(cameraKey,session,generation,rendererRevision,textureTimestampNs,resultTimestampNs,
                    observedAtNs,completedAtNs,referenceExposureNs,referenceIso,referenceUserEv,referenceAutoEv,
                    domain,rawProxyGrid,candidates,progress,candidateUserEv,null);
        }
        public Probe(String cameraKey, long session, long generation, String rendererRevision,
                long textureTimestampNs, long resultTimestampNs, long observedAtNs, long completedAtNs,
                long referenceExposureNs, int referenceIso, double referenceUserEv, double referenceAutoEv,
                ProbeDomain domain, double[] rawProxyGrid, M10RHighlightGuard1A.Stats[] candidates,
                M10RHighlightGuard1A.SubjectProgress[] progress, double candidateUserEv,
                M10RHighlightGuard1A.Stats[] baselineCandidates) {
            this(cameraKey,session,generation,rendererRevision,textureTimestampNs,resultTimestampNs,observedAtNs,completedAtNs,
                    referenceExposureNs,referenceIso,referenceUserEv,referenceAutoEv,domain,rawProxyGrid,candidates,progress,candidateUserEv,baselineCandidates,null);
        }
        public Probe(String cameraKey,long session,long generation,String rendererRevision,
                long textureTimestampNs,long resultTimestampNs,long observedAtNs,long completedAtNs,
                long referenceExposureNs,int referenceIso,double referenceUserEv,double referenceAutoEv,
                ProbeDomain domain,double[] rawProxyGrid,M10RHighlightGuard1A.Stats[] candidates,
                M10RHighlightGuard1A.SubjectProgress[] progress,double candidateUserEv,
                M10RHighlightGuard1A.Stats[] baselineCandidates,M10RMetering1U.Measurement metering) {
            this.metering=metering;
            if (cameraKey == null || cameraKey.isEmpty() || rendererRevision == null || rendererRevision.isEmpty()
                    || session <= 0 || generation <= 0 || referenceExposureNs <= 0 || referenceIso <= 0
                    || domain == null || !finiteEv(candidateUserEv) || !finiteEv(referenceUserEv) || !finiteEv(referenceAutoEv)
                    || rawProxyGrid == null || rawProxyGrid.length != 16 * 22
                    || candidates == null || progress == null || candidates.length != progress.length)
                throw new IllegalArgumentException("invalid immutable probe");
            this.cameraKey = cameraKey; this.session = session; this.generation = generation;
            this.rendererRevision = rendererRevision; this.textureTimestampNs = textureTimestampNs;
            this.resultTimestampNs = resultTimestampNs; this.observedAtNs = observedAtNs;
            this.completedAtNs = completedAtNs; this.referenceExposureNs = referenceExposureNs;
            this.referenceIso = referenceIso; this.referenceUserEv = referenceUserEv;
            this.referenceAutoEv = referenceAutoEv; this.domain = domain;
            this.candidateUserEv = candidateUserEv;
            if(domain==ProbeDomain.M10R_RENDERED_NEUTRAL_REFERENCE && candidateUserEv!=0.0)
                throw new IllegalArgumentException("neutral lattice must have zero candidate user EV");
            this.rawProxyGrid = rawProxyGrid.clone(); this.candidates = candidates.clone();
            this.progress = progress.clone();
            this.baselineCandidates=baselineCandidates==null?null:baselineCandidates.clone();
            M10RExposureBaseline1F.evaluate(this.baselineCandidates); // validate owned optional E1F evidence
            for (double v : this.rawProxyGrid)
                if (!Double.isFinite(v) || v < 0 || v > 1) throw new IllegalArgumentException("invalid MFM grid");
            for (int i = 0; i < this.candidates.length; i++)
                if (this.candidates[i] == null || this.progress[i] == null)
                    throw new IllegalArgumentException("incomplete rendered candidate");
        }
    }

    /** An explicit per-shutter context. Manual bypass does not allocate/overwrite a pair. */
    public static final class Request {
        public final String cameraKey, rendererRevision;
        public final long session, shutterNs;
        public final double userEv, aperture, focal35;
        public final int minIso, maxIso;
        public final boolean autoIsoAndShutter;
        public final M10RMetering1U.Config metering;
        public Request(String cameraKey, long session, String rendererRevision, long shutterNs,
                double userEv, double aperture, double focal35, int minIso, int maxIso,
                boolean autoIsoAndShutter) {
            this(cameraKey,session,rendererRevision,shutterNs,userEv,aperture,focal35,minIso,maxIso,autoIsoAndShutter,null);
        }
        public Request(String cameraKey,long session,String rendererRevision,long shutterNs,
                double userEv,double aperture,double focal35,int minIso,int maxIso,boolean autoIsoAndShutter,
                M10RMetering1U.Config metering) {
            this.metering=metering;
            if (cameraKey == null || cameraKey.isEmpty() || rendererRevision == null || rendererRevision.isEmpty()
                    || session <= 0 || shutterNs <= 0 || !finiteEv(userEv) || !Double.isFinite(aperture)
                    || aperture <= 0 || !Double.isFinite(focal35) || focal35 <= 0
                    || minIso <= 0 || maxIso < minIso)
                throw new IllegalArgumentException("invalid exposure request");
            this.cameraKey = cameraKey; this.session = session; this.rendererRevision = rendererRevision;
            this.shutterNs = shutterNs; this.userEv = userEv; this.aperture = aperture; this.focal35 = focal35;
            this.minIso = minIso; this.maxIso = maxIso; this.autoIsoAndShutter = autoIsoAndShutter;
        }
    }

    /** No READY plan can contain an unbound or invalid meter. Not a Camera2 request. */
    public static final class Plan {
        public final Status status;
        public final long generation;
        public final double userEv, requestedAutoEv, appliedAutoEv, totalIntentEv, deltaFromReferenceEv;
        public final M10RHighlightGuard1A.Limit highlight;
        public final M10RMfm1B.Decision mfm;
        public final M10RAe1BPolicy.Decision allocation;
        public final M10RExposureBaseline1F.Decision baseline;
        public final M10RMultiField1G.Decision multiField;
        public final M10RMetering1U.Measurement metering;
        private Plan(Status status, long generation, double userEv, double requestedAutoEv,
                double appliedAutoEv, double totalIntentEv, double deltaFromReferenceEv,
                M10RHighlightGuard1A.Limit highlight, M10RMfm1B.Decision mfm,
                M10RAe1BPolicy.Decision allocation, M10RExposureBaseline1F.Decision baseline,
                M10RMultiField1G.Decision multiField,M10RMetering1U.Measurement metering) {
            this.metering=metering;
            this.status = status; this.generation = generation; this.userEv = userEv;
            this.requestedAutoEv = requestedAutoEv; this.appliedAutoEv = appliedAutoEv;
            this.totalIntentEv = totalIntentEv; this.deltaFromReferenceEv = deltaFromReferenceEv;
            this.highlight = highlight; this.mfm = mfm; this.allocation = allocation;
            this.baseline=baseline;
            this.multiField=multiField;
        }
        public boolean ready() { return status == Status.READY; }
    }

    private static Plan rejected(Status why, Request request) {
        return new Plan(why, 0, request.userEv, Double.NaN, Double.NaN, Double.NaN,
                Double.NaN, null, null, null, null, null, null);
    }

    public static Plan prepare(Probe probe, Request request) {
        if (request == null) throw new IllegalArgumentException("request missing");
        if (!request.autoIsoAndShutter) return rejected(Status.BYPASS_MANUAL, request);
        if (probe == null) return rejected(Status.NO_PROBE, request);
        if (!probe.cameraKey.equals(request.cameraKey)) return rejected(Status.SOURCE_MISMATCH, request);
        if (probe.session != request.session) return rejected(Status.SESSION_MISMATCH, request);
        if (!probe.rendererRevision.equals(request.rendererRevision)) return rejected(Status.RENDERER_MISMATCH, request);
        if (probe.domain != ProbeDomain.M10R_RENDERED_NEUTRAL_REFERENCE
                && probe.domain != ProbeDomain.M10R_RENDERED_USER_EV_REFERENCE) return rejected(Status.WRONG_DOMAIN, request);
        if ((probe.metering==null)!=(request.metering==null)
                ||(probe.metering!=null&&!probe.metering.config.key().equals(request.metering.key())))
            return rejected(Status.METERING_MISMATCH,request);
        if (Math.abs(probe.candidateUserEv-request.userEv)>1e-9) return rejected(Status.USER_EV_MISMATCH, request);
        if (probe.textureTimestampNs <= 0 || probe.resultTimestampNs != probe.textureTimestampNs)
            return rejected(Status.TIMESTAMP_MISMATCH, request);
        // Use one monotonic host-clock domain for age. Sensor timestamp equality is
        // a separate check: a sensor timestamp is never subtracted from host time.
        if (probe.observedAtNs <= 0 || probe.completedAtNs < probe.observedAtNs
                || probe.completedAtNs > request.shutterNs || probe.observedAtNs > request.shutterNs
                || request.shutterNs - probe.observedAtNs > MAX_AGE_NS)
            return rejected(Status.STALE_OR_FUTURE, request);
        // E1H production supplies 0..1.5 EV in quarter stops. Complete legacy
        // four-step probes remain valid, but cannot authorize the extended range.
        if (!M10RExposureRange1H.completeLattice(probe.candidates.length))
            return rejected(Status.INCOMPLETE_LATTICE, request);
        M10RMfm1B.Decision mfm = probe.metering==null?M10RMfm1B.evaluate(probe.rawProxyGrid):
                M10RMfm1B.evaluate(probe.metering.cells(),probe.metering.regions());
        if (!mfm.valid) return rejected(Status.INVALID_MFM, request);
        M10RMultiField1G.Decision multiField=null;
        M10RHighlightGuard1A.Limit limit;
        M10RExposureBaseline1F.Decision baseline=M10RExposureBaseline1F.evaluate(probe.baselineCandidates);
        double auto,guarded;
        if(probe.metering!=null) {
            boolean multi=request.metering.mode==M10RMetering1U.Mode.MULTI_FIELD;
            auto=multi?mfm.recommendedEv:probe.metering.spatialEv;
            limit=M10RHighlightGuard1A.limit(probe.candidates,M10RHighlightGuard1A.noSubject(probe.candidates.length));
            // Spot and Centre-Weighted honor their selected field. A bright source
            // elsewhere must not silently turn either into a global highlight meter.
            guarded=multi&&auto>0?Math.min(auto,limit.maxPositiveEv):auto;
            if(multi&&baseline.correctionEv<0)guarded=Math.min(guarded,baseline.correctionEv);
        } else {
            // Historical replay only. Production always supplies a bound mode.
            multiField=M10RMultiField1G.evaluate(mfm,
                    probe.baselineCandidates==null?null:probe.baselineCandidates[0],probe.candidates,probe.progress);
            auto=M10RExposureRange1H.requested(mfm,multiField,probe.candidates.length);
            limit=M10RHighlightGuard1A.limit(probe.candidates,multiField.progress());
            guarded=auto>0?Math.min(auto,limit.maxPositiveEv):auto;
            if(baseline.correctionEv<0) {
                guarded=Math.min(guarded,baseline.correctionEv);
                if(mfm.wouldApply&&mfm.recommendedEv<0)guarded=Math.min(guarded,mfm.recommendedEv);
            }
        }
        double intent = request.userEv + guarded;
        // Both reference terms are explicit, so preview-applied intent cannot be
        // applied a second time. The source producer must neutralize that same
        // reference intent before producing BOTH the grid and rendered candidates.
        double delta = intent - (probe.referenceUserEv + probe.referenceAutoEv);
        M10RAe1BPolicy.Decision allocation = M10RAe1BPolicy.solve(probe.referenceExposureNs,
                probe.referenceIso, request.aperture, request.focal35, delta, request.minIso, request.maxIso);
        if (!allocation.valid || allocation.oracle == null) return rejected(Status.ALLOCATOR_REJECTED, request);
        return new Plan(Status.READY, probe.generation, request.userEv, auto, guarded,
                intent, delta, limit, mfm, allocation, baseline, multiField,probe.metering);
    }

    private static boolean finiteEv(double ev) { return Double.isFinite(ev) && Math.abs(ev) <= 32; }
}
