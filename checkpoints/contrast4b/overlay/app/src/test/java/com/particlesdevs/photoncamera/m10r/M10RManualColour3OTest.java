package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.CaptureResult;
import android.util.Base64;
import java.lang.reflect.Field;
import java.util.Arrays;
import org.json.JSONObject;
import org.junit.AfterClass;
import org.junit.BeforeClass;
import org.junit.Test;
import org.mockito.MockedStatic;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/** Real source/target preparation and native pixel response while vendor neutral is held fixed. */
public class M10RManualColour3OTest {
    private static MockedStatic<Base64> base64;
    @BeforeClass public static void keys() throws Exception {
        M10RSourceCalibration3CTest.keys();
        base64=mockStatic(Base64.class);
        base64.when(()->Base64.decode(anyString(),anyInt()))
                .thenAnswer(i->java.util.Base64.getDecoder().decode((String)i.getArgument(0)));
    }
    @AfterClass public static void restore() throws Exception {
        try { if(base64!=null)base64.close(); }
        finally { M10RSourceCalibration3CTest.restore(); }
    }
    static M10RSourceCalibration3CTest.Fixture fixture() throws Exception {
        var fixture=new M10RSourceCalibration3CTest.Fixture(0,true);
        when(fixture.r.get(CaptureResult.SENSOR_TIMESTAMP)).thenReturn(1234567890L);
        return fixture;
    }
    static Object field(Object value,String name) throws Exception {
        Field f=value.getClass().getDeclaredField(name);f.setAccessible(true);return f.get(value);
    }
    static M10RNativeRenderer.PreparedColour prepare(M10RSourceCalibration3CTest.Fixture f,
            CaptureRequest request,JSONObject diagnostics) throws Exception {
        try(var log=mockStatic(com.particlesdevs.photoncamera.util.Log.class)) {
            return M10RNativeRenderer.prepareColourForFrame(f.c,f.r,request,diagnostics);
        }
    }
    static M10RExposureNative1B.Context preview(M10RSourceCalibration3CTest.Fixture f) throws Exception {
        try(var log=mockStatic(com.particlesdevs.photoncamera.util.Log.class)) {
            return M10RNativeRenderer.previewContext1A(f.c,f.r,"source0");
        }
    }
    static M10RExposureNative1B.Context meter(M10RSourceCalibration3CTest.Fixture f) throws Exception {
        try(var log=mockStatic(com.particlesdevs.photoncamera.util.Log.class)) {
            return M10RNativeRenderer.exposureContext1B(f.c,f.r,"source0");
        }
    }
    static final short[] PIXELS={3000,3000,3000,7000,10000,8000,3000,1000,1000,
            1000,3000,1000,1000,1000,3000};

    @Test public void manualRequestsChangeNativePixelsWhenVendorNeutralDoesNotChange() throws Exception {
        var f=fixture();var vendor=f.r.get(CaptureResult.SENSOR_NEUTRAL_COLOR_POINT);
        CaptureRequest first=M10RRequestedWhite3OTest.request(2,1,1,1.4f);
        CaptureRequest second=M10RRequestedWhite3OTest.request(1.4f,1,1,2.8f);
        when(f.r.getRequest()).thenReturn(first);var a=preview(f);
        when(f.r.getRequest()).thenReturn(second);var b=preview(f);
        assertFalse(Arrays.equals((double[])field(a,"sourceToTarget"),(double[])field(b,"sourceToTarget")));
        assertFalse(Arrays.equals(a.render(PIXELS,1),b.render(PIXELS,1)));
        assertSame(vendor,f.r.get(CaptureResult.SENSOR_NEUTRAL_COLOR_POINT));
        assertArrayEquals(M10RSourceWhite3N.manualNeutral(first),a.sourceWhite.copySourceNeutral(),0);
        assertArrayEquals(M10RSourceWhite3N.manualNeutral(second),b.sourceWhite.copySourceNeutral(),0);
    }

    @Test public void savedRequestWinsAndMatchingPreviewMeterKeepItsSelectedWhite() throws Exception {
        var f=fixture();CaptureRequest saved=M10RRequestedWhite3OTest.request(2,1,1,1.4f);
        CaptureRequest other=M10RRequestedWhite3OTest.request(1.4f,1,1,2.8f);
        when(f.r.getRequest()).thenReturn(other);JSONObject diagnostics=new JSONObject();
        var prepared=prepare(f,saved,diagnostics);
        assertArrayEquals(M10RSourceWhite3N.manualNeutral(saved),prepared.sourceWhite().copySourceNeutral(),0);
        JSONObject white=diagnostics.getJSONObject("whiteBalanceSnapshot3N");
        assertEquals("MANUAL_CAPTURE_REQUEST_GAINS",white.getString("authority"));
        assertFalse(white.getBoolean("calibratedKelvinClaimed"));
        assertFalse(white.getBoolean("selectedSourceNeutralClamped"));
        assertTrue(diagnostics.getJSONObject("whiteBalanceAuthority3L").getBoolean("newWhiteBalanceAdjustmentApplied"));
        when(f.r.getRequest()).thenReturn(saved);
        var preview=preview(f);var meter=meter(f);
        for(var context:new M10RExposureNative1B.Context[]{preview,meter}) {
            assertArrayEquals(prepared.copySourceToTargetCamera(),(double[])field(context,"sourceToTarget"),0);
            assertArrayEquals(prepared.copyCa9(),(int[])field(context,"ca9"));
            assertArrayEquals(prepared.sourceWhite().copySourceNeutral(),context.sourceWhite.copySourceNeutral(),0);
            assertEquals(1234567890L,context.frameTimestampNs);
        }
        Field factory=M10RNativeRenderer.class.getDeclaredField("RENDERED_COLOR");factory.setAccessible(true);
        assertSame(preview.sourceWhite,preview.withRenderedColor((M10RRenderedColor1A)factory.get(null),false).sourceWhite);
    }

    @Test public void autoRestoresExactContextAndPixelsDespiteLeftoverManualGains() throws Exception {
        var f=fixture();var baseline=preview(f);
        CaptureRequest manual=M10RRequestedWhite3OTest.request(2,1,1,1.4f);
        when(f.r.getRequest()).thenReturn(manual);assertFalse(Arrays.equals(baseline.render(PIXELS,1),preview(f).render(PIXELS,1)));
        CaptureRequest auto=M10RRequestedWhite3OTest.autoRequest();
        var leftover=M10RRequestedWhite3OTest.gains(2,1,1,1.4f);
        when(auto.get(CaptureRequest.COLOR_CORRECTION_GAINS)).thenReturn(leftover);
        when(f.r.getRequest()).thenReturn(auto);var restored=preview(f);
        assertEquals(M10RSourceWhite3N.Authority.VENDOR_CAPTURE_RESULT,restored.sourceWhite.authority());
        for(String name:new String[]{"sourceToTarget","targetToWorking","workingToOutput"})
            assertArrayEquals((double[])field(baseline,name),(double[])field(restored,name),0);
        assertArrayEquals((int[])field(baseline,"ca9"),(int[])field(restored,"ca9"));
        assertArrayEquals(baseline.render(PIXELS,1),restored.render(PIXELS,1));
    }

    @Test public void invalidManualWhiteProducesExplicitRejectionWithoutImportingVendor() throws Exception {
        var f=fixture();CaptureRequest bad=M10RRequestedWhite3OTest.request(Float.NaN,1,1,2);
        JSONObject diagnostics=new JSONObject();
        assertThrows(IllegalArgumentException.class,()->prepare(f,bad,diagnostics));
        JSONObject white=diagnostics.getJSONObject("whiteBalanceSnapshot3N");
        assertEquals("rejected",white.getString("status"));
        assertEquals("manual_WB_request_gains_invalid",white.getString("reason"));
        assertFalse(white.getBoolean("vendorFallbackApplied"));
        assertFalse(diagnostics.has("sourceSensorNeutral"));
    }
}
