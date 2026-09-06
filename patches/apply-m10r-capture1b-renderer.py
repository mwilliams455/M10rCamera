#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: apply-m10r-capture1b-renderer.py <PhotonCamera-root>')

root = Path(sys.argv[1]).resolve()
if not (root / 'app').is_dir():
    raise SystemExit('CAPTURE1B: not a PhotonCamera root')

def read(rel):
    p = root / rel
    if not p.exists():
        raise SystemExit('CAPTURE1B missing expected file: ' + rel)
    return p.read_text()

def write(rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)

# CAPTURE1B is applied only after the already-proven CAPTURE1 single-frame patch.
gradle_rel = 'app/build.gradle'
g = read(gradle_rel)
old = "versionName '0.97-m10rcapture1'"
if g.count(old) != 1:
    raise SystemExit('CAPTURE1B requires exactly one CAPTURE1 versionName anchor')
g = g.replace(old, "versionName '0.97-m10rcapture1b'", 1)
write(gradle_rel, g)

for rel in ['app/src/main/res/values/strings.xml', 'app/src/main/res/values-ko-rKR/strings.xml']:
    p = root / rel
    if not p.exists():
        continue
    s = p.read_text()
    old_name = '<string name="app_name" translatable="false">M10RCam Capture1</string>'
    if old_name not in s:
        raise SystemExit('CAPTURE1B app-name anchor missing in ' + rel)
    p.write_text(s.replace(old_name,
            '<string name="app_name" translatable="false">M10RCam Capture1B</string>', 1))

renderer_rel = 'app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'
if (root / renderer_rel).exists():
    raise SystemExit('CAPTURE1B renderer already exists; refusing ambiguous reapply')

renderer_java = r'''package com.particlesdevs.photoncamera.m10r;

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
    public static final String SCHEMA =
            "m10rcam.capture1b.nativecamera2_xyz_d50.m10r_c_promoted.v1";
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
    private static final double[] DEFAULT_SRGB_CC1 = {
            1.3895, -0.1693, -0.2202,
           -0.2288,  1.2317, -0.0029,
           -0.0176, -0.0963,  1.1139
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
        double[] targetToSrgb = matMul(DEFAULT_SRGB_CC1,
                matMul(PCS_TO_INTERNAL, matMul(sceneToD50, inverse3(targetProfile))));

        d.put("sourceInterpolationFactor", source.interpolationFactor);
        d.put("sceneWhiteX", source.sceneXy[0]);
        d.put("sceneWhiteY", source.sceneXy[1]);
        d.put("sceneCctKelvinLeicaLocus", source.sceneKelvin);
        d.put("m10rSyntheticAsShotNeutral", json(targetAsn));
        d.put("m10rCa9Gains", json(ca9));
        d.put("rawHeadroomRetained", false);
        d.put("ca9NeutralClipEnabled", true);

        double[] black = resolveBlack(characteristics, captureResult);
        int white = resolveWhite(characteristics, captureResult);
        LensShadingMap map = captureResult.get(CaptureResult.STATISTICS_LENS_SHADING_CORRECTION_MAP);
        BayerFrame normalized = normalizeBayer(
                frame.buffer, frame.width, frame.height, cfa, black, white, map, d);

        Mat rawMat = null;
        Mat bgr16 = null;
        Bitmap bitmap = null;
        try {
            rawMat = new Mat(frame.height, frame.width, CvType.CV_16UC1);
            rawMat.put(0, 0, normalized.data);
            bgr16 = new Mat();
            Imgproc.cvtColor(rawMat, bgr16, demosaicCode(cfa));
            rawMat.release();
            rawMat = null;

            bitmap = Bitmap.createBitmap(frame.width, frame.height, Bitmap.Config.ARGB_8888);
            final int blockRows = 64;
            short[] bgr = new short[Math.multiplyExact(frame.width * blockRows, 3)];
            int[] argb = new int[frame.width * blockRows];
            long[] neutralClipCounts = new long[3];
            double inverseStorageScale = 1.0 / normalized.storageScale;

            for (int y0 = 0; y0 < frame.height; y0 += blockRows) {
                int rows = Math.min(blockRows, frame.height - y0);
                int shortCount = frame.width * rows * 3;
                if (bgr.length < shortCount) bgr = new short[shortCount];
                bgr16.get(y0, 0, bgr);
                int pixels = frame.width * rows;
                for (int i = 0; i < pixels; i++) {
                    double sb = (bgr[i * 3] & 0xffff) / 65535.0 * inverseStorageScale;
                    double sg = (bgr[i * 3 + 1] & 0xffff) / 65535.0 * inverseStorageScale;
                    double sr = (bgr[i * 3 + 2] & 0xffff) / 65535.0 * inverseStorageScale;

                    double tr = srcToTargetCamera[0]*sr + srcToTargetCamera[1]*sg + srcToTargetCamera[2]*sb;
                    double tg = srcToTargetCamera[3]*sr + srcToTargetCamera[4]*sg + srcToTargetCamera[5]*sb;
                    double tb = srcToTargetCamera[6]*sr + srcToTargetCamera[7]*sg + srcToTargetCamera[8]*sb;

                    tr = ca9Clip(tr, ca9[0], neutralClipCounts, 0);
                    tg = ca9Clip(tg, ca9[1], neutralClipCounts, 1);
                    tb = ca9Clip(tb, ca9[2], neutralClipCounts, 2);

                    double lr = targetToSrgb[0]*tr + targetToSrgb[1]*tg + targetToSrgb[2]*tb;
                    double lg = targetToSrgb[3]*tr + targetToSrgb[4]*tg + targetToSrgb[5]*tb;
                    double lb = targetToSrgb[6]*tr + targetToSrgb[7]*tg + targetToSrgb[8]*tb;
                    argb[i] = 0xff000000 | (toSrgb8(lr) << 16) | (toSrgb8(lg) << 8) | toSrgb8(lb);
                }
                bitmap.setPixels(argb, 0, frame.width, 0, y0, frame.width, rows);
            }
            d.put("neutralDomainClipCounts", json(neutralClipCounts));
            d.put("sourceWhiteLevelClipCount", normalized.sourceWhiteClipCount);

            bgr16.release();
            bgr16 = null;

            int rotation = ((cameraRotation % 360) + 360) % 360;
            if (rotation != 0) {
                Matrix m = new Matrix();
                m.postRotate(rotation);
                Bitmap rotated = Bitmap.createBitmap(bitmap, 0, 0,
                        bitmap.getWidth(), bitmap.getHeight(), m, true);
                if (rotated != bitmap) bitmap.recycle();
                bitmap = rotated;
            }
            d.put("cameraRotationDegrees", rotation);
            d.put("outputWidth", bitmap.getWidth());
            d.put("outputHeight", bitmap.getHeight());
            d.put("status", "success");
            d.put("renderElapsedMs", (System.nanoTime() - startNs) / 1_000_000.0);
            return new Result(bitmap, d);
        } catch (Throwable t) {
            if (bitmap != null && !bitmap.isRecycled()) bitmap.recycle();
            throw t;
        } finally {
            if (rawMat != null) rawMat.release();
            if (bgr16 != null) bgr16.release();
        }
    }

    public static void persistDiagnostics(Path dngPath, JSONObject diagnostics) {
        if (dngPath == null || diagnostics == null) return;
        try {
            String name = dngPath.getFileName().toString();
            int dot = name.lastIndexOf('.');
            String stem = dot > 0 ? name.substring(0, dot) : name;
            Path sidecar = dngPath.resolveSibling(stem + "_M10R_CAPTURE1B.json");
            Files.write(sidecar,
                    diagnostics.toString(2).getBytes(StandardCharsets.UTF_8));
        } catch (Throwable ignored) {}
    }

    private static SourceModel buildSourceModel(CameraCharacteristics c,
                                                CaptureResult r,
                                                JSONObject d) throws Exception {
        Integer ref1Obj = c.get(CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT1);
        Integer ref2Obj = c.get(CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT2);
        if (ref1Obj == null) throw new IllegalStateException("source illuminant1 missing");
        int ref1 = ref1Obj;
        int ref2 = ref2Obj != null ? ref2Obj : ref1;
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
        Rational[] r=new Rational[9];
        t.copyElements(r,0);
        float[] out=new float[9];
        for(int i=0;i<9;i++) out[i]=r[i].floatValue();
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
'''
write(renderer_rel, renderer_java)

saver_rel = 'app/src/main/java/com/particlesdevs/photoncamera/processing/DefaultSaver.java'
s = read(saver_rel)
import_anchor = 'import com.particlesdevs.photoncamera.processing.processor.UnlimitedProcessor;\n'
if import_anchor not in s:
    raise SystemExit('CAPTURE1B DefaultSaver import anchor missing')
s = s.replace(import_anchor, import_anchor +
        'import com.particlesdevs.photoncamera.m10r.M10RNativeRenderer;\n', 1)

old_block = '''        // M10R CAPTURE1: one untouched RAW DNG, then stop before Hdrx/PostPipeline.
        if (PhotonCamera.getSettings().selectedMode == com.particlesdevs.photoncamera.api.CameraMode.PHOTO) {
            Path capture1Dng = ImagePath.newDNGFilePath();
            ImageFrame capture1Frame = IMAGE_BUFFER.get(0);
            boolean capture1Saved = false;
            try {
                capture1Saved = ImageSaver.Util.saveSingleRaw(
                        capture1Dng, capture1Frame, characteristics, captureResult, cameraRotation);
                processingEventsListener.notifyImageSavedStatus(capture1Saved, capture1Dng);
                processingEventsListener.onProcessingFinished(
                        capture1Saved
                                ? "M10-R CAPTURE1: single RAW DNG saved"
                                : "M10-R CAPTURE1: RAW save failed");
            } finally {
                capture1Frame.close();
                IMAGE_BUFFER.clear();
                bufferLock = false;
            }
            return;
        }
'''
new_block = '''        // M10R CAPTURE1B: one RAW frame -> untouched DNG + Cobalt-free native-source M10-R C JPEG.
        if (PhotonCamera.getSettings().selectedMode == com.particlesdevs.photoncamera.api.CameraMode.PHOTO) {
            Path capture1Dng = ImagePath.newDNGFilePath();
            Path capture1Jpeg = ImagePath.newImageFilePath();
            ImageFrame capture1Frame = IMAGE_BUFFER.get(0);
            boolean dngSaved = false;
            boolean jpegSaved = false;
            M10RNativeRenderer.Result capture1b = null;
            try {
                // DNG publication is unconditional for CAPTURE1B; Photon HDR/PostPipeline remains bypassed.
                dngSaved = ImageSaver.Util.saveSingleRaw(
                        capture1Dng, capture1Frame, characteristics, captureResult, cameraRotation);
                processingEventsListener.notifyImageSavedStatus(dngSaved, capture1Dng);
                try {
                    capture1b = M10RNativeRenderer.render(
                            capture1Frame, characteristics, captureResult, captureRequest, cameraRotation);
                    capture1b.diagnostics.put("dngSaved", dngSaved);
                    capture1b.diagnostics.put("dngPath", capture1Dng.toString());
                    capture1b.diagnostics.put("jpegPath", capture1Jpeg.toString());
                    jpegSaved = ImageSaver.Util.saveBitmapAsJPG(
                            capture1Jpeg, capture1b.bitmap, 95,
                            ParseExif.parse(captureResult, captureRequest));
                    capture1b.diagnostics.put("jpegSaved", jpegSaved);
                    processingEventsListener.notifyImageSavedStatus(jpegSaved, capture1Jpeg);
                } catch (Throwable renderError) {
                    Log.e(TAG, "M10-R CAPTURE1B renderer failed; DNG preserved", renderError);
                    if (capture1b != null) {
                        try { capture1b.diagnostics.put("rendererError", renderError.toString()); } catch (Throwable ignored) {}
                    }
                } finally {
                    if (capture1b != null) {
                        M10RNativeRenderer.persistDiagnostics(capture1Dng, capture1b.diagnostics);
                    }
                }
                processingEventsListener.onProcessingFinished(
                        jpegSaved
                                ? "M10-R CAPTURE1B: DNG + promoted-C JPEG saved"
                                : (dngSaved
                                    ? "M10-R CAPTURE1B: DNG saved; JPEG render failed"
                                    : "M10-R CAPTURE1B: capture save failed"));
            } finally {
                capture1Frame.close();
                IMAGE_BUFFER.clear();
                bufferLock = false;
            }
            return;
        }
'''
if s.count(old_block) != 1:
    raise SystemExit('CAPTURE1B requires exactly one CAPTURE1 DefaultSaver block')
s = s.replace(old_block, new_block, 1)
write(saver_rel, s)

for rel, needles in {
    gradle_rel: ["0.97-m10rcapture1b"],
    saver_rel: ['M10RNativeRenderer.render(', 'saveBitmapAsJPG(', 'DNG publication is unconditional', 'capture1Frame.close()'],
    renderer_rel: ['cobaltRuntimeDependency", false', 'fourBayerPatternsSupported", true',
                   'sourceColorMatrixRowNormalizationApplied", false', 'ca9NeutralClipEnabled", true',
                   'COLOR_BayerGR2BGR_EA', 'gainChannelsForCfa']
}.items():
    text=read(rel)
    for needle in needles:
        if needle not in text:
            raise SystemExit('CAPTURE1B verify failed: %r missing from %s' % (needle, rel))

print('M10-R CAPTURE1B renderer patch applied')
print(' - single RAW/DNG capture foundation preserved')
print(' - Camera2 native dual-illuminant source -> XYZ D50')
print(' - CFA-aware RGGB/GRBG/GBRG/BGGR lens shading + EA demosaic')
print(' - synthetic M10-R camera domain + promoted C CA9 neutral clip')
print(' - Cobalt runtime dependency: none')
print(' - JPEG + JSON diagnostic sidecar wired; no HDR/PostPipeline')
