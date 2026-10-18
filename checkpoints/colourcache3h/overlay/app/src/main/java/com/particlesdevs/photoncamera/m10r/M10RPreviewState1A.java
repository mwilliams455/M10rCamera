package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CaptureResult;
import java.util.ArrayDeque;

/** Bounded exact-timestamp metadata exchange; no camera requests originate on the GL thread. */
public final class M10RPreviewState1A {
    private M10RPreviewState1A() {}
    private static final ArrayDeque<Observation> frames=new ArrayDeque<>();
    // A display-only callback must not erase the last complete metering result.
    // Keep its original sensor timestamp and arrival time; never renew it on a gap.
    private static Observation captureReference;
    // Separate authority: fresh physical measurements plus explicit request EV
    // may seed a NEW RAW probe, but cannot authorize reuse of a displayed plan.
    private static Observation meterReference;
    private static Object currentOwner;
    private static String currentControls,currentKey;
    private static volatile M10RPreviewPlan1A plan;
    // Display-only pairing tolerates a result arriving just after its texture. It is
    // never used by forTexture() or by captureEligible(). Both clocks are bounded.
    public static final long DISPLAY_METADATA_LAG_NS=100_000_000L;
    private static long exactBinds,heldBinds,fallbackBinds,recentBinds,transitionBinds,rejectedResults,requestEvResults,meterSeedResults;
    private static String lastFallback="none";
    private static String lastRejected="none";
    private static double lastScale=1;
    public static final class Display {
        public final long planId,atNs;
        public final String status;
        private Display(long id,long at,String status){planId=id;atNs=at;this.status=status;}
    }
    private static volatile Display display=new Display(0,0,"waiting_for_preview");
    public static Display display(){return display;}
    public static void unavailable(String reason){display=new Display(0,0,reason);}
    public static synchronized void countExact(){exactBinds++;}
    public static synchronized void countHeld(String reason){
        heldBinds++;unavailable("display_only_metadata_grace:"+reason);
    }
    public static synchronized void countFallback(String reason){fallbackBinds++;lastFallback=reason;unavailable(reason);}
    public static synchronized void countRecent(){recentBinds++;}
    public static synchronized void countRequestEv(){requestEvResults++;}
    public static synchronized void presentation(double scale,boolean transition){
        lastScale=scale;if(transition)transitionBinds++;
    }
    public static synchronized String debugStatus(){
        String status=display.status;
        if(status.equals("M10R_colour_user_EV_waiting_for_guarded_plan"))status="colour / waiting for meter";
        else if(status.equals("recent_plan_display_only_capture_will_recheck"))status="recent plan / shutter rechecks";
        else if(status.equals("display_only_recent_metadata"))status="recent metadata / display only";
        else if(status.equals("display_only_exposure_transition"))status="exposure settling / display only";
        else if(status.equals("display_only_request_EV"))status="request EV / display only";
        return String.format(java.util.Locale.US,"%.2fx ",lastScale)+status;
    }
    public static synchronized String debugCounts(){
        return "E="+exactBinds+" R="+recentBinds+" H="+heldBinds+" F="+fallbackBinds+" bad="+rejectedResults+" req="+requestEvResults+" seed="+meterSeedResults;
    }
    public static synchronized String debugReason(){return "fallback="+lastFallback+"; rejected="+lastRejected
            +"; meter="+(meterReference==null?"none":meterReference.referenceEvSource);}
    public static synchronized void appendDiagnostics(org.json.JSONObject d)throws org.json.JSONException {
        d.put("previewContinuityRevision","M10R_PREVIEW1I_METER_REFERENCE");
        d.put("previewColourRevision","M10R_PREVIEW1J_COLOUR_REFRESH");
        d.put("previewMetadataGraceMs",M10RPreviewContinuity1C.GRACE_NS/1_000_000L);
        d.put("previewDisplayMetadataLagMs",DISPLAY_METADATA_LAG_NS/1_000_000L);
        d.put("previewExactBindCount",exactBinds);d.put("previewHeldBindCount",heldBinds);
        d.put("previewFallbackBindCount",fallbackBinds);
        d.put("previewRecentBindCount",recentBinds);d.put("previewTransitionBindCount",transitionBinds);
        d.put("previewLastFallback",lastFallback);d.put("previewExposureScale",lastScale);
        d.put("previewRejectedResultCount",rejectedResults);
        d.put("previewRequestEvResultCount",requestEvResults);d.put("previewLastRejectedReason",lastRejected);
        d.put("previewRequestEvMeterSeedCount",meterSeedResults);
        d.put("previewMeterReferenceSource",meterReference==null?"none":meterReference.referenceEvSource);
    }
    public static synchronized void displayed(Observation o,M10RPreviewPlan1A p,long now,String status){
        if(current(o)&&(p==null||p==plan))display=new Display(p==null||!o.captureEvidence?0:p.id,now,status);
    }
    public static final class Observation {
        public final Object owner;
        public final String key,controls;
        public final CameraCharacteristics characteristics;
        public final CaptureResult result;
        public final long timestamp,observedNs,exposureNs;
        public final int iso;
        public final double userEv,referenceEv;
        public final boolean captureEvidence;
        public final boolean meterEvidence;
        public final String referenceEvSource;
        public Observation(Object owner,String key,String controls,CameraCharacteristics c,CaptureResult r,
                long now,double userEv,double referenceEv) {
            this(owner,key,controls,c,r,now,userEv,referenceEv,true);
        }
        public Observation(Object owner,String key,String controls,CameraCharacteristics c,CaptureResult r,
                long now,double userEv,double referenceEv,boolean captureEvidence) {
            this(owner,key,controls,c,r,now,userEv,referenceEv,r.get(CaptureResult.SENSOR_TIMESTAMP),
                    r.get(CaptureResult.SENSOR_EXPOSURE_TIME),r.get(CaptureResult.SENSOR_SENSITIVITY),captureEvidence);
        }
        public Observation(Object owner,String key,String controls,CameraCharacteristics c,CaptureResult r,
                long now,double userEv,double referenceEv,boolean captureEvidence,boolean requestMeterSeed) {
            this(owner,key,controls,c,r,now,userEv,referenceEv,r.get(CaptureResult.SENSOR_TIMESTAMP),
                    r.get(CaptureResult.SENSOR_EXPOSURE_TIME),r.get(CaptureResult.SENSOR_SENSITIVITY),captureEvidence,requestMeterSeed);
        }
        Observation(Object owner,String key,String controls,CameraCharacteristics c,CaptureResult r,
                long now,double userEv,double referenceEv,Long ts,Long ns,Integer sensitivity) {
            this(owner,key,controls,c,r,now,userEv,referenceEv,ts,ns,sensitivity,true);
        }
        Observation(Object owner,String key,String controls,CameraCharacteristics c,CaptureResult r,
                long now,double userEv,double referenceEv,Long ts,Long ns,Integer sensitivity,boolean captureEvidence) {
            this(owner,key,controls,c,r,now,userEv,referenceEv,ts,ns,sensitivity,captureEvidence,false);
        }
        Observation(Object owner,String key,String controls,CameraCharacteristics c,CaptureResult r,
                long now,double userEv,double referenceEv,Long ts,Long ns,Integer sensitivity,
                boolean captureEvidence,boolean requestMeterSeed) {
            if(owner==null||key==null||controls==null||ts==null||ts<=0||ns==null||ns<=0
                    ||sensitivity==null||sensitivity<=0||!Double.isFinite(userEv)||!Double.isFinite(referenceEv))
                throw new IllegalArgumentException("preview observation binding");
            this.owner=owner;this.key=key;this.controls=controls;characteristics=c;result=r;
            timestamp=ts;exposureNs=ns;iso=sensitivity;observedNs=now;
            this.userEv=userEv;this.referenceEv=referenceEv;
            this.captureEvidence=captureEvidence;
            meterEvidence=captureEvidence||requestMeterSeed;
            referenceEvSource=captureEvidence?"reported_preview_EV":requestMeterSeed?"matched_request_EV":"display_only_request_EV";
        }
    }
    public static synchronized void observe(Observation o) {
        if(currentOwner!=o.owner||!o.controls.equals(currentControls)||!o.key.equals(currentKey)) {
            frames.clear();captureReference=null;meterReference=null;plan=null;resetDiagnostics();
            unavailable("camera_or_controls_changed");
        }
        currentOwner=o.owner;currentControls=o.controls;currentKey=o.key;
        frames.addLast(o);while(frames.size()>48)frames.removeFirst();
        if(o.captureEvidence&&(captureReference==null||o.timestamp>captureReference.timestamp))
            captureReference=o;
        if(o.meterEvidence&&(meterReference==null||o.timestamp>meterReference.timestamp)) {
            meterReference=o;
            if(!o.captureEvidence)meterSeedResults++;
        }
    }
    /** A complete result may seed a new RAW meter, under the existing 1.2 s limit.
     * This does not acknowledge a displayed plan or authorize plan reuse. */
    public static synchronized Observation captureReference(Object owner,String key,String controls,long now){
        Observation o=captureReference;
        return current(o)&&o.owner==owner&&o.key.equals(key)&&o.controls.equals(controls)
                &&now>=o.observedNs&&now-o.observedNs<=M10RExposure1A.MAX_AGE_NS?o:null;
    }
    /** Request-EV seeds retain physical timestamp, exposure and ISO. This lookup
     * never promotes them to captureEvidence or plan reuse. Colour reconstruction
     * separately requires complete, reported colour metadata. */
    public static synchronized Observation meterReference(Object owner,String key,String controls,long now){
        Observation o=meterReference;
        return current(o)&&o.owner==owner&&o.key.equals(key)&&o.controls.equals(controls)
                &&now>=o.observedNs&&now-o.observedNs<=M10RExposure1A.MAX_AGE_NS?o:null;
    }
    public static synchronized Observation forTexture(long timestamp,long now) {
        for(Observation o:frames)if(o.timestamp==timestamp&&now>=o.observedNs
                &&now-o.observedNs<=250_000_000L)return o;
        return null;
    }
    public static synchronized Observation recentForDisplay(long timestamp,long now) {
        Observation best=null;
        for(Observation o:frames)if(o.timestamp<timestamp&&timestamp-o.timestamp<=DISPLAY_METADATA_LAG_NS
                &&now>=o.observedNs&&now-o.observedNs<=DISPLAY_METADATA_LAG_NS
                &&(best==null||o.timestamp>best.timestamp))best=o;
        return best;
    }
    /** A malformed result is no new evidence. Keep the prior display evidence under
     * its ORIGINAL age bounds, but retire it immediately if any identity changed. */
    public static synchronized void rejectObservation(Object owner,String key,String controls){
        rejectObservation(owner,key,controls,"unspecified_incomplete_result");
    }
    public static synchronized void rejectObservation(Object owner,String key,String controls,String reason){
        if(owner!=currentOwner||!java.util.Objects.equals(key,currentKey)
                ||!java.util.Objects.equals(controls,currentControls))clear(null);
        rejectedResults++;lastRejected=reason==null?"unspecified_incomplete_result":reason;
        unavailable("preview_result_incomplete");
    }
    public static synchronized boolean current(Observation o) {
        return o!=null&&currentOwner==o.owner&&o.controls.equals(currentControls)&&o.key.equals(currentKey);
    }
    public static synchronized void publish(M10RPreviewPlan1A p) {
        if(currentOwner==p.owner&&p.controls.equals(currentControls)&&p.cameraKey.equals(currentKey))plan=p;
    }
    public static M10RPreviewPlan1A plan(){return plan;}
    public static synchronized void clear(Object owner) {
        if(owner!=null&&owner!=currentOwner)return;
        frames.clear();captureReference=null;meterReference=null;plan=null;currentOwner=null;currentControls=null;currentKey=null;
        resetDiagnostics();
        unavailable("waiting_for_preview");
    }
    private static void resetDiagnostics(){
        exactBinds=heldBinds=fallbackBinds=recentBinds=transitionBinds=rejectedResults=requestEvResults=meterSeedResults=0;
        lastFallback=lastRejected="none";lastScale=1;
    }
}
