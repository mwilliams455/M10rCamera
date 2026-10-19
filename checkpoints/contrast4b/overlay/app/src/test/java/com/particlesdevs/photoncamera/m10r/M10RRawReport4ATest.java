package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.CaptureRequest;
import org.json.JSONObject;
import org.junit.Test;

import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/** Regression contract for legacy exposure-tag consumers after RAW provenance is attached. */
public class M10RRawReport4ATest {
    @Test public void addingRawContextPreservesExactFrozenExposurePayload() throws Exception {
        JSONObject selection = new JSONObject().put("exposureNs", 9736251L).put("iso", 100);
        JSONObject input = new JSONObject().put("selection", selection).put("manualWhite", true);
        M10RExposureReport1C original = new M10RExposureReport1C(input);
        String frozen = original.json;
        M10RRawBinding4A.CameraContext context = mock(M10RRawBinding4A.CameraContext.class);
        M10RExposureReport1C attached = original.withRawContext4A(context);

        selection.put("iso", 6400);
        input.put("manualWhite", false);

        assertEquals(frozen, original.json);
        assertEquals(frozen, attached.json);
        assertNull(original.rawContext4A);
        assertSame(context, attached.rawContext4A);
        JSONObject legacyView = new JSONObject(attached.json);
        assertEquals(100, legacyView.getJSONObject("selection").getInt("iso"));
        assertTrue(legacyView.getBoolean("manualWhite"));
    }

    @Test public void rendererCanReadBothExposureAndRawContextFromSameRequestTag() throws Exception {
        M10RRawBinding4A.CameraContext context = mock(M10RRawBinding4A.CameraContext.class);
        M10RExposureReport1C report = new M10RExposureReport1C(
                new JSONObject().put("status", "ready")).withRawContext4A(context);
        CaptureRequest request = mock(CaptureRequest.class);
        when(request.getTag()).thenReturn(report);

        assertTrue(request.getTag() instanceof M10RExposureReport1C);
        assertEquals("ready", new JSONObject(((M10RExposureReport1C) request.getTag()).json)
                .getString("status"));
        assertSame(context, M10RRawBinding4A.fromTag(request));
    }

    @Test public void legacyAndUnrelatedTagsRemainValidWithoutInventedRawContext() throws Exception {
        CaptureRequest request = mock(CaptureRequest.class);
        when(request.getTag()).thenReturn(new M10RExposureReport1C(new JSONObject()));
        assertNull(M10RRawBinding4A.fromTag(request));
        when(request.getTag()).thenReturn("unrelated legacy tag");
        assertNull(M10RRawBinding4A.fromTag(request));
        when(request.getTag()).thenReturn(null);
        assertNull(M10RRawBinding4A.fromTag(request));
        assertNull(M10RRawBinding4A.fromTag(null));
    }
}
