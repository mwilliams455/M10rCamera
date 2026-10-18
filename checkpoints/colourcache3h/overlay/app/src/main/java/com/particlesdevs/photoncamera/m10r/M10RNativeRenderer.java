package com.particlesdevs.photoncamera.m10r;

import android.graphics.Bitmap;
import android.graphics.Matrix;
import android.graphics.Point;
import android.graphics.Rect;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.CaptureResult;
import android.hardware.camera2.params.BlackLevelPattern;
import android.hardware.camera2.params.ColorSpaceTransform;
import android.hardware.camera2.params.LensShadingMap;
import android.hardware.camera2.params.MeteringRectangle;
import android.util.Rational;
import android.util.SizeF;

import com.particlesdevs.photoncamera.processing.ImageFrame;
import com.particlesdevs.photoncamera.BuildConfig;
import com.particlesdevs.photoncamera.processing.render.Converter;

import org.json.JSONArray;
import org.json.JSONObject;
import org.opencv.android.OpenCVLoader;
import org.opencv.core.CvType;
import org.opencv.core.Mat;
import org.opencv.imgproc.Imgproc;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.ShortBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * CAPTURE1B integration renderer.
 *
 * One Xiaomi RAW frame -> Camera2 native dual-illuminant source model -> XYZ D50
 * -> synthetic M10-R camera domain -> promoted C CA9 neutral clip -> frozen M10-R
 * ColorSpec-equivalent linear sRGB -> sRGB transfer.
 *
 * This is intentionally Cobalt-free and CFA-aware. It is an integration candidate,
 * not a claim of exact Leica CA9 integer arithmetic, nonlinear tone, or final sensor calibration.
 */
public final class M10RNativeRenderer {
    static { System.loadLibrary("dngCreator"); }
    private static native void nativeProcessTile(
            short[] rgb16, int pixels, double inverseStorageScale,
            double[] srcToTargetCamera, int[] ca9, double[] targetToWorking,
            double[] workingToSrgb, int[] toneTable, int[] dgTable,
            int[] argbOut, long[] exactCounts, boolean cc1BeforeDg);
    private static native long nativeEdgePass(Bitmap bitmap, int iso);
    private static native long nativeInverseSrgbTransfer(Bitmap bitmap);

    public static final String SCHEMA =
            "m10rcam.capture1b.nativecamera2_xyz_d50.m10r_c_promoted.tonedg1b.v1";
    private static final double ASN_SCALE = 256.0;
    private static final int GAIN_MIN = 1;
    private static final int GAIN_MAX = 2000;
    private static final double[] D50_XY = {0.3457, 0.3585};

    // Validated M10-R target profile fixtures from RENDER_PARITY1A.
    // CM1 = Standard A (2856 K), CM2 = D65 (6504 K), XYZ -> M10-R camera.
    private static final double[] M10_CM_A = {
            0.71240234, -0.25000000, -0.04345703,
           -0.57373047,  1.55224609,  0.35961914,
           -0.10961914,  0.29223633,  0.77441406
    };
    private static final double[] M10_CM_D65 = {
            0.48779297, -0.12866211, -0.04858398,
           -0.58398438,  1.37011719,  0.22070313,
           -0.18041992,  0.33691406,  0.52514648
    };
    private static final double[] PCS_TO_INTERNAL = {
            1.3460, -0.2556, -0.0511,
           -0.5446,  1.5082,  0.0205,
            0.0000,  0.0000,  1.2123
    };
    // CC1MAP1A: factory STILL sRGB maps to CA9 mode 0. The recovered
    // field1 matrix is ProPhoto RGB -> sRGB (max standard-matrix error <5e-5).
    private static final double[] DEFAULT_SRGB_CC1 = {
            2.0341, -0.7273, -0.3067,
           -0.2288,  1.2317, -0.0029,
           -0.0086, -0.1533,  1.1619
    };
    private static final double[] BRADFORD = {
             0.8951,  0.2664, -0.1614,
            -0.7502,  1.7135,  0.0367,
             0.0389, -0.0685,  1.0296
    };
    private static final double[] BRADFORD_INV = inverse3(BRADFORD);

    // Leica M10-R firmware locus table already validated by M10RReferenceColorCore.
    // mired, u, v, slope, sqrt(1+slope^2)
    private static final double[][] LOCUS = {
        {0, .18006, .26352, -.24341, 1.029197954},
        {10,.18066,.26589,-.25479,1.031948615},{20,.18133,.26846,-.26876,1.035486329},
        {30,.18208,.27119,-.28539,1.039926657},{40,.18293,.27407,-.30470,1.045390879},
        {50,.18388,.27709,-.32675,1.052029259},{60,.18494,.28021,-.35156,1.059997374},
        {70,.18611,.28342,-.37915,1.069464690},{80,.18740,.28668,-.40955,1.080616122},
        {90,.18880,.28997,-.44278,1.093642596},{100,.19032,.29326,-.47888,1.108749771},
        {125,.19462,.30141,-.58204,1.157052532},{150,.19962,.30921,-.70471,1.223362654},
        {175,.20525,.31647,-.84901,1.311799520},{200,.21142,.32312,-1.01820,1.427140932},
        {225,.21807,.32909,-1.21680,1.574992775},{250,.22511,.33439,-1.45120,1.762379482},
        {275,.23247,.33904,-1.72980,1.998051060},{300,.24010,.34308,-2.06370,2.293219939},
        {325,.24792,.34655,-2.46810,2.662990350},{350,.25591,.34951,-2.96410,3.128240529},
        {375,.26400,.35200,-3.58140,3.718390238},{400,.27218,.35407,-4.36330,4.476425682},
        {425,.28039,.35577,-5.37620,5.468411693},{450,.28863,.35714,-6.72620,6.800129884},
        {475,.29685,.35823,-8.59550,8.653474461},{500,.30505,.35907,-11.3240,11.368068260},
        {525,.31320,.35968,-15.6280,15.659961170},{550,.32129,.36011,-23.3250,23.346426390},
        {575,.32931,.36038,-40.7700,40.782262080},{600,.33724,.36051,-116.450,116.454293600}
    };

    private static final M10RRenderedColor1A RENDERED_COLOR =
            new M10RRenderedColor1A(M10_CM_A, M10_CM_D65, LOCUS);

    private static volatile boolean OPEN_CV_READY = false;

    private static synchronized void ensureOpenCv() {
        if (OPEN_CV_READY) return;
        if (!OpenCVLoader.initDebug()) {
            throw new IllegalStateException("OpenCV Android initialization failed");
        }
        OPEN_CV_READY = true;
    }

    private M10RNativeRenderer() {}

    public static final class Result {
        public final Bitmap bitmap;
        public final JSONObject diagnostics;
        Result(Bitmap bitmap, JSONObject diagnostics) {
            this.bitmap = bitmap;
            this.diagnostics = diagnostics;
        }
    }

    private static final class SourceModel {
        final float[] sensorToXyzD50;
        final double[] sceneXy;
        final double sceneKelvin;
        final double interpolationFactor;
        SourceModel(float[] sensorToXyzD50, double[] sceneXy,
                    double sceneKelvin, double interpolationFactor) {
            this.sensorToXyzD50 = sensorToXyzD50;
            this.sceneXy = sceneXy;
            this.sceneKelvin = sceneKelvin;
            this.interpolationFactor = interpolationFactor;
        }
    }

    private static final class BayerFrame {
        final short[] data;
        final double storageScale;
        final long sourceWhiteClipCount;
        BayerFrame(short[] data, double storageScale, long sourceWhiteClipCount) {
            this.data = data;
            this.storageScale = storageScale;
            this.sourceWhiteClipCount = sourceWhiteClipCount;
        }
    }

    public static Result render(ImageFrame frame,
                                CameraCharacteristics characteristics,
                                CaptureResult captureResult,
                                CaptureRequest captureRequest,
                                int cameraRotation) throws Exception {
        long startNs = System.nanoTime();
        M10RStageTiming3E timing3E = new M10RStageTiming3E("frameMetadata", startNs);
        if (frame == null || frame.buffer == null) throw new IllegalArgumentException("RAW frame missing");
        if (characteristics == null || captureResult == null) {
            throw new IllegalArgumentException("Camera2 characteristics/result missing");
        }

        JSONObject d = new JSONObject();
        d.put("schema", SCHEMA);
        M10RExposureDelivery1K.append(d,characteristics,captureResult,captureRequest);
        if(captureRequest!=null&&captureRequest.getTag() instanceof M10RExposureReport1C)
            d.put("m10rExposure1C",new JSONObject(((M10RExposureReport1C)captureRequest.getTag()).json));
        d.put("captureMode", "single_frame_raw");
        d.put("sourceFrameCount", 1);
        d.put("hdrEnabled", false);
        d.put("stackingEnabled", false);
        d.put("photonPostPipelineUsed", false);
        d.put("cobaltRuntimeDependency", false);
        d.put("sourceModel", "Camera2_dual_illuminant_native_XYZ_D50");
        d.put("sourceMatrixConventionFix", "SOURCECM1A");
        d.put("sourceCamera2TransformConversion", "Photon_Converter.convertColorspaceTransform");
        d.put("sourceCamera2RawCopyElementsUsed", false);
        d.put("targetModel", "M10R_RENDER_PARITY1A_promoted_C");
        d.put("exactFirmwareParityClaimed", false);
        d.put("width", frame.width);
        d.put("height", frame.height);

        Integer cfaObj = characteristics.get(CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT);
        if (cfaObj == null || cfaObj < 0 || cfaObj > 3) {
            throw new IllegalStateException("unsupported/missing Bayer CFA: " + cfaObj);
        }
        int cfa = cfaObj;
        d.put("cfaPatternCode", cfa);
        d.put("cfaPatternName", cfaName(cfa));
        d.put("fourBayerPatternsSupported", true);
        // PORT1A: renderer authority is the active physical Camera2 sensor.
        // No zoom label, camera ID or per-lens Leica look is allowed downstream.
        d.put("portabilityRevision", "M10R_PORT1A");
        d.put("cfaAuthority", "physical_camera2_characteristics");
        d.put("resolvedSourceCfaPattern", cfa);
        d.put("sourceRawOriginX", 0);
        d.put("sourceRawOriginY", 0);
        d.put("sourceRawOriginProven", false);
        d.put("sourceRawOriginEvidence",
                "Photon_ImageFrame_full_RAW_buffer_origin0_assumption_pending_nonzero_crop_evidence");
        long tightBytes = (long) frame.width * (long) frame.height * 2L;
        d.put("sourceRawExpectedTightU16Bytes", tightBytes);
        d.put("sourceRawBufferCapacityBytes", frame.buffer.capacity());
        d.put("sourceRawBufferTightU16", (long) frame.buffer.capacity() == tightBytes);
        d.put("sourceAdapterSelection",
                "active_physical_Camera2_characteristics_and_capture_result");
        d.put("sourceAdapterPerPhysicalSensor", true);
        d.put("perLensPhotographicTuningApplied", false);
        d.put("perLensHsmApplied", false);
        d.put("cobaltHsmApplied", false);
        d.put("cobaltHueSatMapApplied", false);
        d.put("targetRendererLensIndependent", true);
        d.put("demosaicOutputChannelOrder", "RGB");
        d.put("demosaicChannelOrderFix", "RGBORDER1A");
        d.put("postDemosaicRedBlueSwapApplied", false);

// METERAREA1A_INSERT_BEGIN
        final M10RMeterArea1A.Bound meterAreaBound = M10RMeterArea1A.bind();
        timing3E.next("sourceColourPreparation");
// METERAREA1A_INSERT_END
        SourceModel source = buildSourceModel(characteristics, captureResult, d);
        double[] targetProfile = interpolateM10Profile(source.sceneKelvin);
        double[] sceneWhiteXyz = xyToXyz(source.sceneXy);
        double[] targetNeutralRaw = matVec(targetProfile, sceneWhiteXyz);
        if (!(targetNeutralRaw[1] > 0.0)) throw new IllegalStateException("M10-R synthetic neutral invalid");
        double[] targetAsn = {
                targetNeutralRaw[0] / targetNeutralRaw[1],
                1.0,
                targetNeutralRaw[2] / targetNeutralRaw[1]
        };
        int[] ca9 = recoverCa9Gains(targetAsn);

        double[] d50ToScene = mapWhite(D50_XY, source.sceneXy);
        double[] sceneToD50 = mapWhite(source.sceneXy, D50_XY);
        double[] srcToXyz = toDouble(source.sensorToXyzD50);
        double[] srcToTargetCamera = matMul(targetProfile, matMul(d50ToScene, srcToXyz));
        // WORKING1A: keep Leica's fixed internal basis on the input side of
        // nonlinear B2Y processing; apply output CC1 only after MEDIUM/DG.
        double[] targetToWorking = matMul(PCS_TO_INTERNAL,
                matMul(sceneToD50, inverse3(targetProfile)));
        double[] workingToSrgb = DEFAULT_SRGB_CC1.clone();

        M10RRenderedColor1A.Result renderedColor = RENDERED_COLOR.select(
                BuildConfig.M10R_RENDERED_COLOR1A, ca9, targetToWorking, workingToSrgb);
        targetToWorking = renderedColor.targetToWorking;
        workingToSrgb = renderedColor.workingToOutput;
        appendRenderedColor(d, renderedColor);

        d.put("sourceInterpolationFactor", source.interpolationFactor);
        d.put("sceneWhiteX", source.sceneXy[0]);
        d.put("sceneWhiteY", source.sceneXy[1]);
        d.put("sceneCctKelvinLeicaLocus", source.sceneKelvin);
        d.put("m10rSyntheticAsShotNeutral", json(targetAsn));
        d.put("m10rCa9Gains", json(ca9));
        d.put("rawHeadroomRetained", false);
        d.put("ca9NeutralClipEnabled", true);
        d.put("nonlinearRenderer", "TONEDG1B");
        d.put("nonlinearToneAsset", "MEDIUM");
        d.put("nonlinearOrder", "MEDIUM_THEN_DIFFERENTIAL_GAMMA");
        d.put("deKneeEnabled", false);
        d.put("interpolationGammaEnabled", false);
        d.put("toneAssetSha256", M10RToneDg1A.TONE_SHA256);
        d.put("differentialGammaExpandedSha256", M10RToneDg1A.DG_SHA256);
        d.put("b2yInputCoordinateMapping", "native_TCYC_and_RGB_coordinates_0_1_to_14bit_round_clamp");
        d.put("b2yLiveSignalNormalizationFrozen", false);
        d.put("toneArithmetic", "Q15_idx_x_shift1_truncate_rounding_not_hardware_frozen");
        d.put("nonlinearPlacement", "YA_TOPOLOGY1A_common_working_tone_then_RGB_DG_with_CC1_order_in_rendererOrder1A");
        d.put("workingBasisPlacementFix", "WORKING1A");
        d.put("cc0WorkingBasisPlacement", "pre_MEDIUM_DG");
        d.put("cc1Placement", (BuildConfig.M10R_COLOR_ORDER1A && renderedColor.applied) ? "after_common_MEDIUM_tone_before_RGB_DG" : "after_common_MEDIUM_tone_and_RGB_DG");
        d.put("workingBasisFirmwareEvidence", "v232_CC0_internal_tone_CC1_output");
        d.put("workingBasisPlacementExactHardwareParityClaimed", false);
        d.put("nonlinearApplicationMode", "YA_TOPOLOGY1A_common_tone_gain_then_independent_RGB_DG");
        d.put("nonlinearLumaProxy", "TCYC_Q12_1024_2661_410_for_native_common_tone");
        d.put("lookExperiment", "YA_TOPOLOGY1A_with_rendererOrder1A");
        d.put("b2yYcConvertMatrixQ12", "1224,2403,469;-691,-1357,2048;2048,-1715,-333");
        d.put("b2yYcConvertMatrixDivisor", 4096);
        d.put("b2yChromaPolicy", "native_common_tone_gain_preserves_working_RGB_ratios_then_RGB_DG;_YBLEND1B_counterfactual_only");
        d.put("yc2aMatrixCorrectionApplied", false);
        d.put("yc2aMetadataRole", "legacy_counterfactual_sampler_not_photographic_pixels");
        d.put("yc2aMatrixSource", "B2Y_record_0x0C_plus_IMG_System_driver_default_v123");
        d.put("yc2aMatrixRowSums", "4096,0,0");
        d.put("yc2aExactInverseApplied", false);
        d.put("yc2aYBlendStillDeferred", true);
        d.put("yc2aTrailingBoundaryPairsStillDeferred", true);
        d.put("b2yYBlendApplied", false);
        d.put("b2yLocalSixFieldConditioningApplied", false);
        d.put("toneCoordinateScalingStillProvisional", true);
        d.put("lumaGainStatisticSemantic", "legacy_Yc_mappedY_over_inputY_counterfactual_only_not_native_TCYC_tone_gain");
        d.put("nonlinearChromaticityPreservationIntent", false);
        d.put("commonToneGainPreservesWorkingRgbRatios", true);
        d.put("nonlinearPerChannelCurveApplied", true);

        double[] black = resolveBlack(characteristics, captureResult);
        int white = resolveWhite(characteristics, captureResult);
        timing3E.next("photographicRawResponseDiagnostic");
        // Actual photograph, including manual captures that bypass the automatic RAW probe.
        try { M10RRawResponse2S.append(d,frame,characteristics,captureResult,captureRequest); }
        catch(RuntimeException|LinkageError|OutOfMemoryError ignored) { /* diagnostic only */ }
        timing3E.next("rawNormalizationWithInlineMeterStats");
        LensShadingMap map = captureResult.get(CaptureResult.STATISTICS_LENS_SHADING_CORRECTION_MAP);
        BayerFrame normalized = normalizeBayer(
                frame.buffer, frame.width, frame.height, cfa, black, white, map, d);

        timing3E.next("whiteBalanceDiagnostic");
        // WBPROBE1D observes this capture only. Its proposal cannot change source,
        // reconstruction, renderer matrices, exposure metering or preview state.
        M10RWhiteBalanceDiagnostics1D.append(d, normalized.data, frame.width, frame.height,
                cfa, normalized.storageScale, source.sceneKelvin, characteristics, captureRequest, captureResult);

        timing3E.next("openCvInitialization");
        // Official OpenCV Android AAR from Maven Central supplies the Java API and
        // arm64-v8a/armeabi-v7a native runtime used only for deterministic EA demosaic.
        ensureOpenCv();
        d.put("openCvAndroidAar", "org.opencv:opencv:4.13.0");
        d.put("openCvPurpose", "single_frame_Bayer_EA_demosaic_only");

        Mat tileRaw = null;
        Mat tileBgr = null;
        Bitmap bitmap = null;
// AMAZE1A_INSERT_BEGIN
        M10RAmaze1A amaze = null;
        long amazeInitNs = 0L, amazeBandsNs = 0L;
// AMAZE1A_INSERT_END
        try {
// AMAZE1A_INSERT_BEGIN
            timing3E.next("amazeInitialization");
            long amazeStartNs = System.nanoTime();
            amaze = M10RAmaze1A.open(normalized.data, frame.width, frame.height,
                    cfa, normalized.storageScale, captureResult, d);
            amazeInitNs = System.nanoTime() - amazeStartNs;
            timing3E.next("outputAndScratchAllocation");
// AMAZE1A_INSERT_END
            final int rotation = ((cameraRotation % 360) + 360) % 360;
            final boolean quarterTurn = rotation == 90 || rotation == 270;
            final int outputWidth = quarterTurn ? frame.height : frame.width;
            final int outputHeight = quarterTurn ? frame.width : frame.height;
            bitmap = Bitmap.createBitmap(outputWidth, outputHeight, Bitmap.Config.ARGB_8888);
            final int blockRows = 256;
            final int demosaicHaloRows = 4;
            short[] bgr = new short[Math.multiplyExact(frame.width * blockRows, 3)];
            int[] argb = new int[frame.width * blockRows];
            int[] oriented = new int[frame.width * blockRows];
            short[] rawTileData = new short[Math.multiplyExact(frame.width, blockRows + 2*demosaicHaloRows + 2)];
            long[] neutralClipCounts = new long[3];
            M10RToneDg1A.Diagnostics toneDgStats = new M10RToneDg1A.Diagnostics();
            double inverseStorageScale = 1.0 / normalized.storageScale;
            final int[] nativeToneTable = M10RToneDg1A.nativeToneTable();
            final int[] nativeDgTable = M10RToneDg1A.nativeDgTable();
            final long[] nativeExactCounts = new long[32];
            final M10RColour3H colour3H = new M10RColour3H();
            final JSONArray gamutRowBands = new JSONArray();
            final long[] sampledNeutralClipScratch = new long[3];
            // REDTRACE1A sampled counters.  Arrays are final so the existing
            // tile loop can mutate them without adding any output-path state.
            // counts: 0=samples, 1..3=postYc RGB >1, 4..6=postCC1 RGB >1,
            // 7=CC1-created R>1, 8=R>1 already postYc and still >1 postCC1,
            // 9=postCC1 red-only >1, 10=postCC1 B<0, 11=postYc B<0.
            final long[] redTraceCounts = new long[12];
            // For samples where postCC1 R>1: mappedY,Cb,Cr,yRatio, postYc RGB,
            // postCC1 RGB, input Cb, input Cr.
            final double[] redTraceExcursionSums = new double[12];
            // REDTRACE1B: 3 classes x 4 luminance bins = 12 subsets.
            // Class 0=all, 1=warm relative chroma, 2=near-neutral relative chroma.
            // count columns: 0=samples, 1=postYc R>1, 2=postCC1 R>1,
            // 3=CC1-created R>1, 4=postCC1 red-only >1, 5=postCC1 B<0.
            final long[][] redTrace1BCounts = new long[12][6];
            // sum columns: mappedY, relCb, relCr, postYc RGB, postCC1 RGB,
            // and CC1 delta RGB.
            final double[][] redTrace1BSums = new double[12][12];
            // YBLEND1A proof sampler, same stride as REDTRACE1B.
            // 3 classes x 4 mapped-Y bins. Class 0=all; 1=warm by INPUT Cr/Y;
            // 2=near-neutral by INPUT Cb/Y and Cr/Y. Input-relative classes are
            // invariant to the experiment, making RENDER1M/1N comparisons clean.
            final long[][] yBlend1ACounts = new long[12][2];
            // sum columns: inputY, mappedY, oldScale, appliedScale, originalCb,
            // originalCr, reconstructedCb, reconstructedCr, postRecon R/G/B.
            final double[][] yBlend1ASums = new double[12][11];

            for (int y0 = 0; y0 < frame.height; y0 += blockRows) {
                timing3E.next("eaDemosaicAndTransfers");
                int rows = Math.min(blockRows, frame.height - y0);
                int shortCount = frame.width * rows * 3;
                if (bgr.length < shortCount) bgr = new short[shortCount];

                // Keep tile row 0 on the same Bayer phase as full-frame row 0.
                int srcY0 = Math.max(0, y0 - demosaicHaloRows);
                if ((srcY0 & 1) != 0) srcY0--;
                int srcY1 = Math.min(frame.height, y0 + rows + demosaicHaloRows);
                if ((srcY1 & 1) != 0 && srcY1 < frame.height) srcY1++;
                int tileRows = srcY1 - srcY0;
                int tileSamples = Math.multiplyExact(frame.width, tileRows);
                System.arraycopy(normalized.data, srcY0 * frame.width, rawTileData, 0, tileSamples);

                tileRaw = new Mat(tileRows, frame.width, CvType.CV_16UC1);
                tileRaw.put(0, 0, rawTileData);
                tileBgr = new Mat();
                Imgproc.cvtColor(tileRaw, tileBgr, demosaicCode(cfa));
                tileRaw.release();
                tileRaw = null;

                int centralRow = y0 - srcY0;
                tileBgr.get(centralRow, 0, bgr);
// AMAZE1A_INSERT_BEGIN
                timing3E.next("amazeBandReconstruction");
                long amazeBandStartNs = System.nanoTime();
                amaze.readBand(y0, rows, bgr);
                amazeBandsNs += System.nanoTime() - amazeBandStartNs;
                timing3E.next("nativeColourAndTone");
// AMAZE1A_INSERT_END
                int pixels = frame.width * rows;
                final long[] gamutBefore = nativeExactCounts.clone();
                if (!colour3H.process(bgr, pixels, inverseStorageScale,
                        srcToTargetCamera, ca9, targetToWorking, workingToSrgb,
                        nativeToneTable, nativeDgTable, argb, nativeExactCounts,
                        BuildConfig.M10R_COLOR_ORDER1A && renderedColor.applied)) {
                nativeProcessTile(
                        bgr, pixels, inverseStorageScale,
                        srcToTargetCamera, ca9, targetToWorking, workingToSrgb,
                        nativeToneTable, nativeDgTable, argb, nativeExactCounts,
                        BuildConfig.M10R_COLOR_ORDER1A && renderedColor.applied);
                }
                timing3E.next("bandDiagnosticJson");
                gamutRowBands.put(new JSONObject()
                        .put("sensorY0", y0).put("sourceRows", rows)
                        .put("mappedPixels", nativeExactCounts[10]-gamutBefore[10])
                        .put("preHighRGB", json(new long[]{nativeExactCounts[15]-gamutBefore[15], nativeExactCounts[16]-gamutBefore[16], nativeExactCounts[17]-gamutBefore[17]}))
                        .put("preLowRGB", json(new long[]{nativeExactCounts[12]-gamutBefore[12], nativeExactCounts[13]-gamutBefore[13], nativeExactCounts[14]-gamutBefore[14]})));

                timing3E.next("legacyJavaDiagnosticSampling");
                // RENDERPERF3F: optional legacy research distributions. Output pixels
                // and full-frame native counters have already been produced above.
                if (BuildConfig.M10R_LEGACY_DIAGNOSTICS3F) {
                for (int i = 0; i < pixels; i += 64) {
                    double sr = (bgr[i * 3] & 0xffff) / 65535.0 * inverseStorageScale;
                    double sg = (bgr[i * 3 + 1] & 0xffff) / 65535.0 * inverseStorageScale;
                    double sb = (bgr[i * 3 + 2] & 0xffff) / 65535.0 * inverseStorageScale;
                    double tr = srcToTargetCamera[0]*sr + srcToTargetCamera[1]*sg + srcToTargetCamera[2]*sb;
                    double tg = srcToTargetCamera[3]*sr + srcToTargetCamera[4]*sg + srcToTargetCamera[5]*sb;
                    double tb = srcToTargetCamera[6]*sr + srcToTargetCamera[7]*sg + srcToTargetCamera[8]*sb;
                    tr = ca9Clip(tr, ca9[0], sampledNeutralClipScratch, 0);
                    tg = ca9Clip(tg, ca9[1], sampledNeutralClipScratch, 1);
                    tb = ca9Clip(tb, ca9[2], sampledNeutralClipScratch, 2);
                    double wr = targetToWorking[0]*tr + targetToWorking[1]*tg + targetToWorking[2]*tb;
                    double wg = targetToWorking[3]*tr + targetToWorking[4]*tg + targetToWorking[5]*tb;
                    double wb = targetToWorking[6]*tr + targetToWorking[7]*tg + targetToWorking[8]*tb;
                    toneDgStats.preTone.add(wr, wg, wb);
                    double ycY = (1224.0*wr + 2403.0*wg + 469.0*wb) / 4096.0;
                    double ycCb = (-691.0*wr - 1357.0*wg + 2048.0*wb) / 4096.0;
                    double ycCr = (2048.0*wr - 1715.0*wg - 333.0*wb) / 4096.0;
                    int xy = M10RToneDg1A.toInputLumaNoStats(ycY);
                    toneDgStats.toneInput.add(xy, xy, xy);
                    int my = M10RToneDg1A.medium(xy);
                    toneDgStats.postTone.add(my, my, my);
                    int dy = M10RToneDg1A.dgLumaNoStats(my);
                    toneDgStats.postDg.add(dy, dy, dy);
                    double mappedY = dy / (double)M10RToneDg1A.DG_OUT_MAX;
                    double yRatio = (ycY > 1.0e-12) ? (mappedY / ycY) : 0.0;
                    toneDgStats.lumaGain.add(yRatio);
                    // RENDER1N YBLEND1A: mappedY is unchanged. Only the chroma
                    // carrier scale moves halfway from absolute (1.0) to the
                    // frozen RENDER1M relative scale (yRatio). Preserve the old
                    // zero-Y guard so near-black behavior is not broadened.
                    // RENDER1Q YBLEND1B_K035: preserve the same mappedY and
                    // zero-Y guard, but inherit only 35% of tone gain above unity.
                    double yBlendChromaScale = (ycY > 1.0e-12) ? (1.0 + 0.35 * (yRatio - 1.0)) : 0.0;
                    double mappedCb = ycCb * yBlendChromaScale;
                    double mappedCr = ycCr * yBlendChromaScale;
                    double nr = 1.000000000000*mappedY - 0.001043337611*mappedCb + 1.401991725445*mappedCr;
                    double ng = 1.000000000000*mappedY - 0.345114690199*mappedCb - 0.714098755336*mappedCr;
                    double nb = 1.000000000000*mappedY + 1.770975790582*mappedCb - 0.000124867533*mappedCr;
                    double outR = workingToSrgb[0]*nr + workingToSrgb[1]*ng + workingToSrgb[2]*nb;
                    double outG = workingToSrgb[3]*nr + workingToSrgb[4]*ng + workingToSrgb[5]*nb;
                    double outB = workingToSrgb[6]*nr + workingToSrgb[7]*ng + workingToSrgb[8]*nb;

                    // REDTRACE1A: diagnostics only.  The native output pixels are
                    // already formed above by nativeProcessTile; none of these
                    // counters feed back into rendering.
                    redTraceCounts[0]++;
                    if (nr > 1.0) redTraceCounts[1]++;
                    if (ng > 1.0) redTraceCounts[2]++;
                    if (nb > 1.0) redTraceCounts[3]++;
                    if (outR > 1.0) redTraceCounts[4]++;
                    if (outG > 1.0) redTraceCounts[5]++;
                    if (outB > 1.0) redTraceCounts[6]++;
                    if (outR > 1.0 && nr <= 1.0) redTraceCounts[7]++;
                    if (outR > 1.0 && nr > 1.0) redTraceCounts[8]++;
                    if (outR > 1.0 && outG <= 1.0 && outB <= 1.0) redTraceCounts[9]++;
                    if (outB < 0.0) redTraceCounts[10]++;
                    if (nb < 0.0) redTraceCounts[11]++;
                    if (outR > 1.0) {
                        redTraceExcursionSums[0] += mappedY;
                        redTraceExcursionSums[1] += mappedCb;
                        redTraceExcursionSums[2] += mappedCr;
                        redTraceExcursionSums[3] += yRatio;
                        redTraceExcursionSums[4] += nr;
                        redTraceExcursionSums[5] += ng;
                        redTraceExcursionSums[6] += nb;
                        redTraceExcursionSums[7] += outR;
                        redTraceExcursionSums[8] += outG;
                        redTraceExcursionSums[9] += outB;
                        redTraceExcursionSums[10] += ycCb;
                        redTraceExcursionSums[11] += ycCr;
                    }
                    // YBLEND1A diagnostics classify warm/neutral on the PRE-MAP
                    // Yc ratios, so membership does not move merely because this
                    // experiment changed the chroma carrier scale.
                    final double ybInputRelCb = Math.abs(ycY) > 1.0e-9 ? ycCb / ycY : 0.0;
                    final double ybInputRelCr = Math.abs(ycY) > 1.0e-9 ? ycCr / ycY : 0.0;
                    final int ybBin = mappedY < 0.18 ? 0 : (mappedY < 0.40 ? 1 : (mappedY < 0.75 ? 2 : 3));
                    final boolean ybWarm = ycY > 0.03 && ybInputRelCr >= 0.04;
                    final boolean ybNeutral = ycY > 0.03 && Math.abs(ybInputRelCb) <= 0.02 && Math.abs(ybInputRelCr) <= 0.02;
                    for (int ybCls = 0; ybCls < 3; ybCls++) {
                        if (ybCls == 1 && !ybWarm) continue;
                        if (ybCls == 2 && !ybNeutral) continue;
                        final int ybIdx = ybCls * 4 + ybBin;
                        final long[] ybc = yBlend1ACounts[ybIdx];
                        final double[] ybs = yBlend1ASums[ybIdx];
                        ybc[0]++;
                        if (yBlendChromaScale + 1.0e-12 < yRatio) ybc[1]++;
                        ybs[0] += ycY;
                        ybs[1] += mappedY;
                        ybs[2] += yRatio;
                        ybs[3] += yBlendChromaScale;
                        ybs[4] += ycCb;
                        ybs[5] += ycCr;
                        ybs[6] += mappedCb;
                        ybs[7] += mappedCr;
                        ybs[8] += nr;
                        ybs[9] += ng;
                        ybs[10] += nb;
                    }

                    // REDTRACE1B: classify by mapped luminance and relative
                    // chroma so a clipped/near-white window cannot overwhelm
                    // the portrait/midtone discriminator. Relative chroma is
                    // stable under the current Yc policy because Cb/Cr and Y
                    // are scaled by the same yRatio. Diagnostics only.
                    final double relCb1B = Math.abs(mappedY) > 1.0e-9 ? mappedCb / mappedY : 0.0;
                    final double relCr1B = Math.abs(mappedY) > 1.0e-9 ? mappedCr / mappedY : 0.0;
                    final int yBin1B = mappedY < 0.18 ? 0 : (mappedY < 0.40 ? 1 : (mappedY < 0.75 ? 2 : 3));
                    final boolean warm1B = mappedY > 0.03 && relCr1B >= 0.04;
                    final boolean neutral1B = mappedY > 0.03 && Math.abs(relCb1B) <= 0.02 && Math.abs(relCr1B) <= 0.02;
                    final double dR1B = outR - nr;
                    final double dG1B = outG - ng;
                    final double dB1B = outB - nb;
                    for (int cls1B = 0; cls1B < 3; cls1B++) {
                        if (cls1B == 1 && !warm1B) continue;
                        if (cls1B == 2 && !neutral1B) continue;
                        int idx1B = cls1B * 4 + yBin1B;
                        long[] bc1B = redTrace1BCounts[idx1B];
                        double[] bs1B = redTrace1BSums[idx1B];
                        bc1B[0]++;
                        if (nr > 1.0) bc1B[1]++;
                        if (outR > 1.0) bc1B[2]++;
                        if (outR > 1.0 && nr <= 1.0) bc1B[3]++;
                        if (outR > 1.0 && outG <= 1.0 && outB <= 1.0) bc1B[4]++;
                        if (outB < 0.0) bc1B[5]++;
                        bs1B[0] += mappedY;
                        bs1B[1] += relCb1B;
                        bs1B[2] += relCr1B;
                        bs1B[3] += nr;
                        bs1B[4] += ng;
                        bs1B[5] += nb;
                        bs1B[6] += outR;
                        bs1B[7] += outG;
                        bs1B[8] += outB;
                        bs1B[9] += dR1B;
                        bs1B[10] += dG1B;
                        bs1B[11] += dB1B;
                    }
                    toneDgStats.preSrgb.add(outR, outG, outB);
                }
                }
                timing3E.next("tileReleaseAndOrientedBitmapWrite");
                tileBgr.release();
                tileBgr = null;

                // Write directly into final orientation: no second full-size bitmap.
                if (rotation == 0) {
                    bitmap.setPixels(argb, 0, frame.width, 0, y0, frame.width, rows);
                } else if (rotation == 180) {
                    for (int sy=0; sy<rows; sy++) {
                        int dstRow = rows - 1 - sy;
                        int so = sy * frame.width;
                        int dst = dstRow * frame.width;
                        for (int x=0; x<frame.width; x++) oriented[dst + (frame.width - 1 - x)] = argb[so + x];
                    }
                    bitmap.setPixels(oriented, 0, frame.width, 0, frame.height - y0 - rows, frame.width, rows);
                } else if (rotation == 90) {
                    int stripeX = frame.height - y0 - rows;
                    for (int sy=0; sy<rows; sy++) {
                        int localX = rows - 1 - sy;
                        int so = sy * frame.width;
                        for (int x=0; x<frame.width; x++) oriented[x * rows + localX] = argb[so + x];
                    }
                    bitmap.setPixels(oriented, 0, rows, stripeX, 0, rows, frame.width);
                } else if (rotation == 270) {
                    int stripeX = y0;
                    for (int sy=0; sy<rows; sy++) {
                        int so = sy * frame.width;
                        for (int x=0; x<frame.width; x++) oriented[(frame.width - 1 - x) * rows + sy] = argb[so + x];
                    }
                    bitmap.setPixels(oriented, 0, rows, stripeX, 0, rows, frame.width);
                } else {
                    throw new IllegalStateException("unsupported camera rotation: " + rotation);
                }
            }
            timing3E.next("diagnosticSummaryJson");
            neutralClipCounts[0] = nativeExactCounts[0];
            neutralClipCounts[1] = nativeExactCounts[1];
            neutralClipCounts[2] = nativeExactCounts[2];
            toneDgStats.lumaInputLow = nativeExactCounts[3];
            toneDgStats.lumaInputHigh = nativeExactCounts[4];
            toneDgStats.lumaInputNonFinite = nativeExactCounts[5];
            toneDgStats.lumaDgLow = nativeExactCounts[6];
            toneDgStats.lumaDgHigh = nativeExactCounts[7];
            d.put("neutralDomainClipCounts", json(neutralClipCounts));
            d.put("sourceWhiteLevelClipCount", normalized.sourceWhiteClipCount);
            d.put("toneDg1aSignalStatistics", annotateSignalStatistics2X(
                    BuildConfig.M10R_LEGACY_DIAGNOSTICS3F ? toneDgStats.json() : new JSONObject(),
                    nativeExactCounts, BuildConfig.M10R_LEGACY_DIAGNOSTICS3F));
            if (BuildConfig.M10R_LEGACY_DIAGNOSTICS3F) {
            JSONObject redTrace = new JSONObject();
            long rtN = redTraceCounts[0];
            long rtR = redTraceCounts[4];
            redTrace.put("sampleCount", rtN);
            redTrace.put("postYcWorkingAbove1RGB", json(new long[]{redTraceCounts[1], redTraceCounts[2], redTraceCounts[3]}));
            redTrace.put("postCc1Above1RGB", json(new long[]{redTraceCounts[4], redTraceCounts[5], redTraceCounts[6]}));
            redTrace.put("cc1CreatedRedAbove1Count", redTraceCounts[7]);
            redTrace.put("redAlreadyAbove1PostYcAndStillAbovePostCc1Count", redTraceCounts[8]);
            redTrace.put("postCc1RedOnlyAbove1Count", redTraceCounts[9]);
            redTrace.put("postCc1BlueBelow0Count", redTraceCounts[10]);
            redTrace.put("postYcBlueBelow0Count", redTraceCounts[11]);
            redTrace.put("postCc1RedAbove1Fraction", rtN > 0 ? redTraceCounts[4] / (double)rtN : 0.0);
            redTrace.put("cc1CreatedShareOfPostCc1RedAbove1", rtR > 0 ? redTraceCounts[7] / (double)rtR : 0.0);
            redTrace.put("redOnlyShareOfPostCc1RedAbove1", rtR > 0 ? redTraceCounts[9] / (double)rtR : 0.0);
            redTrace.put("cc1Matrix", java.util.Arrays.toString(workingToSrgb));
            redTrace.put("cc1MatrixRowMajor", json(workingToSrgb));
            redTrace.put("stage", "legacy_Yc_YBLEND1B_post_CC1_counterfactual_not_actual_native_output");
            redTrace.put("cc1RedEquation", "outR=("+workingToSrgb[0]+")*postYcR+("+workingToSrgb[1]+")*postYcG+("+workingToSrgb[2]+")*postYcB");
            JSONObject exc = new JSONObject();
            exc.put("count", rtR);
            if (rtR > 0) {
                exc.put("meanMappedY", redTraceExcursionSums[0] / rtR);
                exc.put("meanMappedCb", redTraceExcursionSums[1] / rtR);
                exc.put("meanMappedCr", redTraceExcursionSums[2] / rtR);
                exc.put("meanYRatio", redTraceExcursionSums[3] / rtR);
                exc.put("meanPostYcR", redTraceExcursionSums[4] / rtR);
                exc.put("meanPostYcG", redTraceExcursionSums[5] / rtR);
                exc.put("meanPostYcB", redTraceExcursionSums[6] / rtR);
                exc.put("meanPostCc1R", redTraceExcursionSums[7] / rtR);
                exc.put("meanPostCc1G", redTraceExcursionSums[8] / rtR);
                exc.put("meanPostCc1B", redTraceExcursionSums[9] / rtR);
                exc.put("meanInputCb", redTraceExcursionSums[10] / rtR);
                exc.put("meanInputCr", redTraceExcursionSums[11] / rtR);
            }
            redTrace.put("redExcursionSubset", exc);
            redTrace.put("diagnosticOnly", true);
            d.put("redTrace1A", redTrace);
            JSONObject redTrace1B = new JSONObject();
            redTrace1B.put("sampleStride", 64);
            redTrace1B.put("diagnosticOnly", true);
            redTrace1B.put("photographicOutputStillCc1Bypassed", false);
            redTrace1B.put("counterfactualCc1StillEvaluated", true);
            redTrace1B.put("role", "legacy_Yc_YBLEND1B_counterfactual_not_actual_native_output");
            redTrace1B.put("actualPreGamutCc1Evaluated", false);
            redTrace1B.put("counterfactualRender1SAnchorEvaluated", true);
            redTrace1B.put("lumaBinEdges", "0.18,0.40,0.75");
            redTrace1B.put("relativeChromaBasis", "mappedCb_over_mappedY_and_mappedCr_over_mappedY");
            redTrace1B.put("warmThresholdRelCr", 0.04);
            redTrace1B.put("neutralAbsRelCbCrThreshold", 0.02);
            String[] rt1bClassNames = new String[]{"all", "warmRelCr", "neutralRelChroma"};
            String[] rt1bBinNames = new String[]{"shadow", "lowMid", "midHigh", "highlight"};
            for (int cls1B = 0; cls1B < 3; cls1B++) {
                JSONObject classJson1B = new JSONObject();
                for (int bin1B = 0; bin1B < 4; bin1B++) {
                    int idx1B = cls1B * 4 + bin1B;
                    long[] bc1B = redTrace1BCounts[idx1B];
                    double[] bs1B = redTrace1BSums[idx1B];
                    long n1B = bc1B[0];
                    JSONObject binJson1B = new JSONObject();
                    binJson1B.put("count", n1B);
                    binJson1B.put("postYcRedAbove1Count", bc1B[1]);
                    binJson1B.put("postCc1RedAbove1Count", bc1B[2]);
                    binJson1B.put("cc1CreatedRedAbove1Count", bc1B[3]);
                    binJson1B.put("postCc1RedOnlyAbove1Count", bc1B[4]);
                    binJson1B.put("postCc1BlueBelow0Count", bc1B[5]);
                    binJson1B.put("cc1CreatedRedAbove1FractionOfSubset", n1B > 0 ? bc1B[3] / (double)n1B : 0.0);
                    if (n1B > 0) {
                        binJson1B.put("meanMappedY", bs1B[0] / n1B);
                        binJson1B.put("meanRelCb", bs1B[1] / n1B);
                        binJson1B.put("meanRelCr", bs1B[2] / n1B);
                        binJson1B.put("meanPostYcR", bs1B[3] / n1B);
                        binJson1B.put("meanPostYcG", bs1B[4] / n1B);
                        binJson1B.put("meanPostYcB", bs1B[5] / n1B);
                        binJson1B.put("meanCounterfactualRender1SPostCc1R", bs1B[6] / n1B);
                        binJson1B.put("meanCounterfactualRender1SPostCc1G", bs1B[7] / n1B);
                        binJson1B.put("meanCounterfactualRender1SPostCc1B", bs1B[8] / n1B);
                        binJson1B.put("meanCc1DeltaR", bs1B[9] / n1B);
                        binJson1B.put("meanCc1DeltaG", bs1B[10] / n1B);
                        binJson1B.put("meanCc1DeltaB", bs1B[11] / n1B);
                    }
                    classJson1B.put(rt1bBinNames[bin1B], binJson1B);
                }
                redTrace1B.put(rt1bClassNames[cls1B], classJson1B);
            }
            d.put("redTrace1B", redTrace1B);
            JSONObject yBlend1A = new JSONObject();
            yBlend1A.put("sampleStride", 64);
            yBlend1A.put("experimentalOnly", true);
            yBlend1A.put("role", "legacy_Yc_YBLEND1B_counterfactual_only_not_used_as_native_lightness_anchor");
            yBlend1A.put("firmwareFormulaClaim", false);
            yBlend1A.put("mappedYFormula", "dy_over_DG_OUT_MAX_UNCHANGED_FROM_RENDER1M");
            yBlend1A.put("oldChromaScaleFormula", "mappedY_over_inputY");
            yBlend1A.put("appliedChromaScaleFormula", "1_plus_0.35_times_(mappedY_over_inputY_minus_1)");
            yBlend1A.put("probeK", 0.35);
            yBlend1A.put("zeroYGuard", "scale_zero_when_inputY_le_1e-12");
            yBlend1A.put("classificationBasis", "pre_map_input_Cb_over_Y_and_Cr_over_Y");
            yBlend1A.put("lumaBinEdges", "0.18,0.40,0.75");
            String[] ybClassNames = new String[]{"all", "warmInputRelCr", "neutralInputRelChroma"};
            String[] ybBinNames = new String[]{"shadow", "lowMid", "midHigh", "highlight"};
            for (int ybCls = 0; ybCls < 3; ybCls++) {
                JSONObject ybClass = new JSONObject();
                for (int ybBin = 0; ybBin < 4; ybBin++) {
                    final int ybIdx = ybCls * 4 + ybBin;
                    final long[] ybc = yBlend1ACounts[ybIdx];
                    final double[] ybs = yBlend1ASums[ybIdx];
                    final long yn = ybc[0];
                    JSONObject ybj = new JSONObject();
                    ybj.put("count", yn);
                    ybj.put("chromaScaleReducedVsRender1MCount", ybc[1]);
                    ybj.put("chromaScaleReducedVsRender1MFraction", yn > 0 ? ybc[1] / (double)yn : 0.0);
                    if (yn > 0) {
                        ybj.put("meanInputY", ybs[0] / yn);
                        ybj.put("meanMappedY", ybs[1] / yn);
                        ybj.put("meanRender1MChromaScale", ybs[2] / yn);
                        ybj.put("meanYBlend1BAppliedChromaScale", ybs[3] / yn);
                        ybj.put("meanOriginalCb", ybs[4] / yn);
                        ybj.put("meanOriginalCr", ybs[5] / yn);
                        ybj.put("meanReconstructedCb", ybs[6] / yn);
                        ybj.put("meanReconstructedCr", ybs[7] / yn);
                        ybj.put("meanPostReconR", ybs[8] / yn);
                        ybj.put("meanPostReconG", ybs[9] / yn);
                        ybj.put("meanPostReconB", ybs[10] / yn);
                    }
                    ybClass.put(ybBinNames[ybBin], ybj);
                }
                yBlend1A.put(ybClassNames[ybCls], ybClass);
            }
            d.put("yBlend1B", yBlend1A);
            } else {
                for (String key : new String[]{"redTrace1A", "redTrace1B", "yBlend1B"}) {
                    d.put(key, new JSONObject().put("available", false)
                            .put("status", "disabled_legacy_research_sampling_RENDERPERF3F")
                            .put("diagnosticOnly", true).put("affectsPixels", false));
                }
            }
            d.put("renderPerf3F", new JSONObject().put("revision", "M10R_RENDERPERF3F")
                    .put("lensShading", "exact_horizontal_interpolation_two_row_cache")
                    .put("legacyResearchSamplingEnabled", BuildConfig.M10R_LEGACY_DIAGNOSTICS3F)
                    .put("nativeFullFrameCountersEnabled", true));

// AMAZE1A_INSERT_BEGIN
            timing3E.next("amazeRelease");
            amaze.close();
            amaze = null;
            timing3E.next("outputMetadata");
            d.put("amazeInitMs", amazeInitNs / 1_000_000.0);
            d.put("amazeBandsMs", amazeBandsNs / 1_000_000.0);
// AMAZE1A_INSERT_END
            d.put("renderStabilityFix", "STABILITY3_NATIVE1_FOUR_THREAD_PIXEL_CORE");
            d.put("nativeColour3H", colour3H.diagnostics());
            d.put("nativePixelCore", true);
            d.put("nativePixelCoreThreads", 4);
            d.put("nativePixelCoreLibrary", "m10rcolour3h_with_dngCreator_fallback_see_nativeColour3H");
            d.put("diagnosticSamplingEnabled", BuildConfig.M10R_LEGACY_DIAGNOSTICS3F);
            d.put("diagnosticSamplingStride", BuildConfig.M10R_LEGACY_DIAGNOSTICS3F ? 64 : JSONObject.NULL);
            d.put("diagnosticSamplingAffectsPixels", false);
            d.put("demosaicTileRows", blockRows);
            d.put("demosaicHaloRows", demosaicHaloRows);
            d.put("fullFrameBgrMatAllocated", false);
            d.put("secondRotationBitmapAllocated", false);
            d.put("cameraRotationDegrees", rotation);
            // DETAIL3D: bounded opt-in trial of the retained native pass, after
            // the accepted colour output. Its bitmap-domain interpretation is
            // experimental; no native coefficients or colour stages change.
            timing3E.next("detail3D");
            final Bitmap detailBitmap = bitmap;
            M10RDetail3D.Result detail3D = M10RDetail3D.run(BuildConfig.M10R_DETAIL3D,
                    captureResult.get(CaptureResult.SENSOR_SENSITIVITY),
                    iso -> nativeEdgePass(detailBitmap, iso));
            int edgeIso = detail3D.iso;
            boolean edgeExecuted = detail3D.executed;
            long edgeAffectedPixels = detail3D.affectedPixels;
            double edgeElapsedMs = detail3D.elapsedMs;
            timing3E.next("outputMetadata");

            // TRANSFER1A: preserve the entire WORKING1A + EDGE1A path, then
            // cancel only the final textbook sRGB coding before JPEG save.
            // NATIVEOUT1A: no separate display-transfer pass.  The native
            // pixel core now publishes post-CC1 values directly with 8-bit
            // clamp/round, followed by TONECAL1A and the optional DETAIL3D trial.
            long transferPixels = 0L;
            double transferElapsedMs = 0.0;
            d.put("renderLook", "RENDER2G_YATOPOLOGY1A_GAMUT1A_TONECAL1A_MFM1D"
                    + (edgeExecuted ? "_DETAIL3D_EXPERIMENTAL" : "_EDGE0A")
                    + (renderedColor.applied ? "_RENDEREDCC1A" : ""));
            d.put("colorRecon1A", new JSONObject()
                    .put("enabled", false)
                    .put("bypassedBy", "YA_TOPOLOGY1A")
                    .put("reason", "public_reference_native_validation_preferred_firmware_shaped_RGB_topology")
                    .put("validationRunId", "36244571736"));
            d.put("yaTopology1A", new JSONObject()
                    .put("enabled", true)
                    .put("publicReferenceValidated", true)
                    .put("validationRunId", "36244571736")
                    .put("validationCommit", "6852a749a9882d65083c81366d98d84a27b94a2c")
                    .put("toneLuma", "TCYC_Q12_1024_2661_410")
                    .put("toneApplication", "common_gain_preserve_working_RGB_ratios")
                    .put("differentialGammaApplication", "same_recovered_curve_independently_R_G_B")
                    .put("mainLuminance", "Ya_post_RGB_nonlinear")
                    .put("mainlineYbContribution", 0.0)
                    .put("empiricalChromaKApplied", false)
                    .put("exactAsicGammaBankRoutingClaimed", false)
                    .put("gamut1AChanged", false)
                    .put("toneCal1AChanged", false)
                    .put("mfm1bChanged", false)
                    .put("captureExposureChanged", false)
                    .put("whiteBalanceChanged", false)
                    .put("sourceProcessingChanged", false));
            d.put("nativeExactCountsFirst24Semantic",
                    "0_to_2_CA9;_3_to_5_combined_TCYC_and_RGB_input_checks;_6_to_7_RGB_DG_index_checks;_8_to_23_GAMUT1A;_24_to_31_reserved_zero");
            d.put("outputGamut1A", new JSONObject()
                    .put("enabled", true).put("empiricalNotFirmware", true)
                    .put("stage", (BuildConfig.M10R_COLOR_ORDER1A && renderedColor.applied) ? "post_RGB_DG_before_direct_ARGB8_then_TONECAL1A" : "post_CC1_after_RGB_DG_before_direct_ARGB8_then_TONECAL1A")
                    .put("method", "clipped_baseline_code_luma_anchor_unclipped_RGB_opponent_ray")
                    .put("coordinate", (BuildConfig.M10R_COLOR_ORDER1A && renderedColor.applied) ? "DG_output_divided_by_16383_no_additional_sRGB_OETF" : "CC1_of_normalized_DG_output_not_asserted_linear_light")
                    .put("perceptualHueOrLstarPreservationClaimed", false)
                    .put("inGamutPixelPolicy", "exact_bypass")
                    .put("captureExposureChanged", false).put("whiteBalanceChanged", false)
                    .put("toneCurveChanged", false).put("chromaKChanged", false)
                    .put("chromaReconstructionChanged", true)
                    .put("sampleStride", 1).put("nativeExactPixelCounts", true)
                    .put("totalPixels", nativeExactCounts[8])
                    .put("inGamutBypassPixels", nativeExactCounts[9])
                    .put("mappedPixels", nativeExactCounts[10])
                    .put("nonFiniteFallbackPixels", nativeExactCounts[11])
                    .put("preMapBelowZeroRGB", json(new long[]{nativeExactCounts[12],nativeExactCounts[13],nativeExactCounts[14]}))
                    .put("preMapAboveOneRGB", json(new long[]{nativeExactCounts[15],nativeExactCounts[16],nativeExactCounts[17]}))
                    .put("postMapBelowZeroRGB", json(new long[]{nativeExactCounts[18],nativeExactCounts[19],nativeExactCounts[20]}))
                    .put("postMapAboveOneRGB", json(new long[]{nativeExactCounts[21],nativeExactCounts[22],nativeExactCounts[23]}))
                    .put("countPartitionValid", nativeExactCounts[8]==nativeExactCounts[9]+nativeExactCounts[10]+nativeExactCounts[11])
                    .put("framePixelCountValid", nativeExactCounts[8]==(long)frame.width*frame.height)
                    .put("rowBandsCoordinate", "source_sensor_before_cameraRotationDegrees")
                    .put("rowBands", gamutRowBands));
            d.put("toneCal1A", new JSONObject()
                    .put("enabled", true)
                    .put("model", "fixed_smooth_Lstar_residual_v1")
                    .put("stage", "after_GAMUT1A_ARGB8_publication_same_TONECAL1A_curve")
                    .put("trainingScenes", "PhotographyBlog_M10R_01_03_05_neutral_only")
                    .put("coefficients", new JSONArray(new double[]{-3.229545380578171,-0.25128474545011054,-0.17860038493017244}))
                    .put("empiricalNotFirmware", true)
                    .put("captureExposureChanged", false)
                    .put("whiteBalanceChanged", false)
                    .put("chromaGainChanged", false)
                    .put("upstreamDiagnosticsArePreCorrection", true));
            d.put("yBlend1BProbeK", 0.35);
            d.put("yBlend1BOnlyPhotographicVariable", false);
            d.put("cc1MappingFix", "CC1MAP1A");
            d.put("cc1FactoryStillColorSpace", "sRGB");
            d.put("cc1Ca9ModeIndex", 0);
            d.put("cc1Semantic", "ProPhoto_RGB_to_sRGB");
            d.put("cc1Mode1PriorMislabel", "ProPhoto_RGB_to_AdobeRGB");
            d.put("cc1MappingFirmwareEvidence", "v231_factory_sRGB_to_CA9_mode0_plus_v230_field1_standard_matrix_closure");
            d.put("photographicConvergenceExperiment", "YA_TOPOLOGY1A_with_rendererOrder1A_no_COLORRECON1A");
            d.put("cc1RestoreOnlyPhotographicVariable", false);
            d.put("chromaReconstructionExperiment", "YA_TOPOLOGY1A");
            d.put("yBlend1BExperimentalApplied", false);
            d.put("yBlend1BPhotographicRole", "removed_from_YA_TOPOLOGY1A_photographic_path");
            d.put("yBlend1BFirmwareClaim", false);
            d.put("yBlend1BK", 0.35);
            d.put("yBlend1BInputY", "pre_MEDIUM_DG_Yc_Y");
            d.put("yBlend1BMappedY", "unchanged_dy_over_DG_OUT_MAX");
            d.put("yBlend1BPreviousScale", "YBLEND1A_k0p50");
            d.put("yBlend1BNewChromaScale", "1_plus_0.35_times_(mappedY_over_inputY_minus_1)");
            d.put("yBlend1BLumaArithmeticChanged", false);
            d.put("yBlend1BMediumDgChanged", false);
            d.put("redTrace1BExperiment", "REDTRACE1B_LUMA_RELCHROMA_STRATIFIED_CC1_COUNTERFACTUAL");
            d.put("redTrace1BPhotographicPixelsChanged", false);
            d.put("redTrace1BReason", "prevent_highlight_window_pixels_from_masking_CC1_warm_midtone_behavior");
            d.put("redTrace1BLumaBins", "shadow_[0,0.18);lowmid_[0.18,0.40);midhigh_[0.40,0.75);highlight_[0.75,+inf)");
            d.put("redTrace1BWarmDefinition", "mappedY>0.03_and_mappedCr/mappedY>=0.04");
            d.put("redTrace1BNeutralDefinition", "mappedY>0.03_and_abs(mappedCb/mappedY)<=0.02_and_abs(mappedCr/mappedY)<=0.02");
            d.put("cc1Experiment", "CC1ON1A_PHOTOGRAPHIC_OUTPUT_RESTORE");
            d.put("cc1AppliedToPhotographicPixels", true);
            d.put("cc1MatrixRetainedUnusedForPhotographicOutput", false);
            d.put("cc1RedTraceMatchesPhotographicOutput", false);
            d.put("cc1RedTraceMatchesActualPreGamutOutput", false);
            d.put("cc1On1ARestoresFinalColourOnly", false);
            d.put("cc1Input", (BuildConfig.M10R_COLOR_ORDER1A && renderedColor.applied) ? "post_common_tone_working_RGB" : "normalized_post_DG_working_RGB");
            d.put("cc1Output", (BuildConfig.M10R_COLOR_ORDER1A && renderedColor.applied) ? "RGB_coordinates_before_DG_input_round_clamp" : "direct_output_RGB_before_GAMUT1A");
            d.put("preSrgbStatisticsRole", "legacy_Yc_YBLEND1B_counterfactual_not_actual_native_output");
            d.put("redTraceExperiment", "REDTRACE1A_YC_INVERSE_VS_CC1_EXCURSION");
            d.put("redTracePhotographicPixelsChanged", false);
            d.put("redTraceSamplingStride", 64);
            d.put("redTracePurpose", "locate_red_above_one_before_or_after_CC1_without_colour_tuning");
            d.put("outputTransferExperiment", "YA_TOPOLOGY1A_DIRECT_OUTPUT_QUANTIZATION");
            d.put("outputTransferPlacement", "native_after_RGB_DG_and_order_dependent_CC1_then_GAMUT1A_then_ARGB8_then_TONECAL1A");
            d.put("working1aNativeSrgbOetfRetainedForEdgeInvariant", false);
            d.put("edgeInputDomainUnchangedFromWorking1A", false);
            d.put("edgeInputDomainNotApplicableDueEdge0A", !edgeExecuted);
            d.put("netOutputTransfer", "direct_clamp_round_to_RGB8_then_TONECAL1A_internal_sRGB_decode_Lstar_adjust_encode"
                    + (edgeExecuted ? "_then_DETAIL3D_bitmap_sRGB_decode_edge_encode" : ""));
            d.put("outputTransferQuantization", "direct_output_coordinate_8bit_round_after_GAMUT1A_before_TONECAL1A");
            d.put("outputTransferExactHardwareParityClaimed", false);
            d.put("outputTransferPixels", transferPixels);
            d.put("outputTransferElapsedMs", transferElapsedMs);
            d.put("outputTransferSeparatePassExecuted", false);
            d.put("textbookSrgbOetfApplied", edgeExecuted);
            d.put("textbookSrgbOetfScope", edgeExecuted ? "DETAIL3D_reencode_changed_edge_pixels_only" : "none");
            d.put("transfer1aInverseExecuted", false);
            d.put("transferRoundTripRemoved", true);
            d.put("nativePixelOutputQuantizer", "direct_clamp_round_after_GAMUT1A_then_unchanged_TONECAL1A");
            d.put("inverseSrgbImplementationRetainedUnused", true);
            d.put("edgePassEnabled", edgeExecuted);
            d.put("edgeExperiment", edgeExecuted ? "DETAIL3D_BITMAP_DOMAIN_TRIAL" : "EDGE0A_BYPASS_ONLY");
            d.put("edgeCallExecuted", edgeExecuted);
            d.put("edgeNativeImplementationRetained", true);
            d.put("edgeBypassReason", edgeExecuted ? JSONObject.NULL : "domain_provisional_isolation_before_clean_native_output");
            d.put("detail3DExperimental", edgeExecuted);
            d.put("detail3DDefaultBuildEnabled", false);
            d.put("detail3DOnlyPhotographicVariableVsSourceAudit3C", edgeExecuted);
            d.put("detail3DPreviewApplied", false);
            d.put("detail3DNativeParametersChanged", false);
            d.put("detail3DNewReferenceHoldouts", false);
            d.put("edgeSrgbDecodeEncodeApplied", edgeExecuted);
            d.put("edgeInputDomainExactFirmwareParityClaimed", false);
            d.put("edgeIsoMapping", "delivered_phone_sensor_ISO_not_calibrated_Leica_ISO_equivalence");
            d.put("edge0aOnlyPhotographicVariable", false);
            d.put("oetfRetainedForTransferControl", true);
            d.put("transfer1aInverseRetainedForControl", true);
            d.put("edgeSource", "M10R_B2Y_STILL_SHARPNESS_MEDIUM_HIGH_FREQ_PLUS_EDGE_SYNTHESIS_ISO_GAIN");
            d.put("edgeKernelGeometry", "5x5_D4_symmetric_zero_DC");
            d.put("edgeKernelOrbitCoefficients", "316,-46,-4,-20,-3,-3");
            d.put("edgeKernelWeightedSum", 0);
            d.put("edgeKernelShiftCandidate", 8);
            d.put("edgeCoringCandidate", 450);
            d.put("edgeLimitCandidate", 1001);
            d.put("edgeIso", edgeIso);
            d.put("edgeSynthesisGainQ12", edgeIso <= 160 ? 5400 : (edgeIso <= 640 ? 4096 : 3700));
            d.put("edgeAffectedPixels", edgeAffectedPixels);
            d.put("edgeAffectedPixelsSemantic", "Y14_delta_ge_half_before_RGB8_requantization_not_exact_changed_pixel_count");
            d.put("edgeElapsedMs", edgeElapsedMs);
            d.put("edgeArithmeticExactFirmwareParityClaimed", false);
            d.put("edgeScaleTableApplied", edgeExecuted);
            d.put("edgeScaleTableSource", "B2Y_record_0x1E_HighEdge_Scale_Table_exact_16384_u16");
            d.put("edgeScaleTableSha256", "e4e8da0735a8847d4cc3c3766b58818ec29fe31d42d0710880a880e4ba7b8d1a");
            d.put("edgeScaleTableEntries", 16384);
            d.put("edgeScaleTableMin", 358);
            d.put("edgeScaleTableMax", 1023);
            d.put("edgeScaleCoordinate", "center_Y14_INFERRED_FROM_14BIT_SCALE_DOMAIN_EXPERIMENTAL");
            d.put("edgeScaleNormalization", "scale_u10_over_1023_EXPERIMENTAL");
            d.put("edgeHfRecordGainApplied", edgeExecuted);
            d.put("edgeHfRecordGainSource", "B2Y_record_0x0F_offset_0x118_10bit");
            d.put("edgeHfRecordGainValues", "ISO100_160=160,ISO200_640=128,ISO800plus=80");
            d.put("edgeHfRecordGainNormalization", "value_over_256_Q8_GAIN_CANDIDATE");
            d.put("edgeHfRecordGainSemanticExactFirmwareParityClaimed", false);
            d.put("edgeHfRecordMaxField0x11c", 1023);
            d.put("edgeHfRecordMaxFieldSemantic", "10bit_fullscale_constant_role_not_yet_proven");
            d.put("edgeStepTableIdentity", true);
            d.put("edgeStepTableAppliedSeparately", false);
            d.put("edgeStepTableReason", "firmware_HighEdge_Step_Table_is_exact_identity_0_to_8191");
            d.put("edgePlacement", edgeExecuted ? "post_TONECAL1A_final_bitmap_sRGB_decode_Y14_edge_reencode_EXPERIMENTAL" : "bypassed");
            d.put("textureEnhancementBlockEnabled", false);
            d.put("textureEnhancementReason", "firmware_calibration_enable_field_is_zero");
            d.put("lowFrequencyEdgeApplied", false);
            d.put("lowFrequencyEdgeReason", "combination_scaling_not_yet_constrained_enough");
            d.put("outputWidth", bitmap.getWidth());
            d.put("outputHeight", bitmap.getHeight());
            timing3E.next("aeOracleDiagnostic");
            try {
                appendAe1ADiagnostics(d, characteristics, captureResult, captureRequest);
            } catch (Throwable ae1aError) {
                d.put("m10rAe1A", new JSONObject()
                        .put("enabled", true)
                        .put("diagnosticOnly", true)
                        .put("realExposureMutated", false)
                        .put("status", "diagnostic_failed")
                        .put("error", ae1aError.toString()));
            }
            timing3E.next("exposureStateDiagnostic");
            try {
                appendAe1BState(d, captureRequest);
            } catch (Throwable ae1bError) {
                d.put("m10rAe1B", new JSONObject()
                        .put("enabled", true).put("activeCapture", true)
                        .put("status", "telemetry_failed").put("error", ae1bError.toString()));
            }
            timing3E.next("previewMeterDiagnostic");
            try {
                appendMeter1A(d);
            } catch (Throwable meter1aError) {
                d.put("m10rMeter1A", new JSONObject()
                        .put("enabled", true).put("diagnosticOnly", true)
                        .put("status", "telemetry_failed").put("error", meter1aError.toString()));
            }
            timing3E.next("firmwareMeterDiagnostic");
            try {
                appendMfm1B(d);
            } catch (Throwable mfm1bError) {
                d.put("m10rMfm1B", new JSONObject()
                        .put("enabled", true).put("activeCapture", true)
                        .put("status", "telemetry_failed").put("error", mfm1bError.toString()));
            }
// METERAREA1A_INSERT_BEGIN
            timing3E.next("meterAreaDiagnostic");
            M10RMeterArea1A.append(d, meterAreaBound, characteristics, captureResult, captureRequest);
// METERAREA1A_INSERT_END
            timing3E.next("renderFinalization");
            d.put("status", "success");
            M10RStageTiming3E.Snapshot renderTiming3E = timing3E.finish();
            d.put("rendererTiming3E", renderTiming3E.json("renderer_entry_through_final_diagnostics")
                    .put("legacyAmazeAndEdgeTimersOverlapStages", true)
                    .put("excludes", "JPEG_DNG_save_sidecar_IO_and_finally_cleanup"));
            d.put("renderElapsedMs", (System.nanoTime() - startNs) / 1_000_000.0);
            d.put("rendererTimingPublicationMs", d.getDouble("renderElapsedMs") - renderTiming3E.elapsedNs / 1_000_000.0);
            return new Result(bitmap, d);
        } catch (Throwable t) {
            if (bitmap != null && !bitmap.isRecycled()) bitmap.recycle();
            if (t instanceof Exception) throw (Exception)t;
            throw new RuntimeException(t);
        } finally {
// AMAZE1A_INSERT_BEGIN
            if (amaze != null) amaze.close();
// AMAZE1A_INSERT_END
            if (tileRaw != null) tileRaw.release();
            if (tileBgr != null) tileBgr.release();
        }
    }

    public static void persistBreadcrumb(Path dngPath, String stage) {
        if (dngPath == null || stage == null) return;
        try {
            String name = dngPath.getFileName().toString();
            int dot = name.lastIndexOf('.');
            String stem = dot > 0 ? name.substring(0, dot) : name;
            Path sidecar = dngPath.resolveSibling(stem + "_M10R_STABILITY1.txt");
            String line = System.currentTimeMillis() + " " + stage + "\n";
            Files.write(sidecar, line.getBytes(StandardCharsets.UTF_8),
                    java.nio.file.StandardOpenOption.CREATE,
                    java.nio.file.StandardOpenOption.APPEND);
        } catch (Throwable ignored) {}
    }

    public static boolean persistDiagnostics(Path anchorPath, JSONObject diagnostics) {
        if (anchorPath == null || diagnostics == null) return false;
        Path sidecar = null;
        try {
            Path parent = anchorPath.getParent();
            if (parent == null) return false;
            String name = anchorPath.getFileName().toString();
            int dot = name.lastIndexOf('.');
            String stem = dot > 0 ? name.substring(0, dot) : name;
            sidecar = parent.resolve(stem + "_M10R_CAPTURE1B.json");
            diagnostics.put("diagnosticsSidecarPath", sidecar.toString());

            java.io.OutputStream safOut =
                    com.particlesdevs.photoncamera.util.SimpleStorageHelper
                            .openOutputStreamByAbsPath(sidecar.toString());
            if (safOut != null) {
                diagnostics.put("diagnosticsWriter", "DIAG1C_SAF_ABSPATH");
                byte[] payload = diagnostics.toString(2).getBytes(StandardCharsets.UTF_8);
                try (java.io.OutputStream out = safOut) {
                    out.write(payload);
                    out.flush();
                }
                android.util.Log.d("M10RNativeRenderer",
                        "M10-R DIAG1C SAF JSON saved bytes=" + payload.length + " path=" + sidecar);
                return payload.length > 0;
            }

            diagnostics.put("diagnosticsWriter", "DIAG1C_DIRECT_FALLBACK");
            byte[] payload = diagnostics.toString(2).getBytes(StandardCharsets.UTF_8);
            Files.createDirectories(parent);
            try (java.io.OutputStream out = Files.newOutputStream(sidecar)) {
                out.write(payload);
                out.flush();
            }
            boolean ok = Files.exists(sidecar) && Files.size(sidecar) > 0L;
            android.util.Log.d("M10RNativeRenderer",
                    "M10-R DIAG1C direct JSON saved=" + ok + " path=" + sidecar);
            return ok;
        } catch (Throwable error) {
            android.util.Log.e("M10RNativeRenderer",
                    "M10-R DIAG1C JSON WRITE FAILED path=" + sidecar + " "
                            + android.util.Log.getStackTraceString(error));
            android.util.Log.e("M10RNativeRenderer",
                    "M10-R DIAG1C JSON PAYLOAD=" + diagnostics.toString());
            return false;
        }
    }

    public static void persistFailureDiagnostics(Path dngPath, Throwable error,
                                                 ImageFrame frame,
                                                 CameraCharacteristics characteristics) {
        try {
            JSONObject d = new JSONObject();
            d.put("schema", SCHEMA);
            d.put("status", "renderer_failed_before_result");
            d.put("errorClass", error != null ? error.getClass().getName() : "unknown");
            d.put("error", error != null ? String.valueOf(error.getMessage()) : "unknown");
            d.put("openCvAndroidAar", "org.opencv:opencv:4.13.0");
            d.put("captureMode", "single_frame_raw");
            d.put("hdrEnabled", false);
            d.put("stackingEnabled", false);
            if (frame != null) {
                d.put("width", frame.width);
                d.put("height", frame.height);
                d.put("rawBufferCapacity", frame.buffer != null ? frame.buffer.capacity() : -1);
            }
            if (characteristics != null) {
                Integer cfa = characteristics.get(CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT);
                d.put("cfaPatternCode", cfa != null ? cfa : -1);
                if (cfa != null && cfa >= 0 && cfa <= 3) d.put("cfaPatternName", cfaName(cfa));
            }
            persistDiagnostics(dngPath, d);
        } catch (Throwable ignored) {}
    }

    private static double ae1aLog2(double x) {
        return Math.log(x) / Math.log(2.0);
    }

    private static double ae1aOneOverFTv(double focalMm) {
        if (!(focalMm > 0.0) || !Double.isFinite(focalMm)) return Double.NaN;
        return Math.round(ae1aLog2(focalMm) * 2.0) / 2.0;
    }

    private static JSONObject ae1aResultJson(M10RAeOracle.Result r, double tvIsoEv) throws Exception {
        return new JSONObject()
                .put("tvIsoEv", tvIsoEv)
                .put("predictedTvEv", r.tvEv())
                .put("predictedSvEv", r.svEv())
                .put("predictedIso", r.iso)
                .put("predictedShutterSeconds", r.shutterSeconds)
                .put("predictedDEv", r.dEv())
                .put("autoIsoActivated", r.autoIsoActivated)
                .put("autoIsoSteps", r.autoIsoSteps)
                .put("tvIsoReached", r.tvIsoReached)
                .put("svUpperBoundHit", r.svUpperBoundHit)
                .put("constraintReason", r.constraintReason);
    }

    private static JSONObject ae1aPredictionSet(double bvEv, double avEv, double oneOverFTv) throws Exception {
        JSONObject o = new JSONObject();
        if (!Double.isFinite(bvEv) || !Double.isFinite(avEv) || !Double.isFinite(oneOverFTv)) {
            return o.put("valid", false);
        }
        o.put("valid", true)
                .put("oneOverF", ae1aResultJson(M10RAeOracle.solveAMode(bvEv, avEv, oneOverFTv, 100, 50000), oneOverFTv))
                .put("oneOver2F", ae1aResultJson(M10RAeOracle.solveAMode(bvEv, avEv, oneOverFTv + 1.0, 100, 50000), oneOverFTv + 1.0))
                .put("oneOver3F", ae1aResultJson(M10RAeOracle.solveAMode(bvEv, avEv, oneOverFTv + 1.5, 100, 50000), oneOverFTv + 1.5))
                .put("oneOver4F", ae1aResultJson(M10RAeOracle.solveAMode(bvEv, avEv, oneOverFTv + 2.0, 100, 50000), oneOverFTv + 2.0));
        return o;
    }

    private static JSONArray ae1aRegions(CaptureRequest request) throws Exception {
        JSONArray out = new JSONArray();
        if (request == null) return out;
        MeteringRectangle[] regions = request.get(CaptureRequest.CONTROL_AE_REGIONS);
        if (regions == null) return out;
        for (MeteringRectangle region : regions) {
            if (region == null) continue;
            Rect r = region.getRect();
            out.put(new JSONObject()
                    .put("left", r.left).put("top", r.top)
                    .put("right", r.right).put("bottom", r.bottom)
                    .put("weight", region.getMeteringWeight()));
        }
        return out;
    }

    private static void appendAe1ADiagnostics(JSONObject d,
                                               CameraCharacteristics characteristics,
                                               CaptureResult captureResult,
                                               CaptureRequest captureRequest) throws Exception {
        JSONObject ae = new JSONObject()
                .put("enabled", true)
                .put("diagnosticOnly", true)
                .put("realExposureMutated", false)
                .put("rendererPixelsChanged", false)
                .put("oracle", "recovered_M10R_production_A_mode_Q8_8")
                .put("svMinIso", 100)
                .put("svMaxIso", 50000)
                .put("svLimitsSemantic", "diagnostic_host_oracle_defaults_not_user_setting")
                .put("meterProxySemantic",
                        "actual_capture_APEX_inverse_plus_post_capture_RAW_center_vs_whole_delta_not_calibrated_M10R_meter");

        Long exposureNs = captureResult.get(CaptureResult.SENSOR_EXPOSURE_TIME);
        Integer iso = captureResult.get(CaptureResult.SENSOR_SENSITIVITY);
        Float aperture = captureResult.get(CaptureResult.LENS_APERTURE);
        Float focal = captureResult.get(CaptureResult.LENS_FOCAL_LENGTH);
        if (aperture == null) {
            float[] a = characteristics.get(CameraCharacteristics.LENS_INFO_AVAILABLE_APERTURES);
            if (a != null && a.length > 0) aperture = a[0];
        }
        if (focal == null) {
            float[] f = characteristics.get(CameraCharacteristics.LENS_INFO_AVAILABLE_FOCAL_LENGTHS);
            if (f != null && f.length > 0) focal = f[0];
        }

        if (captureRequest != null) {
            Long requestedNs = captureRequest.get(CaptureRequest.SENSOR_EXPOSURE_TIME);
            Integer requestedIso = captureRequest.get(CaptureRequest.SENSOR_SENSITIVITY);
            Integer requestedAeMode = captureRequest.get(CaptureRequest.CONTROL_AE_MODE);
            if (requestedNs != null) ae.put("requestedExposureTimeNs", requestedNs);
            if (requestedIso != null) ae.put("requestedIso", requestedIso);
            if (requestedAeMode != null) ae.put("requestedAeMode", requestedAeMode);
        }
        ae.put("captureAeRegions", ae1aRegions(captureRequest));

        Rect active = characteristics.get(CameraCharacteristics.SENSOR_INFO_ACTIVE_ARRAY_SIZE);
        if (active != null) {
            ae.put("activeArray", new JSONObject()
                    .put("left", active.left).put("top", active.top)
                    .put("right", active.right).put("bottom", active.bottom));
        }

        boolean complete = exposureNs != null && exposureNs > 0L && iso != null && iso > 0
                && aperture != null && aperture > 0.0f && focal != null && focal > 0.0f;
        ae.put("inputComplete", complete);
        if (!complete) {
            d.put("m10rAe1A", ae);
            return;
        }

        double exposureSeconds = exposureNs / 1.0e9;
        double actualTv = ae1aLog2(1.0 / exposureSeconds);
        double actualAv = 2.0 * ae1aLog2(aperture);
        double actualSv = ae1aLog2(iso / 3.125);
        double actualBv = actualTv + actualAv - actualSv;
        double physicalTv1f = ae1aOneOverFTv(focal);

        ae.put("actualExposureTimeNs", exposureNs)
                .put("actualExposureSeconds", exposureSeconds)
                .put("actualIso", iso)
                .put("apertureFNumber", aperture)
                .put("focalLengthMm", focal)
                .put("actualTvEv", actualTv)
                .put("actualAvEv", actualAv)
                .put("actualSvApexEv", actualSv)
                .put("actualApexBvProxy", actualBv)
                .put("oneOverFPhysicalTvEv", physicalTv1f);

        SizeF sensor = characteristics.get(CameraCharacteristics.SENSOR_INFO_PHYSICAL_SIZE);
        double equivalentFocal = Double.NaN;
        if (sensor != null && sensor.getWidth() > 0.0f) {
            equivalentFocal = focal * (36.0 / sensor.getWidth());
            ae.put("sensorPhysicalWidthMm", sensor.getWidth())
                    .put("focalLength35mmWidthApprox", equivalentFocal)
                    .put("oneOverF35mmWidthApproxTvEv", ae1aOneOverFTv(equivalentFocal));
        }

        JSONObject rawProbe = d.optJSONObject("m10rAe1A_rawMeterProbe");
        double centerDeltaEv = rawProbe != null
                ? rawProbe.optDouble("centerWeightedVsWholeEv", Double.NaN) : Double.NaN;
        ae.put("rawCenterWeightedVsWholeEv",
                Double.isFinite(centerDeltaEv) ? centerDeltaEv : JSONObject.NULL);

        double centerBv = Double.isFinite(centerDeltaEv) ? actualBv + centerDeltaEv : Double.NaN;
        ae.put("centerWeightedBvProxy",
                Double.isFinite(centerBv) ? centerBv : JSONObject.NULL);

        ae.put("physicalFocalPredictionsFromActualBv",
                ae1aPredictionSet(actualBv, actualAv, physicalTv1f));
        ae.put("physicalFocalPredictionsFromCenterWeightedBv",
                ae1aPredictionSet(centerBv, actualAv, physicalTv1f));

        if (Double.isFinite(equivalentFocal)) {
            double equivalentTv1f = ae1aOneOverFTv(equivalentFocal);
            ae.put("widthEquivalentPredictionsFromActualBv",
                    ae1aPredictionSet(actualBv, actualAv, equivalentTv1f));
            ae.put("widthEquivalentPredictionsFromCenterWeightedBv",
                    ae1aPredictionSet(centerBv, actualAv, equivalentTv1f));
        }

        d.put("m10rAe1A", ae);
    }

    private static M10RMfm1B.Decision mfm1bRawCounterfactual(JSONObject d) {
        try {
            JSONObject raw = d.optJSONObject("m10rAe1A_rawMeterProbe");
            JSONArray rows = raw != null ? raw.optJSONArray("leicaRawGrid16x22") : null;
            if (rows == null || rows.length() != M10RMfm1B.GRID_R) return M10RMfm1B.evaluate(null);
            double[] grid = new double[M10RMfm1B.GRID_R * M10RMfm1B.GRID_C];
            for (int r = 0; r < M10RMfm1B.GRID_R; r++) {
                JSONArray row = rows.optJSONArray(r);
                if (row == null || row.length() != M10RMfm1B.GRID_C) return M10RMfm1B.evaluate(null);
                for (int c = 0; c < M10RMfm1B.GRID_C; c++) {
                    grid[r * M10RMfm1B.GRID_C + c] = row.optDouble(c, Double.NaN);
                }
            }
            return M10RMfm1B.evaluate(grid);
        } catch (Throwable ignored) {
            return M10RMfm1B.evaluate(null);
        }
    }

    private static JSONObject mfm1bDecisionJson(M10RMfm1B.Decision x) throws Exception {
        JSONObject o = new JSONObject()
                .put("valid", x != null && x.valid)
                .put("wouldApply", x != null && x.wouldApply)
                .put("recommendedEv", x != null ? x.recommendedEv : 0.0)
                .put("reason", x != null ? x.reason : "missing");
        if (x != null && x.valid) {
            o.put("integralY", x.integralY)
                    .put("regionalMedianY", x.regionalMedianY)
                    .put("regionalLowQuarterY", x.regionalLowQuarterY)
                    .put("regionalHighQuarterY", x.regionalHighQuarterY)
                    .put("sceneSpreadEv", x.sceneSpreadEv)
                    .put("center8Y", x.center8Y)
                    .put("lower12Y", x.lower12Y)
                    .put("upper6Y", x.upper6Y)
                    .put("edge16Y", x.edge16Y)
                    .put("inner8Y", x.inner8Y)
                    .put("integralVsMedianEv", x.integralVsMedianEv)
                    .put("integralVsCenterEv", x.integralVsCenterEv)
                    .put("integralVsLowerEv", x.integralVsLowerEv)
                    .put("edgeVsInnerEv", x.edgeVsInnerEv)
                    .put("upperVsLowerEv", x.upperVsLowerEv)
                    .put("centerOverIntegralEv", x.centerOverIntegralEv)
                    .put("innerVsEdgeEv", x.innerVsEdgeEv)
                    .put("left4Y", x.left4Y)
                    .put("right4Y", x.right4Y)
                    .put("bottom6Y", x.bottom6Y)
                    .put("brightestSideY", x.brightestSideY)
                    .put("brightestSideVsInnerEv", x.brightestSideVsInnerEv)
                    .put("positiveBaseEv", x.positiveBaseEv)
                    .put("sideGeometryConfidence", x.sideGeometryConfidence)
                    .put("integralDominanceConfidence", x.integralDominanceConfidence)
                    .put("positiveBaseConfidence", x.positiveBaseConfidence)
                    .put("positiveCandidateEv", x.positiveCandidateEv)
                    .put("negativeCandidateEv", x.negativeCandidateEv)
                    .put("rawBlendEv", x.rawBlendEv)
                    .put("brightRegionCount", x.brightRegionCount)
                    .put("darkRegionCount", x.darkRegionCount)
                    .put("brightRegionFraction", x.brightRegionFraction)
                    .put("darkRegionFraction", x.darkRegionFraction)
                    .put("positiveGeometryConfidence", x.positiveGeometryConfidence)
                    .put("positiveConfidence", x.positiveConfidence)
                    .put("negativeGeometryConfidence", x.negativeGeometryConfidence)
                    .put("negativeConfidence", x.negativeConfidence);
            JSONArray regions = new JSONArray();
            if (x.regions4x6 != null) for (double v : x.regions4x6) regions.put(v);
            o.put("regions4x6", regions);
        }
        return o;
    }

    private static void appendMfm1B(JSONObject d) throws Exception {
        M10RMfm1BState.Snapshot s = M10RMfm1BState.snapshot();
        M10RMfm1DSourceState.Snapshot sourceProxy = M10RMfm1DSourceState.snapshot();
        M10RMfm1B.Decision raw = mfm1bRawCounterfactual(d);
        JSONObject o = new JSONObject()
                .put("enabled", true)
                .put("activeCapture", true)
                .put("architectureProxy", true)
                .put("exactCa9ThirteenFeatureParityClaimed", false)
                .put("recoveredIntegralMask", "exact_0x4001349c_sum14160")
                .put("recoveredRegionalTopology", "4x6_24_regions")
                .put("boundsOrigin", "research_safety_not_M10R_firmware_constant")
                .put("positiveLimitEv", M10RMfm1B.MAX_POSITIVE_EV)
                .put("negativeLimitEv", -M10RMfm1B.MAX_NEGATIVE_EV)
                .put("deadBandEv", M10RMfm1B.DEAD_BAND_EV)
                .put("positiveGain", M10RMfm1B.POSITIVE_GAIN)
                .put("meterRevision", "MFM1D_SOURCEPROXY1C_STABLE_FINGERPRINT")
                .put("liveInputBeforeProxy",
                        "GL_SurfaceTexture_RGBA8_inverse_sRGB_per_channel_Rec709_luma")
                .put("sourceProxyStateValid", sourceProxy.valid)
                .put("sourceProxyProfileId", sourceProxy.profileId)
                .put("sourceProxyPhysicalFingerprint", sourceProxy.fingerprint)
                .put("sourceProxyCanonicalDescriptor", sourceProxy.canonicalDescriptor)
                .put("sourceProxyCalibrationStatus", sourceProxy.calibrationStatus)
                .put("sourceProxyCalibrationEvidenceId", sourceProxy.calibrationEvidenceId)
                .put("sourceProxyFingerprintVersion", M10RMfm1DSourceProxy.IDENTITY_VERSION)
                .put("sourceProxyCurrentOpticalStateInFingerprint", false)
                .put("sourceProxyCurrentFocalApertureTelemetryOnly", true)
                .put("sourceProxyFingerprintIncludesStaticMatrices", true)
                .put("sourceProxyFingerprintUsesAvailableOptics", true)
                .put("sourceProxyFullSignatureCalibrationValidated", false)
                .put("sourceProxyAutomaticLearningEnabled", false)
                .put("sourceProxyIdentityImpliesTransferParity", false)
                .put("sourceProxyBasis", sourceProxy.basis)
                .put("sourceProxyActiveWidth", sourceProxy.activeWidth)
                .put("sourceProxyActiveHeight", sourceProxy.activeHeight)
                .put("sourceProxySensorWidthMm", (Double.isFinite(sourceProxy.sensorWidthMm) ? sourceProxy.sensorWidthMm : JSONObject.NULL))
                .put("sourceProxyPhysicalFocalMm", (Double.isFinite(sourceProxy.physicalFocalMm) ? sourceProxy.physicalFocalMm : JSONObject.NULL))
                .put("sourceProxyAperture", (Double.isFinite(sourceProxy.aperture) ? sourceProxy.aperture : JSONObject.NULL))
                .put("sourceProxyCfa", sourceProxy.cfa)
                .put("sourceProxyWhiteLevel", sourceProxy.whiteLevel)
                .put("sourceProxyReferenceIlluminant1", sourceProxy.referenceIlluminant1)
                .put("sourceProxyReferenceIlluminant2", sourceProxy.referenceIlluminant2)
                .put("sourceProxyIdentitySemantic",
                        "static_CameraCharacteristics_signature_not_current_optical_state_not_hardware_serial")
                .put("liveRawProxyTransform", "pow_clamp01_Y_sensor_profile_exponent")
                .put("liveRawProxyExponent", sourceProxy.exponent)
                .put("liveRawProxyMonotonic", true)
                .put("unknownSensorFallbackExponent", M10RMfm1DSourceProxy.FALLBACK_EXPONENT)
                .put("rawCounterfactualProxyApplied", false)
                .put("rawCounterfactualDomain", "normalized_RAW_green_pre_lens_shading")
                .put("rendererPixelsChangedByMfm1D", false)
                .put("perLensLeicaMeterTuningApplied", false)
                .put("sourceNormalizationPerPhysicalSensor", true)
                .put("positiveGeometrySemantic",
                        "rotation_invariant_brightest_side_vs_inner_integral_dominance_telemetry_only")
                .put("positiveMagnitudeSemantic",
                        "0p65_integral_vs_median_plus_0p35_integral_vs_center_no_lower_half_penalty")
                .put("positiveBaseGate", "smoothstep_positive_base_ev_0p16_to_0p32")
                .put("stateValid", s.valid)
                .put("stateGeneration", s.generation)
                .put("liveGridGeneration", s.liveGridGeneration)
                .put("userExposureCorrectionEv", s.userExposureCorrectionEv)
                .put("mfmExposureCorrectionEv", s.mfmExposureCorrectionEv)
                .put("totalExposureCorrectionEv", s.totalExposureCorrectionEv)
                .put("liveDecision", mfm1bDecisionJson(s.decision))
                .put("rawCounterfactualDecision", mfm1bDecisionJson(raw));
        if (s.decision != null && s.decision.valid && raw != null && raw.valid) {
            o.put("liveMinusRawRecommendedEv", s.decision.recommendedEv - raw.recommendedEv)
                    .put("liveRawDecisionSignAgreement",
                            Math.signum(s.decision.recommendedEv) == Math.signum(raw.recommendedEv))
                    .put("liveRawWouldApplyAgreement", s.decision.wouldApply == raw.wouldApply);
        }
        d.put("m10rMfm1D", o);
    }

    private static void appendMeter1A(JSONObject d) throws Exception {
        M10RLiveMeterState.Snapshot s = M10RLiveMeterState.frozenSnapshot();
        JSONObject o = new JSONObject()
                .put("enabled", true)
                .put("diagnosticOnly", true)
                .put("affectsExposure", false)
                .put("affectsPixels", false)
                .put("grid", "22x16")
                .put("sampleSource", "GL_SurfaceTexture_offscreen_RGBA8")
                .put("sampleCadence", "every_6_rendered_preview_frames")
                .put("sensorOrientationIntent", "source_sensor_top_down_left_right")
                .put("gridMapFix", "GRIDMAP1A_shader_axis_swap_transposed_fbo_16x22")
                .put("meterFboRaster", "16wide_x22high_then_rawRow_to_sensorCol_rawCol_to_sensorRow")
                .put("integralMask", "exact_recovered_M10R_Integral_0x4001349C")
                .put("integralMaskWeightSum", M10RIntegralMask.WEIGHT_SUM)
                .put("linearization", "inverse_sRGB_per_channel_then_Rec709_luma_approx")
                .put("previewPipelineParityClaimed", false)
                .put("valid", s.valid)
                .put("generation", s.generation)
                .put("sampleTimestampNs", s.timestampNs)
                .put("previewExposureTimeNs", s.previewExposureNs)
                .put("previewIso", s.previewIso);
        if (s.valid) {
            o.put("codeWholeMean", s.codeWholeMean)
                    .put("codeIntegralMean", s.codeIntegralMean)
                    .put("codeIntegralVsWholeEv", s.codeIntegralVsWholeEv)
                    .put("linearWholeMean", s.linearWholeMean)
                    .put("linearIntegralMean", s.linearIntegralMean)
                    .put("linearIntegralVsWholeEv", s.linearIntegralVsWholeEv);
            JSONArray rows = new JSONArray();
            if (s.linearGrid != null && s.linearGrid.length == M10RIntegralMask.ROWS * M10RIntegralMask.COLS) {
                for (int row = 0; row < M10RIntegralMask.ROWS; row++) {
                    JSONArray r = new JSONArray();
                    for (int col = 0; col < M10RIntegralMask.COLS; col++) {
                        r.put(s.linearGrid[row * M10RIntegralMask.COLS + col]);
                    }
                    rows.put(r);
                }
            }
            o.put("linearGrid16x22", rows);

            JSONObject raw = d.optJSONObject("m10rAe1A_rawMeterProbe");
            if (raw != null && raw.has("leicaIntegralVsWholeEv")) {
                double rawEv = raw.optDouble("leicaIntegralVsWholeEv", Double.NaN);
                o.put("rawLeicaIntegralVsWholeEv",
                        Double.isFinite(rawEv) ? rawEv : JSONObject.NULL);
                o.put("linearPreviewMinusRawIntegralDeltaEv",
                        Double.isFinite(rawEv) && Double.isFinite(s.linearIntegralVsWholeEv)
                                ? s.linearIntegralVsWholeEv - rawEv : JSONObject.NULL);
                o.put("codePreviewMinusRawIntegralDeltaEv",
                        Double.isFinite(rawEv) && Double.isFinite(s.codeIntegralVsWholeEv)
                                ? s.codeIntegralVsWholeEv - rawEv : JSONObject.NULL);
            }
        }
        d.put("m10rMeter1A", o);
    }

    private static void appendAe1BState(JSONObject d, CaptureRequest captureRequest) throws Exception {
        M10RAe1BState.Snapshot s = M10RAe1BState.snapshot();
        JSONObject o = new JSONObject()
                .put("enabled", true)
                .put("activeCapture", true)
                .put("rendererPixelsChanged", false)
                .put("centerWeightedPreviewMeterForced", true)
                .put("tapChangesAeMetering", com.particlesdevs.photoncamera.settings.PreferenceKeys.getAeMeteringStd()==2)
                .put("meterSource", "Camera2_preview_AE_center_weighted_phone_proxy")
                .put("allocator", "recovered_M10R_production_A_mode_Q8_8")
                .put("autoIsoPolicy", "1_over_f_35mm_width_equivalent_half_stop")
                .put("svMinIso", 100).put("svMaxIso", 50000)
                .put("stateValid", s.valid)
                .put("stateGeneration", s.generation)
                .put("sensorClampApplied", s.sensorClampApplied);
        if (s.valid) {
            Long requestNs = captureRequest != null ? captureRequest.get(CaptureRequest.SENSOR_EXPOSURE_TIME) : null;
            Integer requestIso = captureRequest != null ? captureRequest.get(CaptureRequest.SENSOR_SENSITIVITY) : null;
            o.put("captureRequestExposureTimeNs", requestNs != null ? requestNs : JSONObject.NULL)
                    .put("captureRequestIso", requestIso != null ? requestIso : JSONObject.NULL)
                    .put("captureRequestMatchesFrozenState",
                            requestNs != null && requestIso != null
                            && requestNs == s.appliedExposureNs && requestIso == s.appliedIso)
                    .put("previewExposureTimeNs", s.previewExposureNs)
                    .put("previewIso", s.previewIso)
                    .put("apertureFNumber", s.aperture)
                    .put("focalLengthMm", s.focalLengthMm)
                    .put("focalLength35mmWidthApprox", s.focalLength35mm)
                    .put("previewTvEv", s.previewTvEv)
                    .put("previewAvEv", s.previewAvEv)
                    .put("previewSvEv", s.previewSvEv)
                    .put("previewBvEv", s.previewBvEv)
                    .put("tvIsoEv", s.tvIsoEv)
                    .put("exposureCorrectionEv", s.exposureCorrectionEv)
                    .put("oracleExposureTimeNs", s.oracleExposureNs)
                    .put("oracleIso", s.oracleIso)
                    .put("appliedExposureTimeNs", s.appliedExposureNs)
                    .put("appliedIso", s.appliedIso)
                    .put("predictedDEv", s.predictedDEv)
                    .put("constraintReason", s.constraintReason);
        }
        d.put("m10rAe1B", o);
    }

    private static SourceModel buildSourceModel(CameraCharacteristics c,
                                                CaptureResult r,
                                                JSONObject d) throws Exception {
        Integer ref1Obj = c.get(CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT1);
        Byte ref2Obj = c.get(CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT2);
        if (ref1Obj == null) throw new IllegalStateException("source illuminant1 missing");
        int ref1 = ref1Obj;
        int ref2 = ref2Obj != null ? (ref2Obj & 0xff) : ref1;
        float[] cal1 = transform(c.get(CameraCharacteristics.SENSOR_CALIBRATION_TRANSFORM1));
        float[] cal2 = transform(c.get(CameraCharacteristics.SENSOR_CALIBRATION_TRANSFORM2));
        float[] cm1 = transform(c.get(CameraCharacteristics.SENSOR_COLOR_TRANSFORM1));
        float[] cm2 = transform(c.get(CameraCharacteristics.SENSOR_COLOR_TRANSFORM2));
        float[] fm1 = transform(c.get(CameraCharacteristics.SENSOR_FORWARD_MATRIX1));
        float[] fm2 = transform(c.get(CameraCharacteristics.SENSOR_FORWARD_MATRIX2));
        float[] neutral = rationalVector(r.get(CaptureResult.SENSOR_NEUTRAL_COLOR_POINT));
        // SOURCECAL3C: Camera2 permits a single calibration illuminant. Only
        // when the second illuminant is absent, use the complete first profile.
        // An advertised but incomplete second profile remains an error.
        boolean singleIlluminant = ref2Obj == null;
        if (singleIlluminant) {
            cal2 = cal1;
            cm2 = cm1;
            fm2 = fm1;
        }
        if (!valid9(cal1) || !valid9(cal2) || !valid9(cm1) || !valid9(cm2)
                || !valid9(fm1) || !valid9(fm2) || neutral == null) {
            throw new IllegalStateException("native Camera2 source calibration metadata incomplete");
        }

        // SOURCECAL2A correction: ColorMatrix stays XYZ->reference-camera unmodified.
        // Only ForwardMatrix gets Converter's DNG forward normalization.
        float[] nfm1 = fm1.clone();
        float[] nfm2 = fm2.clone();
        Converter.normalizeFM(nfm1);
        Converter.normalizeFM(nfm2);
        double factor = singleIlluminant ? 0.0 : Converter.findDngInterpolationFactor(
                ref1, ref2, cal1, cal2, cm1, cm2, neutral);
        float[] sensorToXyzD50 = new float[9];
        Converter.calculateCameraToXYZD50Transform(
                nfm1, nfm2, cal1, cal2, neutral, factor, sensorToXyzD50);

        double[] xyzToCamera1 = matMul(toDouble(cal1), toDouble(cm1));
        double[] xyzToCamera2 = matMul(toDouble(cal2), toDouble(cm2));
        double[] xyzToCamera = lerp9(xyzToCamera1, xyzToCamera2, factor);
        double[] xyzNeutral = matVec(inverse3(xyzToCamera),
                new double[]{neutral[0], neutral[1], neutral[2]});
        double sum = xyzNeutral[0] + xyzNeutral[1] + xyzNeutral[2];
        if (!(sum > 0.0) || !Double.isFinite(sum)) {
            throw new IllegalStateException("source scene-white solve invalid");
        }
        double[] xy = {xyzNeutral[0]/sum, xyzNeutral[1]/sum};
        double kelvin = xyToTemperatureLeica(xy);

        d.put("sourceReferenceIlluminant1", ref1);
        d.put("sourceReferenceIlluminant2", ref2);
        d.put("sourceCalibrationRevision", "M10R_SOURCECAL3C_SINGLE_OR_DUAL_ILLUMINANT");
        d.put("sourceCalibrationIlluminantCount", singleIlluminant ? 1 : 2);
        d.put("sourceSingleIlluminantFallbackApplied", singleIlluminant);
        if (singleIlluminant) d.put("sourceModel", "Camera2_single_illuminant_native_XYZ_D50");
        d.put("sourceColorMatrixConvention", "DNG_XYZ_to_reference_camera_unmodified");
        d.put("sourceColorMatrixRowNormalizationApplied", false);
        d.put("sourceForwardMatrixNormalizationApplied", true);
        d.put("sourceSensorNeutral", json(neutral));
        d.put("sourceSensorToXYZD50", jsonMatrix(sensorToXyzD50));
        return new SourceModel(sensorToXyzD50, xy, kelvin, factor);
    }

    private static BayerFrame normalizeBayer(ByteBuffer buffer, int width, int height,
                                             int cfa, double[] black, int white,
                                             LensShadingMap lensMap, JSONObject d) throws Exception {
        int pixels = Math.multiplyExact(width, height);
        ByteBuffer dup = buffer.duplicate().order(ByteOrder.LITTLE_ENDIAN);
        dup.position(0);
        if (dup.remaining() < Math.multiplyExact(pixels, 2)) {
            throw new IllegalArgumentException("RAW buffer too small");
        }
        ShortBuffer raw = dup.asShortBuffer();
        float[] map = null;
        int cols = 0, rows = 0;
        double maxGain = 1.0;
        if (lensMap != null && lensMap.getColumnCount() >= 2 && lensMap.getRowCount() >= 2) {
            cols = lensMap.getColumnCount();
            rows = lensMap.getRowCount();
            map = new float[lensMap.getGainFactorCount()];
            lensMap.copyGainFactors(map, 0);
            for (float g : map) if (Float.isFinite(g) && g > maxGain) maxGain = g;
        }
        double storageScale = 1.0 / maxGain;
        M10RPhotoNormalization3G.Result preparation3G = M10RPhotoNormalization3G.tryPrepare(
                BuildConfig.M10R_NATIVE_NORMALIZE3G, dup, width, height, cfa,
                black, white, map, cols, rows, storageScale);
        M10RExposureRaw1B.Prepared native3G = preparation3G.prepared;
        final boolean sparse3G = native3G != null;
        long javaScanStart3G = System.nanoTime();
        short[] out = sparse3G ? native3G.normalized : new short[pixels];
        // RENDERPERF3F: reuse exact horizontal gain interpolation and phase denominators.
        M10RLensShading3F shading3F = map == null ? null
                : new M10RLensShading3F(map, cols, rows, width, height);
        double[] phaseDenom3F = new double[4];
        for (int phase = 0; phase < 4; phase++)
            phaseDenom3F[phase] = Math.max(1.0, white - black[phase]);
        int[] siteToGainChannel = gainChannelsForCfa(cfa);
        long whiteClipCount = 0L;
        long[] sourceAtWhite2S = sparse3G ? native3G.atWhiteByCfaPhase() : new long[4];
        long[] sourceAboveWhite2S = sparse3G ? native3G.aboveWhiteByCfaPhase() : new long[4];
        // With finite 0 <= black < white, the original unit > 1 condition is
        // exactly sourceCode > white, including fractional phase black levels.
        if (sparse3G) for (long count : sourceAboveWhite2S) whiteClipCount += count;
// METERAREA1A_INSERT_BEGIN

        // Separate CFA-aware references; leave the legacy raw counterfactual unchanged.
        double[] meterAreaPreSum = new double[352];
        double[] meterAreaPostSum = new double[352];
        double[] meterAreaGainSum = new double[352];
        long[] meterAreaCounts = new long[352];
// METERAREA1A_INSERT_END

        // AE1A is diagnostic-only. Sample two green CFA sites per 8x8 block
        // before lens shading so the later meter proxy cannot alter RAW pixels.
        double ae1aFullSum = 0.0, ae1a70Sum = 0.0, ae1a45Sum = 0.0, ae1a20Sum = 0.0;
        long ae1aFullCount = 0L, ae1a70Count = 0L, ae1a45Count = 0L, ae1a20Count = 0L;
        double ae1aIntegralWeightedSum = 0.0, ae1aIntegralWeightSum = 0.0;
        double[] ae1aRawGridSum = new double[M10RIntegralMask.ROWS * M10RIntegralMask.COLS];
        long[] ae1aRawGridCount = new long[M10RIntegralMask.ROWS * M10RIntegralMask.COLS];

        long javaSites3G = 0;
        // Both existing meter lattices lie in the top-left 2x2 of each 8x8.
        // Visit their union in the original y-major order; all sums keep their
        // exact order. The 3F fallback still visits every sensor site.
        for (int y=0; y<height; y += sparse3G ? ((y & 7) == 0 ? 1 : 7) : 1) {
            if (shading3F != null) shading3F.prepareRow(y);
            for (int x=0; x<width; x += sparse3G ? ((x & 7) == 0 ? 1 : 7) : 1) {
                int i = y * width + x;
                javaSites3G++;
                int site = ((y & 1) << 1) | (x & 1);
                double lo = black[site];
                double denom = phaseDenom3F[site];
                int sourceCode2S = raw.get(i) & 0xffff;
                if (!sparse3G) {
                    if(sourceCode2S == white) sourceAtWhite2S[site]++;
                    if(sourceCode2S > white) sourceAboveWhite2S[site]++;
                }
                double base = sourceCode2S - lo;
                if (base < 0.0) base = 0.0;
                double unit = base / denom;
                if (unit > 1.0) { unit = 1.0; if (!sparse3G) whiteClipCount++; }

                // One green of each Bayer parity in each 8x8 tile.
                boolean ae1aSample = (site == 1 || site == 2)
                        && ((((y & 7) == 0) && ((x & 7) == 1))
                        || (((y & 7) == 1) && ((x & 7) == 0)));
                if (ae1aSample) {
                    ae1aFullSum += unit;
                    ae1aFullCount++;
                    int meterRow = Math.min(M10RIntegralMask.ROWS - 1,
                            Math.max(0, (int)((long)y * M10RIntegralMask.ROWS / height)));
                    int meterCol = Math.min(M10RIntegralMask.COLS - 1,
                            Math.max(0, (int)((long)x * M10RIntegralMask.COLS / width)));
                    int meterIndex = meterRow * M10RIntegralMask.COLS + meterCol;
                    ae1aRawGridSum[meterIndex] += unit;
                    ae1aRawGridCount[meterIndex]++;
                    int integralWeight = M10RIntegralMask.weight(meterRow, meterCol);
                    if (integralWeight > 0) {
                        ae1aIntegralWeightedSum += unit * integralWeight;
                        ae1aIntegralWeightSum += integralWeight;
                    }
                    double nx = (x + 0.5) / (double) width;
                    double ny = (y + 0.5) / (double) height;
                    double dx = Math.abs(nx - 0.5);
                    double dy = Math.abs(ny - 0.5);
                    if (dx <= 0.35 && dy <= 0.35) { ae1a70Sum += unit; ae1a70Count++; }
                    if (dx <= 0.225 && dy <= 0.225) { ae1a45Sum += unit; ae1a45Count++; }
                    if (dx <= 0.10 && dy <= 0.10) { ae1a20Sum += unit; ae1a20Count++; }
                }
                double gain = 1.0;
                if (map != null) {
                    gain = shading3F.gain(x, siteToGainChannel[site]);
                    if (!Double.isFinite(gain) || gain < 1.0) gain = 1.0;
                }
                if (!sparse3G) {
                    double stored = unit * gain * storageScale;
                    if (stored < 0.0) stored = 0.0;
                    if (stored > 1.0) stored = 1.0;
                    out[i] = (short)Math.round(stored * 65535.0);
                }
// METERAREA1A_INSERT_BEGIN

                // The top-left 2x2 in every 8x8 tile contains both green parities
                // for all four conventional Bayer arrangements, not just RGGB.
                int meterAreaChannel = siteToGainChannel[site];
                if ((meterAreaChannel == 1 || meterAreaChannel == 2)
                        && (x & 7) < 2 && (y & 7) < 2) {
                    int mr = Math.min(15, (int)((long)y * 16 / height));
                    int mc = Math.min(21, (int)((long)x * 22 / width));
                    int mi = mr * 22 + mc;
                    meterAreaPreSum[mi] += unit;
                    meterAreaPostSum[mi] += unit * gain;
                    meterAreaGainSum[mi] += gain;
                    meterAreaCounts[mi]++;
                }
// METERAREA1A_INSERT_END
            }
        }
        long javaScanNs3G = System.nanoTime() - javaScanStart3G;
        d.put("rawNormalization3G", new JSONObject()
                .put("revision", M10RPhotoNormalization3G.REVISION)
                .put("requested", BuildConfig.M10R_NATIVE_NORMALIZE3G)
                .put("nativeApplied", sparse3G).put("status", preparation3G.status)
                .put("nativeLibrary", sparse3G ? "existing_m10rexposureprep_EXPOSURE1E" : JSONObject.NULL)
                .put("nativeWorkers", sparse3G ? 4 : 0)
                .put("nativePreparationMs", preparation3G.elapsedNs / 1_000_000.0)
                .put("javaScanAndSetupMs", javaScanNs3G / 1_000_000.0)
                .put("subtimingsNestedIn", "rendererTiming3E.rawNormalizationWithInlineMeterStats")
                .put("subtimingsExclude", "initial_metadata_map_copy_and_final_diagnostic_JSON")
                .put("javaSensorSitesVisited", javaSites3G)
                .put("javaGainCacheScope", sparse3G ? "sparse_meter_samples" : "full_photographic_3F_fallback")
                .put("meterAccumulationOrderPreserved", true)
                .put("additionalPhotographicFrames", 0));
        d.put("blackLevel", json(black));
        d.put("whiteLevel", white);
        d.put("sourceWhiteLevelClampAppliedBeforeLensShading", true);
        d.put("lensShadingMapApplied", map != null);
        d.put("lensShadingMapColumns", cols);
        d.put("lensShadingMapRows", rows);
        d.put("lensShadingMaxGain", maxGain);
        d.put("lensShadingStorageScale", storageScale);
        d.put("lensShadingGainChannelMapping", json(siteToGainChannel));
        d.put("lensShadingHeadroomPolicy",
                "source_white_clamp_then_gainmap_then_scale_to_u16_inverse_scale_after_demosaic");

        double ae1aFullMean = ae1aFullCount > 0 ? ae1aFullSum / ae1aFullCount : 0.0;
        double ae1a70Mean = ae1a70Count > 0 ? ae1a70Sum / ae1a70Count : 0.0;
        double ae1a45Mean = ae1a45Count > 0 ? ae1a45Sum / ae1a45Count : 0.0;
        double ae1a20Mean = ae1a20Count > 0 ? ae1a20Sum / ae1a20Count : 0.0;
        double ae1aCenterWeightedMean =
                (200.0 * ae1a70Mean + 300.0 * ae1a45Mean + 500.0 * ae1a20Mean) / 1000.0;
        double ae1aIntegralMean = ae1aIntegralWeightSum > 0.0
                ? ae1aIntegralWeightedSum / ae1aIntegralWeightSum : 0.0;
        JSONObject ae1aProbe = new JSONObject()
                .put("enabled", true)
                .put("diagnosticOnly", true)
                .put("affectsPixels", false)
                .put("domain", "normalized_RAW_green_pre_lens_shading")
                .put("samplePattern", "two_green_CFA_sites_per_8x8_tile")
                .put("wholeMean", ae1aFullMean)
                .put("center70Mean", ae1a70Mean)
                .put("center45Mean", ae1a45Mean)
                .put("center20Mean", ae1a20Mean)
                .put("centerWeightedMean", ae1aCenterWeightedMean)
                .put("leicaIntegral16x22Mean", ae1aIntegralMean)
                .put("leicaIntegralMaskWeightSum", M10RIntegralMask.WEIGHT_SUM)
                .put("leicaIntegralMaskFirmwareRecovered", true)
                .put("wholeSamples", ae1aFullCount)
                .put("center70Samples", ae1a70Count)
                .put("center45Samples", ae1a45Count)
                .put("center20Samples", ae1a20Count)
                .put("centerWeights", "70pct=200,45pct=300,20pct=500_overlap_intentional");
        if (ae1aFullMean > 0.0 && ae1aCenterWeightedMean > 0.0) {
            ae1aProbe.put("centerWeightedVsWholeEv",
                    Math.log(ae1aCenterWeightedMean / ae1aFullMean) / Math.log(2.0));
        } else {
            ae1aProbe.put("centerWeightedVsWholeEv", JSONObject.NULL);
        }
        if (ae1aFullMean > 0.0 && ae1aIntegralMean > 0.0) {
            ae1aProbe.put("leicaIntegralVsWholeEv",
                    Math.log(ae1aIntegralMean / ae1aFullMean) / Math.log(2.0));
        } else {
            ae1aProbe.put("leicaIntegralVsWholeEv", JSONObject.NULL);
        }
        JSONArray ae1aRawRows = new JSONArray();
        for (int meterRow = 0; meterRow < M10RIntegralMask.ROWS; meterRow++) {
            JSONArray meterJsonRow = new JSONArray();
            for (int meterCol = 0; meterCol < M10RIntegralMask.COLS; meterCol++) {
                int meterIndex = meterRow * M10RIntegralMask.COLS + meterCol;
                long n = ae1aRawGridCount[meterIndex];
                meterJsonRow.put(n > 0L ? ae1aRawGridSum[meterIndex] / n : 0.0);
            }
            ae1aRawRows.put(meterJsonRow);
        }
        ae1aProbe.put("leicaRawGrid16x22", ae1aRawRows);
        ae1aProbe.put("leicaRawGridCoordinate", "source_sensor_top_down_left_right");
        d.put("m10rAe1A_rawMeterProbe", ae1aProbe);
// METERAREA1A_INSERT_BEGIN

        try {
            double[] pre = new double[352], post = new double[352], gains = new double[352];
            for (int mi=0; mi<352; mi++) {
                long n=meterAreaCounts[mi];
                pre[mi]=n>0?meterAreaPreSum[mi]/n:0;
                post[mi]=n>0?meterAreaPostSum[mi]/n:0;
                gains[mi]=n>0?meterAreaGainSum[mi]/n:1;
            }
            JSONObject areaRaw=new JSONObject().put("diagnosticOnly",true).put("affectsPixels",false)
                    .put("sampling","two_CFA_resolved_green_sites_per_8x8_tile")
                    .put("coordinate","existing_renderer_full_raw_normalized_coordinates")
                    .put("mapCoordinateCorrectnessIndependentlyVerified",false)
                    .put("postShadingDomain","unit_times_render_gain_before_storageScale_no_extra_clip")
                    .put("legacyGreenSamplingCompatible",cfa==0 || cfa==3)
                    .put("greenPreShadingGrid16x22",M10RMeterArea1A.grid(pre))
                    .put("greenPostShadingGrid16x22",M10RMeterArea1A.grid(post))
                    .put("meanGreenGainGrid16x22",M10RMeterArea1A.grid(gains))
                    .put("sampleCountsRowMajor",new JSONArray(meterAreaCounts))
                    .put("preShadingDecision",M10RMeterArea1A.decision(pre))
                    .put("postShadingDecision",M10RMeterArea1A.decision(post));
            d.put("m10rMeterAreaRaw1A",areaRaw);
        } catch(Exception areaRawError) {
            d.put("m10rMeterAreaRaw1A",new JSONObject().put("diagnosticOnly",true)
                    .put("status","telemetry_failed").put("error",areaRawError.toString()));
        }
// METERAREA1A_INSERT_END
        try { d.put("sourceSaturation2S",new JSONObject()
                .put("source","full_photographic_RAW_before_normalization_LSC_WB")
                .put("atWhiteByCfaPhase",new JSONArray(sourceAtWhite2S))
                .put("aboveWhiteByCfaPhase",new JSONArray(sourceAboveWhite2S))
                .put("totalSensorSites",(long)width*height).put("white",white)
                .put("legacySourceWhiteLevelClipCountSemantic","strictly_above_white_only"));
        } catch(Exception|OutOfMemoryError ignored) { /* diagnostic only */ }
        return new BayerFrame(out, storageScale, whiteClipCount);
    }

    private static double[] resolveBlack(CameraCharacteristics c, CaptureResult r) {
        float[] dyn = r.get(CaptureResult.SENSOR_DYNAMIC_BLACK_LEVEL);
        if (dyn != null && dyn.length >= 4) {
            return new double[]{dyn[0],dyn[1],dyn[2],dyn[3]};
        }
        BlackLevelPattern p = c.get(CameraCharacteristics.SENSOR_BLACK_LEVEL_PATTERN);
        int[] b = new int[4];
        if (p != null) p.copyTo(b, 0); else { b[0]=b[1]=b[2]=b[3]=64; }
        return new double[]{b[0],b[1],b[2],b[3]};
    }

    private static int resolveWhite(CameraCharacteristics c, CaptureResult r) {
        Integer dyn = r.get(CaptureResult.SENSOR_DYNAMIC_WHITE_LEVEL);
        if (dyn != null && dyn > 0) return dyn;
        Integer v = c.get(CameraCharacteristics.SENSOR_INFO_WHITE_LEVEL);
        if (v == null || v <= 0) throw new IllegalStateException("source white level missing");
        return v;
    }

    private static int[] gainChannelsForCfa(int cfa) {
        switch (cfa) {
            case 0: return new int[]{0,1,2,3};       // RGGB
            case 1: return new int[]{1,0,3,2};       // GRBG
            case 2: return new int[]{1,3,0,2};       // GBRG
            case 3: return new int[]{3,1,2,0};       // BGGR
            default: throw new IllegalArgumentException("unsupported CFA " + cfa);
        }
    }

    private static int demosaicCode(int cfa) {
        switch (cfa) {
            case 0: return Imgproc.COLOR_BayerRG2BGR_EA;
            case 1: return Imgproc.COLOR_BayerGR2BGR_EA;
            case 2: return Imgproc.COLOR_BayerGB2BGR_EA;
            case 3: return Imgproc.COLOR_BayerBG2BGR_EA;
            default: throw new IllegalArgumentException("unsupported CFA " + cfa);
        }
    }

    private static String cfaName(int cfa) {
        return new String[]{"RGGB","GRBG","GBRG","BGGR"}[cfa];
    }

    private static double bilinearGain(float[] map, int cols, int rows,
                                       int channel, double u, double v) {
        double gx = Math.max(0.0, Math.min(1.0,u)) * (cols-1);
        double gy = Math.max(0.0, Math.min(1.0,v)) * (rows-1);
        int x0=(int)Math.floor(gx), y0=(int)Math.floor(gy);
        int x1=Math.min(cols-1,x0+1), y1=Math.min(rows-1,y0+1);
        double fx=gx-x0, fy=gy-y0;
        double a=map[(y0*cols+x0)*4+channel];
        double b=map[(y0*cols+x1)*4+channel];
        double c=map[(y1*cols+x0)*4+channel];
        double e=map[(y1*cols+x1)*4+channel];
        return (a*(1-fx)+b*fx)*(1-fy) + (c*(1-fx)+e*fx)*fy;
    }

    private static double ca9Clip(double camera, int gain, long[] counts, int c) {
        double balanced = camera * gain / ASN_SCALE;
        if (balanced > 1.0) { balanced = 1.0; counts[c]++; }
        if (balanced < 0.0) balanced = 0.0;
        return balanced * ASN_SCALE / gain;
    }

    private static int[] recoverCa9Gains(double[] asn) {
        int[] g = new int[3];
        for (int i=0;i<3;i++) {
            if (!(asn[i] > 0.0) || !Double.isFinite(asn[i])) {
                throw new IllegalArgumentException("synthetic M10-R ASN invalid");
            }
            // Frozen RENDER_PARITY1A candidate behavior; exact integer parity is researched separately.
            int q = (int)Math.rint(ASN_SCALE / asn[i]);
            g[i] = Math.max(GAIN_MIN, Math.min(GAIN_MAX, q));
        }
        return g;
    }


    // RENDERDIAG2X: publication-only clarification. No bitmap, RAW, exposure or
    // renderer state enters this method; old numerical fields remain available.
    private static JSONObject annotateSignalStatistics2X(JSONObject statistics,
            long[] nativeCounts, boolean sampled) throws Exception {
        statistics.put("revision", "RENDERDIAG2X_STAGE_ATTRIBUTION");
        statistics.put("mixedProvenance", sampled);
        statistics.put("legacySampledStagesAvailable", sampled);
        statistics.put("legacySamplingStatus", sampled ? "enabled" : "disabled_RENDERPERF3F");
        if (sampled) statistics.put("sampledStageRoles", new JSONObject()
                .put("sampleStride", 64)
                .put("preTone", "actual_post_CA9_CC0_working_RGB_before_common_tone")
                .put("toneInputCoordinate", "legacy_Yc_luma_counterfactual_not_native_TCYC")
                .put("postMediumTone", "legacy_Yc_luma_counterfactual")
                .put("postDifferentialGamma", "legacy_luma_only_DG_counterfactual_not_native_RGB_DG")
                .put("preSrgb", "legacy_YBLEND1B_post_CC1_counterfactual_not_actual_output")
                .put("lumaGain", "legacy_mapped_Yc_over_input_Yc_not_native_common_tone_gain"));
        statistics.put("legacyRgbClipArraysMeasuredForActivePath", false);
        statistics.put("nativeCoordinateChecks", new JSONObject()
                .put("source", "m10rRender.cpp_nativeProcessTile_exact_full_frame_counters")
                .put("unit", "coordinate_checks_not_unique_pixels")
                .put("toneInputChecksPerPixel", 4)
                .put("toneInputCoordinates", "one_TCYC_luma_plus_three_order_dependent_RGB_DG_inputs")
                .put("toneInputClipLow", nativeCounts[3])
                .put("toneInputClipHigh", nativeCounts[4])
                .put("toneInputNonFinite", nativeCounts[5])
                .put("dgIndexChecksPerPixel", 3)
                .put("dgIndexClipLow", nativeCounts[6])
                .put("dgIndexClipHigh", nativeCounts[7])
                .put("separateLumaAndRgbCountsAvailable", false));
        if (sampled) statistics.put("legacyLumaCounterAliases", new JSONObject()
                .put("lumaToneInputClipLow", "nativeCoordinateChecks.toneInputClipLow")
                .put("lumaToneInputClipHigh", "nativeCoordinateChecks.toneInputClipHigh")
                .put("lumaToneInputNonFinite", "nativeCoordinateChecks.toneInputNonFinite")
                .put("lumaDifferentialGammaIndexClipLow", "nativeCoordinateChecks.dgIndexClipLow")
                .put("lumaDifferentialGammaIndexClipHigh", "nativeCoordinateChecks.dgIndexClipHigh"));
        return statistics;
    }

    private static double[] interpolateM10Profile(double kelvin) {
        if (kelvin <= 2856.0) return M10_CM_A.clone();
        if (kelvin >= 6504.0) return M10_CM_D65.clone();
        double g = (1.0/kelvin - 1.0/6504.0) / (1.0/2856.0 - 1.0/6504.0);
        double[] out = new double[9];
        for (int i=0;i<9;i++) out[i] = g*M10_CM_A[i] + (1.0-g)*M10_CM_D65[i];
        return out;
    }

    private static double xyToTemperatureLeica(double[] xy) {
        double x=xy[0], y=xy[1];
        double den=1.5-x+6.0*y;
        double u=2.0*x/den, v=3.0*y/den;
        double previous=Double.NaN;
        for (int i=1;i<LOCUS.length;i++) {
            double[] row=LOCUS[i];
            double distance=((v-row[2])-(u-row[1])*row[3])/row[4];
            if (distance <= 0.0) {
                double current=-distance;
                double fraction;
                if (i==1) fraction=0.0;
                else {
                    double sum=previous+current;
                    fraction=sum>0.0 ? current/sum : 0.5;
                }
                double mired=LOCUS[i-1][0]*fraction + row[0]*(1.0-fraction);
                return mired>0.0 ? 1_000_000.0/mired : 100000.0;
            }
            previous=distance;
        }
        return 1_000_000.0/LOCUS[LOCUS.length-1][0];
    }

    private static double[] mapWhite(double[] srcXy, double[] dstXy) {
        double[] src=matVec(BRADFORD,xyToXyz(srcXy));
        double[] dst=matVec(BRADFORD,xyToXyz(dstXy));
        double[] diag={dst[0]/src[0],0,0,0,dst[1]/src[1],0,0,0,dst[2]/src[2]};
        return matMul(BRADFORD_INV,matMul(diag,BRADFORD));
    }

    private static double[] xyToXyz(double[] xy) {
        return new double[]{xy[0]/xy[1],1.0,(1.0-xy[0]-xy[1])/xy[1]};
    }

    private static float[] transform(ColorSpaceTransform t) {
        if (t == null) return null;
        float[] out = new float[9];
        // SOURCECM1A: match Photon/M9 matrix representation exactly.
        Converter.convertColorspaceTransform(t, out);
        return out;
    }

    private static float[] rationalVector(Rational[] r) {
        if (r == null || r.length < 3) return null;
        return new float[]{r[0].floatValue(),r[1].floatValue(),r[2].floatValue()};
    }

    private static boolean valid9(float[] a) { return a != null && a.length == 9; }
    private static double[] toDouble(float[] a) {
        double[] d=new double[a.length]; for(int i=0;i<a.length;i++) d[i]=a[i]; return d;
    }
    private static double[] lerp9(double[] a,double[] b,double f) {
        double[] o=new double[9]; for(int i=0;i<9;i++) o[i]=a[i]*(1.0-f)+b[i]*f; return o;
    }
    private static double[] matMul(double[] a,double[] b) {
        double[] o=new double[9];
        for(int r=0;r<3;r++) for(int c=0;c<3;c++)
            o[r*3+c]=a[r*3]*b[c]+a[r*3+1]*b[3+c]+a[r*3+2]*b[6+c];
        return o;
    }
    private static double[] matVec(double[] a,double[] v) {
        return new double[]{a[0]*v[0]+a[1]*v[1]+a[2]*v[2],
                            a[3]*v[0]+a[4]*v[1]+a[5]*v[2],
                            a[6]*v[0]+a[7]*v[1]+a[8]*v[2]};
    }
    private static double[] inverse3(double[] m) {
        double a=m[0],b=m[1],c=m[2],d=m[3],e=m[4],f=m[5],g=m[6],h=m[7],i=m[8];
        double det=a*(e*i-f*h)-b*(d*i-f*g)+c*(d*h-e*g);
        if (!Double.isFinite(det) || Math.abs(det)<1e-15) throw new IllegalArgumentException("singular matrix");
        double s=1.0/det;
        return new double[]{(e*i-f*h)*s,(c*h-b*i)*s,(b*f-c*e)*s,
                            (f*g-d*i)*s,(a*i-c*g)*s,(c*d-a*f)*s,
                            (d*h-e*g)*s,(b*g-a*h)*s,(a*e-b*d)*s};
    }
    private static int toSrgb8(double linear) {
        double c=Math.max(0.0,Math.min(1.0,linear));
        double e=c<=0.0031308 ? 12.92*c : 1.055*Math.pow(c,1.0/2.4)-0.055;
        return (int)Math.round(Math.max(0.0,Math.min(1.0,e))*255.0);
    }

    private static JSONArray json(double[] a) throws Exception {
        JSONArray x=new JSONArray(); for(double v:a)x.put(v); return x;
    }
    private static JSONArray json(float[] a) throws Exception {
        JSONArray x=new JSONArray(); for(float v:a)x.put(v); return x;
    }
    private static JSONArray json(int[] a) throws Exception {
        JSONArray x=new JSONArray(); for(int v:a)x.put(v); return x;
    }
    private static JSONArray json(long[] a) throws Exception {
        JSONArray x=new JSONArray(); for(long v:a)x.put(v); return x;
    }
    private static JSONArray jsonMatrix(float[] a) throws Exception {
        JSONArray rows=new JSONArray();
        for(int r=0;r<3;r++) {
            JSONArray row=new JSONArray(); for(int c=0;c<3;c++) row.put(a[r*3+c]); rows.put(row);
        }
        return rows;
    }
// EXPOSURE1B_BRIDGE_BEGIN
    // Preview follows the saved-image matrices. METER1M opts the RAW exposure
    // probe into the same preparation/order, preserving the legacy A/B factory.
    static M10RExposureNative1B.Context previewContext1A(CameraCharacteristics characteristics,
            CaptureResult captureResult,String cameraKey) throws Exception {
        return legacyExposureContext1B(characteristics,captureResult,cameraKey)
                .withRenderedColor(RENDERED_COLOR,BuildConfig.M10R_RENDERED_COLOR1A,
                        BuildConfig.M10R_COLOR_ORDER1A);
    }

    private static void appendRenderedColor(JSONObject d,M10RRenderedColor1A.Result r) throws Exception {
        JSONObject record=new JSONObject()
                .put("revision",M10RRenderedColor1A.REVISION)
                .put("requested",BuildConfig.M10R_RENDERED_COLOR1A)
                .put("applied",r.applied).put("reason",r.reason)
                .put("meterMatricesChanged",BuildConfig.M10R_METER_RENDERER1M && BuildConfig.M10R_RENDERED_COLOR1A)
                .put("temperaturePairProvenance","nominal_2856_6504_reference_fixture_bridge")
                .put("ispMacParityClaimed",false)
                .put("targetToWorking",json(r.targetToWorking))
                .put("workingToOutput",json(r.workingToOutput));
        if (r.applied) {
            record.put("neutral",json(r.neutral)).put("whiteXy",json(r.whiteXy))
                    .put("kelvin",r.kelvin).put("iterations",r.passes)
                    .put("cc0Scale",r.cc0.scale).put("cc0Denominator",r.cc0.denominator)
                    .put("cc0Integers",json(r.cc0.integers)).put("cc0Clipped",r.cc0.clipped)
                    .put("cc1Scale",r.cc1.scale).put("cc1Denominator",r.cc1.denominator)
                    .put("cc1Integers",json(r.cc1.integers)).put("cc1Clipped",r.cc1.clipped);
        }
        d.put("renderedColor1A",record);
        d.put("rendererOrder1A",new JSONObject()
                .put("revision","M10R_COLORORDER1A_CC1_BEFORE_DG")
                .put("requested",BuildConfig.M10R_COLOR_ORDER1A)
                .put("applied",BuildConfig.M10R_COLOR_ORDER1A && r.applied)
                .put("meterOrderChanged",BuildConfig.M10R_METER_RENDERER1M && BuildConfig.M10R_COLOR_ORDER1A)
                .put("experimental",true)
                .put("firmwareRoutingProven",false));
    }

    static M10RExposureNative1B.Context exposureContext1B(CameraCharacteristics characteristics,
            CaptureResult captureResult,String cameraKey) throws Exception {
        return M10RExposureRenderer1M.select(
                legacyExposureContext1B(characteristics,captureResult,cameraKey),RENDERED_COLOR,
                BuildConfig.M10R_METER_RENDERER1M,BuildConfig.M10R_RENDERED_COLOR1A,
                BuildConfig.M10R_COLOR_ORDER1A);
    }

    private static M10RExposureNative1B.Context legacyExposureContext1B(CameraCharacteristics characteristics,
            CaptureResult captureResult,String cameraKey) throws Exception {
        Long frameTimestamp = captureResult.get(CaptureResult.SENSOR_TIMESTAMP);
        if(frameTimestamp==null||frameTimestamp<=0)throw new IllegalArgumentException("probe timestamp missing");
        JSONObject d = new JSONObject();
        SourceModel source = buildSourceModel(characteristics, captureResult, d);
        double[] targetProfile = interpolateM10Profile(source.sceneKelvin);
        double[] sceneWhiteXyz = xyToXyz(source.sceneXy);
        double[] targetNeutralRaw = matVec(targetProfile, sceneWhiteXyz);
        if (!(targetNeutralRaw[1] > 0.0)) throw new IllegalStateException("M10-R synthetic neutral invalid");
        double[] targetAsn = {
                targetNeutralRaw[0] / targetNeutralRaw[1],
                1.0,
                targetNeutralRaw[2] / targetNeutralRaw[1]
        };
        int[] ca9 = recoverCa9Gains(targetAsn);

        double[] d50ToScene = mapWhite(D50_XY, source.sceneXy);
        double[] sceneToD50 = mapWhite(source.sceneXy, D50_XY);
        double[] srcToXyz = toDouble(source.sensorToXyzD50);
        double[] srcToTargetCamera = matMul(targetProfile, matMul(d50ToScene, srcToXyz));
        // WORKING1A: keep Leica's fixed internal basis on the input side of
        // nonlinear B2Y processing; apply output CC1 only after MEDIUM/DG.
        double[] targetToWorking = matMul(PCS_TO_INTERNAL,
                matMul(sceneToD50, inverse3(targetProfile)));
        double[] workingToSrgb = DEFAULT_SRGB_CC1.clone();

        return new M10RExposureNative1B.Context(srcToTargetCamera,ca9,targetToWorking,workingToSrgb,cameraKey,frameTimestamp);
    }
    static double[] exposureBlack1B(CameraCharacteristics c,CaptureResult r){return resolveBlack(c,r);}
    static int exposureWhite1B(CameraCharacteristics c,CaptureResult r){return resolveWhite(c,r);}
// EXPOSURE1B_BRIDGE_END
}
