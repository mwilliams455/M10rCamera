package com.particlesdevs.photoncamera.m10r;

import org.junit.After;
import org.junit.Test;
import static org.junit.Assert.*;

public class M10RPreviewContinuity1CTest {
    static final long NOW=2_000_000_000L,TS=9_000_000_000L,MS=1_000_000L;
    final Object owner=new Object();
    final M10RPreviewContinuity1C continuity=new M10RPreviewContinuity1C();
    M10RPreviewState1A.Observation observation(String key,String controls,long ts,long now) {
        return new M10RPreviewState1A.Observation(owner,key,controls,null,null,now,0,0,ts,10_000_000L,200);
    }
    M10RPreviewColour1A.Frame colour(M10RPreviewState1A.Observation o) {
        return new M10RPreviewColour1A.Frame(o,true,"ready",new byte[4],new byte[4],new float[9]);
    }
    M10RPreviewState1A.Observation seed() {
        var o=observation("cam","controls",TS,NOW);
        M10RPreviewState1A.observe(o);continuity.drawn(o,colour(o),1.75,NOW);return o;
    }
    @After public void cleanup(){M10RPreviewState1A.clear(null);}
    @Test public void lateMetadataKeepsCorrectionWithoutPretendingTimestampMatched() {
        seed();assertNull(M10RPreviewState1A.forTexture(TS+33*MS,NOW+33*MS));
        var h=continuity.held(TS+33*MS,NOW+33*MS);assertNotNull(h);assertEquals(1.75,h.scale,0);
        M10RPreviewState1A.countHeld("texture_metadata_unmatched");
        assertEquals(0,M10RPreviewState1A.display().planId);
        assertEquals(0,M10RPreviewState1A.display().atNs);
    }
    @Test public void repeatedMissesCannotRenewGrace() {
        seed();
        for(int i=1;i<=120;i++)assertNotNull(continuity.held(TS+i*MS,NOW+i*MS));
        assertNull(continuity.held(TS+121*MS,NOW+121*MS));
    }
    @Test public void exactRecoveryCanStartANewGraceInterval() {
        seed();var o=observation("cam","controls",TS+100*MS,NOW+100*MS);
        M10RPreviewState1A.observe(o);continuity.drawn(o,colour(o),.75,NOW+100*MS);
        assertEquals(.75,continuity.held(TS+150*MS,NOW+150*MS).scale,0);
    }
    @Test public void lensAndControlsChangesDiscardOldCorrection() {
        seed();M10RPreviewState1A.observe(observation("tele","controls",TS+MS,NOW+MS));
        assertNull(continuity.held(TS+MS,NOW+MS));
        seed();M10RPreviewState1A.observe(observation("cam","newEV",TS+MS,NOW+MS));
        assertNull(continuity.held(TS+MS,NOW+MS));
    }
    @Test public void retirementAndGlResetDiscardOldCorrection() {
        seed();M10RPreviewState1A.clear(null);assertNull(continuity.held(TS+MS,NOW+MS));
        seed();continuity.clear();assertNull(continuity.held(TS+MS,NOW+MS));
    }
    @Test public void backwardOrDistantTextureCannotUseGrace() {
        seed();assertNull(continuity.held(TS-1,NOW+MS));
        seed();assertNull(continuity.held(TS+121*MS,NOW+MS));
        seed();assertNull(continuity.held(TS,NOW-1));
    }
    @Test public void oldColourNeverGetsExtraLifetimeFromRecentDraw() {
        var old=observation("cam","controls",TS-950*MS,NOW-950*MS);
        var o=observation("cam","controls",TS,NOW);M10RPreviewState1A.observe(o);
        continuity.drawn(o,colour(old),1,NOW);
        assertNotNull(continuity.held(TS+40*MS,NOW+40*MS));
        assertNull(continuity.held(TS+60*MS,NOW+60*MS));
    }
    @Test public void transientRefreshFailurePreservesGoodColourOnlyUntilOriginalDeadline() {
        var o=seed();var good=colour(o);var failed=M10RPreviewColour1A.Frame.failure(o,"refresh_failed");
        assertSame(good,M10RPreviewColour1A.available(good,failed,o,NOW+500*MS));
        assertSame(failed,M10RPreviewColour1A.available(good,failed,o,NOW+1001*MS));
    }
    @Test public void oldCameraColourAndFailureCannotLeakIntoNewCamera() {
        var o=seed();var next=observation("tele","controls",TS+MS,NOW+MS);
        assertNull(M10RPreviewColour1A.available(colour(o),M10RPreviewColour1A.Frame.failure(o,"failed"),next,NOW+MS));
    }
    @Test public void invalidOrUnreadyTransformsDoNotSeedGrace() {
        var o=observation("cam","controls",TS,NOW);M10RPreviewState1A.observe(o);
        continuity.drawn(o,M10RPreviewColour1A.Frame.failure(o,"failed"),1,NOW);
        assertNull(continuity.held(TS,NOW));
        continuity.drawn(o,colour(o),Double.NaN,NOW);assertNull(continuity.held(TS,NOW));
    }
    @Test public void diagnosticsSeparateExactHeldAndFallbackBinds()throws Exception {
        seed();M10RPreviewState1A.countExact();M10RPreviewState1A.countHeld("late");
        M10RPreviewState1A.countFallback("expired");var json=new org.json.JSONObject();
        M10RPreviewState1A.appendDiagnostics(json);
        assertEquals(1,json.getLong("previewExactBindCount"));
        assertEquals(1,json.getLong("previewHeldBindCount"));
        assertEquals(1,json.getLong("previewFallbackBindCount"));
        assertEquals(120,json.getLong("previewMetadataGraceMs"));
    }
}
