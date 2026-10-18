package com.particlesdevs.photoncamera.m10r;

import org.junit.After;
import org.junit.Test;
import static org.junit.Assert.*;

public class M10RPreviewCaptureReference1FTest {
    static final long MS=1_000_000L, START=1_100_000_000L, TS=9_000_000_000L;
    final M10RPreviewPlan1ATest fixture=new M10RPreviewPlan1ATest();
    M10RPreviewState1A.Observation frame(Object owner,String key,String controls,long ts,long now,boolean complete){
        return new M10RPreviewState1A.Observation(owner,key,controls,null,null,now,0,0,ts,10_000_000L,200,complete);
    }
    M10RPreviewState1A.Observation frame(long ts,long now,boolean complete){
        return frame(fixture.owner,"cam","controls",ts,now,complete);
    }
    M10RPreviewState1A.Observation reference(long now){
        return M10RPreviewState1A.captureReference(fixture.owner,"cam","controls",now);
    }
    @After public void cleanup(){M10RPreviewState1A.clear(null);}
    @Test public void threeConsecutiveShotsKeepCompleteReferenceWhenLatestFrameIsDisplayOnly(){
        for(int shot=0;shot<3;shot++){
            long now=START+shot*600*MS,ts=TS+shot*600*MS;
            var complete=frame(ts,now,true);M10RPreviewState1A.observe(complete);
            for(int i=1;i<=5;i++){
                var sparse=frame(ts+i*33*MS,now+i*33*MS,false);
                M10RPreviewState1A.observe(sparse);
                assertSame(sparse,M10RPreviewState1A.forTexture(sparse.timestamp,sparse.observedNs));
            }
            // Both starting the meter and completing it may follow a sparse callback.
            assertSame("shutter "+shot,complete,reference(now+165*MS));
            M10RPreviewState1A.observe(frame(ts+300*MS,now+300*MS,false));
            assertSame("meter completion "+shot,complete,reference(now+300*MS));
            assertEquals(now,reference(now+300*MS).observedNs);
        }
    }
    @Test public void longPartialBurstNeverRefreshesAgeEvenWhenDisplayDequeRollsOver(){
        var complete=frame(TS,START,true);M10RPreviewState1A.observe(complete);
        for(int i=1;i<=80;i++)M10RPreviewState1A.observe(frame(TS+i*10*MS,START+i*10*MS,false));
        assertNull(M10RPreviewState1A.forTexture(TS,START+800*MS));
        assertSame(complete,reference(START+1200*MS));
        assertNull(reference(START+1200*MS+1));assertNull(reference(START-1));
    }
    @Test public void duplicateOrOutOfOrderCompleteResultsCannotRenewOldEvidence(){
        var complete=frame(TS,START,true);M10RPreviewState1A.observe(complete);
        M10RPreviewState1A.observe(frame(TS,START+900*MS,true));
        M10RPreviewState1A.observe(frame(TS-1,START+1000*MS,true));
        assertSame(complete,reference(START+1100*MS));
        assertNull(reference(START+1201*MS));
        var next=frame(TS+1300*MS,START+1300*MS,true);M10RPreviewState1A.observe(next);
        assertSame(next,reference(START+1301*MS));
    }
    @Test public void newSessionLensOrControlsClearsReferenceEvenIfNewFrameIsSparse(){
        for(int variant=0;variant<3;variant++){
            M10RPreviewState1A.clear(null);M10RPreviewState1A.observe(frame(TS,START,true));
            Object owner=variant==0?new Object():fixture.owner;
            String key=variant==1?"tele":"cam",controls=variant==2?"newEV":"controls";
            M10RPreviewState1A.observe(frame(owner,key,controls,TS+MS,START+MS,false));
            assertNull(reference(START+MS));
            assertNull(M10RPreviewState1A.captureReference(owner,key,controls,START+MS));
        }
    }
    @Test public void lookupRejectsDifferentIdentityAndRetirementClearsReference(){
        M10RPreviewState1A.observe(frame(TS,START,true));
        assertNull(M10RPreviewState1A.captureReference(new Object(),"cam","controls",START));
        assertNull(M10RPreviewState1A.captureReference(fixture.owner,"tele","controls",START));
        assertNull(M10RPreviewState1A.captureReference(fixture.owner,"cam","newEV",START));
        M10RPreviewState1A.clear(fixture.owner);assertNull(reference(START));
        M10RPreviewState1A.observe(frame(TS+MS,START+MS,false));assertNull(reference(START+MS));
    }
    @Test public void rejectedResultPreservesSameSourceOnlyWithinOriginalDeadline(){
        var complete=frame(TS,START,true);M10RPreviewState1A.observe(complete);
        M10RPreviewState1A.rejectObservation(fixture.owner,"cam","controls","preview_sensor_ISO_missing");
        assertSame(complete,reference(START+100*MS));assertNull(reference(START+1201*MS));
        M10RPreviewState1A.rejectObservation(fixture.owner,"tele","controls","wrong_physical_source");
        assertNull(reference(START+100*MS));
    }
    @Test public void retainedReferenceDoesNotMakeDisplayOnlyFrameCaptureEligible(){
        var complete=frame(TS,START,true);M10RPreviewState1A.observe(complete);
        var p=fixture.plan(0,false);M10RPreviewState1A.publish(p);
        var sparse=frame(TS+33*MS,START+33*MS,false);M10RPreviewState1A.observe(sparse);
        M10RPreviewState1A.displayed(sparse,p,START+33*MS,"display_only_request_EV");
        assertSame(complete,reference(START+33*MS));
        assertEquals(0,M10RPreviewState1A.display().planId);
        assertFalse(fixture.capture(p,START+33*MS,M10RPreviewState1A.display().planId));
    }
}
