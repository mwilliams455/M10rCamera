package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.CaptureRequest;
import com.particlesdevs.photoncamera.app.PhotonCamera;
import com.particlesdevs.photoncamera.settings.PreferenceKeys;
import java.util.ArrayList;
import org.json.JSONObject;
import org.junit.*;
import static com.particlesdevs.photoncamera.m10r.M10RContrast4B.Level.*;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/** Immutable request identity and real preview cache/worker retirement. */
public class M10RContrastLifecycle4BTest {
    static final long NOW=2_000_000_000L, TS=9_000_000_000L;
    final Object owner=new Object();

    @BeforeClass public static void initializePreferenceResources() throws Exception {
        // PreferenceKeys.Key resolves resource names during class initialization.
        // This suite must also run before any controller fixture has initialized it.
        try(var app=mockStatic(PhotonCamera.class)){
            app.when(()->PhotonCamera.getStringStatic(anyInt()))
                    .thenAnswer(i->"test_resource_"+i.getArgument(0));
            Class.forName(PreferenceKeys.class.getName(),true,PreferenceKeys.class.getClassLoader());
        }
    }

    @Before public void setup() throws Exception {
        M10RPreviewState1A.clear(null);M10RPreviewColourRecovery1JTest.resetCache();
    }
    @After public void cleanup() throws Exception {
        M10RPreviewState1A.clear(null);M10RPreviewColourRecovery1JTest.resetCache();
    }
    M10RPreviewState1A.Observation observation(M10RContrast4B.Level level,long offset){
        return new M10RPreviewState1A.Observation(owner,"camera",M10RContrast4B.controlKey("controls",level),
                null,null,NOW+offset,0,0,TS+offset,10_000_000L,200).withContrast(level);
    }
    M10RPreviewState1A.Observation observe(M10RContrast4B.Level level,long offset){
        var o=observation(level,offset);M10RPreviewState1A.observe(o);return o;
    }
    M10RPreviewColour1A.Frame colour(M10RPreviewState1A.Observation o){
        return new M10RPreviewColour1A.Frame(o,true,"test_native_result",new byte[4],new byte[4],new float[9]);
    }

    @Test public void preferenceKeysAreExactAndMissingOrUnknownUseStandard(){
        assertEquals(LOW,M10RContrast4B.fromPreference("low"));
        assertEquals(STANDARD,M10RContrast4B.fromPreference("standard"));
        assertEquals(HIGH,M10RContrast4B.fromPreference("high"));
        for(String value:new String[]{null,"","medium","LOW","restored_unknown"})
            assertEquals(STANDARD,M10RContrast4B.fromPreference(value));
    }

    @Test public void legacyCarriersAndMissingRequestNeverReadCurrentPreference() throws Exception {
        try(var prefs=mockStatic(PreferenceKeys.class)){
            prefs.when(PreferenceKeys::getM10RContrastValue).thenReturn("high");
            assertEquals(STANDARD,new M10RExposureReport1C(new JSONObject()).contrast4B);
            assertEquals(STANDARD,new M10RExposureCamera1C.Input(null,null,null,null,null,"camera","2","2",
                    null,null,"controls",1,0,0).contrast4B);
            assertEquals(STANDARD,new M10RExposureProbe1B.Binding("camera",1,1,TS,NOW,10_000_000L,200,0,0,0).contrast4B);
            assertEquals(STANDARD,new M10RPreviewState1A.Observation(owner,"camera","controls",null,null,
                    NOW,0,0,TS,10_000_000L,200).contrast4B);
            assertEquals(STANDARD,M10RContrast4B.fromRequest(null));
            assertEquals(STANDARD,M10RContrast4B.fromRequest(mock(CaptureRequest.class)));
            prefs.verifyNoInteractions();
        }
    }

    @Test public void rawTagRetainsExactExposureJsonAndFrozenContrastAfterPreferencesChange() throws Exception {
        JSONObject original=new JSONObject().put("selectedIso",200);
        var report=new M10RExposureReport1C(original,LOW);String frozenJson=report.json;
        original.put("selectedIso",6400);
        var raw=mock(M10RRawBinding4A.CameraContext.class);
        var tagged=report.withRawContext4A(raw);
        CaptureRequest request=mock(CaptureRequest.class);when(request.getTag()).thenReturn(tagged);
        try(var prefs=mockStatic(PreferenceKeys.class)){
            prefs.when(PreferenceKeys::getM10RContrastValue).thenReturn("high");
            assertEquals(frozenJson,tagged.json);assertEquals(200,new JSONObject(tagged.json).getInt("selectedIso"));
            assertEquals(LOW,tagged.contrast4B);assertEquals(LOW,M10RContrast4B.fromRequest(request));
            assertSame(raw,M10RRawBinding4A.fromTag(request));
            assertNull(report.rawContext4A);prefs.verifyNoInteractions();
        }
    }

    @Test public void observationCopyCannotRenewItsGenerationOrMetadata(){
        var original=observation(STANDARD,0);var low=original.withContrast(LOW);
        assertEquals(STANDARD,original.contrast4B);assertEquals(LOW,low.contrast4B);
        assertEquals(original.generation4B,low.generation4B);
        assertEquals(original.timestamp,low.timestamp);assertEquals(original.observedNs,low.observedNs);
        assertSame(original.owner,low.owner);assertSame(original.controls,low.controls);
        M10RPreviewState1A.clear(null);
        var high=low.withContrast(HIGH);assertEquals(low.generation4B,high.generation4B);
        M10RPreviewState1A.observe(high);
        assertFalse(M10RPreviewState1A.current(high));assertNull(M10RPreviewState1A.forTexture(TS,NOW));
    }

    @Test public void clearAndReturnToSameLevelCannotReuseCachedColour(){
        var low=observe(LOW,0);var cached=colour(low);
        assertSame(cached,M10RPreviewColour1A.available(cached,null,low,NOW));
        M10RPreviewState1A.clear(null);
        assertNull(M10RPreviewColour1A.available(cached,null,low,NOW));
        observe(HIGH,1);M10RPreviewState1A.clear(null);var newLow=observe(LOW,2);
        assertEquals(low.controls,newLow.controls);assertFalse(M10RPreviewState1A.current(low));
        assertFalse(cached.matches(newLow));
        assertNull(M10RPreviewColour1A.available(cached,null,newLow,NOW+2));
    }

    @Test public void queuedColourCompletionCannotPublishAfterLowHighLowRoundTrip(){
        var low=observe(LOW,0);ArrayList<Runnable> tasks=new ArrayList<>();
        assertNull(M10RPreviewColour1A.request(low,NOW,tasks::add,this::colour));assertEquals(1,tasks.size());
        M10RPreviewState1A.clear(null);observe(HIGH,1);
        M10RPreviewState1A.clear(null);var newLow=observe(LOW,2);
        tasks.get(0).run();
        assertNull(M10RPreviewColour1A.request(newLow,NOW+2,tasks::add,this::colour));assertEquals(2,tasks.size());
        tasks.get(1).run();
        var fresh=M10RPreviewColour1A.request(newLow,NOW+2,tasks::add,this::colour);
        assertNotNull(fresh);assertEquals(newLow.generation4B,fresh.generation4B);
    }

    @Test public void backgroundPlanPublicationChecksSubmissionGeneration() throws Exception {
        var low=observe(LOW,0);long submitted=low.generation4B;
        var template=new M10RPreviewPlan1ATest().plan(0,false);
        var plan=new M10RPreviewPlan1A(1,owner,"camera",low.controls,template.observedNs,template.completedNs,
                template.referenceNs,template.referenceIso,template.selection,new M10RExposureReport1C(new JSONObject(),LOW));
        M10RPreviewState1A.clear(null);var newLow=observe(LOW,1);
        M10RPreviewState1A.publish(plan,submitted);assertNull(M10RPreviewState1A.plan());
        M10RPreviewState1A.publish(plan,newLow.generation4B);assertSame(plan,M10RPreviewState1A.plan());
    }
}
