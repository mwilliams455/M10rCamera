package com.particlesdevs.photoncamera.m10r;

import org.junit.Test;
import org.junit.After;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CaptureResult;

public class M10RPreviewPlan1ATest {
    final Object owner=new Object();
    M10RPreviewPlan1A plan(double user,boolean negative) {
        var probe=M10RExposureRange1HTest.probe(7,-1,user,negative,M10RExposureRange1HTest.backlit());
        var selected=M10RExposureCapture1B.select(probe,M10RExposureRange1HTest.request(user,true,1_020_000_000L),null,
                new M10RExposureCapture1B.Limits(1,1_000_000_000L,50,6400));
        return new M10RPreviewPlan1A(7,owner,"cam","controls",probe.observedAtNs,1_020_000_000L,
                probe.referenceExposureNs,probe.referenceIso,selected,null);
    }
    boolean capture(M10RPreviewPlan1A p,long now,long displayed) {
        return p.captureEligible(owner,"cam","controls",now,10_000_000L,200,displayed,now);
    }
    @After public void cleanup(){M10RPreviewState1A.clear(null);}
    @Test public void freshDisplayedPlanKeepsExactRealAllocatorPair(){
        var p=plan(0,false);assertTrue(capture(p,1_100_000_000L,7));
        assertEquals(M10RExposureRange1HTest.SYNTHETIC_DEMAND,p.selection.appliedAutoEv,1e-12);
        double expected=(double)p.selection.exposureNs*p.selection.iso/(10_000_000.0*200);
        assertEquals(expected,p.previewScale(10_000_000,200),1e-12);
    }
    @Test public void actualPreviewExposureRemovesAlreadyAppliedIntentExactlyOnce(){
        for(double user:new double[]{-1,0,1}){
            var p=plan(user,false);double scale=p.previewScale(20_000_000,200);
            assertEquals((double)p.selection.iso*p.selection.exposureNs,scale*20_000_000*200,.001);
            assertEquals(p.previewScale(10_000_000,200)/2,scale,1e-12);
        }
    }
    @Test public void baselineNegativeDecisionIsAlsoShownWithoutAdditionalLift(){
        var p=plan(0,true);assertEquals(-.25,p.selection.appliedAutoEv,0);
        assertTrue(p.previewScale(10_000_000,200)<1);
    }
    @Test public void displayHoldNeverExtendsCaptureEvidenceDeadline(){
        var p=plan(0,false);
        assertTrue(p.matches(owner,"cam","controls",2_300_000_000L));
        assertFalse(capture(p,2_300_000_000L,7));
        assertFalse(p.matches(owner,"cam","controls",4_000_000_000L));
        assertFalse(capture(p,1_000_000_000L,7));
    }
    @Test public void undisplayedPlanAndChangedSceneCannotBeReused(){
        var p=plan(0,false);assertFalse(capture(p,1_100_000_000L,6));
        assertFalse(p.captureEligible(owner,"cam","controls",1_100_000_000L,20_000_000,200,7,1_100_000_000L));
        assertFalse(p.captureEligible(owner,"cam","controls",1_500_000_000L,10_000_000,200,7,1_100_000_000L));
    }
    @Test public void cameraSessionAndEveryControlsIdentityAreBound(){
        var p=plan(0,false);
        assertFalse(p.matches(new Object(),"cam","controls",1_100_000_000L));
        assertFalse(p.matches(owner,"tele","controls",1_100_000_000L));
        assertFalse(p.matches(owner,"cam","newEV",1_100_000_000L));
    }
    M10RPreviewState1A.Observation frame(Object owner,String key,String controls,long ts,long now){
        return new M10RPreviewState1A.Observation(owner,key,controls,null,null,now,0,0,ts,10_000_000L,200);
    }
    @Test public void physicalLensChangeClearsPlanEvenWithinSameLogicalSession(){
        M10RPreviewState1A.observe(frame(owner,"cam","controls",1,1_020_000_000L));
        M10RPreviewState1A.publish(plan(0,false));assertNotNull(M10RPreviewState1A.plan());
        M10RPreviewState1A.observe(frame(owner,"tele","controls",2,1_030_000_000L));
        assertNull(M10RPreviewState1A.plan());
        M10RPreviewState1A.publish(plan(0,false));assertNull(M10RPreviewState1A.plan());
        assertNull(M10RPreviewState1A.forTexture(1,1_040_000_000L));
    }
    @Test public void metadataRingRequiresExactTimestampAndFreshArrival(){
        for(int i=1;i<=60;i++)M10RPreviewState1A.observe(frame(owner,"cam","controls",i,1_000_000_000L+i));
        assertNull(M10RPreviewState1A.forTexture(1,1_100_000_000L));
        assertNotNull(M10RPreviewState1A.forTexture(60,1_100_000_000L));
        assertNull(M10RPreviewState1A.forTexture(61,1_100_000_000L));
        assertNull(M10RPreviewState1A.forTexture(60,1_400_000_000L));
        assertNull(M10RPreviewState1A.forTexture(60,100));
    }
    @Test public void retiredOwnerCannotClearNewCameraButGlobalRetirementDoes(){
        Object next=new Object();
        M10RPreviewState1A.observe(frame(next,"tele","controls",2,1_030_000_000L));
        M10RPreviewState1A.clear(owner);
        assertNotNull(M10RPreviewState1A.forTexture(2,1_040_000_000L));
        M10RPreviewState1A.clear(null);
        assertNull(M10RPreviewState1A.forTexture(2,1_040_000_000L));
    }
    @Test public void drawnAcknowledgementCannotReviveRetiredOrReplacedPlan(){
        var o=frame(owner,"cam","controls",1,1_020_000_000L);
        M10RPreviewState1A.observe(o);var p=plan(0,false);M10RPreviewState1A.publish(p);
        M10RPreviewState1A.displayed(o,p,1_030_000_000L,"drawn");
        var ack=M10RPreviewState1A.display();assertEquals(7,ack.planId);assertEquals(1_030_000_000L,ack.atNs);
        M10RPreviewState1A.publish(plan(0,false));M10RPreviewState1A.unavailable("pending");
        M10RPreviewState1A.displayed(o,p,1_040_000_000L,"old");assertEquals(0,M10RPreviewState1A.display().planId);
        M10RPreviewState1A.clear(null);M10RPreviewState1A.displayed(o,p,1_050_000_000L,"old");
        assertEquals(0,M10RPreviewState1A.display().planId);
    }
}
