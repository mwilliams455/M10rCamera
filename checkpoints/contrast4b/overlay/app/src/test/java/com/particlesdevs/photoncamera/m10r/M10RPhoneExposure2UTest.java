package com.particlesdevs.photoncamera.m10r;

import org.junit.Test;
import static org.junit.Assert.*;

/** Phone control invariants, not a sensor-gain fit or an instruction replay. */
public class M10RPhoneExposure2UTest {
    static M10RAe1BPolicy.Decision decision(long ns,int iso,double ev){
        return M10RAe1BPolicy.solve(ns,iso,1.8,35,ev,100,50000);
    }
    static M10RPhoneExposure2U.Result allocate(M10RAe1BPolicy.Decision d){
        return M10RPhoneExposure2U.allocate(d,1,1_000_000_000_000L,1,400000);
    }
    static void product(double expected,M10RPhoneExposure2U.Result p){
        assertEquals(expected,p.targetProduct,Math.abs(expected)*1e-14);
        assertEquals(expected,(double)p.exposureNs*p.iso,p.iso*.51);
    }
    @Test public void fourRecordedRequestsRetainOracleAndRemovePhoneProductOffset(){
        // Verbatim inputs from the four 2026-10-18 11:07/11:08 capture sidecars.
        long[] reference={5524044,5286146,4181395,4083109};
        long[] oldRequested={2971627,2845640,2248416,2194288};
        long[] phoneRequested={2762022,2643073,2090698,2041555};
        double[] aperture={1.6299999952316284,1.6299999952316284,1.7999999523162842,1.7999999523162842};
        double[] focal={23.950196650949387,23.950196650949387,72.19587310995561,72.19587310995561};
        for(int i=0;i<reference.length;i++){
            var d=M10RAe1BPolicy.solve(reference[i],50,aperture[i],focal[i],0,100,50000);
            assertEquals(oldRequested[i],Math.round(d.oracle.shutterSeconds*1e9));
            assertEquals(100,d.oracle.iso);assertFalse(d.oracle.autoIsoActivated);
            var p=allocate(d);assertEquals(phoneRequested[i],p.exposureNs);assertEquals(100,p.iso);
            product((double)reference[i]*50,p);assertFalse(p.physicalClamped);
            assertTrue(p.targetMinusOracleEv<-.104&&p.targetMinusOracleEv>-.107);
        }
        assertEquals(27,M10RAeOracle.svCorrectionQ8(M10RAeOracle.isoToSvQ8(100)));
    }
    @Test public void targetConservesIntentAcrossIsoStepsFocalLengthsAndEv(){
        for(int iso:new int[]{50,64,80,100,125,160,200,800,1090,3200,6402,12800})
            for(long ns:new long[]{50000,10_000_000,100_000_000,5_000_000_000L})
                for(double ev:new double[]{-2,-1.0/3,0,.25,2}){
                    var d=decision(ns,iso,ev);var p=allocate(d);
                    product((double)ns*iso*Math.pow(2,ev),p);
                    assertEquals(d.oracle.iso,p.iso);assertFalse(p.physicalClamped);
                }
    }
    @Test public void zeroDeltaDoesNotAddSensitivityBiasOrQ8Rounding(){
        var p=allocate(decision(10_000_001,100,0));
        assertEquals(10_000_001,p.exposureNs);assertEquals(100,p.iso);
        assertEquals(0,p.residualEv,0);
    }
    @Test public void explicitDeltaHasCorrectSignAndIsNotAConstantOffset(){
        var zero=allocate(decision(12_345_678,640,0));
        for(double ev:new double[]{-2,-.75,.25,1.5}){
            var p=allocate(decision(12_345_678,640,ev));
            assertEquals(ev,Math.log(p.targetProduct/zero.targetProduct)/Math.log(2),1e-12);
        }
    }
    @Test public void phoneCanReachFasterThanFirmwareShutterLimit(){
        var d=decision(214467,50,0);assertEquals(M10RAeOracle.TV_MAX_Q8,d.oracle.tvQ8);
        var p=M10RPhoneExposure2U.allocate(d,11041,1_000_000_000,50,3200);
        assertEquals(107234,p.exposureNs);assertEquals(100,p.iso);assertFalse(p.physicalClamped);
        product(214467.0*50,p);
    }
    @Test public void phoneCanReachSlowerThanFirmwareLimitWithinHardwareRange(){
        var d=M10RAe1BPolicy.solve(300_000_000_000L,100,2,35,0,100,100);
        assertEquals(M10RAeOracle.TV_MIN_Q8,d.oracle.tvQ8);
        var p=allocate(d);assertEquals(300_000_000_000L,p.exposureNs);
        product(300_000_000_000.0*100,p);assertFalse(p.physicalClamped);
    }
    @Test public void minShutterTransfersToIsoAndUnreachableTargetReportsResidual(){
        var d=decision(214467,50,0);
        var p=M10RPhoneExposure2U.allocate(d,200000,1_000_000_000,50,3200);
        assertEquals(54,p.iso);assertEquals(200000,p.exposureNs);assertTrue(p.physicalClamped);
        assertTrue(p.residualEv>0&&p.residualEv<.02);
        var blocked=M10RPhoneExposure2U.allocate(d,244141,1_000_000_000,100,3200);
        assertEquals(100,blocked.iso);assertEquals(244141,blocked.exposureNs);
        assertTrue(blocked.residualEv>1);
    }
    @Test public void analogCapTransfersToTimeWithoutChangingIntent(){
        var d=M10RAe1BPolicy.solve(30_000_000,6402,2.6,98.8708,0,100,50000);
        assertEquals(20000,d.oracle.iso);
        var p=M10RPhoneExposure2U.allocate(d,1000,1_000_000_000,50,6402);
        assertEquals(30_000_000,p.exposureNs);assertEquals(6402,p.iso);assertTrue(p.physicalClamped);
        product(30_000_000.0*6402,p);
    }
    @Test public void extremeIsoTransferCannotWrapBeforePhysicalClamp(){
        var p=M10RPhoneExposure2U.allocate(decision(1_000_000_000,50000,16),1,10,50,6400);
        assertEquals(6400,p.iso);assertEquals(10,p.exposureNs);assertTrue(p.residualEv<0);
    }
    @Test public void invalidDecisionAndNonfiniteTargetCannotAllocate(){
        for(var d:new M10RAe1BPolicy.Decision[]{null,decision(0,100,0),decision(1,100,Double.NaN),decision(1,100,2000)}){
            try{allocate(d);fail("invalid target accepted");}catch(IllegalArgumentException expected){}
        }
    }
}
