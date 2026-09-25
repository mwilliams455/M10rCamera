#!/usr/bin/env python3
"""MFM1A active bounded multi-field assist on top of METER1B/GRIDMAP1A.

Photographic change vs METER1B:
- the validated live 22x16 grid feeds a bounded M10-R architecture proxy;
- its signed correction (-0.50..+0.75 EV, 0.08 EV deadband) is added to user EV
  before the recovered M10-R A-mode Tv/Sv allocator runs.

The exact recovered Integral mask and 4x6/24-region topology are used.
Numerical parity with Leica's unresolved 13-feature CA9 generator is NOT claimed.
RENDER1T native rendering stays byte-identical.
"""
from pathlib import Path
import hashlib,json,re,sys

CPP_SHA="880ce125413bdf1e0f56fbbdcc56591ba91e794f9b5281488f63353dca724637"

def once(s,a,b):
    n=s.count(a)
    if n!=1:
        raise RuntimeError("Unique anchor required (%d): %s" % (n,a[:180]))
    return s.replace(a,b,1)

def patch_iso(s):
    s=once(s,
        "import com.particlesdevs.photoncamera.m10r.M10RAe1BState;\n",
        "import com.particlesdevs.photoncamera.m10r.M10RAe1BState;\n"
        "import com.particlesdevs.photoncamera.m10r.M10RLiveMeterState;\n"
        "import com.particlesdevs.photoncamera.m10r.M10RMfm1A;\n"
        "import com.particlesdevs.photoncamera.m10r.M10RMfm1AState;\n")

    s=once(s,
        """        final long oracleExposureNs;
        final int oracleIso;
        final boolean sensorClampApplied;
        M10RAe1BSelection(ExpoPair pair, M10RAe1BPolicy.Decision decision, double focalLengthMm,
                          long oracleExposureNs, int oracleIso, boolean sensorClampApplied) {
            this.pair=pair; this.decision=decision; this.focalLengthMm=focalLengthMm;
            this.oracleExposureNs=oracleExposureNs; this.oracleIso=oracleIso;
            this.sensorClampApplied=sensorClampApplied;
        }
""",
        """        final long oracleExposureNs;
        final int oracleIso;
        final boolean sensorClampApplied;
        final M10RMfm1A.Decision mfmDecision;
        final long liveGridGeneration;
        final double userExposureCorrectionEv;
        final double mfmExposureCorrectionEv;
        final double totalExposureCorrectionEv;
        M10RAe1BSelection(ExpoPair pair, M10RAe1BPolicy.Decision decision, double focalLengthMm,
                          long oracleExposureNs, int oracleIso, boolean sensorClampApplied,
                          M10RMfm1A.Decision mfmDecision, long liveGridGeneration,
                          double userExposureCorrectionEv, double mfmExposureCorrectionEv,
                          double totalExposureCorrectionEv) {
            this.pair=pair; this.decision=decision; this.focalLengthMm=focalLengthMm;
            this.oracleExposureNs=oracleExposureNs; this.oracleIso=oracleIso;
            this.sensorClampApplied=sensorClampApplied;
            this.mfmDecision=mfmDecision; this.liveGridGeneration=liveGridGeneration;
            this.userExposureCorrectionEv=userExposureCorrectionEv;
            this.mfmExposureCorrectionEv=mfmExposureCorrectionEv;
            this.totalExposureCorrectionEv=totalExposureCorrectionEv;
        }
""")

    s=once(s,
        """    public static void prepareM10rAe1BCapture(CaptureController captureController) {
        m10rAe1BPendingSelection = m10rAe1BSelect(captureController);
    }

    private static M10RAe1BSelection m10rAe1BSelect(CaptureController captureController) {
        if (captureController == null || PhotonCamera.getSettings().selectedMode != CameraMode.PHOTO) return null;
""",
        """    public static void prepareM10rAe1BCapture(CaptureController captureController) {
        m10rAe1BPendingSelection = m10rAe1BSelect(
                captureController, M10RLiveMeterState.frozenSnapshot());
    }

    private static M10RAe1BSelection m10rAe1BSelect(CaptureController captureController) {
        return m10rAe1BSelect(captureController, M10RLiveMeterState.snapshot());
    }

    private static M10RAe1BSelection m10rAe1BSelect(
            CaptureController captureController, M10RLiveMeterState.Snapshot meterSnapshot) {
        if (captureController == null || PhotonCamera.getSettings().selectedMode != CameraMode.PHOTO) return null;
""")

    s=once(s,
        """        double focal35 = focal * (36.0 / sensor.getWidth());
        double exposureCorrection = PhotonCamera.getSettings().exposureCompensation;
        M10RAe1BPolicy.Decision decision = M10RAe1BPolicy.solve(
                previewExposureNs, previewIso, aperture, focal35, exposureCorrection, 100, 50000);
""",
        """        double focal35 = focal * (36.0 / sensor.getWidth());
        double userExposureCorrection = PhotonCamera.getSettings().exposureCompensation;

        M10RMfm1A.Decision mfmDecision = meterSnapshot != null && meterSnapshot.valid
                ? M10RMfm1A.evaluate(meterSnapshot.linearGrid)
                : M10RMfm1A.evaluate(null);
        double mfmExposureCorrection = mfmDecision.valid && mfmDecision.wouldApply
                ? mfmDecision.recommendedEv : 0.0;
        double exposureCorrection = userExposureCorrection + mfmExposureCorrection;

        M10RAe1BPolicy.Decision decision = M10RAe1BPolicy.solve(
                previewExposureNs, previewIso, aperture, focal35, exposureCorrection, 100, 50000);
""")

    s=once(s,
        """        return new M10RAe1BSelection(pair, decision, focal, oracleExposureNs, oracleIso, clamped);
""",
        """        long liveGridGeneration = meterSnapshot != null ? meterSnapshot.generation : 0L;
        return new M10RAe1BSelection(pair, decision, focal, oracleExposureNs, oracleIso, clamped,
                mfmDecision, liveGridGeneration, userExposureCorrection,
                mfmExposureCorrection, exposureCorrection);
""")

    s=once(s,
        """            M10RAe1BState.record(frozen.decision, frozen.focalLengthMm,
                    frozen.oracleExposureNs, frozen.oracleIso,
                    frozen.pair.exposure, frozen.pair.iso, frozen.sensorClampApplied);
            Log.d(TAG, "M10R AE1B FREEZE1 bound still request generation to "
""",
        """            M10RAe1BState.record(frozen.decision, frozen.focalLengthMm,
                    frozen.oracleExposureNs, frozen.oracleIso,
                    frozen.pair.exposure, frozen.pair.iso, frozen.sensorClampApplied);
            M10RMfm1AState.record(frozen.liveGridGeneration,
                    frozen.userExposureCorrectionEv, frozen.mfmExposureCorrectionEv,
                    frozen.totalExposureCorrectionEv, frozen.mfmDecision);
            Log.d(TAG, "M10R MFM1A correction="
                    + String.format(Locale.US, "%.3f", frozen.mfmExposureCorrectionEv)
                    + " totalEV=" + String.format(Locale.US, "%.3f", frozen.totalExposureCorrectionEv));
            Log.d(TAG, "M10R AE1B FREEZE1 bound still request generation to "
""")
    return s

def patch_renderer(s):
    anchor="    private static void appendMeter1A(JSONObject d) throws Exception {\n"
    helper=r'''    private static M10RMfm1A.Decision mfm1aRawCounterfactual(JSONObject d) {
        try {
            JSONObject raw = d.optJSONObject("m10rAe1A_rawMeterProbe");
            JSONArray rows = raw != null ? raw.optJSONArray("leicaRawGrid16x22") : null;
            if (rows == null || rows.length() != M10RMfm1A.GRID_R) return M10RMfm1A.evaluate(null);
            double[] grid = new double[M10RMfm1A.GRID_R * M10RMfm1A.GRID_C];
            for (int r = 0; r < M10RMfm1A.GRID_R; r++) {
                JSONArray row = rows.optJSONArray(r);
                if (row == null || row.length() != M10RMfm1A.GRID_C) return M10RMfm1A.evaluate(null);
                for (int c = 0; c < M10RMfm1A.GRID_C; c++) {
                    grid[r * M10RMfm1A.GRID_C + c] = row.optDouble(c, Double.NaN);
                }
            }
            return M10RMfm1A.evaluate(grid);
        } catch (Throwable ignored) {
            return M10RMfm1A.evaluate(null);
        }
    }

    private static JSONObject mfm1aDecisionJson(M10RMfm1A.Decision x) throws Exception {
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

    private static void appendMfm1A(JSONObject d) throws Exception {
        M10RMfm1AState.Snapshot s = M10RMfm1AState.snapshot();
        M10RMfm1A.Decision raw = mfm1aRawCounterfactual(d);
        JSONObject o = new JSONObject()
                .put("enabled", true)
                .put("activeCapture", true)
                .put("architectureProxy", true)
                .put("exactCa9ThirteenFeatureParityClaimed", false)
                .put("recoveredIntegralMask", "exact_0x4001349c_sum14160")
                .put("recoveredRegionalTopology", "4x6_24_regions")
                .put("boundsOrigin", "research_safety_not_M10R_firmware_constant")
                .put("positiveLimitEv", M10RMfm1A.MAX_POSITIVE_EV)
                .put("negativeLimitEv", -M10RMfm1A.MAX_NEGATIVE_EV)
                .put("deadBandEv", M10RMfm1A.DEAD_BAND_EV)
                .put("stateValid", s.valid)
                .put("stateGeneration", s.generation)
                .put("liveGridGeneration", s.liveGridGeneration)
                .put("userExposureCorrectionEv", s.userExposureCorrectionEv)
                .put("mfmExposureCorrectionEv", s.mfmExposureCorrectionEv)
                .put("totalExposureCorrectionEv", s.totalExposureCorrectionEv)
                .put("liveDecision", mfm1aDecisionJson(s.decision))
                .put("rawCounterfactualDecision", mfm1aDecisionJson(raw));
        if (s.decision != null && s.decision.valid && raw != null && raw.valid) {
            o.put("liveMinusRawRecommendedEv", s.decision.recommendedEv - raw.recommendedEv)
                    .put("liveRawDecisionSignAgreement",
                            Math.signum(s.decision.recommendedEv) == Math.signum(raw.recommendedEv))
                    .put("liveRawWouldApplyAgreement", s.decision.wouldApply == raw.wouldApply);
        }
        d.put("m10rMfm1A", o);
    }

'''
    s=once(s,anchor,helper+anchor)

    s=once(s,
        """            try {
                appendMeter1A(d);
            } catch (Throwable meter1aError) {
                d.put("m10rMeter1A", new JSONObject()
                        .put("enabled", true).put("diagnosticOnly", true)
                        .put("status", "telemetry_failed").put("error", meter1aError.toString()));
            }
            d.put("status", "success");
""",
        """            try {
                appendMeter1A(d);
            } catch (Throwable meter1aError) {
                d.put("m10rMeter1A", new JSONObject()
                        .put("enabled", true).put("diagnosticOnly", true)
                        .put("status", "telemetry_failed").put("error", meter1aError.toString()));
            }
            try {
                appendMfm1A(d);
            } catch (Throwable mfm1aError) {
                d.put("m10rMfm1A", new JSONObject()
                        .put("enabled", true).put("activeCapture", true)
                        .put("status", "telemetry_failed").put("error", mfm1aError.toString()));
            }
            d.put("status", "success");
""")
    return s

def main():
    if len(sys.argv)!=2:
        raise SystemExit("usage: fix-m10r-render1z-mfm1a-live.py <PhotonCamera-root>")
    root=Path(sys.argv[1]).resolve()
    repo=Path(__file__).resolve().parents[1]
    iso=root/"app/src/main/java/com/particlesdevs/photoncamera/processing/parameters/IsoExpoSelector.java"
    renderer=root/"app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java"
    cpp=root/"app/src/main/cpp/m10rRender.cpp"
    gradle=root/"app/build.gradle"
    for p in [iso,renderer,cpp,gradle]:
        if not p.is_file(): raise RuntimeError("missing "+str(p))
    if hashlib.sha256(cpp.read_bytes()).hexdigest()!=CPP_SHA:
        raise RuntimeError("MFM1A refuses changed native renderer")

    iso.write_text(patch_iso(iso.read_text()))
    renderer.write_text(patch_renderer(renderer.read_text()))
    for name in ["M10RMfm1A.java","M10RMfm1AState.java"]:
        (renderer.parent/name).write_bytes((repo/"android"/name).read_bytes())

    g=gradle.read_text()
    versions=re.findall(r"versionName\s+['\"]([^'\"]+)['\"]",g)
    if len(versions)!=1 or "render1y-meter1b-gridmap1a-ae1b-freeze1-render1t-colorrecon1a-tonecal1a-" not in versions[0]:
        raise RuntimeError("unexpected METER1B versionName: %r" % versions)
    version=versions[0].replace(
        "render1y-meter1b-gridmap1a-ae1b-freeze1-render1t-colorrecon1a-tonecal1a-",
        "render1z-mfm1a-live-meter1b-gridmap1a-ae1b-freeze1-render1t-colorrecon1a-tonecal1a-",1)
    gradle.write_text(g.replace(versions[0],version,1))

    if hashlib.sha256(cpp.read_bytes()).hexdigest()!=CPP_SHA:
        raise RuntimeError("MFM1A changed native renderer")
    proof={
        "schema":"RENDER1Z_MFM1A_LIVE_PATCH_V1",
        "baseline":"RENDER1Y_METER1B_GRIDMAP1A_on_AE1B_FREEZE1_on_RENDER1T",
        "versionName":version,
        "activeCaptureCorrection":True,
        "sourceGrid":"validated_live_22x16_GRIDMAP1A_linear_preview",
        "integralMask":"exact_recovered_0x4001349c",
        "regionalTopology":"recovered_4x6_24_regions",
        "exactCa9ThirteenFeatureParityClaimed":False,
        "positiveLimitEv":0.75,
        "negativeLimitEv":-0.50,
        "deadBandEv":0.08,
        "fixedGlobalEvBoost":False,
        "rawCounterfactualValidationIncluded":True,
        "rendererNativeChanged":False,
        "hdrEnabled":False,
        "singleRaw":True,
        "privatePhotoFixtureCommitted":False,
        "deviceValidated":False,
        "productionPromoted":False
    }
    (root/"M10R_RENDER1Z_MFM1A_LIVE_PROVENANCE.json").write_text(json.dumps(proof,indent=2)+"\n")
    print(json.dumps(proof,indent=2))

if __name__=="__main__":
    main()
