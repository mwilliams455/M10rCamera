package com.particlesdevs.photoncamera.m10r;

import org.json.JSONObject;
import org.json.JSONException;
import org.junit.Test;
import static org.junit.Assert.*;

public class M10RExposureTrace1DTest {
    @Test public void preservesExpiryDistinctFromCancellationAndDoesNotExtendDeadline() throws Exception {
        for(String message:new String[]{"probe expired while processing","probe cancelled"}) {
            M10RExposureTrace1D trace=new M10RExposureTrace1D();
            trace.observed(System.nanoTime()-1_300_000_000L);
            trace.step("freshness_before_amaze");trace.failure(new IllegalStateException(message));
            JSONObject out=new JSONObject();assertTrue(trace.appendTo(out));
            JSONObject d=out.getJSONObject("probeDiagnostics");
            assertEquals(message,d.getJSONObject("failure").getString("message"));
            assertTrue(d.getDouble("evidenceAgeMs")>=1300);
            assertEquals(1200,d.getDouble("evidenceDeadlineMs"),0);
            trace.step("later_stage_must_not_replace_failure");
            assertEquals("freshness_before_amaze",trace.stage());
        }
    }
    @Test public void reportSerializationFailureIsContained() {
        M10RExposureTrace1D trace=new M10RExposureTrace1D();
        trace.failure(new IllegalStateException("original"));
        JSONObject broken=new JSONObject(){
            @Override public JSONObject put(String key,Object value)throws JSONException {
                throw new JSONException("test serializer failure");
            }
        };
        assertFalse(trace.appendTo(broken));
        assertTrue(trace.appendTo(new JSONObject()));
    }
    @Test public void reportsAreBoundedAndDetachedFromLiveTrace()throws Exception {
        M10RExposureTrace1D trace=new M10RExposureTrace1D();
        trace.step("raw_normalization");trace.failure(new IllegalStateException("x".repeat(20000)));
        JSONObject out=new JSONObject();assertTrue(trace.appendTo(out));
        JSONObject f=out.getJSONObject("probeDiagnostics").getJSONObject("failure");
        assertEquals(2048,f.getString("message").length());
        assertTrue(f.getString("stackTrace").length()<=12288);assertTrue(f.getBoolean("stackTruncated"));
        String frozen=out.toString();trace.step("ignored");assertEquals(frozen,out.toString());
    }
    @Test public void successfulTraceDoesNotInventAFailure()throws Exception {
        M10RExposureTrace1D trace=new M10RExposureTrace1D();
        trace.step("probe_publication");trace.complete();JSONObject out=new JSONObject();
        assertTrue(trace.appendTo(out));assertFalse(out.getJSONObject("probeDiagnostics").has("failure"));
    }
}
