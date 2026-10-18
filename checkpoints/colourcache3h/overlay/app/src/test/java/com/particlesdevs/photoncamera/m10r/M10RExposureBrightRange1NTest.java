package com.particlesdevs.photoncamera.m10r;

import java.util.Arrays;
import org.junit.Test;
import static org.junit.Assert.*;

/** Bright outdoor capture regression: user EV must survive the firmware Tv limit. */
public class M10RExposureBrightRange1NTest {
    static final long NOW=2_000_000_000L;
    static M10RExposure1A.Request request(double user,boolean auto){
        return new M10RExposure1A.Request("physical",1,"renderer",NOW,user,1.6299999952316284,
                23.950196650949387,100,50000,auto);
    }
    static M10RExposure1A.Probe probe(long ns,int iso,double referenceUser,double candidateUser){
        double[] grid=new double[352];Arrays.fill(grid,.12);
        return new M10RExposure1A.Probe("physical",1,1,"renderer",123,123,NOW,NOW,ns,iso,referenceUser,0,
                M10RExposure1A.ProbeDomain.M10R_RENDERED_USER_EV_REFERENCE,grid,
                M10RExposureRange1HTest.stats(7),M10RHighlightGuard1A.noSubject(7),candidateUser,
                M10RExposureRange1HTest.stats(3));
    }
    static M10RExposureCapture1B.Limits limits(long minNs,int minIso){
        return new M10RExposureCapture1B.Limits(minNs,33_430_445_787L,minIso,12800,3200);
    }
    static double energy(M10RExposureCapture1B.Selection s){return (double)s.exposureNs*s.iso;}
    static double ev(double ratio){return Math.log(ratio)/Math.log(2);}

    @Test public void recordedOutdoorPairNoLongerCollapsesToOneExposure(){
        var a=M10RExposureCapture1B.select(probe(427542,50,0,0),request(0,true),null,limits(11041,50));
        double u=-7.0/6;
        var b=M10RExposureCapture1B.select(probe(214467,50,u,u),request(u,true),null,limits(11041,50));
        // Both original oracle pairs reproduce the recorded failure.
        for(var s:new M10RExposureCapture1B.Selection[]{a,b}){
            assertEquals(244141,Math.round(s.allocation.oracle.shutterSeconds*1e9));
            assertEquals(100,s.allocation.oracle.iso);assertEquals(100,s.iso);
            assertEquals(0,s.plan.deltaFromReferenceEv,0);assertEquals(0,s.appliedAutoEv,0);
            assertTrue(s.exposureNs<244141);assertTrue(s.exposureNs>=11041);
            assertTrue(s.brightRangeCorrectionEv<0);assertEquals(0,s.allocationResidualEv,1e-5);
        }
        assertEquals(-.0859375,a.brightRangeCorrectionEv,0);
        assertEquals(-1.08203125,b.brightRangeCorrectionEv,0);
        assertTrue(b.exposureNs<.51*a.exposureNs);
    }
    @Test public void userEvSweepRemainsResponsiveAcrossFastShutterBoundary(){
        double initial=0,previous=Double.POSITIVE_INFINITY;
        for(int step=0;step<=24;step++){
            double u=-step/6.0;
            var s=M10RExposureCapture1B.select(probe(1_000_000,50,0,u),request(u,true),null,limits(11041,50));
            assertTrue(s.apply);assertEquals(0,s.appliedAutoEv,0);
            assertTrue(energy(s)<previous);previous=energy(s);if(step==0)initial=energy(s);
            assertEquals(u,ev(energy(s)/initial),.006);
            assertEquals(0,s.allocationResidualEv,1e-4);
        }
    }
    @Test public void alreadyAppliedReferenceEvIsNotAppliedTwice(){
        var late=M10RExposureCapture1B.select(probe(427542,50,0,-1),request(-1,true),null,limits(11041,50));
        var bound=M10RExposureCapture1B.select(probe(213771,50,-1,-1),request(-1,true),null,limits(11041,50));
        assertEquals(-1,late.plan.deltaFromReferenceEv,0);assertEquals(0,bound.plan.deltaFromReferenceEv,0);
        assertEquals(energy(late),energy(bound),100);
    }
    @Test public void physicalLimitsTransferToIsoAndReportUnservedExposure(){
        var p=probe(214467,50,-7.0/6,-7.0/6);var r=request(-7.0/6,true);
        var fast=M10RExposureCapture1B.select(p,r,null,limits(11041,50));
        var slower=M10RExposureCapture1B.select(p,r,null,limits(200000,50));
        assertTrue(slower.iso<100);assertTrue(slower.iso>=50);assertTrue(slower.exposureNs>=200000);
        assertEquals(0,ev(energy(slower)/energy(fast)),.02);
        var impossible=M10RExposureCapture1B.select(p,r,null,limits(244141,100));
        assertEquals(244141,impossible.exposureNs);assertEquals(100,impossible.iso);
        assertTrue(impossible.allocationResidualEv>1);
        assertEquals(impossible.allocationResidualEv,ev(energy(impossible)/impossible.targetExposureProduct),1e-12);
    }
    @Test public void normalAndSlowAllocationsConservePhoneIntent(){
        for(long ns:new long[]{1_000_000L,10_000_000L,100_000_000L}){
            var s=M10RExposureCapture1B.select(probe(ns,100,0,0),request(0,true),null,limits(11041,50));
            assertEquals(0,s.brightRangeCorrectionEv,0);
            assertEquals((double)ns*100,(double)s.exposureNs*s.iso,s.iso*.51);
            assertFalse(s.clamped);
            assertEquals(s.allocation.oracle.iso,s.iso);
        }
    }
    @Test public void freshFallbackPreservesUserEvAndExpiredFallbackCannotAllocate(){
        var fresh=new M10RExposureCapture1B.Reference("physical",1,NOW,427542,50,0,0);
        var stale=new M10RExposureCapture1B.Reference("physical",1,1,427542,50,0,0);
        var s=M10RExposureCapture1B.select(null,request(-1,true),fresh,limits(11041,50));
        assertTrue(s.apply);assertTrue(s.fallback);assertEquals(0,s.verifiedRawIso);
        assertTrue(s.exposureNs<130000);assertTrue(s.brightRangeCorrectionEv<0);
        assertFalse(M10RExposureCapture1B.select(null,request(-1,true),stale,limits(11041,50)).apply);
    }
    @Test public void manualBypassAndCandidateMismatchKeepTheirSafetyGates(){
        var p=probe(214467,50,-1,-1);
        var manual=M10RExposureCapture1B.select(p,request(-1,false),null,limits(11041,50));
        assertFalse(manual.apply);assertTrue(manual.manualBypass);assertEquals(0,manual.brightRangeCorrectionEv,0);
        var mismatch=M10RExposureCapture1B.select(p,request(0,true),null,limits(11041,50));
        assertFalse(mismatch.apply);assertEquals(M10RExposure1A.Status.USER_EV_MISMATCH,mismatch.plan.status);
    }
    @Test public void sensorMinimumIsoIsRespectedWithoutADeviceSpecificBranch(){
        var s=M10RExposureCapture1B.select(probe(214467,50,-1,-1),request(-1,true),null,limits(11041,200));
        assertEquals(200,s.iso);assertTrue(s.exposureNs<100000);assertTrue(s.exposureNs>=11041);
        assertEquals(0,s.allocationResidualEv,1e-4);
    }
}
