package com.particlesdevs.photoncamera.m10r;

import android.graphics.ImageFormat;
import android.graphics.Rect;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CameraManager;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.CaptureResult;
import android.hardware.camera2.params.BlackLevelPattern;
import android.hardware.camera2.params.ColorSpaceTransform;
import android.hardware.camera2.params.StreamConfigurationMap;
import android.os.Build;
import android.util.Rational;
import android.util.Size;
import android.util.SizeF;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;

/**
 * Advertised RAW capabilities, captured before Photon changes its working characteristics.
 *
 * This class never selects an output, opens a camera, or changes a CaptureRequest. Sensor
 * array dimensions remain metadata: only the format-specific stream maps advertise sizes.
 * An advertised size is not evidence that the app's complete session combination works.
 */
public final class M10RRawCapabilities4A {
    public static final String REVISION = "M10R_RAW_CAPABILITIES4A";
    private static final int[] RAW_FORMATS = {ImageFormat.RAW_SENSOR, ImageFormat.RAW10,
            ImageFormat.RAW12};
    private static final String[] REQUEST_KEYS = {"android.sensor.pixelMode",
            "android.sensor.exposureTime", "android.sensor.sensitivity",
            "android.scaler.cropRegion", "android.distortionCorrection.mode",
            "xiaomi.remosaic.enabled", "xiaomi.quadcfa.enabled",
            "com.mediatek.control.capture.remosaicenable"};
    private static final String[] RESULT_KEYS = {"android.sensor.pixelMode",
            "android.sensor.rawBinningFactorUsed", "android.sensor.dynamicBlackLevel",
            "android.sensor.dynamicWhiteLevel", "android.sensor.neutralColorPoint",
            "android.logicalMultiCamera.activePhysicalId", "android.scaler.cropRegion", "android.scaler.rawCropRegion",
            "android.distortionCorrection.mode"};

    private M10RRawCapabilities4A() {}

    /** Immutable serialized values; no CameraCharacteristics, Rect, or array is retained. */
    public static final class Snapshot {
        private final String json;
        private final Map<String, String> sources;
        private final Map<String, String> digests;

        private Snapshot(JSONObject document, Map<String, JSONObject> sourceObjects) {
            Map<String, String> copy = new LinkedHashMap<>();
            Map<String, String> hashes = new LinkedHashMap<>();
            JSONObject sourceJson = new JSONObject();
            for (String id : new TreeSet<>(sourceObjects.keySet())) {
                JSONObject source = sourceObjects.get(id);
                String hash = sha256(canonical(source));
                put(source, "sourceDigestSha256", hash);
                String serialized = canonical(source);
                copy.put(id, serialized);
                hashes.put(id, hash);
                put(sourceJson, id, source);
            }
            put(document, "sources", sourceJson);
            json = canonical(document);
            sources = Collections.unmodifiableMap(copy);
            digests = Collections.unmodifiableMap(hashes);
        }

        public JSONObject toJson() { return parse(json); }

        public JSONObject sourceJson(String cameraId) {
            String serialized = cameraId == null ? null : sources.get(cameraId);
            if (serialized != null) return parse(serialized);
            JSONObject missing = state("source_not_in_inventory");
            put(missing, "cameraId", cameraId);
            return missing;
        }

        /** Null for a source that was not discovered; never substitutes another camera. */
        public String sourceDigest(String cameraId) { return digests.get(cameraId); }
    }

    /**
     * Call once per controller before mutating working metadata. Extra IDs must already be
     * resolved physical camera IDs, not UI virtual-lens identifiers. Discovery also walks
     * every public logical camera, including logical cameras excluded from Photon's lens UI.
     */
    public static Snapshot discover(CameraManager manager, Collection<String> appPhysicalIds) {
        return discover(manager, appPhysicalIds, Build.VERSION.SDK_INT);
    }

    // The explicit SDK parameter makes absence/API guards independently testable on the host.
    static Snapshot discover(CameraManager manager, Collection<String> appPhysicalIds, int sdk) {
        long started = System.nanoTime();
        JSONObject document = state("available");
        put(document, "revision", REVISION);
        put(document, "sdkInt", sdk);
        put(document, "evidence", "advertised_metadata_only");
        put(document, "sessionCombinationValidated", false);
        put(document, "changesCaptureConfiguration", false);
        Set<String> appIds = cleanIds(appPhysicalIds);
        Set<String> listed = new TreeSet<>();
        JSONObject enumeration;
        if (manager == null) {
            enumeration = state("camera_manager_unavailable");
        } else {
            try {
                String[] ids = manager.getCameraIdList();
                enumeration = state(ids == null ? "absent" : "available");
                if (ids != null) listed.addAll(cleanIds(Arrays.asList(ids)));
            } catch (Exception failure) {
                enumeration = error(failure);
            }
        }
        put(enumeration, "ids", new JSONArray(listed));
        put(document, "cameraManagerEnumeration", enumeration);
        put(document, "appAccessiblePhysicalIds", new JSONArray(appIds));

        Set<String> pending = new TreeSet<>(listed);
        pending.addAll(appIds);
        Map<String, JSONObject> sources = new LinkedHashMap<>();
        Map<String, Set<String>> parents = new LinkedHashMap<>();
        while (!pending.isEmpty()) {
            String id = pending.iterator().next();
            pending.remove(id);
            if (sources.containsKey(id)) continue;
            JSONObject source = state("available");
            put(source, "cameraId", id);
            put(source, "listedByCameraManager", listed.contains(id));
            put(source, "appAccessiblePhysicalId", appIds.contains(id));
            put(source, "standaloneOpenValidated", false);
            sources.put(id, source);
            if (manager == null) {
                put(source, "status", "camera_manager_unavailable");
                continue;
            }
            try {
                CameraCharacteristics characteristics = manager.getCameraCharacteristics(id);
                if (characteristics == null) {
                    put(source, "status", "characteristics_absent");
                    continue;
                }
                JSONObject physical = state(sdk >= 28 ? "available" : "api_unavailable");
                Set<String> physicalIds = new TreeSet<>();
                if (sdk >= 28) {
                    try {
                        Set<String> values = characteristics.getPhysicalCameraIds();
                        if (values == null) put(physical, "status", "absent");
                        else physicalIds.addAll(cleanIds(values));
                    } catch (Exception failure) { physical = error(failure); }
                }
                put(physical, "ids", new JSONArray(physicalIds));
                put(source, "advertisedPhysicalIds", physical);
                for (String physicalId : physicalIds) {
                    parents.computeIfAbsent(physicalId, ignored -> new TreeSet<>()).add(id);
                    if (!sources.containsKey(physicalId)) pending.add(physicalId);
                }
                put(source, "characteristics", metadata(characteristics, sdk));
                put(source, "requestKeySupport", keySupport(characteristics, REQUEST_KEYS, 0, sdk));
                put(source, "resultKeySupport", keySupport(characteristics, RESULT_KEYS, 1, sdk));
                put(source, "physicalRequestKeySupport", keySupport(characteristics, REQUEST_KEYS, 2, sdk));
                JSONObject streams = new JSONObject();
                put(streams, "default", streamMap(characteristics, false, sdk));
                put(streams, "maximumResolution", streamMap(characteristics, true, sdk));
                put(source, "streams", streams);
            } catch (Exception failure) {
                put(source, "status", "characteristics_error");
                put(source, "error", error(failure));
            }
        }
        int availableSources = 0;
        for (Map.Entry<String, JSONObject> entry : sources.entrySet()) {
            put(entry.getValue(), "logicalParentIds", new JSONArray(
                    parents.getOrDefault(entry.getKey(), Collections.emptySet())));
            if ("available".equals(entry.getValue().optString("status"))) availableSources++;
        }
        put(document, "status", manager == null ? "camera_manager_unavailable"
                : availableSources < sources.size() || !"available".equals(enumeration.optString("status"))
                ? "partial" : "available");
        put(document, "sourceCount", sources.size());
        put(document, "availableSourceCount", availableSources);
        put(document, "discoveryElapsedNs", System.nanoTime() - started);
        return new Snapshot(document, sources);
    }

    private static JSONObject metadata(CameraCharacteristics c, int sdk) {
        JSONObject m = new JSONObject();
        characteristic(m, c, "android.request.availableCapabilities", CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES);
        characteristic(m, c, "android.info.supportedHardwareLevel", CameraCharacteristics.INFO_SUPPORTED_HARDWARE_LEVEL);
        characteristic(m, c, "android.lens.facing", CameraCharacteristics.LENS_FACING);
        characteristic(m, c, "android.sensor.orientation", CameraCharacteristics.SENSOR_ORIENTATION);
        characteristic(m, c, "android.sensor.info.physicalSize", CameraCharacteristics.SENSOR_INFO_PHYSICAL_SIZE);
        characteristic(m, c, "android.sensor.info.pixelArraySize", CameraCharacteristics.SENSOR_INFO_PIXEL_ARRAY_SIZE);
        characteristic(m, c, "android.sensor.info.activeArraySize", CameraCharacteristics.SENSOR_INFO_ACTIVE_ARRAY_SIZE);
        characteristic(m, c, "android.sensor.info.preCorrectionActiveArraySize", CameraCharacteristics.SENSOR_INFO_PRE_CORRECTION_ACTIVE_ARRAY_SIZE);
        characteristic(m, c, "android.sensor.info.colorFilterArrangement", CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT);
        characteristic(m, c, "android.sensor.blackLevelPattern", CameraCharacteristics.SENSOR_BLACK_LEVEL_PATTERN);
        characteristic(m, c, "android.sensor.info.whiteLevel", CameraCharacteristics.SENSOR_INFO_WHITE_LEVEL);
        characteristic(m, c, "android.lens.info.availableFocalLengths", CameraCharacteristics.LENS_INFO_AVAILABLE_FOCAL_LENGTHS);
        characteristic(m, c, "android.lens.info.availableApertures", CameraCharacteristics.LENS_INFO_AVAILABLE_APERTURES);
        characteristic(m, c, "android.sensor.referenceIlluminant1", CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT1);
        characteristic(m, c, "android.sensor.referenceIlluminant2", CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT2);
        characteristic(m, c, "android.sensor.colorTransform1", CameraCharacteristics.SENSOR_COLOR_TRANSFORM1);
        characteristic(m, c, "android.sensor.colorTransform2", CameraCharacteristics.SENSOR_COLOR_TRANSFORM2);
        characteristic(m, c, "android.sensor.calibrationTransform1", CameraCharacteristics.SENSOR_CALIBRATION_TRANSFORM1);
        characteristic(m, c, "android.sensor.calibrationTransform2", CameraCharacteristics.SENSOR_CALIBRATION_TRANSFORM2);
        characteristic(m, c, "android.sensor.forwardMatrix1", CameraCharacteristics.SENSOR_FORWARD_MATRIX1);
        characteristic(m, c, "android.sensor.forwardMatrix2", CameraCharacteristics.SENSOR_FORWARD_MATRIX2);
        if (sdk >= 31) {
            characteristic(m, c, "android.sensor.info.pixelArraySizeMaximumResolution", CameraCharacteristics.SENSOR_INFO_PIXEL_ARRAY_SIZE_MAXIMUM_RESOLUTION);
            characteristic(m, c, "android.sensor.info.activeArraySizeMaximumResolution", CameraCharacteristics.SENSOR_INFO_ACTIVE_ARRAY_SIZE_MAXIMUM_RESOLUTION);
            characteristic(m, c, "android.sensor.info.preCorrectionActiveArraySizeMaximumResolution", CameraCharacteristics.SENSOR_INFO_PRE_CORRECTION_ACTIVE_ARRAY_SIZE_MAXIMUM_RESOLUTION);
            characteristic(m, c, "android.sensor.info.binningFactor", CameraCharacteristics.SENSOR_INFO_BINNING_FACTOR);
        } else {
            for (String name : new String[]{"pixelArraySizeMaximumResolution", "activeArraySizeMaximumResolution",
                    "preCorrectionActiveArraySizeMaximumResolution", "binningFactor"}) {
                put(m, "android.sensor.info." + name, state("api_unavailable"));
            }
        }
        return m;
    }

    private static <T> void characteristic(JSONObject destination, CameraCharacteristics c,
            String name, CameraCharacteristics.Key<T> key) {
        try { put(destination, name, value(c.get(key))); }
        catch (Exception failure) { put(destination, name, error(failure)); }
    }

    /** Key names are compared to the advertised list; absence is not treated as false. */
    private static JSONObject keySupport(CameraCharacteristics c, String[] desired, int kind, int sdk) {
        JSONObject result = state(kind == 2 && sdk < 28 ? "api_unavailable" : "available");
        if (kind == 2 && sdk < 28) return result;
        try {
            List<?> keys = kind == 0 ? c.getAvailableCaptureRequestKeys()
                    : kind == 1 ? c.getAvailableCaptureResultKeys() : c.getAvailablePhysicalCameraRequestKeys();
            if (keys == null) return state("absent");
            Set<String> names = new TreeSet<>();
            for (Object key : keys) {
                String name = key instanceof CaptureRequest.Key
                        ? ((CaptureRequest.Key<?>) key).getName()
                        : key instanceof CaptureResult.Key ? ((CaptureResult.Key<?>) key).getName() : null;
                if (name != null) names.add(name);
            }
            JSONObject available = new JSONObject();
            for (String name : desired) put(available, name, names.contains(name));
            put(result, "keys", available);
        } catch (Exception failure) { return error(failure); }
        return result;
    }

    private static JSONObject streamMap(CameraCharacteristics c, boolean maximum, int sdk) {
        JSONObject result = state(maximum && sdk < 31 ? "api_unavailable" : "available");
        put(result, "pixelMode", maximum ? 1 : 0);
        put(result, "mapKey", maximum ? "android.scaler.streamConfigurationMapMaximumResolution"
                : "android.scaler.streamConfigurationMap");
        if (maximum && sdk < 31) return result;
        StreamConfigurationMap map;
        try {
            map = maximum ? c.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP_MAXIMUM_RESOLUTION)
                    : c.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP);
        } catch (Exception failure) {
            put(result, "status", "error"); put(result, "error", error(failure)); return result;
        }
        if (map == null) { put(result, "status", "absent"); return result; }
        JSONArray formats = new JSONArray();
        for (int format : RAW_FORMATS) {
            JSONObject item = state("available");
            put(item, "format", format); put(item, "formatName", formatName(format));
            try {
                boolean supported = map.isOutputSupportedFor(format);
                put(item, "advertisedSupported", supported);
                if (!supported) {
                    put(item, "status", "format_not_advertised");
                } else {
                    put(item, "regularOutputSizes", sizeList(map, format, false, sdk));
                    put(item, "slowerHighResolutionOutputSizes", sizeList(map, format, true, sdk));
                }
            } catch (Exception failure) {
                put(item, "status", "error"); put(item, "error", error(failure));
            }
            formats.put(item);
        }
        put(result, "formats", formats);
        return result;
    }

    private static JSONObject sizeList(StreamConfigurationMap map, int format, boolean slower, int sdk) {
        if (slower && sdk < 23) return state("api_unavailable");
        try {
            Size[] values = slower ? map.getHighResolutionOutputSizes(format) : map.getOutputSizes(format);
            JSONObject result = state(values == null ? "absent" : values.length == 0 ? "empty" : "available");
            // A null slower list is documented for cameras without BURST_CAPTURE; it is
            // not proof that all outputs are fast, nor proof that no large output exists.
            if (values == null && slower) put(result, "nullInterpretation", "no_separate_slower_list_returned");
            List<Size> sorted = new ArrayList<>();
            if (values != null) for (Size size : values) if (size != null) sorted.add(size);
            sorted.sort((a, b) -> a.getWidth() != b.getWidth() ? Integer.compare(a.getWidth(), b.getWidth())
                    : Integer.compare(a.getHeight(), b.getHeight()));
            JSONArray sizes = new JSONArray();
            for (Size size : sorted) {
                JSONObject item = state(size.getWidth() > 0 && size.getHeight() > 0 ? "advertised" : "invalid_dimensions");
                put(item, "width", size.getWidth()); put(item, "height", size.getHeight());
                put(item, "minFrameDurationNs", duration(map, format, size, false));
                put(item, "stallDurationNs", duration(map, format, size, true));
                sizes.put(item);
            }
            put(result, "sizes", sizes);
            if (values != null) put(result, "nullSizeEntries", values.length - sorted.size());
            return result;
        } catch (Exception failure) { return error(failure); }
    }

    private static JSONObject duration(StreamConfigurationMap map, int format, Size size, boolean stall) {
        try {
            long duration = stall ? map.getOutputStallDuration(format, size) : map.getOutputMinFrameDuration(format, size);
            JSONObject result = state(duration < 0 ? "invalid_negative_duration" : "available");
            put(result, "value", duration);
            if (duration == 0 && !stall) put(result, "interpretation", "zero_reported_no_frame_rate_inferred");
            return result;
        } catch (Exception failure) { return error(failure); }
    }

    private static String formatName(int format) {
        if (format == ImageFormat.RAW_SENSOR) return "RAW_SENSOR";
        if (format == ImageFormat.RAW10) return "RAW10";
        return "RAW12";
    }

    private static Set<String> cleanIds(Collection<String> ids) {
        Set<String> result = new TreeSet<>();
        if (ids != null) for (String id : ids) if (id != null && !id.isEmpty()) result.add(id);
        return result;
    }

    private static JSONObject value(Object value) throws JSONException {
        JSONObject result = state(value == null ? "absent" : "available");
        if (value != null) put(result, "value", serializable(value));
        return result;
    }

    private static Object serializable(Object value) throws JSONException {
        if (value instanceof Rect) {
            Rect rect = (Rect) value;
            return new JSONArray(new int[]{rect.left, rect.top, rect.right, rect.bottom});
        }
        if (value instanceof Size) {
            Size size = (Size) value;
            return new JSONArray(new int[]{size.getWidth(), size.getHeight()});
        }
        if (value instanceof SizeF) {
            SizeF size = (SizeF) value;
            finite(size.getWidth()); finite(size.getHeight());
            return new JSONArray(new float[]{size.getWidth(), size.getHeight()});
        }
        if (value instanceof BlackLevelPattern) {
            BlackLevelPattern pattern = (BlackLevelPattern) value;
            JSONArray values = new JSONArray();
            for (int row = 0; row < 2; row++) for (int column = 0; column < 2; column++)
                values.put(pattern.getOffsetForIndex(column, row));
            return values;
        }
        if (value instanceof ColorSpaceTransform) {
            ColorSpaceTransform transform = (ColorSpaceTransform) value;
            JSONArray values = new JSONArray();
            for (int row = 0; row < 3; row++) for (int column = 0; column < 3; column++) {
                Rational rational = transform.getElement(column, row);
                JSONObject pair = new JSONObject();
                put(pair, "numerator", rational.getNumerator());
                put(pair, "denominator", rational.getDenominator());
                values.put(pair);
            }
            return values;
        }
        if (value instanceof int[]) return new JSONArray((int[]) value);
        if (value instanceof float[]) {
            for (float number : (float[]) value) finite(number);
            return new JSONArray((float[]) value);
        }
        if (value instanceof Number) { finite(((Number) value).doubleValue()); return value; }
        if (value instanceof Boolean || value instanceof String) return value;
        throw new IllegalArgumentException("unsupported_metadata_type_" + value.getClass().getSimpleName());
    }

    private static void finite(double value) {
        if (!Double.isFinite(value)) throw new IllegalArgumentException("nonfinite_metadata_value");
    }

    private static JSONObject state(String status) {
        JSONObject result = new JSONObject(); put(result, "status", status); return result;
    }

    private static JSONObject error(Exception failure) {
        JSONObject result = state("error");
        // Record failure type without device/vendor exception text or incidental private data.
        put(result, "errorType", failure.getClass().getSimpleName());
        return result;
    }

    private static void put(JSONObject destination, String key, Object value) {
        try { destination.put(key, value == null ? JSONObject.NULL : value); }
        catch (JSONException failure) { throw new IllegalStateException("raw_capability_json_invalid", failure); }
    }

    private static JSONObject parse(String serialized) {
        try { return new JSONObject(serialized); }
        catch (JSONException failure) { throw new IllegalStateException("raw_capability_snapshot_invalid", failure); }
    }

    private static String canonical(Object object) {
        if (object instanceof JSONObject) {
            JSONObject value = (JSONObject) object;
            Set<String> keys = new TreeSet<>(); value.keys().forEachRemaining(keys::add);
            StringBuilder result = new StringBuilder("{");
            for (String key : keys) {
                if (result.length() > 1) result.append(',');
                result.append(JSONObject.quote(key)).append(':').append(canonical(value.opt(key)));
            }
            return result.append('}').toString();
        }
        if (object instanceof JSONArray) {
            JSONArray array = (JSONArray) object; StringBuilder result = new StringBuilder("[");
            for (int index = 0; index < array.length(); index++) {
                if (index > 0) result.append(','); result.append(canonical(array.opt(index)));
            }
            return result.append(']').toString();
        }
        if (object == null || object == JSONObject.NULL) return "null";
        if (object instanceof String) return JSONObject.quote((String) object);
        return object.toString();
    }

    private static String sha256(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder result = new StringBuilder(64);
            for (byte b : digest) result.append(String.format(java.util.Locale.ROOT, "%02x", b & 255));
            return result.toString();
        } catch (java.security.NoSuchAlgorithmException failure) { throw new IllegalStateException(failure); }
    }
}
