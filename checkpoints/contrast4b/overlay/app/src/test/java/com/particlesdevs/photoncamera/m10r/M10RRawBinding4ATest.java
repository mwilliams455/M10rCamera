package com.particlesdevs.photoncamera.m10r;

import android.graphics.ImageFormat;
import android.graphics.Rect;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CameraManager;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.CaptureResult;
import android.hardware.camera2.TotalCaptureResult;
import android.hardware.camera2.params.BlackLevelPattern;
import android.hardware.camera2.params.ColorSpaceTransform;
import android.hardware.camera2.params.StreamConfigurationMap;
import android.media.Image;
import android.util.Rational;
import android.util.Size;

import com.particlesdevs.photoncamera.processing.ImageFrame;

import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.AfterClass;
import org.junit.BeforeClass;
import org.junit.Test;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/** Verifies provenance, metadata ambiguity, and identity stability without a phone or pixel changes. */
public class M10RRawBinding4ATest {
    @BeforeClass public static void keys() throws Exception { M10RCaptureMeterReference1ITest.keys(); }
    @AfterClass public static void restore() throws Exception { M10RCaptureMeterReference1ITest.restoreKeys(); }
    static final int WIDTH = 384, HEIGHT = 288;
    static final long TIMESTAMP = 76437411047298L;

    static Rect rect(int l, int t, int r, int b) {
        Rect v = mock(Rect.class); v.left = l; v.top = t; v.right = r; v.bottom = b; return v;
    }
    static Size size(int w, int h) {
        Size v = mock(Size.class); when(v.getWidth()).thenReturn(w); when(v.getHeight()).thenReturn(h); return v;
    }
    static Rational rational(int n, int d) {
        Rational r = mock(Rational.class); when(r.getNumerator()).thenReturn(n); when(r.getDenominator()).thenReturn(d); return r;
    }
    static ColorSpaceTransform matrix() {
        ColorSpaceTransform m = mock(ColorSpaceTransform.class);
        for (int row = 0; row < 3; row++) for (int col = 0; col < 3; col++) {
            Rational coefficient = rational(1 + row * 3 + col, 17 + row * 3 + col);
            when(m.getElement(col, row)).thenReturn(coefficient);
        }
        return m;
    }
    static CameraCharacteristics camera(boolean logical) {
        CameraCharacteristics c = mock(CameraCharacteristics.class);
        when(c.get(CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES)).thenReturn(logical
                ? new int[]{CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES_RAW,
                CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES_LOGICAL_MULTI_CAMERA}
                : new int[]{CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES_RAW});
        when(c.getPhysicalCameraIds()).thenReturn(Collections.emptySet());
        when(c.get(CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT)).thenReturn(0);
        Size pixelArray = size(WIDTH, HEIGHT);
        Rect activeArray = rect(0, 0, WIDTH, HEIGHT);
        Rect preCorrectionArray = rect(0, 0, WIDTH, HEIGHT);
        when(c.get(CameraCharacteristics.SENSOR_INFO_PIXEL_ARRAY_SIZE)).thenReturn(pixelArray);
        when(c.get(CameraCharacteristics.SENSOR_INFO_ACTIVE_ARRAY_SIZE)).thenReturn(activeArray);
        when(c.get(CameraCharacteristics.SENSOR_INFO_PRE_CORRECTION_ACTIVE_ARRAY_SIZE)).thenReturn(preCorrectionArray);
        when(c.get(CameraCharacteristics.SENSOR_INFO_WHITE_LEVEL)).thenReturn(1023);
        BlackLevelPattern black = mock(BlackLevelPattern.class);
        for (int row = 0; row < 2; row++) for (int col = 0; col < 2; col++)
            when(black.getOffsetForIndex(col, row)).thenReturn(64 + row * 2 + col);
        doAnswer(call -> { int[] out = call.getArgument(0); int offset = call.getArgument(1);
            for (int i = 0; i < 4; i++) out[offset + i] = 64 + i; return null;
        }).when(black).copyTo(any(int[].class), anyInt());
        when(c.get(CameraCharacteristics.SENSOR_BLACK_LEVEL_PATTERN)).thenReturn(black);
        when(c.get(CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT1)).thenReturn(21);
        when(c.get(CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT2)).thenReturn((byte) 17);
        for (CameraCharacteristics.Key<ColorSpaceTransform> key : Arrays.asList(
                CameraCharacteristics.SENSOR_COLOR_TRANSFORM1, CameraCharacteristics.SENSOR_COLOR_TRANSFORM2,
                CameraCharacteristics.SENSOR_CALIBRATION_TRANSFORM1, CameraCharacteristics.SENSOR_CALIBRATION_TRANSFORM2,
                CameraCharacteristics.SENSOR_FORWARD_MATRIX1, CameraCharacteristics.SENSOR_FORWARD_MATRIX2)) {
            ColorSpaceTransform value = matrix();
            when(c.get(key)).thenReturn(value);
        }
        StreamConfigurationMap normal = mock(StreamConfigurationMap.class);
        when(normal.isOutputSupportedFor(ImageFormat.RAW_SENSOR)).thenReturn(true);
        Size rawOutput = size(WIDTH, HEIGHT);
        when(normal.getOutputSizes(ImageFormat.RAW_SENSOR)).thenReturn(new Size[]{rawOutput});
        when(normal.getHighResolutionOutputSizes(ImageFormat.RAW_SENSOR)).thenReturn(new Size[0]);
        when(c.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP)).thenReturn(normal);
        return c;
    }
    static M10RRawCapabilities4A.Snapshot snapshot(Map<String, CameraCharacteristics> values, int sdk) throws Exception {
        CameraManager manager = mock(CameraManager.class);
        when(manager.getCameraIdList()).thenReturn(values.keySet().toArray(new String[0]));
        for (Map.Entry<String, CameraCharacteristics> entry : values.entrySet())
            when(manager.getCameraCharacteristics(entry.getKey())).thenReturn(entry.getValue());
        return M10RRawCapabilities4A.discover(manager, values.keySet(), sdk);
    }
    static ImageFrame frame(int originalWidth, int originalHeight, boolean appBin, long ts) throws Exception {
        int rowStride = originalWidth * 2;
        ByteBuffer original = ByteBuffer.allocate(rowStride * originalHeight).order(ByteOrder.BIG_ENDIAN);
        original.position(3); original.mark();
        Image image = mock(Image.class); Image.Plane plane = mock(Image.Plane.class);
        when(image.getFormat()).thenReturn(ImageFormat.RAW_SENSOR);
        when(image.getWidth()).thenReturn(originalWidth); when(image.getHeight()).thenReturn(originalHeight);
        Rect originalCrop = rect(0, 0, originalWidth, originalHeight);
        when(image.getTimestamp()).thenReturn(ts); when(image.getCropRect()).thenReturn(originalCrop);
        when(image.getPlanes()).thenReturn(new Image.Plane[]{plane});
        when(plane.getRowStride()).thenReturn(rowStride); when(plane.getPixelStride()).thenReturn(2);
        when(plane.getBuffer()).thenReturn(original);
        M10RRawBinding4A.ImageEvidence evidence = M10RRawBinding4A.ImageEvidence.captureOriginal(image);
        var constructor = ImageFrame.class.getDeclaredConstructor(); constructor.setAccessible(true);
        ImageFrame frame = constructor.newInstance();
        frame.width = originalWidth / (appBin ? 2 : 1); frame.height = originalHeight / (appBin ? 2 : 1);
        frame.timestamp = ts;
        frame.buffer = appBin ? ByteBuffer.allocate(frame.width * frame.height * 2).asReadOnlyBuffer() : original.asReadOnlyBuffer();
        frame.rawBinding4A = evidence.withConversion(frame, appBin, appBin ? "app_Bayer_binning" : "full_buffer_copy",
                rect(0, 0, originalWidth, originalHeight));
        return frame;
    }
    static TotalCaptureResult result(String id, long timestamp, int mode, CaptureRequest request) {
        TotalCaptureResult r = mock(TotalCaptureResult.class);
        when(r.getCameraId()).thenReturn(id); when(r.getFrameNumber()).thenReturn(267L);
        when(r.get(CaptureResult.SENSOR_TIMESTAMP)).thenReturn(timestamp);
        when(r.get(CaptureResult.SENSOR_PIXEL_MODE)).thenReturn(mode);
        when(r.get(CaptureResult.SENSOR_EXPOSURE_TIME)).thenReturn(9_736_251L);
        when(r.get(CaptureResult.SENSOR_SENSITIVITY)).thenReturn(100);
        when(r.get(CaptureResult.SENSOR_DYNAMIC_BLACK_LEVEL)).thenReturn(new float[]{64, 64, 64, 64});
        when(r.get(CaptureResult.SENSOR_DYNAMIC_WHITE_LEVEL)).thenReturn(1023);
        Rect scalerCrop = rect(0, 0, WIDTH, HEIGHT);
        when(r.get(CaptureResult.SCALER_CROP_REGION)).thenReturn(scalerCrop);
        when(r.get(CaptureResult.DISTORTION_CORRECTION_MODE)).thenReturn(0);
        when(r.getPhysicalCameraTotalResults()).thenReturn(Collections.emptyMap());
        when(r.getPhysicalCameraResults()).thenReturn(Collections.emptyMap());
        when(r.getRequest()).thenReturn(request);
        return r;
    }
    static final class Fixture {
        final CameraCharacteristics c;
        final M10RRawCapabilities4A.Snapshot inventory;
        final M10RRawBinding4A.CameraContext context;
        final CaptureRequest request = mock(CaptureRequest.class);
        final TotalCaptureResult result;
        Fixture() throws Exception { this(camera(false), 36); }
        Fixture(CameraCharacteristics c, int sdk) throws Exception {
            this.c = c; inventory = snapshot(Collections.singletonMap("0", c), sdk);
            context = new M10RRawBinding4A.CameraContext("0", "0", "0", "0", false, inventory);
            M10RExposureReport1C report = new M10RExposureReport1C(new JSONObject().put("existingExposure", true))
                    .withRawContext4A(context);
            when(request.getTag()).thenReturn(report);
            when(request.get(CaptureRequest.SENSOR_PIXEL_MODE)).thenReturn(0);
            result = result("0", TIMESTAMP, 0, request);
        }
        JSONObject parent(ImageFrame frame, int sdk) {
            JSONObject parent = new JSONObject();
            M10RRawBinding4A.append(parent, frame, c, result, request, context, sdk); return parent;
        }
        JSONObject bind(ImageFrame frame) throws org.json.JSONException {
            return parent(frame, 36).getJSONObject("rawBinding4A");
        }
    }

    @Test public void directSensorCaptureBindsExactImageResultAndImmutableCalibration() throws Exception {
        Fixture f = new Fixture(); ImageFrame image = frame(WIDTH, HEIGHT, false, TIMESTAMP);
        JSONObject j = f.bind(image);
        assertEquals("IMAGE_AND_SOURCE_RESULT_BOUND", j.getString("status"));
        assertTrue(j.getBoolean("streamIdentityComplete"));
        assertTrue(j.getBoolean("rendererMetadataMatchesImmutableInventory"));
        assertEquals("verified_direct_nonlogical_device_result", j.getString("sourceResultAuthority"));
        assertEquals("default", j.getJSONObject("geometry").getString("deliveredGeometryFamily"));
        JSONObject first = j.getJSONObject("calibrationMetadata").getJSONObject("android.sensor.colorTransform1")
                .getJSONArray("value").getJSONObject(0);
        assertEquals(1, first.getInt("numerator")); assertEquals(17, first.getInt("denominator"));
        assertEquals("delivered_size_advertised_for_format_and_mode", j.getJSONObject("streamAdvertisementMatch").getString("status"));
        assertFalse(j.getBoolean("controlsWhiteBalance")); assertFalse(j.getBoolean("calibrationEstablished"));
        assertFalse(j.getBoolean("identityAllowsAutomaticCalibrationPromotion"));
        assertFalse(j.getJSONObject("geometry").getBoolean("sensorCfaPhaseAtOriginalBufferOriginProven"));
        assertEquals(3, image.buffer.position());
    }

    @Test public void deliveredIdentityDoesNotChangeWithExposureIsoTimestampOrDynamicLevels() throws Exception {
        Fixture f = new Fixture(); JSONObject first = f.bind(frame(WIDTH, HEIGHT, false, TIMESTAMP));
        when(f.result.get(CaptureResult.SENSOR_TIMESTAMP)).thenReturn(TIMESTAMP + 100);
        when(f.result.get(CaptureResult.SENSOR_EXPOSURE_TIME)).thenReturn(20_000_000L);
        when(f.result.get(CaptureResult.SENSOR_SENSITIVITY)).thenReturn(800);
        when(f.result.get(CaptureResult.SENSOR_DYNAMIC_BLACK_LEVEL)).thenReturn(new float[]{70, 71, 72, 73});
        when(f.result.get(CaptureResult.SENSOR_DYNAMIC_WHITE_LEVEL)).thenReturn(1010);
        JSONObject second = f.bind(frame(WIDTH, HEIGHT, false, TIMESTAMP + 100));
        assertEquals(first.getString("deliveredStreamIdentitySha256"), second.getString("deliveredStreamIdentitySha256"));
        assertEquals(first.getString("physicalSensorMetadataFingerprintSha256"), second.getString("physicalSensorMetadataFingerprintSha256"));
        assertEquals(first.getString("calibrationMetadataFingerprintSha256"), second.getString("calibrationMetadataFingerprintSha256"));
        assertEquals(800, second.getJSONObject("sourceResult").getJSONObject("sensitivityIso").getInt("value"));
        assertEquals(70, second.getJSONObject("levelsForSourceResult").getJSONArray("effectiveBlackLevels").getInt(0));
    }

    @Test public void largerDeliveredFrameDownBinnedByAppKeepsItsOwnStreamIdentity() throws Exception {
        Fixture f = new Fixture(); JSONObject low = f.bind(frame(WIDTH, HEIGHT, false, TIMESTAMP));
        // Scaled host fixture reproduces a 2x-per-axis readout change without a 100 MB test allocation.
        ImageFrame highFrame = frame(WIDTH * 2, HEIGHT * 2, true, TIMESTAMP);
        when(f.result.get(CaptureResult.SENSOR_PIXEL_MODE)).thenReturn(1);
        JSONObject high = f.bind(highFrame);
        assertEquals(WIDTH, high.getJSONObject("workingFrameAtRender").getInt("width"));
        assertEquals(WIDTH * 2, high.getJSONObject("deliveredStreamIdentity").getInt("originalWidth"));
        assertTrue(high.getJSONObject("image").getJSONObject("appConversion").getBoolean("appBayerBinningApplied"));
        assertNotEquals(low.getString("deliveredStreamIdentitySha256"), high.getString("deliveredStreamIdentitySha256"));
        assertEquals(low.getString("calibrationMetadataFingerprintSha256"), high.getString("calibrationMetadataFingerprintSha256"));
        assertEquals(1, high.getJSONObject("sensorPixelMode").getJSONObject("delivered").getInt("value"));
        assertFalse(high.getJSONObject("sensorPixelMode").getBoolean("requestedDeliveredValuesAgree"));
    }

    @Test public void physicalResultOverridesLogicalTelemetryOnlyInsideDiagnostic() throws Exception {
        CameraCharacteristics logical = camera(true), physical = camera(false);
        when(logical.getPhysicalCameraIds()).thenReturn(Collections.singleton("2"));
        Map<String, CameraCharacteristics> cameras = new HashMap<>(); cameras.put("0", logical); cameras.put("2", physical);
        var inventory = snapshot(cameras, 36);
        var context = new M10RRawBinding4A.CameraContext("0", "2", "2", "2", true, inventory);
        CaptureRequest request = mock(CaptureRequest.class); when(request.getTag()).thenReturn(context);
        TotalCaptureResult top = result("0", TIMESTAMP, 0, request), source = result("2", TIMESTAMP, 1, request);
        when(top.get(CaptureResult.SENSOR_DYNAMIC_BLACK_LEVEL)).thenReturn(new float[]{10, 11, 12, 13});
        when(source.get(CaptureResult.SENSOR_DYNAMIC_BLACK_LEVEL)).thenReturn(new float[]{80, 81, 82, 83});
        when(top.getPhysicalCameraTotalResults()).thenReturn(Collections.singletonMap("2", source));
        JSONObject parent = new JSONObject(); ImageFrame frame = frame(WIDTH, HEIGHT, false, TIMESTAMP);
        M10RRawBinding4A.append(parent, frame, physical, top, request, context, 36);
        JSONObject j = parent.getJSONObject("rawBinding4A");
        assertEquals("IMAGE_AND_SOURCE_RESULT_BOUND", j.getString("status"));
        assertEquals("matching_physical_capture_result", j.getString("sourceResultAuthority"));
        assertEquals(1, j.getJSONObject("sensorPixelMode").getJSONObject("delivered").getInt("value"));
        assertEquals(0, j.getJSONObject("rendererResult").getJSONObject("pixelMode").getInt("value"));
        assertEquals(80, j.getJSONObject("levelsForSourceResult").getJSONArray("effectiveBlackLevels").getInt(0));
        assertEquals(10, j.getJSONObject("levelsForRendererInput").getJSONArray("effectiveBlackLevels").getInt(0));
        assertFalse(j.getBoolean("sourceMetadataReplacesRendererMetadata"));

        when(source.getFrameNumber()).thenReturn(268L);
        M10RRawBinding4A.append(parent, frame, physical, top, request, context, 36);
        assertFalse(parent.getJSONObject("rawBinding4A").getBoolean("streamIdentityComplete"));
        when(source.getFrameNumber()).thenReturn(267L);
        when(source.get(CaptureResult.SENSOR_TIMESTAMP)).thenReturn(TIMESTAMP - 1);
        M10RRawBinding4A.append(parent, frame, physical, top, request, context, 36);
        assertFalse(parent.getJSONObject("rawBinding4A").getBoolean("imageTimestampMatchesSourceResult"));
        assertFalse(parent.getJSONObject("rawBinding4A").getBoolean("streamIdentityComplete"));
        when(source.get(CaptureResult.SENSOR_TIMESTAMP)).thenReturn(TIMESTAMP);
        when(source.getCameraId()).thenReturn("9");
        M10RRawBinding4A.append(parent, frame, physical, top, request, context, 36);
        assertFalse(parent.getJSONObject("rawBinding4A").getBoolean("sourceIdentityProvenByOutputAndMetadata"));
    }

    @Test public void logicalIdEqualityAndActiveIdDoNotPretendToBePhysicalResult() throws Exception {
        Fixture f = new Fixture(camera(true), 36); ImageFrame frame = frame(WIDTH, HEIGHT, false, TIMESTAMP);
        JSONObject j = f.bind(frame);
        assertFalse(j.getBoolean("sourceIdentityProvenByOutputAndMetadata"));
        assertFalse(j.getBoolean("streamIdentityComplete"));
        when(f.result.get(CaptureResult.LOGICAL_MULTI_CAMERA_ACTIVE_PHYSICAL_ID)).thenReturn("0");
        j = f.bind(frame);
        assertEquals("logical_active_physical_id_match_without_physical_result", j.getString("sourceResultAuthority"));
        assertFalse(j.getBoolean("sourceIdentityProvenByOutputAndMetadata"));
        assertFalse(j.getBoolean("streamIdentityComplete"));
    }

    @Test public void missingDeliveredModeRemainsUnknownEvenWithMaximumRequestAndLargerImage() throws Exception {
        Fixture f = new Fixture(); when(f.request.get(CaptureRequest.SENSOR_PIXEL_MODE)).thenReturn(1);
        when(f.result.get(CaptureResult.SENSOR_PIXEL_MODE)).thenReturn(null);
        JSONObject j = f.bind(frame(WIDTH * 2, HEIGHT * 2, true, TIMESTAMP));
        assertEquals("absent", j.getJSONObject("sensorPixelMode").getJSONObject("delivered").getString("status"));
        assertTrue(j.getJSONObject("deliveredStreamIdentity").isNull("deliveredPixelMode"));
        assertEquals("unknown_delivered_pixel_mode", j.getJSONObject("geometry").getString("deliveredGeometryFamily"));
        assertFalse(j.getBoolean("streamIdentityComplete"));
        assertTrue(j.getJSONObject("sensorPixelMode").isNull("requestedDeliveredValuesAgree"));
    }

    @Test public void builderFreezesPhysicalRequestModeWithoutChangingItOrPromotingItToDelivery() throws Exception {
        Fixture f = new Fixture(); CaptureRequest.Builder builder = mock(CaptureRequest.Builder.class);
        when(builder.get(CaptureRequest.SENSOR_PIXEL_MODE)).thenReturn(1);
        when(builder.getPhysicalCameraKey(CaptureRequest.SENSOR_PIXEL_MODE, "0")).thenReturn(0);
        var context = f.context.withRequestBuilder(builder, 36);
        when(builder.getPhysicalCameraKey(CaptureRequest.SENSOR_PIXEL_MODE, "0")).thenReturn(1);
        when(f.request.getTag()).thenReturn(context);
        JSONObject parent = new JSONObject();
        M10RRawBinding4A.append(parent, frame(WIDTH, HEIGHT, false, TIMESTAMP), f.c, f.result, f.request, context, 36);
        JSONObject request = parent.getJSONObject("rawBinding4A").getJSONObject("requestContext").getJSONObject("requestBuilder");
        assertEquals(1, request.getJSONObject("logicalPixelMode").getInt("value"));
        assertEquals(0, request.getJSONObject("physicalPixelMode").getInt("value"));
        assertEquals(0, parent.getJSONObject("rawBinding4A").getJSONObject("sensorPixelMode").getJSONObject("requested").getInt("value"));
        verify(builder, never()).set(any(), any());
        verify(builder, never()).setPhysicalCameraKey(any(), any(), anyString());
        verify(builder, never()).build();
    }

    @Test public void oldApiAvoidsNewMethodsAndCannotLabelDeliveredModeDefault() throws Exception {
        Fixture f = new Fixture(camera(false), 26);
        JSONObject j = f.parent(frame(WIDTH, HEIGHT, false, TIMESTAMP), 26).getJSONObject("rawBinding4A");
        assertEquals("api_unavailable", j.getJSONObject("sensorPixelMode").getJSONObject("delivered").getString("status"));
        assertFalse(j.getBoolean("streamIdentityComplete"));
        verify(f.result, never()).get(CaptureResult.SENSOR_PIXEL_MODE);
        verify(f.result, never()).get(CaptureResult.SENSOR_RAW_BINNING_FACTOR_USED);
        verify(f.result, never()).getCameraId();
        verify(f.result, never()).getPhysicalCameraTotalResults();
        verify(f.result, never()).getPhysicalCameraResults();
    }

    @Test public void invalidDynamicLevelsUseExplicitStaticFallbackWithoutInventedDefaults() throws Exception {
        Fixture f = new Fixture();
        when(f.result.get(CaptureResult.SENSOR_DYNAMIC_BLACK_LEVEL)).thenReturn(new float[]{Float.NaN, 64, 64, 64});
        when(f.result.get(CaptureResult.SENSOR_DYNAMIC_WHITE_LEVEL)).thenReturn(-1);
        JSONObject j = f.bind(frame(WIDTH, HEIGHT, false, TIMESTAMP));
        assertEquals("error", j.getJSONObject("sourceResult").getJSONObject("dynamicBlackLevels").getString("status"));
        JSONObject levels = j.getJSONObject("levelsForSourceResult");
        assertEquals("characteristics", levels.getString("blackSource"));
        assertEquals("characteristics", levels.getString("whiteSource"));
        assertEquals(67, levels.getJSONArray("effectiveBlackLevels").getInt(3));
        assertEquals(1023, levels.getInt("effectiveWhiteLevel"));
        CameraCharacteristics missing = camera(false);
        when(missing.get(CameraCharacteristics.SENSOR_BLACK_LEVEL_PATTERN)).thenReturn(null);
        when(missing.get(CameraCharacteristics.SENSOR_INFO_WHITE_LEVEL)).thenReturn(null);
        Fixture absent = new Fixture(missing, 36);
        when(absent.result.get(CaptureResult.SENSOR_DYNAMIC_BLACK_LEVEL)).thenReturn(null);
        when(absent.result.get(CaptureResult.SENSOR_DYNAMIC_WHITE_LEVEL)).thenReturn(null);
        levels = absent.bind(frame(WIDTH, HEIGHT, false, TIMESTAMP)).getJSONObject("levelsForSourceResult");
        assertEquals("unavailable", levels.getString("blackSource")); assertTrue(levels.isNull("effectiveWhiteLevel"));
    }

    @Test public void changedRendererGeometryAndMatricesDoNotRewriteCapturedInventoryOrFingerprint() throws Exception {
        Fixture f = new Fixture(); JSONObject before = f.bind(frame(WIDTH, HEIGHT, false, TIMESTAMP));
        Rect changedActiveArray = rect(0, 0, WIDTH * 2, HEIGHT * 2);
        when(f.c.get(CameraCharacteristics.SENSOR_INFO_ACTIVE_ARRAY_SIZE)).thenReturn(changedActiveArray);
        ColorSpaceTransform changed = matrix(); Rational changedCoefficient = rational(17, 23);
        when(changed.getElement(0, 0)).thenReturn(changedCoefficient);
        when(f.c.get(CameraCharacteristics.SENSOR_COLOR_TRANSFORM1)).thenReturn(changed);
        JSONObject after = f.bind(frame(WIDTH, HEIGHT, false, TIMESTAMP));
        assertFalse(after.getBoolean("rendererMetadataMatchesImmutableInventory"));
        assertEquals(before.getString("deliveredStreamIdentitySha256"), after.getString("deliveredStreamIdentitySha256"));
        assertEquals(1, after.getJSONObject("calibrationMetadata").getJSONObject("android.sensor.colorTransform1")
                .getJSONArray("value").getJSONObject(0).getInt("numerator"));
        assertEquals(17, after.getJSONObject("rendererCharacteristicsAtRender").getJSONObject("android.sensor.colorTransform1")
                .getJSONArray("value").getJSONObject(0).getInt("numerator"));
    }

    @Test public void groupedLayoutOrMissingRemosaicFlagRemainsUnsupportedWithoutBlockingCapture() throws Exception {
        CameraCharacteristics c = camera(false);
        Size binningFactor = size(2, 2);
        when(c.get(CameraCharacteristics.SENSOR_INFO_BINNING_FACTOR)).thenReturn(binningFactor);
        when(c.get(CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES)).thenReturn(new int[]{
                CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES_RAW,
                CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES_ULTRA_HIGH_RESOLUTION_SENSOR,
                CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES_REMOSAIC_REPROCESSING});
        Fixture f = new Fixture(c, 36); ImageFrame frame = frame(WIDTH, HEIGHT, false, TIMESTAMP);
        when(f.result.get(CaptureResult.SENSOR_RAW_BINNING_FACTOR_USED)).thenReturn(true);
        JSONObject j = f.bind(frame);
        assertEquals("unsupported_grouped_color_filter_layout", j.getJSONObject("rawInterpretation").getString("layoutStatus"));
        assertFalse(j.getJSONObject("rawInterpretation").getBoolean("standardBayerInterpretationSupportedByMetadata"));
        assertFalse(j.getJSONObject("workingFrameCompatibility").getBoolean("enforcesNewCaptureGate"));
        when(f.result.get(CaptureResult.SENSOR_RAW_BINNING_FACTOR_USED)).thenReturn(null);
        j = f.bind(frame);
        assertEquals("layout_unproven_remosaic_result_flag_missing", j.getJSONObject("rawInterpretation").getString("layoutStatus"));
        when(f.result.get(CaptureResult.SENSOR_RAW_BINNING_FACTOR_USED)).thenReturn(false);
        assertTrue(f.bind(frame).getJSONObject("rawInterpretation").getBoolean("standardBayerInterpretationSupportedByMetadata"));
    }

    @Test public void wrongTimestampMissingContextOrDifferentResultContextCannotFullyBind() throws Exception {
        Fixture f = new Fixture();
        JSONObject j = f.bind(frame(WIDTH, HEIGHT, false, TIMESTAMP + 1));
        assertEquals("UNBOUND_IMAGE_OR_METADATA", j.getString("status"));
        assertFalse(j.getBoolean("streamIdentityComplete"));
        CaptureRequest other = mock(CaptureRequest.class); when(f.result.getRequest()).thenReturn(other);
        j = f.bind(frame(WIDTH, HEIGHT, false, TIMESTAMP));
        assertTrue(j.isNull("resultAndSubmittedRequestShareFrozenContext"));
        assertFalse(j.getBoolean("streamIdentityComplete"));
        var otherContext = new M10RRawBinding4A.CameraContext("0", "0", "0", "0", false, f.inventory);
        when(other.getTag()).thenReturn(otherContext);
        j = f.bind(frame(WIDTH, HEIGHT, false, TIMESTAMP));
        assertFalse(j.getBoolean("resultAndSubmittedRequestShareFrozenContext"));
        assertFalse(j.getBoolean("streamIdentityComplete"));
        JSONObject parent = new JSONObject();
        M10RRawBinding4A.append(parent, frame(WIDTH, HEIGHT, false, TIMESTAMP), f.c, f.result, f.request, null, 36);
        assertEquals("request_bound_inventory_unavailable", parent.getJSONObject("rawCapabilities4A").getString("status"));
        assertFalse(parent.getJSONObject("rawBinding4A").getBoolean("sourceIdentityProvenByOutputAndMetadata"));
    }

    @Test public void captureSidecarIncludesInactiveCamerasAndTheirMaximumRawSizes() throws Exception {
        CameraCharacteristics active = camera(false), inactive = camera(false);
        StreamConfigurationMap max = mock(StreamConfigurationMap.class);
        when(max.isOutputSupportedFor(ImageFormat.RAW_SENSOR)).thenReturn(true);
        Size highOutput = size(8192, 6144);
        when(max.getOutputSizes(ImageFormat.RAW_SENSOR)).thenReturn(new Size[]{highOutput});
        when(inactive.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP_MAXIMUM_RESOLUTION)).thenReturn(max);
        Map<String, CameraCharacteristics> sources = new HashMap<>(); sources.put("0", active); sources.put("3", inactive);
        var inventory = snapshot(sources, 36);
        var context = new M10RRawBinding4A.CameraContext("0", "0", "0", "0", false, inventory);
        CaptureRequest request = mock(CaptureRequest.class); when(request.getTag()).thenReturn(context);
        JSONObject parent = new JSONObject();
        M10RRawBinding4A.append(parent, frame(WIDTH, HEIGHT, false, TIMESTAMP), active,
                result("0", TIMESTAMP, 0, request), request, context, 36);
        JSONObject source = parent.getJSONObject("rawCapabilities4A").getJSONObject("sources").getJSONObject("3");
        JSONArray formats = source.getJSONObject("streams").getJSONObject("maximumResolution").getJSONArray("formats");
        boolean found = false;
        for (int i = 0; i < formats.length(); i++) {
            JSONObject format = formats.getJSONObject(i);
            if (format.getInt("format") != ImageFormat.RAW_SENSOR) continue;
            JSONObject size = format.getJSONObject("regularOutputSizes").getJSONArray("sizes").getJSONObject(0);
            assertEquals(8192, size.getInt("width")); assertEquals(6144, size.getInt("height")); found = true;
        }
        assertTrue(found);
        parent.getJSONObject("rawCapabilities4A").getJSONObject("sources").remove("3");
        assertEquals("available", inventory.sourceJson("3").getString("status"));
    }

    @Test public void mismatchedRendererCameraNeverSuppliesStaticFallbackForPhysicalSource() throws Exception {
        CameraCharacteristics logical = camera(true), physical = camera(false), wrong = camera(false);
        when(logical.getPhysicalCameraIds()).thenReturn(Collections.singleton("2"));
        when(wrong.get(CameraCharacteristics.SENSOR_INFO_WHITE_LEVEL)).thenReturn(16383);
        Map<String, CameraCharacteristics> cameras = new HashMap<>(); cameras.put("0", logical); cameras.put("2", physical); cameras.put("9", wrong);
        var context = new M10RRawBinding4A.CameraContext("0", "2", "2", "9", true, snapshot(cameras, 36));
        CaptureRequest request = mock(CaptureRequest.class); when(request.getTag()).thenReturn(context);
        TotalCaptureResult top = result("0", TIMESTAMP, 0, request), source = result("2", TIMESTAMP, 0, request);
        when(source.get(CaptureResult.SENSOR_DYNAMIC_WHITE_LEVEL)).thenReturn(null);
        when(top.getPhysicalCameraTotalResults()).thenReturn(Collections.singletonMap("2", source));
        JSONObject parent = new JSONObject();
        M10RRawBinding4A.append(parent, frame(WIDTH, HEIGHT, false, TIMESTAMP), wrong, top, request, context, 36);
        JSONObject j = parent.getJSONObject("rawBinding4A");
        assertFalse(j.getBoolean("sourceMatchesRendererCharacteristicsId"));
        assertFalse(j.getBoolean("streamIdentityComplete"));
        assertEquals(1023, j.getJSONObject("levelsForSourceResult").getInt("effectiveWhiteLevel"));
        assertEquals(16383, j.getJSONObject("levelsForRendererInput").getInt("staticWhiteLevel"));
    }
}
