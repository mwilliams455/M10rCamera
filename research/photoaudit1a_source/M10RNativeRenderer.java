package com.particlesdevs.photoncamera.m10r;

import android.graphics.Bitmap;
import android.graphics.Matrix;
import android.graphics.Point;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.CaptureResult;
import android.hardware.camera2.params.BlackLevelPattern;
import android.hardware.camera2.params.ColorSpaceTransform;
import android.hardware.camera2.params.LensShadingMap;
import android.util.Rational;

import com.particlesdevs.photoncamera.processing.ImageFrame;
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
            int[] argbOut, long[] exactCounts);
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
        if (frame == null || frame.buffer == null) throw new IllegalArgumentException("RAW frame missing");
        if (characteristics == null || captureResult == null) {
            throw new IllegalArgumentException("Camera2 characteristics/result missing");
        }

        JSONObject d = new JSONObject();
        d.put("schema", SCHEMA);
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
        d.put("demosaicOutputChannelOrder", "RGB");
        d.put("demosaicChannelOrderFix", "RGBORDER1A");
        d.put("postDemosaicRedBlueSwapApplied", false);

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
        d.put("b2yInputCoordinateMapping", "DIAGNOSTIC_linear_sRGB_0_1_to_14bit_0_16383_round_clamp");
        d.put("b2yLiveSignalNormalizationFrozen", false);
        d.put("toneArithmetic", "Q15_idx_x_shift1_truncate_rounding_not_hardware_frozen");
        d.put("nonlinearPlacement", "M10R_internal_working_RGB_between_CC0_CC1");
        d.put("workingBasisPlacementFix", "WORKING1A");
        d.put("cc0WorkingBasisPlacement", "pre_MEDIUM_DG");
        d.put("cc1Placement", "post_MEDIUM_DG_after_Yc_exact_inverse_before_direct_8bit_output");
        d.put("workingBasisFirmwareEvidence", "v232_CC0_internal_tone_CC1_output");
        d.put("workingBasisPlacementExactHardwareParityClaimed", false);
        d.put("nonlinearApplicationMode", "M10R_Yc_Convert_map_Y_YBLEND1B_k035_chroma_exact_inverse");
        d.put("nonlinearLumaProxy", "M10R_Yc_Convert_Y_Q12_1224_2403_469");
        d.put("lookExperiment", "LOOK1B_YC1B");
        d.put("b2yYcConvertMatrixQ12", "1224,2403,469;-691,-1357,2048;2048,-1715,-333");
        d.put("b2yYcConvertMatrixDivisor", 4096);
        d.put("b2yChromaPolicy", "YBLEND1B_k035_between_absolute_and_relative_chroma_then_exact_matrix_inverse");
        d.put("yc2aMatrixCorrectionApplied", true);
        d.put("yc2aMatrixSource", "B2Y_record_0x0C_plus_IMG_System_driver_default_v123");
        d.put("yc2aMatrixRowSums", "4096,0,0");
        d.put("yc2aExactInverseApplied", true);
        d.put("yc2aYBlendStillDeferred", true);
        d.put("yc2aTrailingBoundaryPairsStillDeferred", true);
        d.put("b2yYBlendApplied", false);
        d.put("b2yLocalSixFieldConditioningApplied", false);
        d.put("toneCoordinateScalingStillProvisional", true);
        d.put("lumaGainStatisticSemantic", "mappedY_over_inputY_retained_as_diagnostic_full_relative_scale;_YBLEND1B_applies_k0p35_excess_gain_to_chroma_only");
        d.put("nonlinearChromaticityPreservationIntent", true);
        d.put("nonlinearPerChannelCurveApplied", false);

        double[] black = resolveBlack(characteristics, captureResult);
        int white = resolveWhite(characteristics, captureResult);
        LensShadingMap map = captureResult.get(CaptureResult.STATISTICS_LENS_SHADING_CORRECTION_MAP);
        BayerFrame normalized = normalizeBayer(
                frame.buffer, frame.width, frame.height, cfa, black, white, map, d);

        // Official OpenCV Android AAR from Maven Central supplies the Java API and
        // arm64-v8a/armeabi-v7a native runtime used only for deterministic EA demosaic.
        ensureOpenCv();
        d.put("openCvAndroidAar", "org.opencv:opencv:4.13.0");
        d.put("openCvPurpose", "single_frame_Bayer_EA_demosaic_only");

        Mat tileRaw = null;
        Mat tileBgr = null;
        Bitmap bitmap = null;
        try {
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
            final long[] nativeExactCounts = new long[8];
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
                int pixels = frame.width * rows;
                nativeProcessTile(
                        bgr, pixels, inverseStorageScale,
                        srcToTargetCamera, ca9, targetToWorking, workingToSrgb,
                        nativeToneTable, nativeDgTable, argb, nativeExactCounts);

                // Preserve the research distributions at the exact STABILITY2 1/64
                // sampling phase without making Java form any output pixels.
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
            d.put("toneDg1aSignalStatistics", toneDgStats.json());
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
            redTrace.put("cc1Matrix", "1.3895,-0.1693,-0.2202;-0.2288,1.2317,-0.0029;-0.0176,-0.0963,1.1139");
            redTrace.put("cc1RedEquation", "outR=1.3895*postYcR-0.1693*postYcG-0.2202*postYcB");
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
            redTrace1B.put("photographicOutputStillCc1Bypassed", true);
            redTrace1B.put("counterfactualCc1StillEvaluated", true);
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
                        binJson1B.put("meanCounterfactualPostCc1R", bs1B[6] / n1B);
                        binJson1B.put("meanCounterfactualPostCc1G", bs1B[7] / n1B);
                        binJson1B.put("meanCounterfactualPostCc1B", bs1B[8] / n1B);
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

            d.put("renderStabilityFix", "STABILITY3_NATIVE1_FOUR_THREAD_PIXEL_CORE");
            d.put("nativePixelCore", true);
            d.put("nativePixelCoreThreads", 4);
            d.put("nativePixelCoreLibrary", "dngCreator/m10rRender.cpp");
            d.put("diagnosticSamplingStride", 64);
            d.put("diagnosticSamplingAffectsPixels", false);
            d.put("demosaicTileRows", blockRows);
            d.put("demosaicHaloRows", demosaicHaloRows);
            d.put("fullFrameBgrMatAllocated", false);
            d.put("secondRotationBitmapAllocated", false);
            d.put("cameraRotationDegrees", rotation);
            Integer edgeIsoObj = captureResult.get(CaptureResult.SENSOR_SENSITIVITY);
            int edgeIso = edgeIsoObj != null && edgeIsoObj > 0 ? edgeIsoObj : 100;
            // EDGE0A: bounded bypass. Keep the native EDGE1A implementation
            // resident, but do not execute it on the photographic bitmap.
            long edgeAffectedPixels = 0L;
            double edgeElapsedMs = 0.0;

            // TRANSFER1A: preserve the entire WORKING1A + EDGE1A path, then
            // cancel only the final textbook sRGB coding before JPEG save.
            // NATIVEOUT1A: no separate display-transfer pass.  The native
            // pixel core now publishes post-CC1 values directly with 8-bit
            // linear clamp/round.  EDGE0A remains bypassed.
            long transferPixels = 0L;
            double transferElapsedMs = 0.0;
            d.put("renderLook", "RENDER1Q_CC1MAP1A_YBLEND1B_K035_REDTRACE1B_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A");
            d.put("yBlend1BProbeK", 0.35);
            d.put("yBlend1BOnlyPhotographicVariable", true);
            d.put("cc1MappingFix", "CC1MAP1A");
            d.put("cc1FactoryStillColorSpace", "sRGB");
            d.put("cc1Ca9ModeIndex", 0);
            d.put("cc1Semantic", "ProPhoto_RGB_to_sRGB");
            d.put("cc1Mode1PriorMislabel", "ProPhoto_RGB_to_AdobeRGB");
            d.put("cc1MappingFirmwareEvidence", "v231_factory_sRGB_to_CA9_mode0_plus_v230_field1_standard_matrix_closure");
            d.put("photographicConvergenceExperiment", "YBLEND1B_K035_CONTROLLED_PROBE_AFTER_CC1MAP1A");
            d.put("cc1RestoreOnlyPhotographicVariable", true);
            d.put("chromaReconstructionExperiment", "YBLEND1B_K035");
            d.put("yBlend1BExperimentalApplied", true);
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
            d.put("cc1RedTraceMatchesPhotographicOutput", true);
            d.put("cc1On1ARestoresFinalColourOnly", true);
            d.put("cc1Input", "post_Yc_exact_inverse_working_RGB");
            d.put("cc1Output", "post_CC1_output_RGB_direct_linear8");
            d.put("preSrgbStatisticsRole", "actual_post_CC1_photographic_output");
            d.put("redTraceExperiment", "REDTRACE1A_YC_INVERSE_VS_CC1_EXCURSION");
            d.put("redTracePhotographicPixelsChanged", false);
            d.put("redTraceSamplingStride", 64);
            d.put("redTracePurpose", "locate_red_above_one_before_or_after_CC1_without_colour_tuning");
            d.put("outputTransferExperiment", "NATIVEOUT1A_DIRECT_POST_CC1_LINEAR8");
            d.put("outputTransferPlacement", "native_post_CC1_direct_8bit_before_JPEG");
            d.put("working1aNativeSrgbOetfRetainedForEdgeInvariant", false);
            d.put("edgeInputDomainUnchangedFromWorking1A", false);
            d.put("edgeInputDomainNotApplicableDueEdge0A", true);
            d.put("netOutputTransfer", "post_CC1_linear_direct_8bit");
            d.put("outputTransferQuantization", "direct_8bit_linear_round_clamp");
            d.put("outputTransferExactHardwareParityClaimed", false);
            d.put("outputTransferPixels", transferPixels);
            d.put("outputTransferElapsedMs", transferElapsedMs);
            d.put("outputTransferSeparatePassExecuted", false);
            d.put("textbookSrgbOetfApplied", false);
            d.put("transfer1aInverseExecuted", false);
            d.put("transferRoundTripRemoved", true);
            d.put("nativePixelOutputQuantizer", "linear8_post_CC1");
            d.put("inverseSrgbImplementationRetainedUnused", true);
            d.put("edgePassEnabled", false);
            d.put("edgeExperiment", "EDGE0A_BYPASS_ONLY");
            d.put("edgeCallExecuted", false);
            d.put("edgeNativeImplementationRetained", true);
            d.put("edgeBypassReason", "domain_provisional_isolation_before_clean_native_output");
            d.put("edge0aOnlyPhotographicVariable", true);
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
            d.put("edgeElapsedMs", edgeElapsedMs);
            d.put("edgeArithmeticExactFirmwareParityClaimed", false);
            d.put("edgeScaleTableApplied", false);
            d.put("edgeScaleTableSource", "B2Y_record_0x1E_HighEdge_Scale_Table_exact_16384_u16");
            d.put("edgeScaleTableSha256", "e4e8da0735a8847d4cc3c3766b58818ec29fe31d42d0710880a880e4ba7b8d1a");
            d.put("edgeScaleTableEntries", 16384);
            d.put("edgeScaleTableMin", 358);
            d.put("edgeScaleTableMax", 1023);
            d.put("edgeScaleCoordinate", "center_Y14_INFERRED_FROM_14BIT_SCALE_DOMAIN_EXPERIMENTAL");
            d.put("edgeScaleNormalization", "scale_u10_over_1023_EXPERIMENTAL");
            d.put("edgeHfRecordGainApplied", false);
            d.put("edgeHfRecordGainSource", "B2Y_record_0x0F_offset_0x118_10bit");
            d.put("edgeHfRecordGainValues", "ISO100_160=160,ISO200_640=128,ISO800plus=80");
            d.put("edgeHfRecordGainNormalization", "value_over_256_Q8_GAIN_CANDIDATE");
            d.put("edgeHfRecordGainSemanticExactFirmwareParityClaimed", false);
            d.put("edgeHfRecordMaxField0x11c", 1023);
            d.put("edgeHfRecordMaxFieldSemantic", "10bit_fullscale_constant_role_not_yet_proven");
            d.put("edgeStepTableIdentity", true);
            d.put("edgeStepTableAppliedSeparately", false);
            d.put("edgeStepTableReason", "firmware_HighEdge_Step_Table_is_exact_identity_0_to_8191");
            d.put("edgePlacement", "post_LOOK1B_sRGB_decode_linear_Y_reencode_EXPERIMENTAL");
            d.put("textureEnhancementBlockEnabled", false);
            d.put("textureEnhancementReason", "firmware_calibration_enable_field_is_zero");
            d.put("lowFrequencyEdgeApplied", false);
            d.put("lowFrequencyEdgeReason", "combination_scaling_not_yet_constrained_enough");
            d.put("outputWidth", bitmap.getWidth());
            d.put("outputHeight", bitmap.getHeight());
            d.put("status", "success");
            d.put("renderElapsedMs", (System.nanoTime() - startNs) / 1_000_000.0);
            return new Result(bitmap, d);
        } catch (Throwable t) {
            if (bitmap != null && !bitmap.isRecycled()) bitmap.recycle();
            if (t instanceof Exception) throw (Exception)t;
            throw new RuntimeException(t);
        } finally {
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
        if (!valid9(cal1) || !valid9(cal2) || !valid9(cm1) || !valid9(cm2)
                || !valid9(fm1) || !valid9(fm2) || neutral == null) {
            throw new IllegalStateException("native Camera2 dual-illuminant source metadata incomplete");
        }

        // SOURCECAL2A correction: ColorMatrix stays XYZ->reference-camera unmodified.
        // Only ForwardMatrix gets Converter's DNG forward normalization.
        float[] nfm1 = fm1.clone();
        float[] nfm2 = fm2.clone();
        Converter.normalizeFM(nfm1);
        Converter.normalizeFM(nfm2);
        double factor = Converter.findDngInterpolationFactor(
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
        short[] out = new short[pixels];

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
        int[] siteToGainChannel = gainChannelsForCfa(cfa);
        long whiteClipCount = 0L;

        for (int y=0, i=0; y<height; y++) {
            double v = height > 1 ? y/(double)(height-1) : 0.0;
            for (int x=0; x<width; x++, i++) {
                int site = ((y & 1) << 1) | (x & 1);
                double lo = black[site];
                double denom = Math.max(1.0, white - lo);
                double base = (raw.get(i) & 0xffff) - lo;
                if (base < 0.0) base = 0.0;
                double unit = base / denom;
                if (unit > 1.0) { unit = 1.0; whiteClipCount++; }
                double gain = 1.0;
                if (map != null) {
                    double u = width > 1 ? x/(double)(width-1) : 0.0;
                    gain = bilinearGain(map, cols, rows, siteToGainChannel[site], u, v);
                    if (!Double.isFinite(gain) || gain < 1.0) gain = 1.0;
                }
                double stored = unit * gain * storageScale;
                if (stored < 0.0) stored = 0.0;
                if (stored > 1.0) stored = 1.0;
                out[i] = (short)Math.round(stored * 65535.0);
            }
        }
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
}
