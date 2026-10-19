package com.particlesdevs.photoncamera.m10r;

import android.graphics.ImageFormat;
import android.graphics.Rect;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CameraManager;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.CaptureResult;
import android.hardware.camera2.params.ColorSpaceTransform;
import android.hardware.camera2.params.StreamConfigurationMap;
import android.util.Rational;
import android.util.Size;
import android.util.SizeF;

import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.AfterClass;
import org.junit.BeforeClass;
import org.junit.Test;

import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashSet;

import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/** Capability truth, API guards and immutable pre-mutation snapshots without a device. */
public class M10RRawCapabilities4ATest {
    @BeforeClass public static void keys() throws Exception { M10RCaptureMeterReference1ITest.keys(); }
    @AfterClass public static void restore() throws Exception { M10RCaptureMeterReference1ITest.restoreKeys(); }

    static CameraCharacteristics camera() {
        CameraCharacteristics value = mock(CameraCharacteristics.class);
        when(value.getPhysicalCameraIds()).thenReturn(Collections.emptySet());
        return value;
    }

    static Size size(int width, int height) {
        Size value = mock(Size.class);
        when(value.getWidth()).thenReturn(width); when(value.getHeight()).thenReturn(height);
        return value;
    }

    static JSONObject format(JSONObject camera, String mode, int format) throws org.json.JSONException {
        JSONArray formats = camera.getJSONObject("streams").getJSONObject(mode).getJSONArray("formats");
        for (int i = 0; i < formats.length(); i++) {
            JSONObject candidate = formats.getJSONObject(i);
            if (candidate.getInt("format") == format) return candidate;
        }
        fail("format missing"); return null;
    }

    static M10RRawCapabilities4A.Snapshot one(CameraCharacteristics camera, int sdk) throws Exception {
        CameraManager manager = mock(CameraManager.class);
        when(manager.getCameraIdList()).thenReturn(new String[]{"0"});
        when(manager.getCameraCharacteristics("0")).thenReturn(camera);
        return M10RRawCapabilities4A.discover(manager, Collections.singleton("0"), sdk);
    }

    @Test public void enumeratesPublicLogicalPhysicalAndAppExtraIdsOnceWithIsolatedFailure() throws Exception {
        CameraManager manager = mock(CameraManager.class);
        CameraCharacteristics logical = camera(), physical = camera(), extra = camera();
        when(manager.getCameraIdList()).thenReturn(new String[]{"2", "0"});
        when(manager.getCameraCharacteristics("0")).thenReturn(logical);
        when(manager.getCameraCharacteristics("2")).thenReturn(physical);
        when(manager.getCameraCharacteristics("3")).thenThrow(new SecurityException("private vendor detail"));
        when(manager.getCameraCharacteristics("9")).thenReturn(extra);
        when(logical.getPhysicalCameraIds()).thenReturn(new LinkedHashSet<>(Arrays.asList("3", "2")));
        var snapshot = M10RRawCapabilities4A.discover(manager, Arrays.asList("9", "2", "9"), 36);
        assertEquals(4, snapshot.toJson().getInt("sourceCount"));
        assertEquals(3, snapshot.toJson().getInt("availableSourceCount"));
        assertEquals("partial", snapshot.toJson().getString("status"));
        assertEquals("0", snapshot.sourceJson("2").getJSONArray("logicalParentIds").getString(0));
        assertTrue(snapshot.sourceJson("2").getBoolean("listedByCameraManager"));
        assertFalse(snapshot.sourceJson("9").getBoolean("listedByCameraManager"));
        assertTrue(snapshot.sourceJson("9").getBoolean("appAccessiblePhysicalId"));
        assertEquals("characteristics_error", snapshot.sourceJson("3").getString("status"));
        assertEquals("SecurityException", snapshot.sourceJson("3").getJSONObject("error").getString("errorType"));
        assertFalse(snapshot.toJson().toString().contains("private vendor detail"));
        verify(manager).getCameraIdList();
        for (String id : new String[]{"0", "2", "3", "9"}) verify(manager).getCameraCharacteristics(id);
        verifyNoMoreInteractions(manager);
        assertFalse(snapshot.toJson().getBoolean("sessionCombinationValidated"));
        assertFalse(snapshot.toJson().getBoolean("changesCaptureConfiguration"));
    }

    @Test public void keepsDefaultSlowerAndMaximumFormatMapsSeparateWithoutInventingArrayOutputs() throws Exception {
        CameraCharacteristics c = camera();
        StreamConfigurationMap normal = mock(StreamConfigurationMap.class), maximum = mock(StreamConfigurationMap.class);
        when(c.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP)).thenReturn(normal);
        when(c.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP_MAXIMUM_RESOLUTION)).thenReturn(maximum);
        Size maximumArray = size(16384, 12288);
        when(c.get(CameraCharacteristics.SENSOR_INFO_PIXEL_ARRAY_SIZE_MAXIMUM_RESOLUTION)).thenReturn(maximumArray);
        Size regular = size(4096, 3072), slower = size(6000, 4000), high = size(8192, 6144);
        when(normal.isOutputSupportedFor(ImageFormat.RAW_SENSOR)).thenReturn(true);
        when(normal.getOutputSizes(ImageFormat.RAW_SENSOR)).thenReturn(new Size[]{regular});
        when(normal.getHighResolutionOutputSizes(ImageFormat.RAW_SENSOR)).thenReturn(new Size[]{slower});
        when(normal.getOutputMinFrameDuration(ImageFormat.RAW_SENSOR, regular)).thenReturn(33_000_000L);
        when(normal.getOutputStallDuration(ImageFormat.RAW_SENSOR, regular)).thenReturn(14_000_000L);
        when(maximum.isOutputSupportedFor(ImageFormat.RAW10)).thenReturn(true);
        when(maximum.getOutputSizes(ImageFormat.RAW10)).thenReturn(new Size[]{high});
        when(maximum.getHighResolutionOutputSizes(ImageFormat.RAW10)).thenReturn(new Size[0]);
        JSONObject source = one(c, 31).sourceJson("0");
        JSONObject raw = format(source, "default", ImageFormat.RAW_SENSOR);
        JSONObject first = raw.getJSONObject("regularOutputSizes").getJSONArray("sizes").getJSONObject(0);
        assertEquals(4096, first.getInt("width"));
        assertEquals(33_000_000L, first.getJSONObject("minFrameDurationNs").getLong("value"));
        assertEquals(14_000_000L, first.getJSONObject("stallDurationNs").getLong("value"));
        assertEquals(6000, raw.getJSONObject("slowerHighResolutionOutputSizes").getJSONArray("sizes").getJSONObject(0).getInt("width"));
        assertEquals("format_not_advertised", format(source, "maximumResolution", ImageFormat.RAW_SENSOR).getString("status"));
        assertEquals(8192, format(source, "maximumResolution", ImageFormat.RAW10)
                .getJSONObject("regularOutputSizes").getJSONArray("sizes").getJSONObject(0).getInt("width"));
        assertFalse(source.getJSONObject("streams").toString().contains("16384"));
        verify(maximum, never()).getOutputSizes(ImageFormat.RAW_SENSOR);
        verify(normal, never()).getOutputSizes(ImageFormat.RAW12);
    }

    @Test public void snapshotCopiesMutableGeometryMatricesAndJsonWhileDigestRemainsStable() throws Exception {
        CameraCharacteristics c = camera();
        Rect active = mock(Rect.class); active.left = 4; active.top = 6; active.right = 4100; active.bottom = 3078;
        when(c.get(CameraCharacteristics.SENSOR_INFO_ACTIVE_ARRAY_SIZE)).thenReturn(active);
        float[] focals = {8.8f}; when(c.get(CameraCharacteristics.LENS_INFO_AVAILABLE_FOCAL_LENGTHS)).thenReturn(focals);
        ColorSpaceTransform matrix = mock(ColorSpaceTransform.class);
        Rational coefficient = mock(Rational.class);
        when(coefficient.getNumerator()).thenReturn(17); when(coefficient.getDenominator()).thenReturn(29);
        when(matrix.getElement(anyInt(), anyInt())).thenReturn(coefficient);
        when(c.get(CameraCharacteristics.SENSOR_COLOR_TRANSFORM1)).thenReturn(matrix);
        var snapshot = one(c, 36);
        String digest = snapshot.sourceDigest("0");
        JSONObject source = snapshot.sourceJson("0");
        active.right = 8196; focals[0] = 99; when(coefficient.getNumerator()).thenReturn(900);
        source.getJSONObject("characteristics").getJSONObject("android.sensor.info.activeArraySize").getJSONArray("value").put(2, 999);
        snapshot.toJson().getJSONObject("sources").remove("0");
        JSONObject frozen = snapshot.sourceJson("0").getJSONObject("characteristics");
        assertEquals(4100, frozen.getJSONObject("android.sensor.info.activeArraySize").getJSONArray("value").getInt(2));
        assertEquals(8.8, frozen.getJSONObject("android.lens.info.availableFocalLengths").getJSONArray("value").getDouble(0), .00001);
        assertEquals(17, frozen.getJSONObject("android.sensor.colorTransform1").getJSONArray("value").getJSONObject(0).getInt("numerator"));
        assertEquals(29, frozen.getJSONObject("android.sensor.colorTransform1").getJSONArray("value").getJSONObject(0).getInt("denominator"));
        assertEquals(digest, snapshot.sourceDigest("0"));
        assertEquals(64, digest.length());
        assertEquals(digest, snapshot.sourceJson("0").getString("sourceDigestSha256"));
        assertNotEquals(digest, one(c, 36).sourceDigest("0"));
        assertNull(snapshot.sourceDigest("unseen"));
        assertEquals("source_not_in_inventory", snapshot.sourceJson("unseen").getString("status"));
    }

    @Test public void oldApiDoesNotReadMaximumOrPhysicalMethodsAndDoesNotGuessValues() throws Exception {
        CameraCharacteristics c = camera();
        JSONObject source = one(c, 26).sourceJson("0");
        assertEquals("api_unavailable", source.getJSONObject("advertisedPhysicalIds").getString("status"));
        assertEquals("api_unavailable", source.getJSONObject("streams").getJSONObject("maximumResolution").getString("status"));
        assertEquals("api_unavailable", source.getJSONObject("characteristics").getJSONObject("android.sensor.info.binningFactor").getString("status"));
        assertEquals("api_unavailable", source.getJSONObject("physicalRequestKeySupport").getString("status"));
        verify(c, never()).getPhysicalCameraIds();
        verify(c, never()).getAvailablePhysicalCameraRequestKeys();
        verify(c, never()).get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP_MAXIMUM_RESOLUTION);
        verify(c, never()).get(CameraCharacteristics.SENSOR_INFO_BINNING_FACTOR);
    }

    @Test public void missingMapNullSlowerListAndDurationFailureRemainExplicit() throws Exception {
        CameraCharacteristics c = camera(); StreamConfigurationMap normal = mock(StreamConfigurationMap.class);
        when(c.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP)).thenReturn(normal);
        Size raw = size(4096, 3072);
        when(normal.isOutputSupportedFor(ImageFormat.RAW_SENSOR)).thenReturn(true);
        when(normal.getOutputSizes(ImageFormat.RAW_SENSOR)).thenReturn(new Size[]{raw});
        when(normal.getHighResolutionOutputSizes(ImageFormat.RAW_SENSOR)).thenReturn(null);
        when(normal.getOutputMinFrameDuration(ImageFormat.RAW_SENSOR, raw)).thenThrow(new IllegalArgumentException());
        when(normal.getOutputStallDuration(ImageFormat.RAW_SENSOR, raw)).thenReturn(0L);
        when(c.get(CameraCharacteristics.SENSOR_INFO_WHITE_LEVEL)).thenThrow(new IllegalStateException());
        JSONObject source = one(c, 31).sourceJson("0");
        assertEquals("available", source.getString("status"));
        assertEquals("absent", source.getJSONObject("streams").getJSONObject("maximumResolution").getString("status"));
        assertEquals("error", source.getJSONObject("characteristics").getJSONObject("android.sensor.info.whiteLevel").getString("status"));
        JSONObject rawFormat = format(source, "default", ImageFormat.RAW_SENSOR);
        assertEquals("absent", rawFormat.getJSONObject("slowerHighResolutionOutputSizes").getString("status"));
        assertEquals(0, rawFormat.getJSONObject("slowerHighResolutionOutputSizes").getJSONArray("sizes").length());
        JSONObject delivered = rawFormat.getJSONObject("regularOutputSizes").getJSONArray("sizes").getJSONObject(0);
        assertEquals("error", delivered.getJSONObject("minFrameDurationNs").getString("status"));
        assertEquals(0L, delivered.getJSONObject("stallDurationNs").getLong("value"));
    }

    @Test public void supportUsesAdvertisedKeyNamesAndDoesNotTurnMissingListIntoFalse() throws Exception {
        CameraCharacteristics c = camera();
        when(CaptureRequest.SENSOR_PIXEL_MODE.getName()).thenReturn("android.sensor.pixelMode");
        when(CaptureResult.SENSOR_RAW_BINNING_FACTOR_USED.getName()).thenReturn("android.sensor.rawBinningFactorUsed");
        when(c.getAvailableCaptureRequestKeys()).thenReturn(Collections.singletonList(CaptureRequest.SENSOR_PIXEL_MODE));
        when(c.getAvailableCaptureResultKeys()).thenReturn(Collections.singletonList(CaptureResult.SENSOR_RAW_BINNING_FACTOR_USED));
        when(c.getAvailablePhysicalCameraRequestKeys()).thenReturn(null);
        JSONObject source = one(c, 31).sourceJson("0");
        assertTrue(source.getJSONObject("requestKeySupport").getJSONObject("keys").getBoolean("android.sensor.pixelMode"));
        assertFalse(source.getJSONObject("resultKeySupport").getJSONObject("keys").getBoolean("android.sensor.pixelMode"));
        assertTrue(source.getJSONObject("resultKeySupport").getJSONObject("keys").getBoolean("android.sensor.rawBinningFactorUsed"));
        assertEquals("absent", source.getJSONObject("physicalRequestKeySupport").getString("status"));
        assertFalse(source.getJSONObject("physicalRequestKeySupport").has("keys"));
    }

    @Test public void enumerationFailureStillCapturesAppIdsAndMissingManagerIsNonThrowing() throws Exception {
        CameraManager manager = mock(CameraManager.class); CameraCharacteristics c = camera();
        when(manager.getCameraIdList()).thenThrow(new SecurityException());
        when(manager.getCameraCharacteristics("extra")).thenReturn(c);
        var partial = M10RRawCapabilities4A.discover(manager, Collections.singleton("extra"), 31);
        assertEquals("partial", partial.toJson().getString("status"));
        assertEquals("available", partial.sourceJson("extra").getString("status"));
        var absent = M10RRawCapabilities4A.discover(null, Collections.singleton("extra"), 26);
        assertEquals("camera_manager_unavailable", absent.toJson().getString("status"));
        assertEquals("camera_manager_unavailable", absent.sourceJson("extra").getString("status"));
    }

    @Test public void nonfiniteVendorMetadataIsIsolatedToItsKeyAndSnapshotStaysParseable() throws Exception {
        for (float invalid : new float[]{Float.NaN, Float.POSITIVE_INFINITY, Float.NEGATIVE_INFINITY}) {
            CameraCharacteristics c = camera(); SizeF physical = mock(SizeF.class);
            when(physical.getWidth()).thenReturn(invalid); when(physical.getHeight()).thenReturn(10f);
            when(c.get(CameraCharacteristics.SENSOR_INFO_PHYSICAL_SIZE)).thenReturn(physical);
            when(c.get(CameraCharacteristics.LENS_INFO_AVAILABLE_FOCAL_LENGTHS)).thenReturn(new float[]{8.8f, invalid});
            when(c.get(CameraCharacteristics.SENSOR_INFO_WHITE_LEVEL)).thenReturn(1023);
            var snapshot = one(c, 31);
            JSONObject source = snapshot.sourceJson("0");
            assertEquals("available", source.getString("status"));
            JSONObject metadata = source.getJSONObject("characteristics");
            assertEquals("error", metadata.getJSONObject("android.sensor.info.physicalSize").getString("status"));
            assertEquals("error", metadata.getJSONObject("android.lens.info.availableFocalLengths").getString("status"));
            assertEquals(1023, metadata.getJSONObject("android.sensor.info.whiteLevel").getInt("value"));
            assertNotNull(snapshot.toJson()); assertEquals(64, snapshot.sourceDigest("0").length());
        }
    }
}
