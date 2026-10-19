package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.CaptureResult;
import android.hardware.camera2.params.ColorSpaceTransform;

import com.particlesdevs.photoncamera.app.PhotonCamera;
import com.particlesdevs.photoncamera.processing.ImageFrame;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Map;
import java.util.TreeMap;

/**
 * Same-photograph execution of the recovered selector in diagnostic mode.
 *
 * The integer selector has source-derived arithmetic. The fixed profile, scale,
 * black, controls and calibration-bank choices below are explicitly experimental
 * inputs. Results never enter source-white preparation, a capture request, the
 * DNG writer, exposure state, or retained state for another photograph.
 */
public final class M10RWbShadow3Y {
    public static final String REVISION = "M10R_WBSELECTOR3Y_PHOTOGRAPHIC_SHADOW";
    static final String CONFIG_SHA = "eb3dad695d8fae535c2cf2c4af9adbc18d6ec9791deea3e70d4dd3b929649892";
    static final String TABLE_SHA = "f49561f70050f531856ef6a3e74a2ac051c0e758e0321df5a23e3fcab432579c";
    private static final int[] SCALES = {1, 4, 16};
    // Original IMG fallback record; these are not the later resident banks and
    // are not labelled as illuminants, factory measurements, or phone calibration.
    private static final int[] FALLBACK_ANCHORS = {9358, 10446, 10365, 4887,
            5260, 10533, 10464, 7385};
    private static final byte[] GRID_HASH_PREFIX =
            "M10R_WBSELECTOR3Y_GRID_V1\0".getBytes(StandardCharsets.US_ASCII);
    private static volatile Assets cachedAssets;

    private M10RWbShadow3Y() {}

    static final class Profile {
        final int index;
        final Integer illuminant;
        final double[] calibration, color;

        Profile(int index, Integer illuminant, double[] calibration, double[] color) {
            this.index = index;
            this.illuminant = illuminant;
            this.calibration = calibration == null ? null : calibration.clone();
            this.color = color == null ? null : color.clone();
        }
    }

    private static final class Assets {
        final byte[] configuration, table;

        Assets(byte[] configuration, byte[] table) {
            this.configuration = configuration;
            this.table = table;
        }
    }

    /** Called only after the matching photographic RAW grid has been measured. */
    static void append(JSONObject destination, ImageFrame frame,
            CameraCharacteristics characteristics, CaptureResult result,
            CaptureRequest request, double[] targetA, double[] targetD65) {
        final long start = System.nanoTime();
        JSONObject output = null;
        try {
            JSONObject raw = destination.optJSONObject("photographicRawResponse2S");
            Long timestamp = result == null ? null : result.get(CaptureResult.SENSOR_TIMESTAMP);
            if (raw == null || frame == null || characteristics == null || result == null
                    || timestamp == null || timestamp <= 0 || timestamp != frame.timestamp
                    || raw.getLong("imageTimestampNs") != frame.timestamp
                    || raw.getLong("resultTimestampNs") != timestamp
                    || raw.getLong("frameNumber") != result.getFrameNumber()
                    || raw.getInt("rawWidth") != frame.width
                    || raw.getInt("rawHeight") != frame.height) {
                throw new IllegalArgumentException("photographic_frame_binding");
            }
            Integer cfa = characteristics.get(CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT);
            if (cfa == null || raw.getInt("cfa") != cfa) {
                throw new IllegalArgumentException("physical_CFA_binding");
            }
            Integer illuminant1 = characteristics.get(CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT1);
            Byte illuminant2 = characteristics.get(CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT2);
            Profile[] profiles = {
                    new Profile(1, illuminant1,
                            matrix(characteristics.get(CameraCharacteristics.SENSOR_CALIBRATION_TRANSFORM1)),
                            matrix(characteristics.get(CameraCharacteristics.SENSOR_COLOR_TRANSFORM1))),
                    new Profile(2, illuminant2 == null ? null : illuminant2 & 255,
                            matrix(characteristics.get(CameraCharacteristics.SENSOR_CALIBRATION_TRANSFORM2)),
                            matrix(characteristics.get(CameraCharacteristics.SENSOR_COLOR_TRANSFORM2)))
            };
            Assets assets = assets();
            output = evaluate(raw, profiles, assets.configuration, assets.table, targetA, targetD65);
            output.put("actualPhotographicFrameBound", true)
                    .put("requestedAwbMode", optional(request == null ? null
                            : request.get(CaptureRequest.CONTROL_AWB_MODE)))
                    .put("deliveredAwbMode", optional(result.get(CaptureResult.CONTROL_AWB_MODE)))
                    .put("captureWhiteBalanceAuthority", destination.optJSONObject("whiteBalanceSnapshot3N") == null
                            ? JSONObject.NULL : destination.getJSONObject("whiteBalanceSnapshot3N").opt("authority"));
        } catch (Exception | LinkageError | OutOfMemoryError failure) {
            try {
                output = base().put("status", "DIAGNOSTIC_UNAVAILABLE")
                        .put("actualPhotographicFrameBound", false)
                        .put("errorType", failure.getClass().getSimpleName())
                        .put("reason", optional(failure.getMessage()));
            } catch (Exception | LinkageError | OutOfMemoryError ignored) {
                return;
            }
        }
        try {
            output.put("totalDurationNs", System.nanoTime() - start)
                    .put("timingExcludesFinalSidecarSerialization", true);
            destination.put("m10rWbSelector3Y", output);
        } catch (Exception | LinkageError | OutOfMemoryError ignored) {
            // Failure in this diagnostic must not cancel an ordinary photograph.
        }
    }

    /** Pure adapter entry used by host fixtures and the Camera2 wrapper above. */
    static JSONObject evaluate(JSONObject raw, Profile[] profiles, byte[] configuration,
            byte[] table, double[] targetA, double[] targetD65) throws JSONException {
        if (raw == null || !"PHOTOGRAPHIC_RAW_MEASURED".equals(raw.optString("status"))
                || !raw.optBoolean("frameTimestampMatched")
                || !"photographic_RAW_before_normalization_LSC_WB".equals(raw.optString("source"))
                || !raw.optBoolean("beforeLscAndWb") || raw.optBoolean("upperClampApplied")
                || raw.getLong("imageTimestampNs") <= 0
                || raw.getLong("imageTimestampNs") != raw.getLong("resultTimestampNs")
                || raw.getLong("frameNumber") < 0
                || raw.getInt("gridRows") != 16 || raw.getInt("gridColumns") != 22
                || raw.getInt("sparseWidth") != 176 || raw.getInt("sparseHeight") != 128
                || raw.getInt("excludedBorder") != 16
                || !"R,Gr,Gb,B".equals(raw.optString("channelOrder"))) {
            throw new IllegalArgumentException("photographic_RAW_grid_contract");
        }
        if (configuration == null || configuration.length != 0x310
                || !CONFIG_SHA.equals(sha256(configuration)) || table == null || table.length != 40000
                || !TABLE_SHA.equals(sha256(table))) {
            throw new IllegalArgumentException("source_reference_asset_identity");
        }
        int[] counts = integers(raw.getJSONArray("sampleCounts"), 352);
        double[] sums = doubles(raw.getJSONArray("blackSubtractedSumsCellMajor"), 1408);
        double[][] means = phoneMeans(counts, sums);
        JSONObject output = base();
        output.put("input", new JSONObject()
                .put("source", "photographicRawResponse2S")
                .put("rawWidth", raw.getInt("rawWidth")).put("rawHeight", raw.getInt("rawHeight"))
                .put("cfa", raw.getInt("cfa"))
                .put("imageTimestampNs", raw.getLong("imageTimestampNs"))
                .put("resultTimestampNs", raw.getLong("resultTimestampNs"))
                .put("frameNumber", raw.getLong("frameNumber"))
                .put("physicalFingerprint", raw.opt("physicalFingerprint"))
                .put("physicalDescriptor", raw.opt("physicalDescriptor"))
                .put("blackByCfaPhase", raw.getJSONArray("blackByCfaPhase"))
                .put("white", raw.getInt("white"))
                .put("sampledQuadCount", sum(counts))
                .put("gridInputSha256", gridHash(raw, counts, sums))
                .put("gridHashEncoding", "ASCII_M10R_WBSELECTOR3Y_GRID_V1_NUL;LE_i32_width_height_cfa_white;"
                        + "LE_i64_imageTimestamp_frameNumber;LE_f64_black4;LE_i32_counts352;LE_f64_sums1408")
                .put("meanFormula", "R=sumR/n;G=(sumGr+sumGb)/(2*n);B=sumB/n")
                .put("sourceRawOriginIndependentlyProven", false)
                .put("rawStatisticsAssignedPhysicalLeicaProducerMeaning", false)
                .put("jsonSerializationRoundTripUsedBeforeEvaluation", false));
        byte[] packet = experimentPacket();
        output.put("experiment", new JSONObject()
                .put("configurationSha256", CONFIG_SHA).put("classificationTableSha256", TABLE_SHA)
                .put("configurationSource", "CA9_B698_initializer_zero_seed_output")
                .put("configurationUnwrittenHoles", "explicit_zero_reference_seed")
                .put("calibrationAnchorSource", "IMG_original_fallback_record_not_resident_or_per_phone_calibration")
                .put("anchorsB_G0_G1_R_B_G0_G1_R", new JSONArray(FALLBACK_ANCHORS))
                .put("anchorIlluminantIdentitiesAssigned", false)
                .put("packetHex", hex(packet)).put("packetSha256", sha256(packet))
                .put("pointerFieldPolicy", "P0C_zero_records_passed_as_Java_arrays_never_dereferenced")
                .put("wbPacketMode", 1).put("p34Signed16", 256).put("p36Signed16", 256)
                .put("packetFlag32", 0).put("blackP42Signed16", 0)
                .put("sourceBlackAlreadySubtractedInPhoneGrid", true)
                .put("freshWorkAndCellsZeroPerVariant", true)
                .put("retainedOwnerExecuted", false)
                .put("fixedScaleSensitivityFactors", new JSONArray(SCALES))
                .put("syntheticTupleEncoding", "[1,floor(scale*R),floor(scale*G),floor(scale*B)]")
                .put("uniformScaleIncludedInNeutralInverse", false)
                .put("sourceAutoOrManualNeutralUsedToConstructTransform", false)
                .put("phoneForwardMatrixUsed", false).put("lensShadingApplied", false)
                .put("rowNormalizationApplied", false).put("negativeComponentsClipped", false)
                .put("profilePolicy", "each_advertised_ID_independently;21_D65;17_A;other_or_missing_unsupported")
                .put("transformFormula", "T=target_ColorMatrix*inverse(phone_CameraCalibration*phone_ColorMatrix)")
                .put("matrixConvention", "row_major_double64_column_vectors_Camera2_Rational_doubleValue")
                .put("analogBalancePolicy", "identity_Camera2_profile_basis_assumption_not_spectral_calibration"));
        JSONArray outputs = new JSONArray();
        int completed = 0, unsupported = 0;
        if (profiles != null) for (Profile profile : profiles) {
            JSONObject p = new JSONObject().put("profileIndex", profile == null ? JSONObject.NULL : profile.index);
            outputs.put(p);
            try {
                if (profile == null) throw new IllegalArgumentException("profile_missing");
                p.put("reportedIlluminantId", optional(profile.illuminant));
                String endpoint = profile.illuminant == null ? null : endpointName(profile.illuminant);
                if (endpoint == null) throw new IllegalArgumentException("unsupported_or_missing_illuminant_ID");
                p.put("fixedEndpointAssumption", endpoint);
                double[] target = "A".equals(endpoint) ? targetA : targetD65;
                double[] transform = buildTransform(profile.color, profile.calibration, target);
                double[] inverse = inverse3(transform);
                double identityError = identityError(multiply(inverse, transform));
                if (identityError > 1e-12) throw new IllegalArgumentException("matrix_inverse_roundtrip");
                p.put("phoneCalibrationTransform", new JSONArray(profile.calibration))
                        .put("phoneColorTransform", new JSONArray(profile.color))
                        .put("targetColorMatrix", new JSONArray(target))
                        .put("TPhoneToTarget", new JSONArray(transform))
                        .put("TInverseTargetToPhone", new JSONArray(inverse))
                        .put("inverseTimesForwardIdentityMaxAbsError", identityError)
                        .put("transformSha256", sha256(doubleBytes(transform)))
                        .put("status", "FIXED_ENDPOINT_DIAGNOSTIC_ONLY");
                JSONArray variants = new JSONArray();
                p.put("variants", variants);
                for (int scale : SCALES) {
                    long start = System.nanoTime();
                    JSONObject variant = new JSONObject().put("scale", scale)
                            .put("variantKey", "profile" + profile.index + "_" + endpoint + "_scale" + scale);
                    variants.put(variant);
                    try {
                        long[][] records = recordsFor(means, transform, scale);
                        variant.put("tupleSha256", sha256(recordBytes(records)))
                                .put("tupleHashEncoding", "352_cell_major_LE_uint32_D_Rnum_Gnum_Bnum");
                        M10RWbSelector3Y.Result result = M10RWbSelector3Y.evaluate(records, packet, configuration, table);
                        JSONObject countsByClass = new JSONObject();
                        TreeMap<Integer, Integer> classes = new TreeMap<>();
                        for (int[] cell : result.cells) classes.merge(cell[6], 1, Integer::sum);
                        for (Map.Entry<Integer, Integer> entry : classes.entrySet())
                            countsByClass.put(Integer.toString(entry.getKey()), entry.getValue());
                        variant.put("gateAcceptedCells", result.gateAcceptedCells)
                                .put("classCounts", countsByClass)
                                .put("selectionRoute", result.selectionRoute)
                                .put("selectedCoordinates", new JSONArray(result.selectedCoordinates))
                                .put("selectedTargetGainsRGB", new JSONArray(result.selectedGainsRgb))
                                .put("cellStageSha256", stageHashes(result.cellStages))
                                .put("workStageSha256", stageHashes(result.workStages))
                                .put("classificationTableReadCount", result.tableReads.length)
                                .put("classificationTableReadOffsetsSha256", sha256(intBytes(result.tableReads)))
                                .put("inverseNeutral", inverseNeutral(transform, result.selectedGainsRgb))
                                .put("status", "UNCALIBRATED_SELECTOR_TRIAL_COMPLETE");
                        completed++;
                    } catch (RuntimeException failure) {
                        variant.put("status", "UNSUPPORTED_TRIAL_INPUT")
                                .put("errorType", failure.getClass().getSimpleName())
                                .put("reason", optional(failure.getMessage()));
                        unsupported++;
                    }
                    variant.put("durationNs", System.nanoTime() - start);
                }
            } catch (RuntimeException failure) {
                p.put("status", "UNSUPPORTED_PROFILE_METADATA")
                        .put("reason", optional(failure.getMessage()));
            }
        }
        return output.put("profiles", outputs).put("completedTrialCount", completed)
                .put("unsupportedTrialCount", unsupported)
                .put("status", completed > 0 ? "UNCALIBRATED_SHADOW_COMPLETE" : "NO_SUPPORTED_SHADOW_TRIAL");
    }

    static String endpointName(int illuminant) {
        return illuminant == 21 ? "D65" : illuminant == 17 ? "A" : null;
    }

    static double[][] phoneMeans(int[] counts, double[] sums) {
        if (counts == null || counts.length != 352 || sums == null || sums.length != 1408)
            throw new IllegalArgumentException("phone_grid_shape");
        double[][] out = new double[352][3];
        for (int i = 0; i < 352; i++) {
            if (counts[i] <= 0) throw new IllegalArgumentException("phone_grid_sample_count");
            for (int c = 0; c < 4; c++) if (!Double.isFinite(sums[4 * i + c]) || sums[4 * i + c] < 0)
                throw new IllegalArgumentException("phone_grid_sum_domain");
            double n = counts[i];
            out[i][0] = sums[4 * i] / n;
            out[i][1] = (sums[4 * i + 1] + sums[4 * i + 2]) / (2 * n);
            out[i][2] = sums[4 * i + 3] / n;
            for (double value : out[i]) if (!Double.isFinite(value))
                throw new IllegalArgumentException("phone_grid_mean_nonfinite");
        }
        return out;
    }

    static double[] buildTransform(double[] color, double[] calibration, double[] target) {
        requireMatrix(color);
        requireMatrix(calibration);
        requireMatrix(target);
        double[] out = multiply(target, inverse3(multiply(calibration, color)));
        requireMatrix(out);
        return out;
    }

    static long[][] recordsFor(double[][] means, double[] transform, int scale) {
        if (means == null || means.length != 352 || (scale != 1 && scale != 4 && scale != 16))
            throw new IllegalArgumentException("variant_shape_or_scale");
        requireMatrix(transform);
        long[][] out = new long[352][4];
        for (int i = 0; i < 352; i++) {
            double[] values = vector(transform, means[i]);
            out[i][0] = 1;
            for (int channel = 0; channel < 3; channel++) {
                double value = values[channel];
                if (!Double.isFinite(value) || value < 0)
                    throw new IllegalArgumentException("negative_or_nonfinite_transform_cell_" + i);
                double floor = Math.floor(scale * value);
                if (!Double.isFinite(floor) || floor > 32767)
                    throw new IllegalArgumentException("signed16_input_range_cell_" + i);
                out[i][channel + 1] = (long) floor;
            }
        }
        return out;
    }

    static JSONObject inverseNeutral(double[] transform, int[] gainsRgb) throws JSONException {
        JSONObject out = new JSONObject().put("applied", false)
                .put("deviceGainRangeChecked", false).put("negativeComponentsClipped", false)
                .put("formula", "normalize_green(T_inverse*normalize_green([256/gR,256/gG,256/gB]))");
        try {
            if (gainsRgb == null || gainsRgb.length != 3)
                throw new IllegalArgumentException("target_gain_shape");
            for (int gain : gainsRgb) if (gain <= 0)
                throw new IllegalArgumentException("nonpositive_target_gain");
            double[] target = normalize(new double[]{256.0 / gainsRgb[0], 256.0 / gainsRgb[1], 256.0 / gainsRgb[2]});
            double[] phoneUnnormalized = vector(inverse3(transform), target);
            double[] phone = normalize(phoneUnnormalized);
            double[] roundtrip = normalize(vector(transform, phone));
            double error = 0;
            for (int i = 0; i < 3; i++) error = Math.max(error, Math.abs(roundtrip[i] - target[i]));
            if (error > 1e-12) throw new IllegalArgumentException("neutral_roundtrip_error");
            double[] gainShape = {1 / phone[0], 1, 1, 1 / phone[2]};
            for (double gain : gainShape) if (!Double.isFinite(gain) || gain <= 0)
                throw new IllegalArgumentException("phone_reciprocal_gain_nonfinite");
            out.put("targetUnitGreenNeutral", new JSONArray(target))
                    .put("inverseUnnormalizedPhoneNeutral", new JSONArray(phoneUnnormalized))
                    .put("phoneUnitGreenNeutral", new JSONArray(phone))
                    .put("phoneRequestGainShapeRGGBOnly", new JSONArray(gainShape))
                    .put("forwardRoundTripTargetNeutral", new JSONArray(roundtrip))
                    .put("normalizedNeutralRoundTripMaxAbsError", error)
                    .put("status", "POSITIVE_PHONE_NEUTRAL_AND_ROUNDTRIP_VERIFIED");
        } catch (RuntimeException failure) {
            out.put("status", "UNSUPPORTED_INVERSE_NEUTRAL").put("reason", optional(failure.getMessage()));
        }
        return out;
    }

    static double[] inverse3(double[] m) {
        requireMatrix(m);
        double a = m[0], b = m[1], c = m[2], d = m[3], e = m[4], f = m[5],
                g = m[6], h = m[7], i = m[8];
        double det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g);
        if (det == 0 || !Double.isFinite(det)) throw new IllegalArgumentException("singular_or_nonfinite_matrix");
        double s = 1 / det;
        double[] out = {(e * i - f * h) * s, (c * h - b * i) * s, (b * f - c * e) * s,
                (f * g - d * i) * s, (a * i - c * g) * s, (c * d - a * f) * s,
                (d * h - e * g) * s, (b * g - a * h) * s, (a * e - b * d) * s};
        requireMatrix(out);
        return out;
    }

    static byte[] experimentPacket() {
        ByteBuffer b = ByteBuffer.allocate(0x5C).order(ByteOrder.LITTLE_ENDIAN);
        b.putShort(0, (short) 352).putShort(4, (short) 16).putShort(8, (short) 22);
        b.putInt(0x14, 1).putShort(0x34, (short) 256).putShort(0x36, (short) 256);
        for (int i = 0; i < FALLBACK_ANCHORS.length; i++) b.putShort(0x4C + i * 2, (short) FALLBACK_ANCHORS[i]);
        return b.array();
    }

    private static JSONObject base() throws JSONException {
        return new JSONObject().put("revision", REVISION).put("diagnosticOnly", true)
                .put("applied", false).put("controlsPixels", false).put("controlsCameraRequests", false)
                .put("controlsDngNeutral", false).put("controlsExposure", false)
                .put("sensorAdapterCalibrated", false).put("physicalLeicaProducerParityClaimed", false)
                .put("sceneIlluminantEstimated", false).put("profileOrScaleSelected", false)
                .put("additionalRawFrames", 0).put("currentPhotoNeutralUsedForCandidateSelection", false)
                .put("portableAutomaticSelectorArithmeticImplemented", true)
                .put("selectorImplementation", new JSONObject()
                        .put("type", "portable_Java_integer_recovered_CA9_fresh_selector_and_gain_conversion")
                        .put("firmwareDerived", true)
                        .put("firmwareDerivedScope", "selector_arithmetic_only_not_sensor_adapter_or_experiment_controls")
                        .put("portableImplementationValidated", true)
                        .put("validationScope", "offline_complete_cell_and_work_stage_reference_fixtures")
                        .put("originalFirmwareInstructionsExecutedOnDevice", false)
                        .put("thisFrameComparedWithOriginalHardware", false)
                        .put("sourceFunctions", new JSONArray().put("0x4000A688").put("0x40007B08")));
    }

    private static Assets assets() throws IOException {
        Assets value = cachedAssets;
        if (value != null) return value;
        synchronized (M10RWbShadow3Y.class) {
            value = cachedAssets;
            if (value == null) {
                value = new Assets(readAsset("m10r_wbselector3y/ca9_default_k3r.bin", 0x310, CONFIG_SHA),
                        readAsset("m10r_wbselector3y/classification_table3r.bin", 40000, TABLE_SHA));
                cachedAssets = value;
            }
        }
        return value;
    }

    private static byte[] readAsset(String name, int expectedSize, String expectedHash) throws IOException {
        byte[] data = new byte[expectedSize];
        try (InputStream input = PhotonCamera.getAssetLoader().getInputStream(name)) {
            int offset = 0;
            while (offset < expectedSize) {
                int count = input.read(data, offset, expectedSize - offset);
                if (count <= 0) throw new IOException("selector_asset_truncated");
                offset += count;
            }
            if (input.read() != -1) throw new IOException("selector_asset_size");
        }
        if (!expectedHash.equals(sha256(data))) throw new IOException("selector_asset_digest");
        return data;
    }

    private static double[] matrix(ColorSpaceTransform transform) {
        if (transform == null) return null;
        double[] out = new double[9];
        for (int row = 0; row < 3; row++) for (int col = 0; col < 3; col++)
            out[row * 3 + col] = transform.getElement(col, row).doubleValue();
        return out;
    }

    private static void requireMatrix(double[] m) {
        if (m == null || m.length != 9) throw new IllegalArgumentException("matrix_missing_or_wrong_shape");
        for (double v : m) if (!Double.isFinite(v)) throw new IllegalArgumentException("matrix_nonfinite");
    }

    private static double[] multiply(double[] a, double[] b) {
        double[] out = new double[9];
        for (int r = 0; r < 3; r++) for (int c = 0; c < 3; c++)
            out[3 * r + c] = a[3 * r] * b[c] + a[3 * r + 1] * b[3 + c] + a[3 * r + 2] * b[6 + c];
        return out;
    }

    private static double[] vector(double[] m, double[] v) {
        if (v == null || v.length != 3) throw new IllegalArgumentException("vector_shape");
        double[] out = new double[3];
        for (int r = 0; r < 3; r++) out[r] = m[3 * r] * v[0] + m[3 * r + 1] * v[1] + m[3 * r + 2] * v[2];
        return out;
    }

    private static double identityError(double[] m) {
        requireMatrix(m);
        double error = 0;
        for (int i = 0; i < 9; i++) error = Math.max(error, Math.abs(m[i] - (i % 4 == 0 ? 1 : 0)));
        return error;
    }

    private static double[] normalize(double[] v) {
        for (double value : v) if (!Double.isFinite(value) || value <= 0)
            throw new IllegalArgumentException("nonpositive_or_nonfinite_neutral");
        double[] out = {v[0] / v[1], 1, v[2] / v[1]};
        for (double value : out) if (!Double.isFinite(value) || value <= 0)
            throw new IllegalArgumentException("normalized_neutral_domain");
        return out;
    }

    private static JSONObject stageHashes(Map<String, byte[]> stages) throws JSONException {
        JSONObject out = new JSONObject();
        for (Map.Entry<String, byte[]> entry : stages.entrySet())
            out.put(entry.getKey(), new JSONObject().put("bytes", entry.getValue().length)
                    .put("sha256", sha256(entry.getValue())));
        return out;
    }

    private static String gridHash(JSONObject raw, int[] counts, double[] sums) throws JSONException {
        double[] black = doubles(raw.getJSONArray("blackByCfaPhase"), 4);
        ByteBuffer b = ByteBuffer.allocate(GRID_HASH_PREFIX.length + 64 + 4 * counts.length + 8 * sums.length)
                .order(ByteOrder.LITTLE_ENDIAN);
        b.put(GRID_HASH_PREFIX).putInt(raw.getInt("rawWidth")).putInt(raw.getInt("rawHeight"))
                .putInt(raw.getInt("cfa")).putInt(raw.getInt("white"))
                .putLong(raw.getLong("imageTimestampNs")).putLong(raw.getLong("frameNumber"));
        for (double v : black) b.putDouble(v);
        for (int v : counts) b.putInt(v);
        for (double v : sums) b.putDouble(v);
        return sha256(b.array());
    }

    private static byte[] recordBytes(long[][] records) {
        ByteBuffer b = ByteBuffer.allocate(records.length * 16).order(ByteOrder.LITTLE_ENDIAN);
        for (long[] record : records) for (long v : record) b.putInt((int) v);
        return b.array();
    }

    private static byte[] intBytes(int[] values) {
        ByteBuffer b = ByteBuffer.allocate(4 * values.length).order(ByteOrder.LITTLE_ENDIAN);
        for (int v : values) b.putInt(v);
        return b.array();
    }

    private static byte[] doubleBytes(double[] values) {
        ByteBuffer b = ByteBuffer.allocate(8 * values.length).order(ByteOrder.LITTLE_ENDIAN);
        for (double v : values) b.putDouble(v);
        return b.array();
    }

    private static int[] integers(JSONArray values, int size) throws JSONException {
        if (values.length() != size) throw new IllegalArgumentException("integer_array_shape");
        int[] out = new int[size];
        for (int i = 0; i < size; i++) {
            long v = values.getLong(i);
            if (v < Integer.MIN_VALUE || v > Integer.MAX_VALUE || values.getDouble(i) != v)
                throw new IllegalArgumentException("integer_array_domain");
            out[i] = (int) v;
        }
        return out;
    }

    private static double[] doubles(JSONArray values, int size) throws JSONException {
        if (values.length() != size) throw new IllegalArgumentException("double_array_shape");
        double[] out = new double[size];
        for (int i = 0; i < size; i++) {
            out[i] = values.getDouble(i);
            if (!Double.isFinite(out[i])) throw new IllegalArgumentException("double_array_nonfinite");
        }
        return out;
    }

    private static long sum(int[] values) {
        long sum = 0;
        for (int v : values) sum += v;
        return sum;
    }

    static String sha256(byte[] data) {
        try {
            return hex(MessageDigest.getInstance("SHA-256").digest(data));
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException("SHA-256_unavailable", impossible);
        }
    }

    private static String hex(byte[] data) {
        char[] out = new char[data.length * 2];
        char[] digits = "0123456789abcdef".toCharArray();
        for (int i = 0; i < data.length; i++) {
            int v = data[i] & 255;
            out[i * 2] = digits[v >>> 4];
            out[i * 2 + 1] = digits[v & 15];
        }
        return new String(out);
    }

    private static Object optional(Object value) {
        return value == null ? JSONObject.NULL : value;
    }
}
