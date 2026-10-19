package com.particlesdevs.photoncamera.m10r;

import org.junit.After;
import org.junit.Test;
import static org.junit.Assert.*;

public class M10RPreviewPresentation1DTest {
    static final long MS=1_000_000L, START=1_100_000_000L, TS=9_000_000_000L;
    final M10RPreviewPlan1ATest fixture=new M10RPreviewPlan1ATest();
    M10RPreviewState1A.Observation frame(long ts,long now){
        return fixture.frame(fixture.owner,"cam","controls",ts,now);
    }
    @After public void cleanup(){M10RPreviewState1A.clear(null);}
    @Test public void recentDisplaySelectsNearestPrecedingResultRegardlessOfArrivalOrder(){
        var older=frame(TS,START);var nearest=frame(TS+50*MS,START+60*MS);
        M10RPreviewState1A.observe(nearest);M10RPreviewState1A.observe(older);
        assertSame(nearest,M10RPreviewState1A.recentForDisplay(TS+70*MS,START+75*MS));
        assertNull(M10RPreviewState1A.forTexture(TS+70*MS,START+75*MS));
    }
    @Test public void recentDisplayRejectsFutureAndOldSensorFramesEvenWithFreshArrival(){
        M10RPreviewState1A.observe(frame(TS,START));
        assertNull(M10RPreviewState1A.recentForDisplay(TS-1,START));
        assertNull(M10RPreviewState1A.recentForDisplay(TS,START));
        assertNull(M10RPreviewState1A.recentForDisplay(TS+101*MS,START+MS));
        assertNotNull(M10RPreviewState1A.recentForDisplay(TS+100*MS,START+100*MS));
    }
    @Test public void recentDisplayCannotRenewAnOutageOrUseFutureArrivalClock(){
        M10RPreviewState1A.observe(frame(TS,START));
        for(int i=1;i<=100;i++)assertNotNull(M10RPreviewState1A.recentForDisplay(TS+MS,START+i*MS));
        assertNull(M10RPreviewState1A.recentForDisplay(TS+MS,START+101*MS));
        assertNull(M10RPreviewState1A.recentForDisplay(TS+MS,START-1));
    }
    @Test public void recentDisplayNeverCrossesLensControlsSessionOrRetirement(){
        for(int variant=0;variant<4;variant++){
            M10RPreviewState1A.observe(frame(TS,START));
            if(variant==3)M10RPreviewState1A.clear(null);
            else M10RPreviewState1A.observe(fixture.frame(variant==0?new Object():fixture.owner,
                    variant==1?"tele":"cam",variant==2?"newEV":"controls",TS+20*MS,START+20*MS));
            assertNull(M10RPreviewState1A.recentForDisplay(TS+10*MS,START+30*MS));
        }
    }
    @Test public void smoothingConvergesToExactTargetAndLongCapturePauseDoesNotCatchUpInOneFrame(){
        var e=new M10RPreviewExposure1D();var o=frame(TS,START);
        assertEquals(4,e.update(o,4,START),1e-12);
        double scale=e.update(o,1,START+5_000*MS);
        assertEquals(1.85,Math.log(scale)/Math.log(2),1e-12);
        assertFalse(M10RPreviewExposure1D.settled(scale,1));
        for(int i=1;i<=30;i++)scale=e.update(o,1,START+5_000*MS+i*33*MS);
        assertTrue(M10RPreviewExposure1D.settled(scale,1));assertEquals(1,scale,0);
    }
    @Test public void smoothingNeverBlendsAcrossControlsOrPhysicalCameraChanges(){
        var e=new M10RPreviewExposure1D();e.update(frame(TS,START),4,START);
        var next=fixture.frame(fixture.owner,"tele","controls",TS+MS,START+MS);
        assertEquals(1,e.update(next,1,START+MS),0);
        next=fixture.frame(fixture.owner,"tele","newEV",TS+2*MS,START+2*MS);
        assertEquals(2,e.update(next,2,START+2*MS),0);
        e.clear();assertEquals(.5,e.update(next,.5,START+3*MS),0);
    }
    @Test public void displayOnlyDrawAndTransitionCannotMakeExpiredEvidenceCaptureEligible(){
        var o=frame(TS,START);M10RPreviewState1A.observe(o);
        var p=fixture.plan(0,false);M10RPreviewState1A.publish(p);
        M10RPreviewState1A.displayed(o,null,START,"display_only_recent_metadata");
        assertFalse(fixture.capture(p,START,M10RPreviewState1A.display().planId));
        M10RPreviewState1A.displayed(o,p,START,"E1H_plan_displayed");
        assertTrue(fixture.capture(p,START,M10RPreviewState1A.display().planId));
        assertFalse(fixture.capture(p,START+1_201*MS,M10RPreviewState1A.display().planId));
    }
    @Test public void incompleteResultPreservesBoundedDisplayEvidenceWithoutRenewingIt(){
        var o=frame(TS,START);M10RPreviewState1A.observe(o);
        var p=fixture.plan(0,false);M10RPreviewState1A.publish(p);
        M10RPreviewState1A.displayed(o,p,START,"drawn");
        M10RPreviewState1A.rejectObservation(fixture.owner,"cam","controls");
        assertEquals(0,M10RPreviewState1A.display().planId);
        assertSame(p,M10RPreviewState1A.plan());
        assertSame(o,M10RPreviewState1A.recentForDisplay(TS+33*MS,START+33*MS));
        for(int i=0;i<10;i++)M10RPreviewState1A.rejectObservation(fixture.owner,"cam","controls");
        assertNull(M10RPreviewState1A.recentForDisplay(TS+33*MS,START+101*MS));
    }
    @Test public void incompleteResultCannotPreserveEvidenceAcrossChangedIdentity(){
        for(int variant=0;variant<3;variant++){
            M10RPreviewState1A.observe(frame(TS,START));M10RPreviewState1A.publish(fixture.plan(0,false));
            M10RPreviewState1A.rejectObservation(variant==0?new Object():fixture.owner,
                    variant==1?"tele":"cam",variant==2?"newEV":"controls");
            assertNull(M10RPreviewState1A.plan());
            assertNull(M10RPreviewState1A.recentForDisplay(TS+33*MS,START+33*MS));
        }
    }
}
