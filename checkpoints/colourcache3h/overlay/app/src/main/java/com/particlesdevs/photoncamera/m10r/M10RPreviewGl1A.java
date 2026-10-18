package com.particlesdevs.photoncamera.m10r;

import android.opengl.GLES20;
import java.nio.ByteBuffer;

/** GL-owned textures. Missing colour/plan evidence never disables the ordinary preview or shutter. */
public final class M10RPreviewGl1A {
    private final java.util.function.LongSupplier clock;
    public M10RPreviewGl1A(){this(System::nanoTime);}
    M10RPreviewGl1A(java.util.function.LongSupplier clock){this.clock=clock;}
    private final int[] textures=new int[2];
    private M10RPreviewColour1A.Frame uploaded;
    private M10RPreviewState1A.Observation pendingObservation;
    private M10RPreviewPlan1A pendingPlan;
    private String pendingStatus;
    private M10RPreviewColour1A.Frame pendingColour;
    private double pendingScale;
    private boolean pendingExact;
    private final M10RPreviewExposure1D exposure=new M10RPreviewExposure1D();
    private final M10RPreviewContinuity1C continuity=new M10RPreviewContinuity1C();
    public void contextCreated(){textures[0]=textures[1]=0;uploaded=null;continuity.clear();exposure.clear();}
    public void bind(int program,long textureTimestamp) {
        pendingObservation=null;pendingPlan=null;pendingColour=null;pendingExact=false;
        try {bindChecked(program,textureTimestamp);}
        catch(RuntimeException|LinkageError|OutOfMemoryError e){
            uploaded=null;pendingObservation=null;pendingPlan=null;continuity.clear();exposure.clear();
            GLES20.glUniform1i(GLES20.glGetUniformLocation(program,"m10rEnabled"),0);
            M10RPreviewState1A.unavailable("preview_transform_unavailable");
        }finally{GLES20.glActiveTexture(GLES20.GL_TEXTURE0);}
    }
    /** Called after the sharp preview draw; acknowledgement is one atomic record. */
    public void drawn(){
        if(pendingObservation!=null&&GLES20.glGetError()==GLES20.GL_NO_ERROR) {
            long now=clock.getAsLong();
            M10RPreviewState1A.displayed(pendingObservation,pendingPlan,now,pendingStatus);
            // An approximate display must not renew the old exact-frame grace.
            if(pendingExact)continuity.drawn(pendingObservation,pendingColour,pendingScale,now);
        }
    }
    private void bindChecked(int program,long textureTimestamp) {
        int enabled=GLES20.glGetUniformLocation(program,"m10rEnabled");
        GLES20.glUniform1i(enabled,0);
        // Active samplers of different types must never alias unit zero, even on fallback.
        GLES20.glUniform1i(GLES20.glGetUniformLocation(program,"m10rLut"),1);
        GLES20.glUniform1i(GLES20.glGetUniformLocation(program,"m10rInverse"),2);
        M10RPreviewState1A.unavailable("preview_transform_pending");
        long now=clock.getAsLong();
        M10RPreviewState1A.Observation o=M10RPreviewState1A.forTexture(textureTimestamp,now);
        boolean timestampMatched=o!=null;
        if(o==null)o=M10RPreviewState1A.recentForDisplay(textureTimestamp,now);
        if(o==null){hold(program,textureTimestamp,now,"texture_metadata_unmatched");return;}
        boolean exact=timestampMatched&&o.captureEvidence;
        M10RPreviewColour1A.Frame f=M10RPreviewColour1A.request(o,now);
        if(f==null||!f.ready){hold(program,textureTimestamp,now,f==null?"colour_pending":f.reason);return;}
        applyColour(program,f);
        M10RPreviewPlan1A p=M10RPreviewState1A.plan();
        double scale=Math.pow(2,o.userEv-o.referenceEv);
        if(p!=null&&p.matches(o.owner,o.key,o.controls,now)&&p.stableReference(o.exposureNs,o.iso)) {
            scale=p.previewScale(o.exposureNs,o.iso);
            if(exact)pendingPlan=p;
            pendingStatus=now-p.observedNs<=M10RExposure1A.MAX_AGE_NS
                    ?"E1H_plan_displayed":"recent_plan_display_only_capture_will_recheck";
        } else pendingStatus="M10R_colour_user_EV_waiting_for_guarded_plan";
        double target=scale;
        scale=exposure.update(o,target,now);
        boolean settled=M10RPreviewExposure1D.settled(scale,target);
        if(!settled){pendingPlan=null;pendingStatus="display_only_exposure_transition";}
        if(!exact){pendingPlan=null;pendingStatus="display_only_recent_metadata";}
        if(!o.captureEvidence)pendingStatus="display_only_request_EV";
        pendingObservation=o;pendingColour=f;pendingScale=scale;pendingExact=exact;
        GLES20.glUniform1f(GLES20.glGetUniformLocation(program,"m10rExposureScale"),(float)scale);
        GLES20.glUniform1i(enabled,1);
        if(exact)M10RPreviewState1A.countExact();else M10RPreviewState1A.countRecent();
        M10RPreviewState1A.presentation(scale,!settled);
        GLES20.glActiveTexture(GLES20.GL_TEXTURE0);
    }
    private void hold(int program,long timestamp,long now,String reason) {
        M10RPreviewContinuity1C.Held held=continuity.held(timestamp,now);
        if(held==null){M10RPreviewState1A.countFallback(reason);return;}
        applyColour(program,held.colour);
        GLES20.glUniform1f(GLES20.glGetUniformLocation(program,"m10rExposureScale"),(float)held.scale);
        GLES20.glUniform1i(GLES20.glGetUniformLocation(program,"m10rEnabled"),1);
        // Keep live motion, but do not acknowledge this unmatched frame for capture.
        M10RPreviewState1A.countHeld(reason);
    }
    private void applyColour(int program,M10RPreviewColour1A.Frame f) {
        if(textures[0]==0)GLES20.glGenTextures(2,textures,0);
        if(uploaded!=f) {
            upload(1,textures[0],M10RPreviewColour1A.SIZE*M10RPreviewColour1A.SIZE,M10RPreviewColour1A.SIZE,f.pixels,GLES20.GL_LINEAR);
            upload(2,textures[1],1024,2,f.inverse,GLES20.GL_NEAREST);uploaded=f;
        }
        GLES20.glActiveTexture(GLES20.GL_TEXTURE1);GLES20.glBindTexture(GLES20.GL_TEXTURE_2D,textures[0]);
        GLES20.glActiveTexture(GLES20.GL_TEXTURE2);GLES20.glBindTexture(GLES20.GL_TEXTURE_2D,textures[1]);
        GLES20.glUniform1i(GLES20.glGetUniformLocation(program,"m10rLut"),1);
        GLES20.glUniform1i(GLES20.glGetUniformLocation(program,"m10rInverse"),2);
        GLES20.glUniformMatrix3fv(GLES20.glGetUniformLocation(program,"m10rUndo"),1,false,f.undo,0);
    }
    private static void upload(int unit,int texture,int w,int h,byte[] bytes,int filter) {
        GLES20.glActiveTexture(GLES20.GL_TEXTURE0+unit);GLES20.glBindTexture(GLES20.GL_TEXTURE_2D,texture);
        GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D,GLES20.GL_TEXTURE_MIN_FILTER,filter);
        GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D,GLES20.GL_TEXTURE_MAG_FILTER,filter);
        GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D,GLES20.GL_TEXTURE_WRAP_S,GLES20.GL_CLAMP_TO_EDGE);
        GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D,GLES20.GL_TEXTURE_WRAP_T,GLES20.GL_CLAMP_TO_EDGE);
        ByteBuffer b=ByteBuffer.allocateDirect(bytes.length);b.put(bytes).position(0);
        GLES20.glTexImage2D(GLES20.GL_TEXTURE_2D,0,GLES20.GL_RGBA,w,h,0,GLES20.GL_RGBA,GLES20.GL_UNSIGNED_BYTE,b);
        if(GLES20.glGetError()!=GLES20.GL_NO_ERROR)throw new IllegalStateException("preview_texture_upload_failed");
    }
}
