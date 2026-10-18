package com.particlesdevs.photoncamera.m10r;

/** Immutable allocation adapter for the existing still-request freeze point. */
public final class M10RExposureCapture1B {
    public static final String RAW_GAIN_REVISION="M10R_PREVIEW1K_RAW_GAIN_ALLOCATION";
    public static final String BRIGHT_RANGE_REVISION="M10R_BRIGHTRANGE1N_PHYSICAL_FAST_SHUTTER";
    private M10RExposureCapture1B() {}
    public static final class Limits {
        public final long minNs,maxNs;public final int minIso,maxIso;
        public final Integer maxAnalogIso;
        public Limits(long minNs,long maxNs,int minIso,int maxIso){
            this(minNs,maxNs,minIso,maxIso,null);
        }
        public Limits(long minNs,long maxNs,int minIso,int maxIso,Integer maxAnalogIso){
            if(minNs<=0||maxNs<minNs||minIso<=0||maxIso<minIso)throw new IllegalArgumentException("device ranges");
            this.minNs=minNs;this.maxNs=maxNs;this.minIso=minIso;this.maxIso=maxIso;
            // Missing or contradictory characteristics cannot justify a guessed cap.
            this.maxAnalogIso=maxAnalogIso!=null&&maxAnalogIso>=minIso&&maxAnalogIso<=maxIso?maxAnalogIso:null;
        }
    }
    public static final class Reference {
        public final String cameraKey;public final long session,observedNs,exposureNs;
        public final int iso;public final double userEv,autoEv;
        public Reference(String key,long session,long observed,long exposure,int iso,double user,double auto){
            if(key==null||key.isEmpty()||session<=0||observed<=0||exposure<=0||iso<=0
                    ||!Double.isFinite(user)||!Double.isFinite(auto)||Math.abs(user)>32||Math.abs(auto)>32)
                throw new IllegalArgumentException("reference");
            cameraKey=key;this.session=session;observedNs=observed;exposureNs=exposure;this.iso=iso;userEv=user;autoEv=auto;
        }
    }
    public static final class Selection {
        public final M10RExposure1A.Plan plan;
        public final M10RAe1BPolicy.Decision allocation;
        public final boolean apply,manualBypass,fallback,clamped;
        public final long exposureNs;public final int iso;
        public final int autoIsoCeiling,verifiedRawIso;
        public final double appliedAutoEv,allocationResidualEv;
        public final double brightRangeCorrectionEv,targetExposureProduct;
        public final M10RPhoneExposure2U.Result phoneExposure;
        Selection(M10RExposure1A.Plan p,M10RAe1BPolicy.Decision d,boolean apply,boolean manual,
                boolean fallback,boolean clamp,long ns,int iso,double auto,double residual){
            this(p,d,apply,manual,fallback,clamp,ns,iso,auto,residual,0,0,0,0,null);
        }
        Selection(M10RExposure1A.Plan p,M10RAe1BPolicy.Decision d,boolean apply,boolean manual,
                boolean fallback,boolean clamp,long ns,int iso,double auto,double residual,int ceiling,int verified,
                double brightCorrection,double targetProduct,M10RPhoneExposure2U.Result phone){
            plan=p;allocation=d;this.apply=apply;manualBypass=manual;this.fallback=fallback;clamped=clamp;
            exposureNs=ns;this.iso=iso;appliedAutoEv=auto;allocationResidualEv=residual;
            autoIsoCeiling=ceiling;verifiedRawIso=verified;
            brightRangeCorrectionEv=brightCorrection;targetExposureProduct=targetProduct;
            phoneExposure=phone;
        }
    }
    /**
     * Invalid colour evidence cannot authorise an unverified +MFM boost. A fresh exact
     * reference permits user-EV-only fallback. Missing reference -> no new allocation;
     * the caller must retain its physical preview request, NOT fall through to old +MFM.
     */
    public static Selection select(M10RExposure1A.Probe probe,M10RExposure1A.Request r,Reference fallback,Limits lim){
        if(lim==null)throw new IllegalArgumentException("physical ranges required");
        M10RExposure1A.Plan p=M10RExposure1A.prepare(probe,r);
        if(p.status==M10RExposure1A.Status.BYPASS_MANUAL)return new Selection(p,null,false,true,false,false,0,0,0,0);
        M10RAe1BPolicy.Decision d=p.allocation;boolean fb=!p.ready();
        if(fb){
            if(fallback==null||!fallback.cameraKey.equals(r.cameraKey)||fallback.session!=r.session
                    ||fallback.observedNs>r.shutterNs||r.shutterNs-fallback.observedNs>M10RExposure1A.MAX_AGE_NS)
                return new Selection(p,null,false,false,true,false,0,0,0,0);
            d=M10RAe1BPolicy.solve(fallback.exposureNs,fallback.iso,r.aperture,r.focal35,
                    r.userEv-fallback.userEv-fallback.autoEv,r.minIso,r.maxIso);
        }
        if(d==null||!d.valid||d.oracle==null)return new Selection(p,null,false,false,fb,false,0,0,0,0);
        // Retain the historical bright-range quantity for diagnostic comparison.
        // 2U obtains the phone target directly from its bound reference instead;
        // this legacy multiplier is no longer applied to the exposure product.
        double brightCorrection=d.oracle.tvQ8==M10RAeOracle.TV_MAX_Q8
                && !d.oracle.autoIsoActivated && d.oracle.dEvQ8>0 ? -d.oracle.dEv() : 0;
        // The advertised sensitivity range may exceed what a manual RAW request
        // delivers. Prefer the physical analog range, permitting higher gain only
        // when this fresh, fully validated RAW probe actually reported it. This is
        // a conservative host policy, not a claim that all digital RAW gain is invalid.
        // Preview-only fallback and rejected/stale/wrong-source probes grant no such evidence.
        int verified=p.ready()?probe.referenceIso:0;
        int ceiling=lim.maxAnalogIso==null?lim.maxIso:Math.min(lim.maxIso,Math.max(lim.maxAnalogIso,verified));
        M10RPhoneExposure2U.Result phone=M10RPhoneExposure2U.allocate(d,lim.minNs,lim.maxNs,lim.minIso,ceiling);
        return new Selection(p,d,true,false,fb,phone.physicalClamped,phone.exposureNs,phone.iso,
                fb?0:p.appliedAutoEv,phone.residualEv,ceiling,verified,
                brightCorrection,phone.targetProduct,phone);
    }
}
