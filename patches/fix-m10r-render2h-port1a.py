#!/usr/bin/env python3
"""RENDER2H PORT1A: physical-sensor CFA authority + all-lens RAW-meter portability.

This patch is intentionally downstream of the validated RENDER2G YA_TOPOLOGY1A
renderer. It does not change m10rRender.cpp, RENDER2G colour/tone/gamut math,
JPEG quality, capture frame count, WB/source matrix math, or the MFM1B formula.

Changes:
1. Make the post-capture RAW MFM oracle choose semantic green CFA sites for all
   four conventional Bayer arrangements instead of hard-coding local sites 1/2.
   RGGB/BGGR keep exactly the previous two green sample coordinates.
2. Keep Camera2 physical CFA as the renderer authority and expose that contract
   explicitly in diagnostics.
3. Make the M10-R DNG writer use the active physical Camera2 CFA, preventing a
   Photon/global CFA override from writing the wrong Bayer tag.
4. Add fail-closed portability/provenance checks. No Cobalt/HSM source profile
   is introduced; source calibration remains active physical Camera2/DNG data.
"""
from pathlib import Path
import hashlib
import json
import re
import sys

VALIDATED_CPP_SHA = "3f7b696cdf33e29348d7c0532f658c11819f9b8e54772b55753e357fb6018985"

def once(s, old, new, label):
    n = s.count(old)
    if n != 1:
        raise RuntimeError(f"PORT1A {label}: expected one anchor, found {n}")
    return s.replace(old, new, 1)

def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: fix-m10r-render2h-port1a.py <PhotonCamera-root>")
    root = Path(sys.argv[1]).resolve()
    renderer = root / "app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java"
    saver = root / "app/src/main/java/com/particlesdevs/photoncamera/processing/ImageSaver.java"
    default_saver = root / "app/src/main/java/com/particlesdevs/photoncamera/processing/DefaultSaver.java"
    gradle = root / "app/build.gradle"
    cpp = root / "app/src/main/cpp/m10rRender.cpp"
    for p in (renderer, saver, default_saver, gradle, cpp):
        if not p.is_file():
            raise RuntimeError("PORT1A missing " + str(p))

    cpp_before = hashlib.sha256(cpp.read_bytes()).hexdigest()
    if cpp_before != VALIDATED_CPP_SHA:
        raise RuntimeError("PORT1A refuses non-RENDER2G native source: " + cpp_before)

    r = renderer.read_text()

    # Final assembled RENDER2G must already be physically sourced and Cobalt-free.
    for marker in [
        'cobaltRuntimeDependency", false',
        'fourBayerPatternsSupported", true',
        'sourceColorMatrixConvention", "DNG_XYZ_to_reference_camera_unmodified"',
        'sourceForwardMatrixNormalizationApplied", true',
        'RENDER2G_YATOPOLOGY1A_GAMUT1A_TONECAL1A_MFM1B_EDGE0A',
    ]:
        if marker not in r:
            raise RuntimeError("PORT1A missing frozen baseline marker: " + marker)

    # AE1A/GRIDMAP1A inherited an RGGB-specific green-site assumption.
    # For RGGB/BGGR, semantic green remains sites 1/2 and therefore samples the
    # exact same pixels as before. For GRBG/GBRG, semantic green is sites 0/3.
    old_sample = '''                // One green of each Bayer parity in each 8x8 tile.
                boolean ae1aSample = (site == 1 || site == 2)
                        && ((((y & 7) == 0) && ((x & 7) == 1))
                        || (((y & 7) == 1) && ((x & 7) == 0)));
'''
    new_sample = '''                // PORT1A: choose the two semantic green sites from the active
                // physical Bayer pattern. The first 2x2 cell of every 8x8 tile
                // contains exactly two greens for every conventional Bayer CFA.
                // RGGB/BGGR therefore remain pixel-identical to the old sample
                // positions; GRBG/GBRG now stop sampling red/blue as "green".
                int ae1aSemanticPlane = siteToGainChannel[site];
                boolean ae1aSample = (ae1aSemanticPlane == 1 || ae1aSemanticPlane == 2)
                        && ((y & 7) <= 1) && ((x & 7) <= 1);
'''
    r = once(r, old_sample, new_sample, "CFA-aware RAW meter sample")

    # Make the source/target boundary explicit. These are diagnostics only.
    cfa_anchor = '        d.put("fourBayerPatternsSupported", true);\n'
    cfa_diag = cfa_anchor + '''        d.put("cfaAuthority", "active_physical_Camera2_characteristics");
        d.put("rawOriginX", 0);
        d.put("rawOriginY", 0);
        d.put("rawOriginProven", false);
        d.put("rawOriginEvidence",
                "Photon_ImageFrame_full_RAW_local_origin0_do_not_shift_by_active_array_without_buffer_coordinate_proof");
        d.put("sourceCalibrationPerPhysicalSensor", true);
        d.put("sourceAdapterBoundary", "physical_RAW_to_Camera2_DNG_XYZ_D50_then_shared_M10R_target");
        d.put("targetRendererLensIndependent", true);
        d.put("hsmRuntimeDependency", false);
        d.put("perLensTargetLook", false);
'''
    r = once(r, cfa_anchor, cfa_diag, "source-boundary diagnostics")

    # Update only the RAW-meter diagnostic wording/provenance.
    r = once(
        r,
        '.put("samplePattern", "two_green_CFA_sites_per_8x8_tile")',
        '.put("samplePattern", "two_semantic_green_CFA_sites_per_8x8_tile")\n'
        '                .put("cfaAwareGreenSelection", true)\n'
        '                .put("greenSelectionAuthority", "gainChannelsForCfa_active_physical_CFA")',
        "RAW meter diagnostic"
    )
    renderer.write_text(r)

    # Mirror the M9 CFAAUTHORITY solution for the M10-R DNG route only.
    s = saver.read_text()
    old_method = '''        public static boolean saveSingleRaw(Path dngFilePath,
                                            ImageFrame image,
                                            CameraCharacteristics characteristics,
                                            CaptureResult captureResult,
                                            int cameraRotation) {
            Parameters parameters = new Parameters();

            parameters.FillConstParameters(characteristics, new Point(image.width, image.height));
            int iso = captureResult.get(CaptureResult.SENSOR_SENSITIVITY);
            parameters.FillDynamicParameters(captureResult, null, iso);
            parameters.cameraRotation = cameraRotation;
            Log.d(TAG, "Camera rotation: " + parameters.cameraRotation);
            Log.d(TAG, "activearr:" + characteristics.get(CameraCharacteristics.SENSOR_INFO_ACTIVE_ARRAY_SIZE));
            Log.d(TAG, "precorr:" + characteristics.get(CameraCharacteristics.SENSOR_INFO_PRE_CORRECTION_ACTIVE_ARRAY_SIZE));
            return saveSingleRaw(dngFilePath, image.buffer, parameters);
        }
'''
    new_method = '''        public static boolean saveSingleRaw(Path dngFilePath,
                                            ImageFrame image,
                                            CameraCharacteristics characteristics,
                                            CaptureResult captureResult,
                                            int cameraRotation) {
            return saveSingleRawInternal(dngFilePath, image, characteristics, captureResult,
                    cameraRotation, false);
        }

        /**
         * M10R PORT1A: DNG metadata must describe the active physical RAW mosaic.
         * Camera2 physical CFA wins over Photon's optional/global CFA override.
         * Ordinary Photon callers keep the legacy behavior above.
         */
        public static boolean saveSingleRawM10RPhysicalCfa(Path dngFilePath,
                                                           ImageFrame image,
                                                           CameraCharacteristics characteristics,
                                                           CaptureResult captureResult,
                                                           int cameraRotation) {
            return saveSingleRawInternal(dngFilePath, image, characteristics, captureResult,
                    cameraRotation, true);
        }

        private static boolean saveSingleRawInternal(Path dngFilePath,
                                                     ImageFrame image,
                                                     CameraCharacteristics characteristics,
                                                     CaptureResult captureResult,
                                                     int cameraRotation,
                                                     boolean physicalCfaAuthority) {
            Parameters parameters = new Parameters();

            parameters.FillConstParameters(characteristics, new Point(image.width, image.height));
            if (physicalCfaAuthority && characteristics != null) {
                Integer physicalCfa = characteristics.get(
                        CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT);
                if (physicalCfa == null || physicalCfa < 0 || physicalCfa > 3) {
                    throw new IllegalStateException(
                            "M10R PORT1A requires conventional physical Bayer CFA, got " + physicalCfa);
                }
                parameters.cfaPattern = (byte) (int) physicalCfa;
            }
            int iso = captureResult.get(CaptureResult.SENSOR_SENSITIVITY);
            parameters.FillDynamicParameters(captureResult, null, iso);
            parameters.cameraRotation = cameraRotation;
            Log.d(TAG, "Camera rotation: " + parameters.cameraRotation);
            Log.d(TAG, "activearr:" + characteristics.get(CameraCharacteristics.SENSOR_INFO_ACTIVE_ARRAY_SIZE));
            Log.d(TAG, "precorr:" + characteristics.get(CameraCharacteristics.SENSOR_INFO_PRE_CORRECTION_ACTIVE_ARRAY_SIZE));
            return saveSingleRaw(dngFilePath, image.buffer, parameters);
        }
'''
    if "saveSingleRawM10RPhysicalCfa" not in s:
        s = once(s, old_method, new_method, "ImageSaver physical-CFA DNG writer")
    saver.write_text(s)

    ds = default_saver.read_text()
    old_call = '''                dngSaved = ImageSaver.Util.saveSingleRaw(
                        capture1Dng, capture1Frame, characteristics, captureResult, cameraRotation);
'''
    new_call = '''                dngSaved = ImageSaver.Util.saveSingleRawM10RPhysicalCfa(
                        capture1Dng, capture1Frame, characteristics, captureResult, cameraRotation);
'''
    if "saveSingleRawM10RPhysicalCfa(" not in ds:
        ds = once(ds, old_call, new_call, "M10-R DNG call")
    default_saver.write_text(ds)

    g = gradle.read_text()
    versions = re.findall(r"versionName\s+['\"]([^'\"]+)['\"]", g)
    if len(versions) != 1 or versions[0] != "0.97-m10r2g-yatopology1a":
        raise RuntimeError("PORT1A unexpected RENDER2G versionName: " + repr(versions))
    g = g.replace(versions[0], "0.97-m10r2h-port1a", 1)
    gradle.write_text(g)

    # Fail closed on the core portability invariants.
    r2 = renderer.read_text()
    s2 = saver.read_text()
    ds2 = default_saver.read_text()
    required = [
        'cfaAuthority", "active_physical_Camera2_characteristics"',
        'cfaAwareGreenSelection", true',
        'sourceCalibrationPerPhysicalSensor", true',
        'targetRendererLensIndependent", true',
        'hsmRuntimeDependency", false',
        'perLensTargetLook", false',
        'case 0: return new int[]{0,1,2,3}',
        'case 1: return new int[]{1,0,3,2}',
        'case 2: return new int[]{1,3,0,2}',
        'case 3: return new int[]{3,1,2,0}',
        'COLOR_BayerRG2BGR_EA',
        'COLOR_BayerGR2BGR_EA',
        'COLOR_BayerGB2BGR_EA',
        'COLOR_BayerBG2BGR_EA',
    ]
    for marker in required:
        if marker not in r2:
            raise RuntimeError("PORT1A final renderer invariant missing: " + marker)
    if "saveSingleRawM10RPhysicalCfa" not in s2 or "saveSingleRawM10RPhysicalCfa" not in ds2:
        raise RuntimeError("PORT1A physical CFA DNG route not wired")
    if "(site == 1 || site == 2)" in r2:
        raise RuntimeError("PORT1A stale RGGB-only RAW meter green selection remains")

    cpp_after = hashlib.sha256(cpp.read_bytes()).hexdigest()
    if cpp_after != cpp_before or cpp_after != VALIDATED_CPP_SHA:
        raise RuntimeError("PORT1A changed frozen RENDER2G native pixels")

    proof = {
        "schema": "M10R_RENDER2H_PORT1A_PATCH_V1",
        "baseline": "RENDER2G_YA_TOPOLOGY1A_MFM1B",
        "versionName": "0.97-m10r2h-port1a",
        "validatedNativeCppSha256": VALIDATED_CPP_SHA,
        "nativeRendererChanged": False,
        "render2gColorToneGamutChanged": False,
        "mfm1bFormulaChanged": False,
        "captureExposureChanged": False,
        "jpegQualityChanged": False,
        "singleRaw": True,
        "hdrEnabled": False,
        "cobaltRuntimeDependency": False,
        "hsmRuntimeDependency": False,
        "perLensTargetLook": False,
        "sourceCalibration": "active_physical_Camera2_DNG_dual_illuminant",
        "rendererCfaAuthority": "active_physical_Camera2_characteristics",
        "dngCfaAuthority": "active_physical_Camera2_characteristics",
        "supportedConventionalBayer": ["RGGB", "GRBG", "GBRG", "BGGR"],
        "rawMeterGreenSelection": "semantic_CFA_green_sites",
        "rawMeterMainRggbSampleCoordinatesChanged": False,
        "rawOrigin": [0, 0],
        "rawOriginProven": False,
        "rawOriginPolicy": "do_not_infer_active_array_offset_without_RAW_buffer_coordinate_proof",
        "geometryPolicy": "runtime_frame_width_height_no_lens_name_or_zoom_selector",
        "targetPolicy": "one_shared_M10R_target_renderer_after_physical_source_adapter",
        "deviceValidated": False,
        "productionPromoted": False
    }
    (root / "M10R_RENDER2H_PORT1A_PROVENANCE.json").write_text(
        json.dumps(proof, indent=2) + "\n"
    )
    print(json.dumps(proof, indent=2))

if __name__ == "__main__":
    main()
