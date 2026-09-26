#!/usr/bin/env python3
"""RENDER2I PORT1A + MFM1C on top of frozen RENDER2G YA_TOPOLOGY1A.

PORT1A:
- keeps the validated RENDER2G photographic renderer byte-for-byte native-identical;
- makes the active physical Camera2 CFA authoritative for M10-R DNG metadata;
- records source geometry/CFA portability diagnostics;
- preserves active physical Camera2 dual-illuminant source calibration;
- forbids per-lens Leica/HSM/Cobalt photographic selection.

MFM1C:
- keeps the recovered MFM1B decision topology and thresholds;
- changes only the live meter input from inverse-sRGB Rec.709 Y to a monotonic
  RAW-proxy Y = pow(Y, 1.90);
- RAW counterfactual remains direct normalized RAW green and is not transformed.

The 1.90 exponent is an empirical phone-domain preview de-compression, not a
recovered Leica firmware constant.
"""
from pathlib import Path
import hashlib, json, re, sys

CPP_SHA = "3f7b696cdf33e29348d7c0532f658c11819f9b8e54772b55753e357fb6018985"

def once(s, a, b, label):
    n = s.count(a)
    if n != 1:
        raise RuntimeError("%s anchor count=%d" % (label, n))
    return s.replace(a, b, 1)

def patch_iso(s):
    s = once(
        s,
        "import com.particlesdevs.photoncamera.m10r.M10RMfm1B;\n",
        "import com.particlesdevs.photoncamera.m10r.M10RMfm1B;\n"
        "import com.particlesdevs.photoncamera.m10r.M10RMfm1CProxy;\n",
        "MFM1C import",
    )
    old = """        M10RMfm1B.Decision mfmDecision = meterSnapshot != null && meterSnapshot.valid
                ? M10RMfm1B.evaluate(meterSnapshot.linearGrid)
                : M10RMfm1B.evaluate(null);
"""
    new = """        // MFM1C: preserve the recovered MFM1B spatial decision, but feed it a
        // monotonic preview->RAW proxy instead of the tone-compressed GL grid.
        double[] mfm1cRawProxyGrid = meterSnapshot != null && meterSnapshot.valid
                ? M10RMfm1CProxy.transform(meterSnapshot.linearGrid) : null;
        M10RMfm1B.Decision mfmDecision = M10RMfm1B.evaluate(mfm1cRawProxyGrid);
"""
    s = once(s, old, new, "MFM1C live-grid evaluation")
    return s

def patch_renderer(s):
    # PORT1A diagnostics at the physical-Camera2 CFA authority point.
    cfa_anchor = '''        d.put("cfaPatternCode", cfa);
        d.put("cfaPatternName", cfaName(cfa));
        d.put("fourBayerPatternsSupported", true);
'''
    cfa_block = cfa_anchor + '''        // PORT1A: renderer authority is the active physical Camera2 sensor.
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
'''
    s = once(s, cfa_anchor, cfa_block, "PORT1A CFA diagnostics")

    old_look = 'd.put("renderLook", "RENDER2G_YATOPOLOGY1A_GAMUT1A_TONECAL1A_MFM1B_EDGE0A");'
    new_look = 'd.put("renderLook", "RENDER2G_YATOPOLOGY1A_GAMUT1A_TONECAL1A_MFM1C_EDGE0A");'
    s = once(s, old_look, new_look, "MFM1C renderLook")

    mfm_anchor = '''                .put("positiveGain", M10RMfm1B.POSITIVE_GAIN)
                .put("positiveGeometrySemantic",
'''
    mfm_block = '''                .put("positiveGain", M10RMfm1B.POSITIVE_GAIN)
                .put("meterRevision", "MFM1C_PREVIEW_DECOMPRESS1A")
                .put("liveInputBeforeProxy",
                        "GL_SurfaceTexture_RGBA8_inverse_sRGB_per_channel_Rec709_luma")
                .put("liveRawProxyTransform", "pow_clamp01_Y_1p90")
                .put("liveRawProxyExponent", M10RMfm1CProxy.EXPONENT)
                .put("liveRawProxyMonotonic", true)
                .put("rawCounterfactualProxyApplied", false)
                .put("rawCounterfactualDomain", "normalized_RAW_green_pre_lens_shading")
                .put("rendererPixelsChangedByMfm1C", false)
                .put("positiveGeometrySemantic",
'''
    s = once(s, mfm_anchor, mfm_block, "MFM1C diagnostics")

    s = once(s, 'd.put("m10rMfm1B", o);', 'd.put("m10rMfm1C", o);',
             "MFM1C diagnostic key")
    return s

def patch_image_saver(s):
    old = '''        public static boolean saveSingleRaw(Path dngFilePath,
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
    new = '''        public static boolean saveSingleRaw(Path dngFilePath,
                                            ImageFrame image,
                                            CameraCharacteristics characteristics,
                                            CaptureResult captureResult,
                                            int cameraRotation) {
            return saveSingleRawInternal(dngFilePath, image, characteristics, captureResult,
                    cameraRotation, false);
        }

        /**
         * M10R PORT1A DNG path. The active physical Camera2 CFA is authoritative
         * for the DNG mosaic tag, matching the source lattice consumed by the
         * M10-R renderer. Ordinary Photon saveSingleRaw behavior stays unchanged.
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
                if (physicalCfa != null && physicalCfa >= 0 && physicalCfa <= 3) {
                    parameters.cfaPattern = (byte) (int) physicalCfa;
                }
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
    return once(s, old, new, "PORT1A ImageSaver physical CFA")

def patch_default_saver(s):
    old = '''                dngSaved = ImageSaver.Util.saveSingleRaw(
                        capture1Dng, capture1Frame, characteristics, captureResult, cameraRotation);
'''
    new = '''                dngSaved = ImageSaver.Util.saveSingleRawM10RPhysicalCfa(
                        capture1Dng, capture1Frame, characteristics, captureResult, cameraRotation);
'''
    s = once(s, old, new, "PORT1A DNG call")

    anchor = '''                    try { capture1b.diagnostics.put("dngSaved", dngSaved); } catch (Throwable ignored) {}
                    M10RNativeRenderer.persistDiagnostics(capture1Dng, capture1b.diagnostics);
'''
    repl = '''                    try {
                        capture1b.diagnostics.put("dngSaved", dngSaved);
                        capture1b.diagnostics.put("dngCfaAuthority",
                                "physical_camera2_characteristics");
                    } catch (Throwable ignored) {}
                    M10RNativeRenderer.persistDiagnostics(capture1Dng, capture1b.diagnostics);
'''
    s = once(s, anchor, repl, "PORT1A DNG diagnostics")
    return s

def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: fix-m10r-render2i-port1a-mfm1c.py <PhotonCamera-root>")
    root = Path(sys.argv[1]).resolve()
    repo = Path(__file__).resolve().parents[1]

    iso = root / "app/src/main/java/com/particlesdevs/photoncamera/processing/parameters/IsoExpoSelector.java"
    renderer = root / "app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java"
    saver = root / "app/src/main/java/com/particlesdevs/photoncamera/processing/DefaultSaver.java"
    image_saver = root / "app/src/main/java/com/particlesdevs/photoncamera/processing/ImageSaver.java"
    cpp = root / "app/src/main/cpp/m10rRender.cpp"
    gradle = root / "app/build.gradle"
    for p in (iso, renderer, saver, image_saver, cpp, gradle):
        if not p.is_file():
            raise RuntimeError("missing " + str(p))

    if hashlib.sha256(cpp.read_bytes()).hexdigest() != CPP_SHA:
        raise RuntimeError("PORT1A/MFM1C refuses changed RENDER2G native renderer")

    iso.write_text(patch_iso(iso.read_text()))
    renderer.write_text(patch_renderer(renderer.read_text()))
    image_saver.write_text(patch_image_saver(image_saver.read_text()))
    saver.write_text(patch_default_saver(saver.read_text()))
    (renderer.parent / "M10RMfm1CProxy.java").write_bytes(
        (repo / "android" / "M10RMfm1CProxy.java").read_bytes())

    g = gradle.read_text()
    versions = re.findall(r'versionName\s+[\'"]([^\'"]+)[\'"]', g)
    if len(versions) != 1 or versions[0] != "0.97-m10r2g-yatopology1a":
        raise RuntimeError("unexpected RENDER2G versionName: %r" % versions)
    version = "0.97-m10r2i-port1a-mfm1c"
    gradle.write_text(g.replace(versions[0], version, 1))

    # Hard invariants.
    if hashlib.sha256(cpp.read_bytes()).hexdigest() != CPP_SHA:
        raise RuntimeError("PORT1A/MFM1C changed validated RENDER2G native renderer")

    rr = renderer.read_text()
    ii = iso.read_text()
    ss = saver.read_text()
    ims = image_saver.read_text()
    required_renderer = [
        'cobaltRuntimeDependency", false',
        'fourBayerPatternsSupported", true',
        'COLOR_BayerRG2BGR_EA',
        'COLOR_BayerGR2BGR_EA',
        'COLOR_BayerGB2BGR_EA',
        'COLOR_BayerBG2BGR_EA',
        'case 0: return new int[]{0,1,2,3}',
        'case 1: return new int[]{1,0,3,2}',
        'case 2: return new int[]{1,3,0,2}',
        'case 3: return new int[]{3,1,2,0}',
        'cfaAuthority", "physical_camera2_characteristics"',
        'perLensHsmApplied", false',
        'cobaltHsmApplied", false',
        'targetRendererLensIndependent", true',
        'RENDER2G_YATOPOLOGY1A_GAMUT1A_TONECAL1A_MFM1C_EDGE0A',
        'liveRawProxyExponent", M10RMfm1CProxy.EXPONENT',
        'd.put("m10rMfm1C", o);',
    ]
    for needle in required_renderer:
        if needle not in rr:
            raise RuntimeError("PORT1A/MFM1C renderer invariant missing: " + needle)
    for needle in [
        'M10RMfm1CProxy.transform(meterSnapshot.linearGrid)',
        'M10RMfm1B.evaluate(mfm1cRawProxyGrid)',
    ]:
        if needle not in ii:
            raise RuntimeError("MFM1C ISO invariant missing: " + needle)
    if 'saveSingleRawM10RPhysicalCfa(' not in ims or 'parameters.cfaPattern = (byte) (int) physicalCfa;' not in ims:
        raise RuntimeError("PORT1A ImageSaver physical CFA path missing")
    if 'saveSingleRawM10RPhysicalCfa(' not in ss:
        raise RuntimeError("PORT1A DefaultSaver does not use physical-CFA DNG path")

    # No per-lens target lookup is allowed in the renderer.
    for forbidden in ['m9_r35_calibration', 'Cobalt', 'HueSatMap']:
        if forbidden in rr:
            raise RuntimeError("PORT1A forbidden target dependency in renderer: " + forbidden)

    proof = {
        "schema": "RENDER2I_PORT1A_MFM1C_PATCH_V1",
        "baseline": "RENDER2G_YATOPOLOGY1A_MFM1B",
        "versionName": version,
        "rendererNativeSha256": CPP_SHA,
        "rendererNativeChanged": False,
        "render2gPixelsChanged": False,
        "portabilityRevision": "M10R_PORT1A",
        "physicalCamera2CfaAuthority": True,
        "dngPhysicalCfaAuthority": True,
        "supportedConventionalBayer": ["RGGB", "GRBG", "GBRG", "BGGR"],
        "rawDimensionsDynamic": True,
        "rawOriginAssumption": "origin0_explicit_unproven",
        "activePhysicalCamera2SourceCalibration": True,
        "perLensPhotographicTuningApplied": False,
        "perLensHsmApplied": False,
        "cobaltRuntimeDependency": False,
        "cobaltHsmApplied": False,
        "mfmRevision": "MFM1C_PREVIEW_DECOMPRESS1A",
        "mfmDecisionCore": "MFM1B_unchanged",
        "liveRawProxyTransform": "pow(clamp01(inverse_sRGB_Rec709_Y),1.90)",
        "liveRawProxyExponent": 1.90,
        "rawCounterfactualTransformApplied": False,
        "captureExposureMayChangeFromMfm1C": True,
        "fixedGlobalEvBoost": False,
        "hdrEnabled": False,
        "singleRaw": True,
        "privatePhotoFixtureCommitted": False,
        "privateValidationDataCommitted": False,
        "deviceValidated": False,
        "allLensValidated": False,
        "productionPromoted": False,
    }
    (root / "M10R_RENDER2I_PORT1A_MFM1C_PROVENANCE.json").write_text(
        json.dumps(proof, indent=2) + "\n")
    print(json.dumps(proof, indent=2))

if __name__ == "__main__":
    main()
