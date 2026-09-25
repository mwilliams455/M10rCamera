#!/usr/bin/env python3
"""Apply diagnostic-only M10R-AE1A telemetry to exact validated RENDER1T."""
from pathlib import Path
import hashlib, json, re, sys

BASE_JAVA = "2eb29773aa07ddeec0b4d2db2e28565995138b3855ff3fa4343520057e714a96"
BASE_CPP = "880ce125413bdf1e0f56fbbdcc56591ba91e794f9b5281488f63353dca724637"
HELPER_SHA = "567e80d0eccb6768915afcecb7fc305fe0d99901f536eefb5e8d082e3ff2edcb"

def digest_text(s):
    return hashlib.sha256(s.encode()).hexdigest()

def once(s, a, b):
    n = s.count(a)
    if n != 1:
        raise RuntimeError("Unique anchor required (%d): %s" % (n, a[:140]))
    return s.replace(a, b, 1)

def patch_java(s):
    if digest_text(s) != BASE_JAVA:
        raise RuntimeError("Refusing unknown RENDER1T Java source")

    s = once(s,
        "import android.graphics.Point;\n",
        "import android.graphics.Point;\nimport android.graphics.Rect;\n")
    s = once(s,
        "import android.hardware.camera2.params.LensShadingMap;\n",
        "import android.hardware.camera2.params.LensShadingMap;\nimport android.hardware.camera2.params.MeteringRectangle;\n")
    s = once(s,
        "import android.util.Rational;\n",
        "import android.util.Rational;\nimport android.util.SizeF;\n")

    s = once(s,
        "        long whiteClipCount = 0L;\n",
        """        long whiteClipCount = 0L;

        // AE1A is diagnostic-only. Sample two green CFA sites per 8x8 block
        // before lens shading so the later meter proxy cannot alter RAW pixels.
        double ae1aFullSum = 0.0, ae1a70Sum = 0.0, ae1a45Sum = 0.0, ae1a20Sum = 0.0;
        long ae1aFullCount = 0L, ae1a70Count = 0L, ae1a45Count = 0L, ae1a20Count = 0L;
""")

    s = once(s,
        "                if (unit > 1.0) { unit = 1.0; whiteClipCount++; }\n",
        """                if (unit > 1.0) { unit = 1.0; whiteClipCount++; }

                // One green of each Bayer parity in each 8x8 tile.
                boolean ae1aSample = (site == 1 || site == 2)
                        && ((((y & 7) == 0) && ((x & 7) == 1))
                        || (((y & 7) == 1) && ((x & 7) == 0)));
                if (ae1aSample) {
                    ae1aFullSum += unit;
                    ae1aFullCount++;
                    double nx = (x + 0.5) / (double) width;
                    double ny = (y + 0.5) / (double) height;
                    double dx = Math.abs(nx - 0.5);
                    double dy = Math.abs(ny - 0.5);
                    if (dx <= 0.35 && dy <= 0.35) { ae1a70Sum += unit; ae1a70Count++; }
                    if (dx <= 0.225 && dy <= 0.225) { ae1a45Sum += unit; ae1a45Count++; }
                    if (dx <= 0.10 && dy <= 0.10) { ae1a20Sum += unit; ae1a20Count++; }
                }
""")

    s = once(s,
        '''        d.put("lensShadingHeadroomPolicy",
                "source_white_clamp_then_gainmap_then_scale_to_u16_inverse_scale_after_demosaic");
        return new BayerFrame(out, storageScale, whiteClipCount);
''',
        '''        d.put("lensShadingHeadroomPolicy",
                "source_white_clamp_then_gainmap_then_scale_to_u16_inverse_scale_after_demosaic");

        double ae1aFullMean = ae1aFullCount > 0 ? ae1aFullSum / ae1aFullCount : 0.0;
        double ae1a70Mean = ae1a70Count > 0 ? ae1a70Sum / ae1a70Count : 0.0;
        double ae1a45Mean = ae1a45Count > 0 ? ae1a45Sum / ae1a45Count : 0.0;
        double ae1a20Mean = ae1a20Count > 0 ? ae1a20Sum / ae1a20Count : 0.0;
        double ae1aCenterWeightedMean =
                (200.0 * ae1a70Mean + 300.0 * ae1a45Mean + 500.0 * ae1a20Mean) / 1000.0;
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
        d.put("m10rAe1A_rawMeterProbe", ae1aProbe);
        return new BayerFrame(out, storageScale, whiteClipCount);
''')

    helper_anchor = "    private static SourceModel buildSourceModel("
    helper = r'''    private static double ae1aLog2(double x) {
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

'''
    s = once(s, helper_anchor, helper + helper_anchor)

    s = once(s,
        '            d.put("status", "success");\n',
        '''            try {
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
''')

    return s

def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: fix-m10r-render1u-ae1a-diagnostic.py <PhotonCamera-root>")
    if not __debug__:
        raise RuntimeError("Assertions required")

    root = Path(sys.argv[1]).resolve()
    repo = Path(__file__).resolve().parents[1]
    j = root / "app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java"
    c = root / "app/src/main/cpp/m10rRender.cpp"
    g = root / "app/build.gradle"
    if not j.is_file() or not c.is_file() or not g.is_file():
        raise RuntimeError("Not a reconstructed RENDER1T Photon tree")

    before = j.read_text()
    cpp = c.read_text()
    gradle = g.read_text()
    if digest_text(before) != BASE_JAVA:
        raise RuntimeError("Unexpected RENDER1T Java SHA")
    if digest_text(cpp) != BASE_CPP:
        raise RuntimeError("Unexpected RENDER1T C++ SHA; AE1A must not change pixels")

    helper_src = repo / "android/M10RAeOracle.java"
    helper = helper_src.read_bytes()
    if hashlib.sha256(helper).hexdigest() != HELPER_SHA:
        raise RuntimeError("M10RAeOracle.java hash mismatch")

    after = patch_java(before)
    versions = re.findall(r"versionName\s+['\"]([^'\"]+)['\"]", gradle)
    if len(versions) != 1 or versions[0] != "0.0-render1t-colorrecon1a-tonecal1a-test":
        raise RuntimeError("Unexpected RENDER1T versionName: %r" % versions)
    version = "0.0-render1u-ae1a-diag-render1t-test"

    j.write_text(after)
    g.write_text(gradle.replace(versions[0], version, 1))
    target = j.parent / "M10RAeOracle.java"
    target.write_bytes(helper)

    proof = {
        "schema": "RENDER1U_AE1A_DIAGNOSTIC_PATCH_V1",
        "baseline_render": "RENDER1T_COLORRECON1A_GAMUT1A_TONECAL1A_EDGE0A",
        "baseline_java_sha256": digest_text(before),
        "candidate_java_sha256": digest_text(after),
        "baseline_cpp_sha256": digest_text(cpp),
        "candidate_cpp_sha256": digest_text(cpp),
        "ae_oracle_sha256": hashlib.sha256(helper).hexdigest(),
        "versionName": version,
        "diagnosticOnly": True,
        "realExposureMutated": False,
        "rendererPixelsChanged": False,
        "rawMeterProbeAffectsPixels": False,
        "rawMeterProbe": "green_CFA_pre_lens_shading_two_sites_per_8x8_center_weighted_vs_whole",
        "oracle": "recovered_M10R_production_A_mode_Q8_8",
        "privatePhotoFixtureCommitted": False,
        "deviceValidated": False,
        "productionPromoted": False,
    }
    (root / "M10R_RENDER1U_AE1A_DIAGNOSTIC_PROVENANCE.json").write_text(
        json.dumps(proof, indent=2) + "\n")
    print(json.dumps(proof, indent=2))

if __name__ == "__main__":
    main()
