#!/usr/bin/env python3
"""AE1B FREEZE1: bind one exposure decision to the still request and add exact Leica Integral diagnostics.

Applied after RENDER1T -> AE1A -> AE1B.
Photographic changes vs AE1B:
- freeze one AE1B selection at captureStillPicture entry and use that exact selection in setExpo;
- no meter/tone/render constants changed.

Diagnostics:
- M10R Integral 16x22 mask evaluated on sampled pre-lens-shading RAW green sites;
- sidecar verifies the saved CaptureRequest exposure/ISO match the frozen AE1B state.
"""
from pathlib import Path
import json,re,sys,hashlib

RENDER_CPP_SHA="880ce125413bdf1e0f56fbbdcc56591ba91e794f9b5281488f63353dca724637"

def once(s,a,b):
    n=s.count(a)
    if n!=1:
        raise RuntimeError("Unique anchor required (%d): %s" % (n,a[:180]))
    return s.replace(a,b,1)

def patch_iso(s):
    old_start='''    private static ExpoPair m10rAe1BPair(CaptureController captureController) {
        if (captureController == null || PhotonCamera.getSettings().selectedMode != CameraMode.PHOTO) return null;
'''
    new_start='''    private static final class M10RAe1BSelection {
        final ExpoPair pair;
        final M10RAe1BPolicy.Decision decision;
        final double focalLengthMm;
        final long oracleExposureNs;
        final int oracleIso;
        final boolean sensorClampApplied;
        M10RAe1BSelection(ExpoPair pair, M10RAe1BPolicy.Decision decision, double focalLengthMm,
                          long oracleExposureNs, int oracleIso, boolean sensorClampApplied) {
            this.pair=pair; this.decision=decision; this.focalLengthMm=focalLengthMm;
            this.oracleExposureNs=oracleExposureNs; this.oracleIso=oracleIso;
            this.sensorClampApplied=sensorClampApplied;
        }
    }

    private static volatile M10RAe1BSelection m10rAe1BPendingSelection;

    public static void prepareM10rAe1BCapture(CaptureController captureController) {
        m10rAe1BPendingSelection = m10rAe1BSelect(captureController);
    }

    private static M10RAe1BSelection m10rAe1BSelect(CaptureController captureController) {
        if (captureController == null || PhotonCamera.getSettings().selectedMode != CameraMode.PHOTO) return null;
'''
    s=once(s,old_start,new_start)

    old_tail='''        ExpoPair pair = new ExpoPair(appliedExposureNs, expLow, expHigh,
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
    new_tail='''        ExpoPair pair = new ExpoPair(appliedExposureNs, expLow, expHigh,
                appliedIso, isoLow, isoHigh, isoAnalog);
        pair.curlayer = ExpoPair.exposureLayer.Normal;
        Log.d(TAG, "M10R AE1B select preview=" + ExposureIndex.sec2string(ExposureIndex.time2sec(previewExposureNs))
                + " ISO" + previewIso + " Bv=" + String.format(Locale.US,"%.3f",decision.previewBvEv)
                + " -> " + ExposureIndex.sec2string(ExposureIndex.time2sec(appliedExposureNs))
                + " ISO" + appliedIso + " TVISO=" + String.format(Locale.US,"%.2f",decision.tvIsoEv));
        return new M10RAe1BSelection(pair, decision, focal, oracleExposureNs, oracleIso, clamped);
    }

    private static ExpoPair m10rAe1BPair(CaptureController captureController) {
        M10RAe1BSelection selection = m10rAe1BSelect(captureController);
        return selection != null ? selection.pair : null;
    }

'''
    s=once(s,old_tail,new_tail)

    old_set='''    public static void setExpo(CaptureRequest.Builder builder, int step, CaptureController captureController) {
        Log.v(TAG, "InputParams: " +
                "expo time:" + ExposureIndex.sec2string(ExposureIndex.time2sec(captureController.mPreviewExposureTime)) +
                " iso:" + captureController.mPreviewIso+ " analog:"+getISOAnalog());
        if(step == 0) fullpairs.clear();
        ExpoPair pair = GenerateExpoPair(step,captureController);
        fullpairs.add(pair);
'''
    new_set='''    public static void setExpo(CaptureRequest.Builder builder, int step, CaptureController captureController) {
        Log.v(TAG, "InputParams: " +
                "expo time:" + ExposureIndex.sec2string(ExposureIndex.time2sec(captureController.mPreviewExposureTime)) +
                " iso:" + captureController.mPreviewIso+ " analog:"+getISOAnalog());
        if(step == 0) fullpairs.clear();

        M10RAe1BSelection frozen = null;
        if (PhotonCamera.getSettings().selectedMode == CameraMode.PHOTO && step == 0) {
            frozen = m10rAe1BPendingSelection;
            m10rAe1BPendingSelection = null;
        }
        ExpoPair pair = frozen != null ? frozen.pair : GenerateExpoPair(step,captureController);
        fullpairs.add(pair);
        if (frozen != null) {
            M10RAe1BState.record(frozen.decision, frozen.focalLengthMm,
                    frozen.oracleExposureNs, frozen.oracleIso,
                    frozen.pair.exposure, frozen.pair.iso, frozen.sensorClampApplied);
            Log.d(TAG, "M10R AE1B FREEZE1 bound still request generation to "
                    + ExposureIndex.sec2string(ExposureIndex.time2sec(frozen.pair.exposure))
                    + " ISO" + frozen.pair.iso);
        }
'''
    s=once(s,old_set,new_set)

    old_gen='''    public static ExpoPair GenerateExpoPair(int step, CaptureController captureController) {
        ExpoPair ae1b = m10rAe1BPair(captureController);
'''
    new_gen='''    public static ExpoPair GenerateExpoPair(int step, CaptureController captureController) {
        if (step == -1 && PhotonCamera.getSettings().selectedMode == CameraMode.PHOTO
                && m10rAe1BPendingSelection != null) {
            return new ExpoPair(m10rAe1BPendingSelection.pair);
        }
        ExpoPair ae1b = m10rAe1BPair(captureController);
'''
    s=once(s,old_gen,new_gen)
    return s

def patch_capture(s):
    old='''            float focus = mFocus;
            double frametime = ExposureIndex.time2sec(IsoExpoSelector.GenerateExpoPair(-1, this).exposure);
'''
    new='''            float focus = mFocus;
            // AE1B FREEZE1: bind one preview-derived M10-R decision to this still sequence.
            IsoExpoSelector.prepareM10rAe1BCapture(this);
            double frametime = ExposureIndex.time2sec(IsoExpoSelector.GenerateExpoPair(-1, this).exposure);
'''
    return once(s,old,new)

def patch_renderer(s):
    old_vars='''        double ae1aFullSum = 0.0, ae1a70Sum = 0.0, ae1a45Sum = 0.0, ae1a20Sum = 0.0;
        long ae1aFullCount = 0L, ae1a70Count = 0L, ae1a45Count = 0L, ae1a20Count = 0L;
'''
    new_vars='''        double ae1aFullSum = 0.0, ae1a70Sum = 0.0, ae1a45Sum = 0.0, ae1a20Sum = 0.0;
        long ae1aFullCount = 0L, ae1a70Count = 0L, ae1a45Count = 0L, ae1a20Count = 0L;
        double ae1aIntegralWeightedSum = 0.0, ae1aIntegralWeightSum = 0.0;
'''
    s=once(s,old_vars,new_vars)

    old_sample='''                if (ae1aSample) {
                    ae1aFullSum += unit;
                    ae1aFullCount++;
                    double nx = (x + 0.5) / (double) width;
'''
    new_sample='''                if (ae1aSample) {
                    ae1aFullSum += unit;
                    ae1aFullCount++;
                    int integralWeight = M10RIntegralMask.weightForPixel(x, y, width, height);
                    if (integralWeight > 0) {
                        ae1aIntegralWeightedSum += unit * integralWeight;
                        ae1aIntegralWeightSum += integralWeight;
                    }
                    double nx = (x + 0.5) / (double) width;
'''
    s=once(s,old_sample,new_sample)

    old_calc='''        double ae1aCenterWeightedMean =
                (200.0 * ae1a70Mean + 300.0 * ae1a45Mean + 500.0 * ae1a20Mean) / 1000.0;
        JSONObject ae1aProbe = new JSONObject()
'''
    new_calc='''        double ae1aCenterWeightedMean =
                (200.0 * ae1a70Mean + 300.0 * ae1a45Mean + 500.0 * ae1a20Mean) / 1000.0;
        double ae1aIntegralMean = ae1aIntegralWeightSum > 0.0
                ? ae1aIntegralWeightedSum / ae1aIntegralWeightSum : 0.0;
        JSONObject ae1aProbe = new JSONObject()
'''
    s=once(s,old_calc,new_calc)

    old_put='''                .put("center20Mean", ae1a20Mean)
                .put("centerWeightedMean", ae1aCenterWeightedMean)
                .put("wholeSamples", ae1aFullCount)
'''
    new_put='''                .put("center20Mean", ae1a20Mean)
                .put("centerWeightedMean", ae1aCenterWeightedMean)
                .put("leicaIntegral16x22Mean", ae1aIntegralMean)
                .put("leicaIntegralMaskWeightSum", M10RIntegralMask.WEIGHT_SUM)
                .put("leicaIntegralMaskFirmwareRecovered", true)
                .put("wholeSamples", ae1aFullCount)
'''
    s=once(s,old_put,new_put)

    old_if='''        if (ae1aFullMean > 0.0 && ae1aCenterWeightedMean > 0.0) {
            ae1aProbe.put("centerWeightedVsWholeEv",
                    Math.log(ae1aCenterWeightedMean / ae1aFullMean) / Math.log(2.0));
        } else {
            ae1aProbe.put("centerWeightedVsWholeEv", JSONObject.NULL);
        }
        d.put("m10rAe1A_rawMeterProbe", ae1aProbe);
'''
    new_if='''        if (ae1aFullMean > 0.0 && ae1aCenterWeightedMean > 0.0) {
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
        d.put("m10rAe1A_rawMeterProbe", ae1aProbe);
'''
    s=once(s,old_if,new_if)

    old_state='''        if (s.valid) {
            o.put("previewExposureTimeNs", s.previewExposureNs)
'''
    new_state='''        if (s.valid) {
            Long requestNs = captureRequest != null ? captureRequest.get(CaptureRequest.SENSOR_EXPOSURE_TIME) : null;
            Integer requestIso = captureRequest != null ? captureRequest.get(CaptureRequest.SENSOR_SENSITIVITY) : null;
            o.put("captureRequestExposureTimeNs", requestNs != null ? requestNs : JSONObject.NULL)
                    .put("captureRequestIso", requestIso != null ? requestIso : JSONObject.NULL)
                    .put("captureRequestMatchesFrozenState",
                            requestNs != null && requestIso != null
                            && requestNs == s.appliedExposureNs && requestIso == s.appliedIso)
                    .put("previewExposureTimeNs", s.previewExposureNs)
'''
    # appendAe1BState currently has only d parameter, so change signature and call first
    s=once(s,
        "    private static void appendAe1BState(JSONObject d) throws Exception {",
        "    private static void appendAe1BState(JSONObject d, CaptureRequest captureRequest) throws Exception {")
    s=once(s,old_state,new_state)
    s=once(s,"                appendAe1BState(d);","                appendAe1BState(d, captureRequest);")
    return s

def main():
    if len(sys.argv)!=2:
        raise SystemExit("usage: fix-m10r-render1w-ae1b-freeze1.py <PhotonCamera-root>")
    root=Path(sys.argv[1]).resolve()
    repo=Path(__file__).resolve().parents[1]
    iso=root/"app/src/main/java/com/particlesdevs/photoncamera/processing/parameters/IsoExpoSelector.java"
    cap=root/"app/src/main/java/com/particlesdevs/photoncamera/capture/CaptureController.java"
    renderer=root/"app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java"
    cpp=root/"app/src/main/cpp/m10rRender.cpp"
    gradle=root/"app/build.gradle"
    if hashlib.sha256(cpp.read_bytes()).hexdigest()!=RENDER_CPP_SHA:
        raise RuntimeError("AE1B FREEZE1 refuses changed native renderer")

    iso.write_text(patch_iso(iso.read_text()))
    cap.write_text(patch_capture(cap.read_text()))
    renderer.write_text(patch_renderer(renderer.read_text()))
    (renderer.parent/"M10RIntegralMask.java").write_bytes((repo/"android/M10RIntegralMask.java").read_bytes())

    g=gradle.read_text()
    versions=re.findall(r"versionName\s+['\"]([^'\"]+)['\"]",g)
    if len(versions)!=1 or "render1v-ae1b-live-render1t-colorrecon1a-tonecal1a-" not in versions[0]:
        raise RuntimeError("unexpected AE1B versionName: %r" % versions)
    version=versions[0].replace(
        "render1v-ae1b-live-render1t-colorrecon1a-tonecal1a-",
        "render1w-ae1b-freeze1-render1t-colorrecon1a-tonecal1a-",1)
    gradle.write_text(g.replace(versions[0],version,1))

    if hashlib.sha256(cpp.read_bytes()).hexdigest()!=RENDER_CPP_SHA:
        raise RuntimeError("AE1B FREEZE1 changed native renderer")
    proof={
        "schema":"RENDER1W_AE1B_FREEZE1_PATCH_V1",
        "baseline":"RENDER1V_AE1B_LIVE_on_RENDER1T",
        "versionName":version,
        "realExposureMutated":True,
        "captureDecisionFrozenOncePerStill":True,
        "captureRequestStateCorrelationAdded":True,
        "leicaIntegralMaskDiagnosticsAdded":True,
        "leicaIntegralMaskGrid":"22x16",
        "leicaIntegralMaskWeightSum":14160,
        "nestedAe1AProbeRetainedForComparisonOnly":True,
        "fixedEvBoost":False,
        "rendererNativeChanged":False,
        "hdrEnabled":False,
        "singleRaw":True,
        "deviceValidated":False,
        "productionPromoted":False
    }
    (root/"M10R_RENDER1W_AE1B_FREEZE1_PROVENANCE.json").write_text(json.dumps(proof,indent=2)+"\n")
    print(json.dumps(proof,indent=2))

if __name__=="__main__":
    main()
