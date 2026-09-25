#!/usr/bin/env python3
"""Apply active AE1B on top of exact RENDER1U/AE1A reconstruction.

AE1B changes capture exposure only:
- Camera2 preview AE is forced to the existing concentric center-weighted regions.
- Tap-to-focus retains AF tap regions but no longer replaces AE metering.
- Live preview Tv/Sv + known phone Av are converted to Bv.
- The recovered M10-R A-mode allocator, using 35mm-equivalent 1/f, selects still Tv/Sv.
RENDER1T native pixel arithmetic remains byte-identical.
"""
from pathlib import Path
import json,re,sys

def once(s,a,b):
    n=s.count(a)
    if n!=1:
        raise RuntimeError("Unique anchor required (%d): %s" % (n,a[:160]))
    return s.replace(a,b,1)

def patch_iso(s):
    s=once(s,
        "import com.particlesdevs.photoncamera.capture.CaptureController;\n",
        "import com.particlesdevs.photoncamera.capture.CaptureController;\n"
        "import com.particlesdevs.photoncamera.m10r.M10RAe1BPolicy;\n"
        "import com.particlesdevs.photoncamera.m10r.M10RAe1BState;\n")

    anchor="    private static double mpy1 = 1.0;\n"
    helper=r'''    private static ExpoPair m10rAe1BPair(CaptureController captureController) {
        if (captureController == null || PhotonCamera.getSettings().selectedMode != CameraMode.PHOTO) return null;
        if (captureController.getParamController().getCurrentExposureValue() != 0
                || captureController.getParamController().getCurrentISOValue() != 0) return null;

        long previewExposureNs = captureController.mPreviewExposureTime;
        int previewIso = captureController.mPreviewIso;
        CaptureResult previewResult = CaptureController.mPreviewCaptureResult;
        CameraCharacteristics characteristics = CaptureController.mCameraCharacteristics;
        if (previewExposureNs <= 0L || previewIso <= 0 || characteristics == null) return null;

        Float aperture = previewResult != null ? previewResult.get(CaptureResult.LENS_APERTURE) : null;
        if (aperture == null || aperture <= 0.0f) {
            float[] values = characteristics.get(CameraCharacteristics.LENS_INFO_AVAILABLE_APERTURES);
            if (values != null && values.length > 0) aperture = values[0];
        }
        Float focal = previewResult != null ? previewResult.get(CaptureResult.LENS_FOCAL_LENGTH) : null;
        if (focal == null || focal <= 0.0f) {
            float[] values = characteristics.get(CameraCharacteristics.LENS_INFO_AVAILABLE_FOCAL_LENGTHS);
            if (values != null && values.length > 0) focal = values[0];
        }
        SizeF sensor = characteristics.get(CameraCharacteristics.SENSOR_INFO_PHYSICAL_SIZE);
        if (aperture == null || focal == null || sensor == null || sensor.getWidth() <= 0.0f) return null;

        // A Leica 24 mm lens uses 24 mm, not the phone's physical ~9 mm focal length,
        // for the 1/f shutter preference. Width-equivalent focal length is therefore
        // the phone-domain adapter into the recovered Leica focal-length policy.
        double focal35 = focal * (36.0 / sensor.getWidth());
        double exposureCorrection = PhotonCamera.getSettings().exposureCompensation;
        M10RAe1BPolicy.Decision decision = M10RAe1BPolicy.solve(
                previewExposureNs, previewIso, aperture, focal35, exposureCorrection, 100, 50000);
        if (!decision.valid || decision.oracle == null) return null;

        long oracleExposureNs = Math.max(1L, Math.round(decision.oracle.shutterSeconds * ExposureIndex.sec));
        int oracleIso = decision.oracle.iso;
        long appliedExposureNs = oracleExposureNs;
        int appliedIso = oracleIso;
        boolean clamped = false;

        Range<Long> expRange = characteristics.get(CameraCharacteristics.SENSOR_INFO_EXPOSURE_TIME_RANGE);
        Range<Integer> isoRange = characteristics.get(CameraCharacteristics.SENSOR_INFO_SENSITIVITY_RANGE);
        double targetEnergy = (double) oracleExposureNs * oracleIso;

        if (expRange != null) {
            if (appliedExposureNs < expRange.getLower()) {
                appliedExposureNs = expRange.getLower(); clamped = true;
            } else if (appliedExposureNs > expRange.getUpper()) {
                appliedExposureNs = expRange.getUpper(); clamped = true;
            }
        }
        if (appliedExposureNs > 0L) appliedIso = (int)Math.round(targetEnergy / appliedExposureNs);
        if (isoRange != null) {
            if (appliedIso < isoRange.getLower()) { appliedIso = isoRange.getLower(); clamped = true; }
            else if (appliedIso > isoRange.getUpper()) { appliedIso = isoRange.getUpper(); clamped = true; }
        }
        if (appliedIso > 0) appliedExposureNs = Math.max(1L, Math.round(targetEnergy / appliedIso));
        if (expRange != null) {
            if (appliedExposureNs < expRange.getLower()) { appliedExposureNs = expRange.getLower(); clamped = true; }
            else if (appliedExposureNs > expRange.getUpper()) { appliedExposureNs = expRange.getUpper(); clamped = true; }
        }

        long expLow = getEXPLOW(), expHigh = getEXPHIGH();
        int isoLow = getISOLOW(), isoHigh = getISOHIGH(), isoAnalog = getISOAnalog();
        ExpoPair pair = new ExpoPair(appliedExposureNs, expLow, expHigh,
                appliedIso, isoLow, isoHigh, isoAnalog);
        pair.curlayer = ExpoPair.exposureLayer.Normal;
        M10RAe1BState.record(decision, focal, oracleExposureNs, oracleIso,
                appliedExposureNs, appliedIso, clamped);
        Log.d(TAG, "M10R AE1B preview=" + ExposureIndex.sec2string(ExposureIndex.time2sec(previewExposureNs))
                + " ISO" + previewIso + " Bv=" + String.format(Locale.US,"%.3f",decision.previewBvEv)
                + " -> " + ExposureIndex.sec2string(ExposureIndex.time2sec(appliedExposureNs))
                + " ISO" + appliedIso + " TVISO=" + String.format(Locale.US,"%.2f",decision.tvIsoEv));
        return pair;
    }

'''
    s=once(s,anchor,helper+anchor)

    anchor2='''    public static ExpoPair GenerateExpoPair(int step, CaptureController captureController) {
        ExpoPair pair = new ExpoPair(captureController.mPreviewExposureTime, getEXPLOW(), getEXPHIGH(),
                captureController.mPreviewIso, getISOLOW(), getISOHIGH(),getISOAnalog());
'''
    repl2='''    public static ExpoPair GenerateExpoPair(int step, CaptureController captureController) {
        ExpoPair ae1b = m10rAe1BPair(captureController);
        if (ae1b != null) {
            if (step != -1) {
                if (step == 0) pairs.clear();
                if (pairs.size() < patternSize) pairs.add(ae1b);
            }
            return ae1b;
        }
        ExpoPair pair = new ExpoPair(captureController.mPreviewExposureTime, getEXPLOW(), getEXPHIGH(),
                captureController.mPreviewIso, getISOLOW(), getISOHIGH(),getISOAnalog());
'''
    return once(s,anchor2,repl2)

def patch_capture(s):
    s=once(s,
        '''    private void applyAeMeteringRegions(CaptureRequest.Builder builder) {
        int mode = PreferenceKeys.getAeMeteringStd();
        Log.d(TAG, "applyAeMeteringRegions mode:" + mode);
''',
        '''    private void applyAeMeteringRegions(CaptureRequest.Builder builder) {
        int requestedMode = PreferenceKeys.getAeMeteringStd();
        // M10R AE1B phone adapter: the Leica meter input is center-weighted.
        // Keep this spatial policy separate from the recovered Bv -> Tv/Sv allocator.
        int mode = PhotonCamera.getSettings().selectedMode == CameraMode.PHOTO ? 0 : requestedMode;
        Log.d(TAG, "applyAeMeteringRegions mode:" + mode + " requested:" + requestedMode);
''')
    s=once(s,
        '''            if (mTouchFocus != null && mTouchFocus.isTouchFocus) {
                captureBuilder.set(CaptureRequest.CONTROL_AE_REGIONS, mPreviewRequestBuilder.get(CaptureRequest.CONTROL_AE_REGIONS));
                captureBuilder.set(CaptureRequest.CONTROL_AF_REGIONS, mPreviewRequestBuilder.get(CaptureRequest.CONTROL_AF_REGIONS));
            } else {
                applyAeMeteringRegions(captureBuilder);
            }
''',
        '''            if (mTouchFocus != null && mTouchFocus.isTouchFocus) {
                // AE1B: a focus tap moves AF only. Still AE remains M10-R center-weighted.
                applyAeMeteringRegions(captureBuilder);
                captureBuilder.set(CaptureRequest.CONTROL_AF_REGIONS, mPreviewRequestBuilder.get(CaptureRequest.CONTROL_AF_REGIONS));
            } else {
                applyAeMeteringRegions(captureBuilder);
            }
''')
    return s

def patch_touch(s):
    old='''            activeAfMode = afMode;
            isTouchFocus = true;
            // The tap writes only the AF and AE region arrays; AWB stays untouched.
            boolean afRegionsWritten = false, aeRegionsWritten = false;
            if (maxRegions(characteristics, CameraCharacteristics.CONTROL_MAX_REGIONS_AF) > 0) {
                builder.set(CaptureRequest.CONTROL_AF_REGIONS, regions);
                afRegionsWritten = true;
            }
            if (maxRegions(characteristics, CameraCharacteristics.CONTROL_MAX_REGIONS_AE) > 0) {
                builder.set(CaptureRequest.CONTROL_AE_REGIONS, regions);
                aeRegionsWritten = true;
            }
            armedRegionsTag = (afRegionsWritten || aeRegionsWritten) ? regions : null;
'''
    new='''            activeAfMode = afMode;
            isTouchFocus = true;
            // M10R AE1B: a tap remains an AF operation. Do not replace the
            // continuously center-weighted preview AE region with the small tap box.
            boolean afRegionsWritten = false;
            if (maxRegions(characteristics, CameraCharacteristics.CONTROL_MAX_REGIONS_AF) > 0) {
                builder.set(CaptureRequest.CONTROL_AF_REGIONS, regions);
                afRegionsWritten = true;
            }
            if (maxRegions(characteristics, CameraCharacteristics.CONTROL_MAX_REGIONS_AE) > 0
                    && captureController.mPreviewMeteringAE != null) {
                builder.set(CaptureRequest.CONTROL_AE_REGIONS, captureController.mPreviewMeteringAE);
            }
            armedRegionsTag = afRegionsWritten ? regions : null;
'''
    s=once(s,old,new)
    s=s.replace("Fixed-focus lens: meter on the tapped region but never trigger the lens.",
                "Fixed-focus lens: keep center-weighted AE but never trigger the lens.")
    return s

def patch_renderer(s):
    helper_anchor="    private static SourceModel buildSourceModel("
    helper=r'''    private static void appendAe1BState(JSONObject d) throws Exception {
        M10RAe1BState.Snapshot s = M10RAe1BState.snapshot();
        JSONObject o = new JSONObject()
                .put("enabled", true)
                .put("activeCapture", true)
                .put("rendererPixelsChanged", false)
                .put("centerWeightedPreviewMeterForced", true)
                .put("tapChangesAeMetering", false)
                .put("meterSource", "Camera2_preview_AE_center_weighted_phone_proxy")
                .put("allocator", "recovered_M10R_production_A_mode_Q8_8")
                .put("autoIsoPolicy", "1_over_f_35mm_width_equivalent_half_stop")
                .put("svMinIso", 100).put("svMaxIso", 50000)
                .put("stateValid", s.valid)
                .put("stateGeneration", s.generation)
                .put("sensorClampApplied", s.sensorClampApplied);
        if (s.valid) {
            o.put("previewExposureTimeNs", s.previewExposureNs)
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

'''
    s=once(s,helper_anchor,helper+helper_anchor)
    old='''            try {
                appendAe1ADiagnostics(d, characteristics, captureResult, captureRequest);
            } catch (Throwable ae1aError) {
                d.put("m10rAe1A", new JSONObject()
                        .put("enabled", true)
                        .put("diagnosticOnly", true)
                        .put("realExposureMutated", false)
                        .put("status", "diagnostic_failed")
                        .put("error", ae1aError.toString()));
            }
            d.put("status", "success");
'''
    new='''            try {
                appendAe1ADiagnostics(d, characteristics, captureResult, captureRequest);
            } catch (Throwable ae1aError) {
                d.put("m10rAe1A", new JSONObject()
                        .put("enabled", true)
                        .put("diagnosticOnly", true)
                        .put("realExposureMutated", false)
                        .put("status", "diagnostic_failed")
                        .put("error", ae1aError.toString()));
            }
            try {
                appendAe1BState(d);
            } catch (Throwable ae1bError) {
                d.put("m10rAe1B", new JSONObject()
                        .put("enabled", true).put("activeCapture", true)
                        .put("status", "telemetry_failed").put("error", ae1bError.toString()));
            }
            d.put("status", "success");
'''
    return once(s,old,new)

def main():
    if len(sys.argv)!=2:
        raise SystemExit("usage: fix-m10r-render1v-ae1b-live.py <PhotonCamera-root>")
    root=Path(sys.argv[1]).resolve()
    repo=Path(__file__).resolve().parents[1]
    iso=root/"app/src/main/java/com/particlesdevs/photoncamera/processing/parameters/IsoExpoSelector.java"
    cap=root/"app/src/main/java/com/particlesdevs/photoncamera/capture/CaptureController.java"
    touch=root/"app/src/main/java/com/particlesdevs/photoncamera/control/TouchFocus.java"
    renderer=root/"app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java"
    cpp=root/"app/src/main/cpp/m10rRender.cpp"
    gradle=root/"app/build.gradle"
    for p in [iso,cap,touch,renderer,cpp,gradle]:
        if not p.is_file(): raise RuntimeError("missing "+str(p))

    # AE1B is allowed to alter capture Java only; native RENDER1T stays exact.
    cpp_before=cpp.read_bytes()
    iso.write_text(patch_iso(iso.read_text()))
    cap.write_text(patch_capture(cap.read_text()))
    touch.write_text(patch_touch(touch.read_text()))
    renderer.write_text(patch_renderer(renderer.read_text()))

    for name in ["M10RAe1BPolicy.java","M10RAe1BState.java"]:
        src=repo/"android"/name
        (renderer.parent/name).write_bytes(src.read_bytes())

    g=gradle.read_text()
    versions=re.findall(r"versionName\s+['\"]([^'\"]+)['\"]",g)
    if len(versions)!=1 or "render1u-ae1a-diag-render1t-colorrecon1a-tonecal1a-" not in versions[0]:
        raise RuntimeError("unexpected AE1A versionName: %r" % versions)
    version=versions[0].replace(
        "render1u-ae1a-diag-render1t-colorrecon1a-tonecal1a-",
        "render1v-ae1b-live-render1t-colorrecon1a-tonecal1a-",1)
    gradle.write_text(g.replace(versions[0],version,1))

    if cpp.read_bytes()!=cpp_before:
        raise RuntimeError("AE1B changed native renderer")
    proof={
        "schema":"RENDER1V_AE1B_LIVE_PATCH_V1",
        "baseline":"RENDER1U_AE1A_DIAGNOSTIC_on_RENDER1T",
        "versionName":version,
        "realExposureMutated":True,
        "rendererNativeChanged":False,
        "meterSource":"Camera2_preview_AE_forced_center_weighted",
        "tapAeCouplingDisabled":True,
        "bvAdapter":"preview_Tv_plus_known_Av_minus_preview_Sv",
        "allocator":"recovered_M10R_production_A_mode_Q8_8",
        "autoIsoPolicy":"1_over_f_using_35mm_width_equivalent_focal_length_half_stop",
        "svMinIso":100,"svMaxIso":50000,
        "fixedEvBoost":False,
        "postCaptureRawDeltaAppliedToExposure":False,
        "hdrEnabled":False,
        "singleRaw":True,
        "deviceValidated":False,
        "productionPromoted":False
    }
    (root/"M10R_RENDER1V_AE1B_LIVE_PROVENANCE.json").write_text(json.dumps(proof,indent=2)+"\n")
    print(json.dumps(proof,indent=2))

if __name__=="__main__":
    main()
