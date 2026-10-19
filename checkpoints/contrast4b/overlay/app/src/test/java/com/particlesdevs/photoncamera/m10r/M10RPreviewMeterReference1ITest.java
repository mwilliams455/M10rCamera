package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.*;
import org.junit.*;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/** Reproduces sustained sparse Camera2 control echoes, rather than only a short gap. */
public class M10RPreviewMeterReference1ITest {
    static final long MS = 1_000_000L, START = 2_000_000_000L, TS = 9_000_000_000L;
    private final Object session = new Object();
    private final CameraCharacteristics chars = mock(CameraCharacteristics.class);
    private final CaptureRequest request = mock(CaptureRequest.class);
    @BeforeClass public static void keys() throws Exception { M10RPreviewMetadata1ETest.installFrameworkKeyIdentities(); }
    @AfterClass public static void restoreKeys() throws Exception { M10RPreviewMetadata1ETest.restoreFrameworkKeys(); }
    @After public void clear() { M10RPreviewState1A.clear(null); }
    private M10RPreviewState1A.Observation observation(long elapsedMs, Integer echo) {
        return observation(elapsedMs,echo,0);
    }
    private M10RPreviewState1A.Observation observation(long elapsedMs, Integer echo,int requestedSteps) {
        CaptureResult r = mock(CaptureResult.class);
        when(r.get(CaptureResult.SENSOR_TIMESTAMP)).thenReturn(TS+elapsedMs*MS);
        when(r.get(CaptureResult.SENSOR_EXPOSURE_TIME)).thenReturn(40_000_000L);
        when(r.get(CaptureResult.SENSOR_SENSITIVITY)).thenReturn(125);
        when(r.get(CaptureResult.CONTROL_AE_EXPOSURE_COMPENSATION)).thenReturn(echo);
        when(request.get(CaptureRequest.CONTROL_AE_MODE)).thenReturn(CaptureRequest.CONTROL_AE_MODE_ON);
        when(request.get(CaptureRequest.CONTROL_AE_EXPOSURE_COMPENSATION)).thenReturn(requestedSteps);
        android.util.Rational unit=mock(android.util.Rational.class);when(unit.doubleValue()).thenReturn(1.0/3);
        when(chars.get(CameraCharacteristics.CONTROL_AE_COMPENSATION_STEP)).thenReturn(unit);
        return M10RPreviewMetadata1E.observe(session,"physical:raw","auto0",chars,r,request,START+elapsedMs*MS,0);
    }
    private M10RPreviewState1A.Observation meterReference(long now) throws Exception {
        return M10RPreviewState1A.meterReference(session,"physical:raw","auto0",now);
    }
    @Test public void newRawMeterRemainsAvailableAfterTwoPhotosAndLongSparsePreview() throws Exception {
        M10RPreviewState1A.observe(observation(0,0));
        M10RPreviewState1A.Observation latest = null;
        for (int i=1;i<=300;i++) {
            latest = observation(i*33L,null); M10RPreviewState1A.observe(latest);
        }
        long now = START+9900*MS;
        assertNull("sparse preview must not approve cached capture",M10RPreviewState1A.captureReference(session,"physical:raw","auto0",now));
        assertSame("fresh physical sensor readings must still seed a new RAW measurement",latest,meterReference(now));
        assertFalse(latest.captureEvidence);
    }
    @Test public void missingEchoKeepsExactSensorReadingsAndCalibratedNonzeroRequestEv() throws Exception {
        var seed=observation(0,null,-3);M10RPreviewState1A.observe(seed);
        assertTrue(seed.meterEvidence);assertFalse(seed.captureEvidence);
        assertEquals(-1,seed.referenceEv,1e-12);assertEquals(40_000_000L,seed.exposureNs);assertEquals(125,seed.iso);
        assertSame(seed,meterReference(START));assertEquals("matched_request_EV",seed.referenceEvSource);
    }
    @Test public void duplicateAndOutOfOrderSensorResultsCannotRefreshSeedAge() throws Exception {
        var seed=observation(0,null);M10RPreviewState1A.observe(seed);
        var duplicate=new M10RPreviewState1A.Observation(session,"physical:raw","auto0",chars,seed.result,
                START+900*MS,0,0,false,true);
        M10RPreviewState1A.observe(duplicate);M10RPreviewState1A.observe(observation(-1,null));
        assertSame(seed,meterReference(START+1200*MS));assertNull(meterReference(START+1200*MS+1));
        assertNull(meterReference(START-1));
    }
    @Test public void seedRetiresOnCameraLensOrControlsChange() throws Exception {
        for(int variant=0;variant<3;variant++) {
            var seed=observation(0,null);M10RPreviewState1A.observe(seed);
            Object owner=variant==0?new Object():session;
            String key=variant==1?"tele":"physical:raw",controls=variant==2?"newEV":"auto0";
            assertNull(M10RPreviewState1A.meterReference(owner,key,controls,START));
            M10RPreviewState1A.rejectObservation(owner,key,controls,"source_changed");
            assertNull(meterReference(START));
        }
    }
    @Test public void lateRequestWithChangedControlsCannotSeedMeter() throws Exception {
        var old=observation(0,null);
        var displayOnly=M10RPreviewMetadata1E.observe(session,"physical:raw","auto0",chars,old.result,request,START,0,false);
        M10RPreviewState1A.observe(displayOnly);
        assertFalse(displayOnly.meterEvidence);assertFalse(displayOnly.captureEvidence);assertNull(meterReference(START));
    }
    @Test public void newSeedDoesNotReplaceOrExtendCompleteCaptureAuthority() throws Exception {
        var complete=observation(0,0);M10RPreviewState1A.observe(complete);
        var seed=observation(1000,null);M10RPreviewState1A.observe(seed);
        assertSame(seed,meterReference(START+1500*MS));
        assertNull(M10RPreviewState1A.captureReference(session,"physical:raw","auto0",START+1500*MS));
        assertFalse(seed.captureEvidence);
    }
    @Test public void requestSeedCannotAcknowledgeDisplayedExposurePlan() {
        var seed=observation(0,null);M10RPreviewState1A.observe(seed);
        var fixture=new M10RPreviewPlan1ATest();var template=fixture.plan(0,false);
        var p=new M10RPreviewPlan1A(7,session,"physical:raw","auto0",START,START,
                seed.exposureNs,seed.iso,template.selection,template.report);
        M10RPreviewState1A.publish(p);M10RPreviewState1A.displayed(seed,p,START,"display_only_request_EV");
        assertEquals(0,M10RPreviewState1A.display().planId);
    }
    @Test public void changedSubmittedEvFailsRequestControlComparison() {
        observation(0,null,-3);
        CaptureRequest.Builder builder=mock(CaptureRequest.Builder.class);
        when(builder.get(CaptureRequest.CONTROL_AE_MODE)).thenReturn(CaptureRequest.CONTROL_AE_MODE_ON);
        when(builder.get(CaptureRequest.CONTROL_AE_EXPOSURE_COMPENSATION)).thenReturn(-3);
        assertTrue(M10RPreviewMetadata1E.requestMatchesCurrentControls(request,builder));
        when(builder.get(CaptureRequest.CONTROL_AE_EXPOSURE_COMPENSATION)).thenReturn(0);
        assertFalse(M10RPreviewMetadata1E.requestMatchesCurrentControls(request,builder));
    }
}
