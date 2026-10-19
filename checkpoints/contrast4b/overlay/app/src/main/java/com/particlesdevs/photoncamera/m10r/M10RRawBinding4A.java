package com.particlesdevs.photoncamera.m10r;

import android.graphics.ImageFormat;
import android.graphics.Rect;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.CaptureResult;
import android.hardware.camera2.TotalCaptureResult;
import android.hardware.camera2.params.BlackLevelPattern;
import android.hardware.camera2.params.ColorSpaceTransform;
import android.media.Image;
import android.os.Build;
import android.util.Rational;
import android.util.Size;
import android.util.SizeF;

import com.particlesdevs.photoncamera.processing.ImageFrame;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Map;
import java.util.TreeMap;
import java.util.TreeSet;

/**
 * Per-photograph RAW provenance. All paths are observational: no request, pixel,
 * renderer authority, white balance, or calibration is changed by this class.
 * Delivered sensor mode is read from CaptureResult and is never inferred from
 * dimensions, a request, a QuadBayer setting, or a vendor remosaic switch.
 */
public final class M10RRawBinding4A {
    public static final String REVISION = "M10R_RAW_BINDING4A";
    private static final String PIXEL_MODE = "android.sensor.pixelMode";
    private static final String CAPABILITIES = "android.request.availableCapabilities";
    private static final String CFA = "android.sensor.info.colorFilterArrangement";
    private static final String BINNING = "android.sensor.info.binningFactor";
    private static final String STATIC_BLACK = "android.sensor.blackLevelPattern";
    private static final String STATIC_WHITE = "android.sensor.info.whiteLevel";
    private static final String[] CALIBRATION_KEYS = {
            "android.sensor.referenceIlluminant1", "android.sensor.referenceIlluminant2",
            "android.sensor.colorTransform1", "android.sensor.colorTransform2",
            "android.sensor.calibrationTransform1", "android.sensor.calibrationTransform2",
            "android.sensor.forwardMatrix1", "android.sensor.forwardMatrix2"};
    private static final String[] GEOMETRY_KEYS = {
            "android.sensor.info.pixelArraySize", "android.sensor.info.activeArraySize",
            "android.sensor.info.preCorrectionActiveArraySize",
            "android.sensor.info.pixelArraySizeMaximumResolution",
            "android.sensor.info.activeArraySizeMaximumResolution",
            "android.sensor.info.preCorrectionActiveArraySizeMaximumResolution"};
    private static final String[] VENDOR_REMOSAIC_KEYS = {"xiaomi.remosaic.enabled",
            "xiaomi.quadcfa.enabled", "com.mediatek.control.capture.remosaicenable"};

    private M10RRawBinding4A() {}

    /**
     * Immutable metadata copied while Image is alive. This retains no Image,
     * Plane, ByteBuffer, Rect, CameraCharacteristics, or mutable JSON object.
     */
    public static final class ImageEvidence {
        private final String json;
        private ImageEvidence(JSONObject value) { json = canonical(value); }
        public JSONObject toJson() { return parse(json); }

        /** Call before Allocator changes any source-buffer position. No pixels are read. */
        public static ImageEvidence captureOriginal(Image image) {
            JSONObject root = state("available");
            try {
                if (image == null) return new ImageEvidence(state("image_unavailable"));
                put(root, "format", read(image::getFormat));
                put(root, "width", read(image::getWidth));
                put(root, "height", read(image::getHeight));
                put(root, "timestampNs", read(image::getTimestamp));
                put(root, "imageCropRect", read(image::getCropRect));
                put(root, "imageCropCoordinateSystem", "original_Image_logical_pixels");
                put(root, "bufferMetadataCapturedBeforeAppCopy", true);
                put(root, "pixelsReadByThisDiagnostic", 0);
                JSONArray planes = new JSONArray();
                Image.Plane[] sourcePlanes = image.getPlanes();
                put(root, "planeCount", sourcePlanes == null ? null : sourcePlanes.length);
                if (sourcePlanes != null) for (int i = 0; i < sourcePlanes.length; i++) {
                    Image.Plane plane = sourcePlanes[i];
                    JSONObject p = state(plane == null ? "plane_unavailable" : "available");
                    put(p, "index", i);
                    if (plane != null) {
                        put(p, "rowStrideBytes", read(plane::getRowStride));
                        put(p, "pixelStrideBytes", read(plane::getPixelStride));
                        try {
                            ByteBuffer buffer = plane.getBuffer();
                            put(p, "buffer", bufferInfo(buffer));
                        } catch (Exception | LinkageError failure) {
                            put(p, "buffer", error(failure));
                        }
                    }
                    planes.put(p);
                }
                put(root, "planes", planes);
            } catch (Exception | LinkageError failure) {
                put(root, "status", "partial_image_evidence");
                put(root, "failure", error(failure));
            }
            return new ImageEvidence(root);
        }

        /** Logical image extent used by the copy; retained row padding is described separately. */
        public ImageEvidence withConversion(ImageFrame frame, boolean appBinning,
                String conversion, Rect appCropInSource) {
            JSONObject root = toJson();
            try {
                JSONObject transform = state(frame == null ? "frame_unavailable" : "available");
                put(transform, "operation", conversion);
                put(transform, "appBayerBinningApplied", appBinning);
                put(transform, "appBinningDimensionDivisor", appBinning ? 2 : 1);
                put(transform, "appBinningDoesNotIdentifySensorMode", true);
                put(transform, "cropInOriginalImagePixels", encode(appCropInSource));
                put(transform, "logicalCropSuppliedByIngest", appCropInSource != null);
                put(transform, "cropDescribesLogicalPixels", true);
                put(transform, "copiedRowStorageMayIncludePadding", true);
                put(transform, "preBinningStorageWidthPixels", frame == null ? null
                        : (long) frame.width * (appBinning ? 2 : 1));
                put(transform, "preBinningStorageHeightPixels", frame == null ? null
                        : (long) frame.height * (appBinning ? 2 : 1));
                put(transform, "workingFrameAtIngest", workingFrame(frame));
                put(root, "appConversion", transform);
            } catch (Exception | LinkageError failure) {
                put(root, "appConversion", error(failure));
            }
            return new ImageEvidence(root);
        }
    }

    /** Frozen with the submitted request, never reconstructed from a later selected lens. */
    public static final class CameraContext {
        public final String openedCameraId, selectedPhysicalCameraId, outputPhysicalCameraId;
        public final String characteristicsCameraId;
        public final boolean outputPhysicallyPinned;
        public final M10RRawCapabilities4A.Snapshot inventory;
        private final String requestBuilderEvidence;

        public CameraContext(String openedCameraId, String selectedPhysicalCameraId,
                String outputPhysicalCameraId, String characteristicsCameraId,
                boolean outputPhysicallyPinned, M10RRawCapabilities4A.Snapshot inventory) {
            this(openedCameraId, selectedPhysicalCameraId, outputPhysicalCameraId,
                    characteristicsCameraId, outputPhysicallyPinned, inventory,
                    canonical(state("builder_snapshot_unavailable")));
        }

        private CameraContext(String openedCameraId, String selectedPhysicalCameraId,
                String outputPhysicalCameraId, String characteristicsCameraId,
                boolean outputPhysicallyPinned, M10RRawCapabilities4A.Snapshot inventory,
                String requestBuilderEvidence) {
            this.openedCameraId = clean(openedCameraId);
            this.selectedPhysicalCameraId = clean(selectedPhysicalCameraId);
            this.outputPhysicalCameraId = clean(outputPhysicalCameraId);
            this.characteristicsCameraId = clean(characteristicsCameraId);
            this.outputPhysicallyPinned = outputPhysicallyPinned;
            this.inventory = inventory;
            this.requestBuilderEvidence = requestBuilderEvidence;
        }

        public CameraContext withRequestBuilder(CaptureRequest.Builder builder) {
            return withRequestBuilder(builder, Build.VERSION.SDK_INT);
        }

        // Explicit SDK permits host tests of public API guards without modifying Build globals.
        CameraContext withRequestBuilder(CaptureRequest.Builder builder, int sdk) {
            JSONObject j = state(builder == null ? "builder_unavailable" : "available");
            String physical = outputPhysicallyPinned ? outputPhysicalCameraId : selectedPhysicalCameraId;
            put(j, "physicalCameraId", physical);
            if (builder != null) {
                put(j, "logicalPixelMode", sdk >= 31
                        ? read(() -> builder.get(CaptureRequest.SENSOR_PIXEL_MODE)) : state("api_unavailable"));
                put(j, "physicalPixelMode", sdk >= 31 && physical != null
                        ? read(() -> builder.getPhysicalCameraKey(CaptureRequest.SENSOR_PIXEL_MODE, physical))
                        : state(sdk < 31 ? "api_unavailable" : "physical_id_unavailable"));
                JSONObject vendor = new JSONObject();
                for (String keyName : VENDOR_REMOSAIC_KEYS) {
                    JSONObject values = new JSONObject();
                    put(values, "logical", readVendor(builder, keyName, null, openedCameraId, false, sdk));
                    put(values, "physical", readVendor(builder, keyName, physical, openedCameraId, true, sdk));
                    put(vendor, keyName, values);
                }
                put(j, "vendorRemosaicRequests", vendor);
                put(j, "vendorRequestsDoNotProveDeliveredLayout", true);
                put(j, "requestValuesChanged", false);
            }
            return new CameraContext(openedCameraId, selectedPhysicalCameraId, outputPhysicalCameraId,
                    characteristicsCameraId, outputPhysicallyPinned, inventory, canonical(j));
        }

        private JSONObject readVendor(CaptureRequest.Builder builder, String name, String physical,
                String authority, boolean physicalKey, int sdk) {
            if (physicalKey && (sdk < 28 || physical == null)) return state("physical_key_unavailable");
            JSONObject source = inventory == null ? null : inventory.sourceJson(authority);
            JSONObject support = source == null ? null : source.optJSONObject(
                    physicalKey ? "physicalRequestKeySupport" : "requestKeySupport");
            JSONObject keys = support == null ? null : support.optJSONObject("keys");
            if (support == null || !"available".equals(support.optString("status"))
                    || keys == null || !Boolean.TRUE.equals(keys.opt(name)))
                return state("not_advertised_or_support_unavailable");
            if (name.equals("com.mediatek.control.capture.remosaicenable")) {
                CaptureRequest.Key<int[]> key = new CaptureRequest.Key<>(name, int[].class);
                return read(() -> physicalKey ? builder.getPhysicalCameraKey(key, physical) : builder.get(key));
            }
            CaptureRequest.Key<Byte> key = new CaptureRequest.Key<>(name, Byte.class);
            return read(() -> physicalKey ? builder.getPhysicalCameraKey(key, physical) : builder.get(key));
        }

        public JSONObject toJson() {
            JSONObject j = state("request_bound");
            put(j, "openedCameraId", openedCameraId);
            put(j, "selectedPhysicalCameraId", selectedPhysicalCameraId);
            put(j, "configuredOutputPhysicalCameraId", outputPhysicalCameraId);
            put(j, "configuredOutputPhysicallyPinned", outputPhysicallyPinned);
            put(j, "rendererCharacteristicsCameraId", characteristicsCameraId);
            put(j, "inventorySourceDigestSha256", inventory == null ? null : inventory.sourceDigest(characteristicsCameraId));
            put(j, "requestBuilder", parse(requestBuilderEvidence));
            return j;
        }
    }

    public static CameraContext fromTag(CaptureRequest request) {
        try {
            Object tag = request == null ? null : request.getTag();
            if (tag instanceof CameraContext) return (CameraContext) tag;
            return tag instanceof M10RExposureReport1C ? ((M10RExposureReport1C) tag).rawContext4A : null;
        } catch (RuntimeException | LinkageError ignored) { return null; }
    }

    public static void append(JSONObject parent, ImageFrame frame, CameraCharacteristics characteristics,
            CaptureResult result, CaptureRequest request, CameraContext context) {
        append(parent, frame, characteristics, result, request, context, Build.VERSION.SDK_INT);
    }

    static void append(JSONObject parent, ImageFrame frame, CameraCharacteristics characteristics,
            CaptureResult result, CaptureRequest request, CameraContext context, int sdk) {
        long started = System.nanoTime();
        JSONObject j = state("partial_evidence");
        try {
            if (parent == null) return;
            put(parent, "rawBinding4A", j);
            put(parent, "rawCapabilities4A", context == null || context.inventory == null
                    ? state("request_bound_inventory_unavailable") : context.inventory.toJson());
            put(j, "revision", REVISION);
            put(j, "diagnosticOnly", true);
            put(j, "controlsWhiteBalance", false);
            put(j, "modifiesPixelsOrRequests", false);
            put(j, "calibrationEstablished", false);
            put(j, "sourceMetadataReplacesRendererMetadata", false);
            put(j, "image", frame == null || frame.rawBinding4A == null
                    ? state("original_image_evidence_unavailable") : frame.rawBinding4A.toJson());
            put(j, "workingFrameAtRender", workingFrame(frame));
            put(j, "requestContext", context == null ? state("request_context_unavailable") : context.toJson());
            JSONObject image = j.optJSONObject("image");
            Long imageTs = numberLong(fieldValue(image, "timestampNs"));
            JSONObject top = resultMetadata(result, sdk);
            put(j, "rendererResult", top);
            TreeMap<String, CaptureResult> physical = physicalResults(result, sdk, j);
            String targetId = context == null ? null : context.outputPhysicallyPinned
                    ? context.outputPhysicalCameraId : context.selectedPhysicalCameraId;
            CaptureResult sourceResult = targetId == null ? null : physical.get(targetId);
            String sourceAuthority = "renderer_result_source_unproven";
            String sourceId = null;
            boolean sourceProven = false;
            JSONObject rendererInventorySource = context == null || context.inventory == null
                    ? state("inventory_unavailable") : context.inventory.sourceJson(context.characteristicsCameraId);
            JSONObject openedSource = context == null || context.inventory == null
                    ? state("inventory_unavailable") : context.inventory.sourceJson(context.openedCameraId);
            String activePhysical = stringValue(fieldValue(top, "activePhysicalCameraId"));
            if (sourceResult != null) {
                sourceId = targetId;
                sourceAuthority = "matching_physical_capture_result";
                sourceProven = context != null && context.outputPhysicallyPinned
                        && same(targetId, context.outputPhysicalCameraId);
            } else {
                sourceResult = result;
                if (context != null && same(context.openedCameraId, targetId) && verifiedNonLogical(openedSource)) {
                    sourceId = context.openedCameraId;
                    sourceAuthority = "verified_direct_nonlogical_device_result";
                    sourceProven = true;
                } else if (targetId != null && same(activePhysical, targetId)) {
                    sourceId = targetId;
                    sourceAuthority = "logical_active_physical_id_match_without_physical_result";
                }
            }
            JSONObject source = resultMetadata(sourceResult, sdk);
            String reportedSourceCameraId = stringValue(fieldValue(source, "cameraId"));
            Boolean sourceCameraIdConsistent = reportedSourceCameraId == null || sourceId == null ? null
                    : sourceId.equals(reportedSourceCameraId);
            // A logical result intentionally retains its logical camera ID. Only
            // direct/physical result authorities require an exact ID agreement.
            if (sourceProven && Boolean.FALSE.equals(sourceCameraIdConsistent)) sourceProven = false;
            put(j, "sourceResult", source);
            put(j, "sourceResultAuthority", sourceAuthority);
            put(j, "sourceCameraId", sourceId);
            put(j, "sourceResultCameraIdConsistent", sourceCameraIdConsistent);
            put(j, "physicalResultPresentForRequestedSource", targetId != null && physical.containsKey(targetId));
            put(j, "sourceIdentityProvenByOutputAndMetadata", sourceProven);
            boolean characteristicsMatch = context != null && same(sourceId, context.characteristicsCameraId);
            put(j, "sourceMatchesRendererCharacteristicsId", characteristicsMatch);
            JSONObject inventorySource = context == null || context.inventory == null || sourceId == null
                    ? state("source_inventory_unavailable") : context.inventory.sourceJson(sourceId);
            put(j, "inventorySource", inventorySource);
            put(j, "rendererInventorySource", rendererInventorySource);
            JSONObject originalMetadata = inventorySource.optJSONObject("characteristics");
            JSONObject rendererOriginalMetadata = rendererInventorySource.optJSONObject("characteristics");
            JSONObject rendererMetadata = staticMetadata(characteristics, sdk);
            put(j, "rendererCharacteristicsAtRender", rendererMetadata);
            put(j, "rendererMetadataMatchesImmutableInventory", rendererOriginalMetadata == null ? null
                    : canonical(comparableMetadata(rendererMetadata)).equals(canonical(comparableMetadata(rendererOriginalMetadata))));
            put(j, "metadataComparisonDoesNotEstablishCalibration", true);
            JSONObject calibration = subset(originalMetadata, CALIBRATION_KEYS);
            put(j, "calibrationMetadata", calibration);
            String calibrationDigest = originalMetadata == null ? null : sha256(canonical(calibration));
            put(j, "calibrationMetadataFingerprintSha256", calibrationDigest);
            put(j, "calibrationFingerprintScope", "six_static_matrices_exact_row_major_rationals_and_reference_illuminants");
            JSONObject physicalIdentity = physicalIdentity(sourceId, originalMetadata, calibrationDigest);
            String physicalDigest = sourceId == null || originalMetadata == null ? null : sha256(canonical(physicalIdentity));
            put(j, "physicalSensorMetadataIdentity", physicalIdentity);
            put(j, "physicalSensorMetadataFingerprintSha256", physicalDigest);
            put(j, "levelsForSourceResult", levels(source, originalMetadata));
            put(j, "levelsForRendererInput", levels(top, rendererMetadata));

            JSONObject requestEvidence = requestMetadata(request, sdk);
            put(j, "submittedRequest", requestEvidence);
            JSONObject builderEvidence = context == null ? null : parse(context.requestBuilderEvidence);
            JSONObject requestedMode = builderEvidence == null ? null : builderEvidence.optJSONObject("physicalPixelMode");
            String requestedModeSource = "physical_builder_snapshot";
            if (requestedMode == null || valueOf(requestedMode) == null) {
                requestedMode = requestEvidence.optJSONObject("pixelMode");
                requestedModeSource = "submitted_logical_request_physical_override_not_proven";
            }
            Object deliveredMode = fieldValue(source, "pixelMode");
            JSONObject modes = new JSONObject();
            put(modes, "requested", requestedMode == null ? state("absent") : requestedMode);
            put(modes, "requestedSource", requestedModeSource);
            put(modes, "delivered", source.optJSONObject("pixelMode"));
            put(modes, "deliveredSource", sourceAuthority);
            put(modes, "requestedDeliveredValuesAgree", deliveredMode == null || valueOf(requestedMode) == null
                    ? null : deliveredMode.equals(valueOf(requestedMode)));
            put(modes, "missingDeliveredModeRemainsUnknown", true);
            put(j, "sensorPixelMode", modes);

            boolean imageFrameMatches = imageTs != null && frame != null && imageTs > 0 && imageTs == frame.timestamp;
            Long topTs = numberLong(fieldValue(top, "sensorTimestampNs"));
            Long sourceTs = numberLong(fieldValue(source, "sensorTimestampNs"));
            boolean topMatches = imageFrameMatches && topTs != null && imageTs.equals(topTs);
            boolean sourceMatches = imageFrameMatches && sourceTs != null && imageTs.equals(sourceTs);
            CaptureRequest resultRequest = result == null ? null : safeResultRequest(result);
            CameraContext resultContext = fromTag(resultRequest);
            Boolean requestContextMatches = context == null || resultContext == null ? null : context == resultContext;
            put(j, "originalImageTimestampMatchesWorkingFrame", imageFrameMatches);
            put(j, "imageTimestampMatchesRendererResult", topMatches);
            put(j, "imageTimestampMatchesSourceResult", sourceMatches);
            put(j, "resultAndSubmittedRequestShareFrozenContext", requestContextMatches);
            put(j, "resultAndSubmittedRequestObjectIdentityRequired", false);
            Boolean frameNumbersAgree = sourceResult == null || result == null ? null
                    : sourceResult.getFrameNumber() == result.getFrameNumber();
            put(j, "physicalAndRendererFrameNumbersAgree", frameNumbersAgree);
            boolean fullyBound = sourceProven && characteristicsMatch && sourceMatches && topMatches
                    && Boolean.TRUE.equals(requestContextMatches) && Boolean.TRUE.equals(frameNumbersAgree);
            put(j, "status", fullyBound ? "IMAGE_AND_SOURCE_RESULT_BOUND" : topMatches
                    ? "IMAGE_AND_RENDERER_RESULT_BOUND_SOURCE_UNPROVEN" : "UNBOUND_IMAGE_OR_METADATA");

            JSONObject layout = layout(originalMetadata, source, image);
            put(j, "rawInterpretation", layout);
            JSONObject geometry = geometry(originalMetadata, source, requestEvidence, image);
            put(j, "geometry", geometry);
            JSONObject identity = new JSONObject();
            put(identity, "schema", "RAW_DELIVERY_IDENTITY4A_V1");
            put(identity, "cameraId", sourceId);
            put(identity, "characteristicsCameraId", context == null ? null : context.characteristicsCameraId);
            put(identity, "physicalSensorMetadataFingerprintSha256", physicalDigest);
            put(identity, "calibrationMetadataFingerprintSha256", calibrationDigest);
            put(identity, "staticCfa", fieldValue(originalMetadata, CFA));
            put(identity, "staticBlackLevels", fieldValue(originalMetadata, STATIC_BLACK));
            put(identity, "staticWhiteLevel", fieldValue(originalMetadata, STATIC_WHITE));
            put(identity, "sensorBinningFactor", fieldValue(originalMetadata, BINNING));
            put(identity, "deliveredPixelMode", deliveredMode);
            put(identity, "deliveredRawBinningFactorUsed", fieldValue(source, "rawBinningFactorUsed"));
            put(identity, "originalFormat", fieldValue(image, "format"));
            put(identity, "originalWidth", fieldValue(image, "width"));
            put(identity, "originalHeight", fieldValue(image, "height"));
            put(identity, "sensorGeometry", subset(originalMetadata, GEOMETRY_KEYS));
            put(j, "deliveredStreamIdentity", identity);
            put(j, "deliveredStreamIdentitySha256", sha256(canonical(identity)));
            put(j, "streamIdentityComplete", fullyBound && originalMetadata != null && knownMode(deliveredMode)
                    && fieldValue(image, "format") != null && fieldValue(image, "width") != null
                    && fieldValue(image, "height") != null);
            put(j, "streamIdentityExcludes", new JSONArray(new String[]{"timestamp", "frameNumber", "ISO",
                    "exposureTime", "dynamicBlackLevel", "dynamicWhiteLevel", "appCrop", "appBinning"}));
            put(j, "identityAllowsAutomaticCalibrationPromotion", false);
            put(j, "streamAdvertisementMatch", streamMatch(inventorySource, image, deliveredMode));
            put(j, "workingFrameCompatibility", workingCompatibility(frame, image, layout));
        } catch (Exception | LinkageError | OutOfMemoryError failure) {
            try { put(j, "status", "DIAGNOSTIC_UNAVAILABLE"); put(j, "failure", error(failure)); }
            catch (RuntimeException | OutOfMemoryError ignored) { /* Photograph retains authority. */ }
        } finally {
            try { put(j, "measurementAndObjectBuildNs", System.nanoTime() - started);
                put(j, "timingExcludesFinalSidecarSerialization", true); }
            catch (RuntimeException | OutOfMemoryError ignored) { /* Diagnostic only. */ }
        }
    }

    private static TreeMap<String, CaptureResult> physicalResults(CaptureResult result, int sdk, JSONObject j) {
        TreeMap<String, CaptureResult> out = new TreeMap<>();
        JSONObject evidence = state(result instanceof TotalCaptureResult ? "available" : "not_total_capture_result");
        if (result instanceof TotalCaptureResult) {
            try {
                Map<String, ? extends CaptureResult> map = sdk >= 31
                        ? ((TotalCaptureResult) result).getPhysicalCameraTotalResults()
                        : sdk >= 28 ? ((TotalCaptureResult) result).getPhysicalCameraResults() : null;
                if (sdk < 28) put(evidence, "status", "api_unavailable");
                else if (map == null) put(evidence, "status", "absent");
                else for (Map.Entry<String, ? extends CaptureResult> entry : map.entrySet())
                    if (clean(entry.getKey()) != null && entry.getValue() != null) out.put(entry.getKey(), entry.getValue());
                put(evidence, "api", sdk >= 31 ? "getPhysicalCameraTotalResults" : "getPhysicalCameraResults");
            } catch (Exception | LinkageError failure) { evidence = error(failure); }
        }
        JSONArray entries = new JSONArray();
        for (Map.Entry<String, CaptureResult> entry : out.entrySet()) {
            JSONObject v = new JSONObject();
            put(v, "cameraId", entry.getKey());
            put(v, "sensorTimestampNs", read(() -> entry.getValue().get(CaptureResult.SENSOR_TIMESTAMP)));
            put(v, "frameNumber", read(() -> entry.getValue().getFrameNumber()));
            entries.put(v);
        }
        put(evidence, "entries", entries);
        put(j, "physicalCaptureResults", evidence);
        return out;
    }

    private static JSONObject resultMetadata(CaptureResult r, int sdk) {
        JSONObject j = state(r == null ? "result_unavailable" : "available");
        if (r == null) return j;
        put(j, "cameraId", sdk >= 31 ? read(r::getCameraId) : state("api_unavailable"));
        put(j, "frameNumber", read(r::getFrameNumber));
        put(j, "sensorTimestampNs", read(() -> r.get(CaptureResult.SENSOR_TIMESTAMP)));
        put(j, "pixelMode", sdk >= 31 ? read(() -> r.get(CaptureResult.SENSOR_PIXEL_MODE)) : state("api_unavailable"));
        put(j, "rawBinningFactorUsed", sdk >= 31 ? read(() -> r.get(CaptureResult.SENSOR_RAW_BINNING_FACTOR_USED)) : state("api_unavailable"));
        put(j, "activePhysicalCameraId", sdk >= 28 ? read(() -> r.get(CaptureResult.LOGICAL_MULTI_CAMERA_ACTIVE_PHYSICAL_ID)) : state("api_unavailable"));
        put(j, "scalerCropRegion", read(() -> r.get(CaptureResult.SCALER_CROP_REGION)));
        put(j, "rawCropRegion", sdk >= 34 ? read(() -> r.get(CaptureResult.SCALER_RAW_CROP_REGION)) : state("api_unavailable"));
        put(j, "distortionCorrectionMode", sdk >= 28 ? read(() -> r.get(CaptureResult.DISTORTION_CORRECTION_MODE)) : state("api_unavailable"));
        put(j, "dynamicBlackLevels", read(() -> r.get(CaptureResult.SENSOR_DYNAMIC_BLACK_LEVEL)));
        put(j, "dynamicWhiteLevel", read(() -> r.get(CaptureResult.SENSOR_DYNAMIC_WHITE_LEVEL)));
        put(j, "exposureTimeNs", read(() -> r.get(CaptureResult.SENSOR_EXPOSURE_TIME)));
        put(j, "sensitivityIso", read(() -> r.get(CaptureResult.SENSOR_SENSITIVITY)));
        put(j, "frameDurationNs", read(() -> r.get(CaptureResult.SENSOR_FRAME_DURATION)));
        put(j, "aperture", read(() -> r.get(CaptureResult.LENS_APERTURE)));
        put(j, "focalLengthMm", read(() -> r.get(CaptureResult.LENS_FOCAL_LENGTH)));
        put(j, "focusDistanceDiopters", read(() -> r.get(CaptureResult.LENS_FOCUS_DISTANCE)));
        put(j, "postRawSensitivityBoost", read(() -> r.get(CaptureResult.CONTROL_POST_RAW_SENSITIVITY_BOOST)));
        put(j, "neutralColorPointExact", read(() -> r.get(CaptureResult.SENSOR_NEUTRAL_COLOR_POINT)));
        return j;
    }

    private static JSONObject requestMetadata(CaptureRequest r, int sdk) {
        JSONObject j = state(r == null ? "request_unavailable" : "available");
        if (r == null) return j;
        put(j, "pixelMode", sdk >= 31 ? read(() -> r.get(CaptureRequest.SENSOR_PIXEL_MODE)) : state("api_unavailable"));
        put(j, "scalerCropRegion", read(() -> r.get(CaptureRequest.SCALER_CROP_REGION)));
        put(j, "distortionCorrectionMode", sdk >= 28 ? read(() -> r.get(CaptureRequest.DISTORTION_CORRECTION_MODE)) : state("api_unavailable"));
        put(j, "exposureTimeNs", read(() -> r.get(CaptureRequest.SENSOR_EXPOSURE_TIME)));
        put(j, "sensitivityIso", read(() -> r.get(CaptureRequest.SENSOR_SENSITIVITY)));
        return j;
    }

    private static JSONObject staticMetadata(CameraCharacteristics c, int sdk) {
        JSONObject j = new JSONObject();
        characteristic(j, c, CFA, CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT);
        characteristic(j, c, STATIC_BLACK, CameraCharacteristics.SENSOR_BLACK_LEVEL_PATTERN);
        characteristic(j, c, STATIC_WHITE, CameraCharacteristics.SENSOR_INFO_WHITE_LEVEL);
        characteristic(j, c, CALIBRATION_KEYS[0], CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT1);
        characteristic(j, c, CALIBRATION_KEYS[1], CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT2);
        characteristic(j, c, CALIBRATION_KEYS[2], CameraCharacteristics.SENSOR_COLOR_TRANSFORM1);
        characteristic(j, c, CALIBRATION_KEYS[3], CameraCharacteristics.SENSOR_COLOR_TRANSFORM2);
        characteristic(j, c, CALIBRATION_KEYS[4], CameraCharacteristics.SENSOR_CALIBRATION_TRANSFORM1);
        characteristic(j, c, CALIBRATION_KEYS[5], CameraCharacteristics.SENSOR_CALIBRATION_TRANSFORM2);
        characteristic(j, c, CALIBRATION_KEYS[6], CameraCharacteristics.SENSOR_FORWARD_MATRIX1);
        characteristic(j, c, CALIBRATION_KEYS[7], CameraCharacteristics.SENSOR_FORWARD_MATRIX2);
        characteristic(j, c, GEOMETRY_KEYS[0], CameraCharacteristics.SENSOR_INFO_PIXEL_ARRAY_SIZE);
        characteristic(j, c, GEOMETRY_KEYS[1], CameraCharacteristics.SENSOR_INFO_ACTIVE_ARRAY_SIZE);
        characteristic(j, c, GEOMETRY_KEYS[2], CameraCharacteristics.SENSOR_INFO_PRE_CORRECTION_ACTIVE_ARRAY_SIZE);
        if (sdk >= 31) {
            characteristic(j, c, GEOMETRY_KEYS[3], CameraCharacteristics.SENSOR_INFO_PIXEL_ARRAY_SIZE_MAXIMUM_RESOLUTION);
            characteristic(j, c, GEOMETRY_KEYS[4], CameraCharacteristics.SENSOR_INFO_ACTIVE_ARRAY_SIZE_MAXIMUM_RESOLUTION);
            characteristic(j, c, GEOMETRY_KEYS[5], CameraCharacteristics.SENSOR_INFO_PRE_CORRECTION_ACTIVE_ARRAY_SIZE_MAXIMUM_RESOLUTION);
            characteristic(j, c, BINNING, CameraCharacteristics.SENSOR_INFO_BINNING_FACTOR);
        } else {
            for (int i = 3; i < GEOMETRY_KEYS.length; i++) put(j, GEOMETRY_KEYS[i], state("api_unavailable"));
            put(j, BINNING, state("api_unavailable"));
        }
        return j;
    }

    private static JSONObject levels(JSONObject result, JSONObject characteristics) {
        JSONObject j = new JSONObject();
        put(j, "selectionPolicy", "diagnostic_valid_metadata_choice_not_renderer_fallback_replay");
        put(j, "controlsRendererLevels", false);
        Object dynamicBlack = fieldValue(result, "dynamicBlackLevels");
        Object staticBlack = fieldValue(characteristics, STATIC_BLACK);
        Object dynamicWhite = fieldValue(result, "dynamicWhiteLevel");
        Object staticWhite = fieldValue(characteristics, STATIC_WHITE);
        boolean useDynamicBlack = validBlack(dynamicBlack), useStaticBlack = validBlack(staticBlack);
        boolean useDynamicWhite = positiveInt(dynamicWhite), useStaticWhite = positiveInt(staticWhite);
        put(j, "staticBlackLevels", staticBlack);
        put(j, "staticWhiteLevel", staticWhite);
        put(j, "effectiveBlackLevels", useDynamicBlack ? dynamicBlack : useStaticBlack ? staticBlack : null);
        put(j, "blackSource", useDynamicBlack ? "capture_result" : useStaticBlack ? "characteristics" : "unavailable");
        put(j, "effectiveWhiteLevel", useDynamicWhite ? dynamicWhite : useStaticWhite ? staticWhite : null);
        put(j, "whiteSource", useDynamicWhite ? "capture_result" : useStaticWhite ? "characteristics" : "unavailable");
        put(j, "phaseOrder", "CFA_positions_x0y0_x1y0_x0y1_x1y1");
        put(j, "units", "delivered_RAW_code_units_not_inferred_ADC_bits");
        put(j, "sourceScaleAssigned", false);
        return j;
    }

    private static JSONObject layout(JSONObject c, JSONObject result, JSONObject image) {
        JSONObject j = new JSONObject();
        Object cfa = fieldValue(c, CFA), factor = fieldValue(c, BINNING);
        Object used = fieldValue(result, "rawBinningFactorUsed"), mode = fieldValue(result, "pixelMode");
        put(j, "cfa", cfa);
        put(j, "cfaName", cfaName(cfa));
        put(j, "sensorBinningFactor", factor);
        put(j, "rawBinningFactorUsed", used);
        String status;
        boolean regular = false;
        if (!(cfa instanceof Number) || ((Number) cfa).intValue() < 0 || ((Number) cfa).intValue() > 3) {
            status = "unsupported_or_missing_CFA";
        } else if (Boolean.FALSE.equals(used)) {
            status = "regular_bayer_reported_by_result"; regular = true;
        } else if (Boolean.TRUE.equals(used)) {
            if (unitFactor(factor)) { status = "regular_bayer_unit_binning_factor"; regular = true; }
            else status = groupFactor(factor) ? "unsupported_grouped_color_filter_layout" : "binning_factor_missing_or_invalid";
        } else if (Boolean.TRUE.equals(hasCapability(c, CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES_ULTRA_HIGH_RESOLUTION_SENSOR))
                && Boolean.TRUE.equals(hasCapability(c, CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES_REMOSAIC_REPROCESSING))) {
            status = "layout_unproven_remosaic_result_flag_missing";
        } else if (groupFactor(factor)) {
            if (mode instanceof Number && ((Number) mode).intValue() == CaptureResult.SENSOR_PIXEL_MODE_DEFAULT) {
                status = "regular_bayer_default_mode_metadata"; regular = true;
            } else if (mode instanceof Number && ((Number) mode).intValue() == CaptureResult.SENSOR_PIXEL_MODE_MAXIMUM_RESOLUTION
                    && Boolean.FALSE.equals(hasCapability(c, CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES_ULTRA_HIGH_RESOLUTION_SENSOR))) {
                status = "unsupported_grouped_maximum_mode_without_UHR_capability";
            } else status = "layout_unproven_binning_factor_flag_or_delivered_mode_missing";
        } else if (factor != null && !unitFactor(factor)) {
            status = "binning_factor_invalid";
        } else {
            Boolean uhr = hasCapability(c, CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES_ULTRA_HIGH_RESOLUTION_SENSOR);
            Boolean remosaic = hasCapability(c, CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES_REMOSAIC_REPROCESSING);
            if (Boolean.TRUE.equals(uhr) && Boolean.TRUE.equals(remosaic)) {
                status = "layout_unproven_remosaic_result_flag_missing";
            } else if (c != null && uhr != null && remosaic != null) {
                status = "regular_bayer_Camera2_metadata_contract"; regular = true;
            } else status = "standard_CFA_present_readout_metadata_incomplete";
        }
        put(j, "layoutStatus", status);
        put(j, "standardBayerInterpretationSupportedByMetadata", regular);
        put(j, "sensorReadoutAlgorithmInferred", false);
        put(j, "reconstructionChanged", false);
        put(j, "originalImageFormat", fieldValue(image, "format"));
        return j;
    }

    private static JSONObject geometry(JSONObject c, JSONObject result, JSONObject request, JSONObject image) {
        JSONObject j = new JSONObject();
        put(j, "sensorArrays", subset(c, GEOMETRY_KEYS));
        Object mode = fieldValue(result, "pixelMode");
        String family = !knownMode(mode) ? "unknown_delivered_pixel_mode"
                : ((Number) mode).intValue() == CaptureResult.SENSOR_PIXEL_MODE_MAXIMUM_RESOLUTION ? "maximumResolution" : "default";
        put(j, "deliveredGeometryFamily", family);
        put(j, "requestedScalerCropRegion", fieldValue(request, "scalerCropRegion"));
        put(j, "deliveredScalerCropRegion", fieldValue(result, "scalerCropRegion"));
        put(j, "deliveredRawCropRegion", fieldValue(result, "rawCropRegion"));
        put(j, "deliveredDistortionCorrectionMode", fieldValue(result, "distortionCorrectionMode"));
        Object distortion = fieldValue(result, "distortionCorrectionMode");
        put(j, "scalerCropCoordinateReference", !knownMode(mode) ? "unknown_pixel_mode"
                : distortion == null ? "active_or_preCorrection_not_proven"
                : ((Number) distortion).intValue() == CaptureResult.DISTORTION_CORRECTION_MODE_OFF
                        ? family + ".preCorrectionActiveArray" : family + ".activeArray");
        put(j, "imageCropRect", fieldValue(image, "imageCropRect"));
        JSONObject conversion = image == null ? null : image.optJSONObject("appConversion");
        put(j, "appCropInOriginalImagePixels", conversion == null ? null : conversion.opt("cropInOriginalImagePixels"));
        put(j, "scalerCropIsNotAssumedToCropRawBuffer", true);
        put(j, "sensorToOriginalImageCoordinateTransformProven", false);
        put(j, "sensorCfaPhaseAtOriginalBufferOriginProven", false);
        return j;
    }

    private static JSONObject workingCompatibility(ImageFrame f, JSONObject image, JSONObject layout) {
        JSONObject j = new JSONObject();
        if (f == null) return state("frame_unavailable");
        long required = 2L * f.width * f.height;
        boolean raw16 = f.buffer != null && f.width > 0 && f.height > 0 && required <= Integer.MAX_VALUE
                && f.packedBits == 0 && !f.fp16 && f.buffer.capacity() >= required && f.buffer.limit() >= required;
        put(j, "raw16Container", raw16);
        put(j, "tightWorkingBuffer", raw16 && f.buffer.capacity() == required);
        put(j, "currentWbSamplerDimensionRange", f.width >= 208 && f.height >= 160 && f.width <= 8192 && f.height <= 8192);
        put(j, "standardBayerMetadataSupported", layout.optBoolean("standardBayerInterpretationSupportedByMetadata"));
        JSONObject conversion = image == null ? null : image.optJSONObject("appConversion");
        Object crop = conversion == null ? null : conversion.opt("cropInOriginalImagePixels");
        Integer originalWidth = numberInt(fieldValue(image, "width")), originalHeight = numberInt(fieldValue(image, "height"));
        if (crop instanceof JSONArray && ((JSONArray) crop).length() == 4 && originalWidth != null && originalHeight != null) {
            JSONArray a = (JSONArray) crop;
            put(j, "appCropWithinOriginalLogicalImage", a.optInt(0, -1) >= 0 && a.optInt(1, -1) >= 0
                    && a.optInt(2, Integer.MAX_VALUE) <= originalWidth && a.optInt(3, Integer.MAX_VALUE) <= originalHeight);
            put(j, "appCropEvenOrigin", (a.optInt(0, 1) & 1) == 0 && (a.optInt(1, 1) & 1) == 0);
            int divisor = conversion.optBoolean("appBayerBinningApplied") ? 2 : 1;
            put(j, "workingStorageWiderThanLogicalCrop", (long) f.width * divisor
                    > (long) a.optInt(2, 0) - a.optInt(0, 0));
        } else {
            put(j, "appCropWithinOriginalLogicalImage", null); put(j, "appCropEvenOrigin", null);
            put(j, "workingStorageWiderThanLogicalCrop", null);
        }
        put(j, "enforcesNewCaptureGate", false);
        put(j, "workingDimensionsDoNotReplaceDeliveredStreamDimensions", true);
        return j;
    }

    private static JSONObject streamMatch(JSONObject inventory, JSONObject image, Object mode) {
        JSONObject j = state("unavailable_or_unknown_delivered_mode");
        if (!knownMode(mode) || inventory == null || image == null) return j;
        JSONObject streams = inventory.optJSONObject("streams");
        String family = ((Number) mode).intValue() == CaptureResult.SENSOR_PIXEL_MODE_MAXIMUM_RESOLUTION ? "maximumResolution" : "default";
        JSONObject map = streams == null ? null : streams.optJSONObject(family);
        Integer format = numberInt(fieldValue(image, "format")), width = numberInt(fieldValue(image, "width")), height = numberInt(fieldValue(image, "height"));
        put(j, "map", family);
        if (map == null || !"available".equals(map.optString("status")) || format == null || width == null || height == null) return j;
        JSONArray formats = map.optJSONArray("formats");
        if (formats == null) return j;
        boolean listsComplete = true, formatSeen = false;
        for (int i = 0; i < formats.length(); i++) {
            JSONObject entry = formats.optJSONObject(i);
            if (entry == null || entry.optInt("format", -1) != format) continue;
            formatSeen = true;
            if ("format_not_advertised".equals(entry.optString("status"))) {
                put(j, "status", "delivered_format_not_advertised_in_mode_map"); return j;
            }
            for (String list : new String[]{"regularOutputSizes", "slowerHighResolutionOutputSizes"}) {
                JSONObject sizes = entry.optJSONObject(list);
                if (sizes == null || !("available".equals(sizes.optString("status"))
                        || "empty".equals(sizes.optString("status")) || "absent".equals(sizes.optString("status")))) {
                    listsComplete = false; continue;
                }
                JSONArray values = sizes.optJSONArray("sizes");
                if (values == null) continue;
                for (int k = 0; k < values.length(); k++) {
                    JSONObject size = values.optJSONObject(k);
                    if (size != null && size.optInt("width", -1) == width && size.optInt("height", -1) == height) {
                        put(j, "status", "delivered_size_advertised_for_format_and_mode");
                        put(j, "sizeList", list); put(j, "sessionCombinationValidatedByInventory", false);
                        return j;
                    }
                }
            }
        }
        put(j, "status", formatSeen && listsComplete ? "delivered_size_not_found_in_advertised_mode_lists" : "advertised_lists_incomplete");
        return j;
    }

    private static boolean verifiedNonLogical(JSONObject source) {
        JSONObject c = source == null ? null : source.optJSONObject("characteristics");
        return Boolean.FALSE.equals(hasCapability(c, CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES_LOGICAL_MULTI_CAMERA));
    }

    private static Boolean hasCapability(JSONObject c, int capability) {
        Object value = fieldValue(c, CAPABILITIES);
        if (!(value instanceof JSONArray)) return null;
        JSONArray values = (JSONArray) value;
        for (int i = 0; i < values.length(); i++) {
            if (!(values.opt(i) instanceof Number)) return null;
            if (values.optInt(i, -1) == capability) return true;
        }
        return false;
    }

    private static JSONObject comparableMetadata(JSONObject c) {
        JSONObject j = subset(c, CALIBRATION_KEYS);
        for (String key : GEOMETRY_KEYS) put(j, key, c == null ? state("absent") : c.opt(key));
        for (String key : new String[]{CFA, STATIC_BLACK, STATIC_WHITE, BINNING})
            put(j, key, c == null ? state("absent") : c.opt(key));
        return j;
    }

    private static JSONObject physicalIdentity(String sourceId, JSONObject c, String calibrationDigest) {
        JSONObject j = new JSONObject();
        put(j, "schema", "RAW_STATIC_PHYSICAL_METADATA4A_V1");
        put(j, "manufacturer", Build.MANUFACTURER);
        put(j, "model", Build.MODEL);
        put(j, "cameraId", sourceId);
        put(j, "calibrationMetadataFingerprintSha256", calibrationDigest);
        for (String key : new String[]{"android.sensor.info.physicalSize",
                "android.lens.info.availableFocalLengths", "android.lens.info.availableApertures",
                CFA, STATIC_BLACK, STATIC_WHITE, BINNING})
            put(j, key, c == null || !c.has(key) ? state("absent") : c.opt(key));
        put(j, "sensorGeometry", subset(c, GEOMETRY_KEYS));
        put(j, "isHardwareSerialNumber", false);
        return j;
    }

    private static JSONObject subset(JSONObject source, String[] keys) {
        JSONObject out = new JSONObject();
        for (String key : keys) put(out, key, source == null || !source.has(key) ? state("absent") : source.opt(key));
        return out;
    }

    private static JSONObject workingFrame(ImageFrame frame) {
        JSONObject j = state(frame == null ? "frame_unavailable" : "available");
        if (frame == null) return j;
        put(j, "width", frame.width); put(j, "height", frame.height); put(j, "timestampNs", frame.timestamp);
        put(j, "cropOriginX", frame.cropOriginX); put(j, "cropOriginY", frame.cropOriginY);
        put(j, "fullWidth", frame.fullWidth); put(j, "fullHeight", frame.fullHeight);
        put(j, "packedBits", frame.packedBits); put(j, "fp16", frame.fp16);
        put(j, "buffer", bufferInfo(frame.buffer));
        return j;
    }

    private static JSONObject bufferInfo(ByteBuffer buffer) {
        JSONObject j = state(buffer == null ? "buffer_unavailable" : "available");
        if (buffer != null) {
            put(j, "capacityBytes", buffer.capacity()); put(j, "limitBytes", buffer.limit());
            put(j, "positionBytes", buffer.position()); put(j, "byteOrder", buffer.order().toString());
            put(j, "readOnly", buffer.isReadOnly()); put(j, "direct", buffer.isDirect());
        }
        return j;
    }

    private static <T> void characteristic(JSONObject j, CameraCharacteristics c, String name, CameraCharacteristics.Key<T> key) {
        put(j, name, c == null ? state("characteristics_unavailable") : read(() -> c.get(key)));
    }

    private interface Probe { Object get() throws Exception; }
    private static JSONObject read(Probe probe) {
        try {
            Object value = probe.get();
            JSONObject j = state(value == null ? "absent" : "available");
            if (value != null) put(j, "value", encode(value));
            return j;
        } catch (Exception | LinkageError failure) { return error(failure); }
    }

    private static Object encode(Object value) throws JSONException {
        if (value == null) return JSONObject.NULL;
        if (value instanceof JSONObject || value instanceof JSONArray) return value;
        if (value instanceof Rect) { Rect r = (Rect) value; return new JSONArray(new int[]{r.left, r.top, r.right, r.bottom}); }
        if (value instanceof Size) { Size s = (Size) value; return new JSONArray(new int[]{s.getWidth(), s.getHeight()}); }
        if (value instanceof SizeF) {
            SizeF s = (SizeF) value;
            if (!Float.isFinite(s.getWidth()) || !Float.isFinite(s.getHeight()))
                throw new IllegalArgumentException("nonfinite_metadata");
            return new JSONArray(new double[]{s.getWidth(), s.getHeight()});
        }
        if (value instanceof BlackLevelPattern) {
            int[] offsets = new int[4]; ((BlackLevelPattern) value).copyTo(offsets, 0); return new JSONArray(offsets);
        }
        if (value instanceof ColorSpaceTransform) {
            ColorSpaceTransform matrix = (ColorSpaceTransform) value; JSONArray out = new JSONArray();
            for (int row = 0; row < 3; row++) for (int col = 0; col < 3; col++) out.put(encode(matrix.getElement(col, row)));
            return out;
        }
        if (value instanceof Rational) {
            Rational r = (Rational) value; JSONObject j = new JSONObject();
            put(j, "numerator", r.getNumerator()); put(j, "denominator", r.getDenominator()); return j;
        }
        if (value instanceof Rational[]) { JSONArray j = new JSONArray(); for (Rational r : (Rational[]) value) j.put(encode(r)); return j; }
        if (value instanceof int[]) return new JSONArray(value);
        if (value instanceof float[]) {
            JSONArray j = new JSONArray(); for (float v : (float[]) value) {
                if (!Float.isFinite(v)) throw new IllegalArgumentException("nonfinite_metadata"); j.put((double) v);
            } return j;
        }
        if (value instanceof Byte) return ((Byte) value) & 255;
        if (value instanceof Float || value instanceof Double) {
            if (!Double.isFinite(((Number) value).doubleValue())) throw new IllegalArgumentException("nonfinite_metadata");
        }
        if (value instanceof String || value instanceof Number || value instanceof Boolean) return value;
        throw new IllegalArgumentException("unsupported_metadata_type");
    }

    private static Object valueOf(JSONObject field) {
        if (field == null || !"available".equals(field.optString("status"))) return null;
        Object value = field.opt("value"); return value == JSONObject.NULL ? null : value;
    }
    private static Object fieldValue(JSONObject object, String name) { return object == null ? null : valueOf(object.optJSONObject(name)); }
    private static Integer numberInt(Object v) { return v instanceof Number ? ((Number) v).intValue() : null; }
    private static Long numberLong(Object v) { return v instanceof Number ? ((Number) v).longValue() : null; }
    private static String stringValue(Object v) { return v instanceof String ? clean((String) v) : null; }
    private static boolean positiveInt(Object v) { return v instanceof Number && ((Number) v).doubleValue() > 0 && ((Number) v).doubleValue() <= 65535; }
    private static boolean knownMode(Object v) { return v instanceof Number && (((Number) v).intValue() == 0 || ((Number) v).intValue() == 1); }
    private static boolean validBlack(Object v) {
        if (!(v instanceof JSONArray) || ((JSONArray) v).length() != 4) return false;
        for (int i = 0; i < 4; i++) { Object n = ((JSONArray) v).opt(i);
            if (!(n instanceof Number) || !Double.isFinite(((Number) n).doubleValue()) || ((Number) n).doubleValue() < 0) return false; }
        return true;
    }
    private static boolean unitFactor(Object v) { return v instanceof JSONArray && ((JSONArray) v).length() == 2 && ((JSONArray) v).optInt(0, -1) == 1 && ((JSONArray) v).optInt(1, -1) == 1; }
    private static boolean groupFactor(Object v) { return v instanceof JSONArray && ((JSONArray) v).length() == 2 && ((JSONArray) v).optInt(0, -1) > 0 && ((JSONArray) v).optInt(1, -1) > 0 && (((JSONArray) v).optInt(0, -1) > 1 || ((JSONArray) v).optInt(1, -1) > 1); }
    private static String cfaName(Object cfa) {
        if (!(cfa instanceof Number)) return "unknown";
        int n = ((Number) cfa).intValue(); return n >= 0 && n < 4 ? new String[]{"RGGB", "GRBG", "GBRG", "BGGR"}[n] : "unsupported_" + n;
    }
    private static CaptureRequest safeResultRequest(CaptureResult r) { try { return r.getRequest(); } catch (RuntimeException | LinkageError ignored) { return null; } }
    private static String clean(String value) { return value == null || value.trim().isEmpty() ? null : value.trim(); }
    private static boolean same(String a, String b) { return a != null && b != null && a.equals(b); }
    private static JSONObject state(String status) { JSONObject j = new JSONObject(); put(j, "status", status); return j; }
    private static JSONObject error(Throwable failure) { JSONObject j = state("error"); put(j, "errorType", failure.getClass().getSimpleName()); return j; }
    private static void put(JSONObject object, String key, Object value) {
        try { object.put(key, value == null ? JSONObject.NULL : value); }
        catch (JSONException failure) { throw new IllegalStateException("raw_binding_json_invalid", failure); }
    }
    private static JSONObject parse(String text) {
        try { return new JSONObject(text); }
        catch (JSONException failure) { throw new IllegalStateException("raw_binding_snapshot_invalid", failure); }
    }
    private static String canonical(Object object) {
        if (object instanceof JSONObject) {
            JSONObject j = (JSONObject) object; TreeSet<String> keys = new TreeSet<>(); j.keys().forEachRemaining(keys::add);
            StringBuilder s = new StringBuilder("{");
            for (String key : keys) { if (s.length() > 1) s.append(','); s.append(JSONObject.quote(key)).append(':').append(canonical(j.opt(key))); }
            return s.append('}').toString();
        }
        if (object instanceof JSONArray) {
            JSONArray a = (JSONArray) object; StringBuilder s = new StringBuilder("[");
            for (int i = 0; i < a.length(); i++) { if (i > 0) s.append(','); s.append(canonical(a.opt(i))); }
            return s.append(']').toString();
        }
        if (object == null || object == JSONObject.NULL) return "null";
        return object instanceof String ? JSONObject.quote((String) object) : object.toString();
    }
    private static String sha256(String text) {
        try {
            byte[] hash = MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8));
            StringBuilder out = new StringBuilder(64); char[] hex = "0123456789abcdef".toCharArray();
            for (byte b : hash) out.append(hex[(b & 255) >>> 4]).append(hex[b & 15]); return out.toString();
        } catch (java.security.NoSuchAlgorithmException failure) { throw new IllegalStateException(failure); }
    }
}
