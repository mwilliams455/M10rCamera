#!/usr/bin/env python3
"""RENDER2J MFM1D SOURCEPROXY1A on top of RENDER2I PORT1A/MFM1C.

Photographic renderer: unchanged byte-for-byte RENDER2G native core.
PORT1A: unchanged.
Leica MFM1B decision topology/thresholds: unchanged.

MFM1D moves the preview->RAW proxy exponent out of the shared Leica meter and
into the physical-sensor source adapter:
- Xiaomi 15 Ultra main (~24 mm equiv): 1.90, validated by paired live/RAW anchors.
- Xiaomi 15 Ultra ~100 mm camera: 1.00 identity, provisional paired evidence.
- unknown physical sensor: 1.00 identity fallback until paired live/RAW evidence.

This is source normalization only; no per-lens Leica look/HSM/tone tuning.
"""
from pathlib import Path
import hashlib,json,re,sys

CPP_SHA="3f7b696cdf33e29348d7c0532f658c11819f9b8e54772b55753e357fb6018985"

def once(s,a,b,label):
    n=s.count(a)
    if n!=1:
        raise RuntimeError("%s anchor count=%d" % (label,n))
    return s.replace(a,b,1)

def patch_iso(s):
    s=once(
        s,
        "import com.particlesdevs.photoncamera.m10r.M10RMfm1CProxy;\n",
        "import com.particlesdevs.photoncamera.m10r.M10RMfm1DSourceProxy;\n"
        "import com.particlesdevs.photoncamera.m10r.M10RMfm1DSourceState;\n",
        "MFM1D imports")

    old_fields='''        final M10RMfm1B.Decision mfmDecision;
        final long liveGridGeneration;
        final double userExposureCorrectionEv;
        final double mfmExposureCorrectionEv;
        final double totalExposureCorrectionEv;
        M10RAe1BSelection(ExpoPair pair, M10RAe1BPolicy.Decision decision, double focalLengthMm,
                          long oracleExposureNs, int oracleIso, boolean sensorClampApplied,
                          M10RMfm1B.Decision mfmDecision, long liveGridGeneration,
                          double userExposureCorrectionEv, double mfmExposureCorrectionEv,
                          double totalExposureCorrectionEv) {
'''
    new_fields='''        final M10RMfm1B.Decision mfmDecision;
        final M10RMfm1DSourceProxy.Profile mfmSourceProfile;
        final long liveGridGeneration;
        final double userExposureCorrectionEv;
        final double mfmExposureCorrectionEv;
        final double totalExposureCorrectionEv;
        M10RAe1BSelection(ExpoPair pair, M10RAe1BPolicy.Decision decision, double focalLengthMm,
                          long oracleExposureNs, int oracleIso, boolean sensorClampApplied,
                          M10RMfm1B.Decision mfmDecision,
                          M10RMfm1DSourceProxy.Profile mfmSourceProfile,
                          long liveGridGeneration,
                          double userExposureCorrectionEv, double mfmExposureCorrectionEv,
                          double totalExposureCorrectionEv) {
'''
    s=once(s,old_fields,new_fields,"MFM1D selection fields")
    s=once(
        s,
        '''            this.mfmDecision=mfmDecision; this.liveGridGeneration=liveGridGeneration;
''',
        '''            this.mfmDecision=mfmDecision; this.mfmSourceProfile=mfmSourceProfile;
            this.liveGridGeneration=liveGridGeneration;
''',
        "MFM1D selection assignment")

    old_eval='''        // MFM1C: preserve the recovered MFM1B spatial decision, but feed it a
        // monotonic preview->RAW proxy instead of the tone-compressed GL grid.
        double[] mfm1cRawProxyGrid = meterSnapshot != null && meterSnapshot.valid
                ? M10RMfm1CProxy.transform(meterSnapshot.linearGrid) : null;
        M10RMfm1B.Decision mfmDecision = M10RMfm1B.evaluate(mfm1cRawProxyGrid);
'''
    new_eval='''        // MFM1D SOURCEPROXY1A: normalize each physical phone sensor into the
        // common RAW-proxy meter domain before the unchanged shared MFM1B logic.
        Integer sourceCfaObj = characteristics.get(
                CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT);
        int sourceCfa = sourceCfaObj != null ? sourceCfaObj : -1;
        M10RMfm1DSourceProxy.Profile mfmSourceProfile =
                M10RMfm1DSourceProxy.resolve(sensor.getWidth(), focal, aperture, sourceCfa);
        double[] mfm1dRawProxyGrid = meterSnapshot != null && meterSnapshot.valid
                ? M10RMfm1DSourceProxy.transform(
                        meterSnapshot.linearGrid, mfmSourceProfile) : null;
        M10RMfm1B.Decision mfmDecision = M10RMfm1B.evaluate(mfm1dRawProxyGrid);
'''
    s=once(s,old_eval,new_eval,"MFM1D source proxy evaluation")

    old_return='''        return new M10RAe1BSelection(pair, decision, focal, oracleExposureNs, oracleIso, clamped,
                mfmDecision, liveGridGeneration, userExposureCorrection,
                mfmExposureCorrection, exposureCorrection);
'''
    new_return='''        return new M10RAe1BSelection(pair, decision, focal, oracleExposureNs, oracleIso, clamped,
                mfmDecision, mfmSourceProfile, liveGridGeneration, userExposureCorrection,
                mfmExposureCorrection, exposureCorrection);
'''
    s=once(s,old_return,new_return,"MFM1D selection return")

    record_anchor='''            M10RMfm1BState.record(frozen.liveGridGeneration,
                    frozen.userExposureCorrectionEv, frozen.mfmExposureCorrectionEv,
                    frozen.totalExposureCorrectionEv, frozen.mfmDecision);
'''
    record_new=record_anchor+'''            M10RMfm1DSourceState.record(frozen.mfmSourceProfile);
            Log.d(TAG, "M10R MFM1D sourceProfile="
                    + (frozen.mfmSourceProfile != null ? frozen.mfmSourceProfile.id : "null")
                    + " exponent="
                    + (frozen.mfmSourceProfile != null
                        ? String.format(Locale.US, "%.2f", frozen.mfmSourceProfile.exponent)
                        : "n/a"));
'''
    s=once(s,record_anchor,record_new,"MFM1D still-bound source state")
    return s

def patch_renderer(s):
    # Still uses MFM1B decision state; add the independently still-bound source
    # adapter state alongside it.
    state_anchor='''        M10RMfm1BState.Snapshot s = M10RMfm1BState.snapshot();
        M10RMfm1B.Decision raw = mfm1bRawCounterfactual(d);
'''
    state_new='''        M10RMfm1BState.Snapshot s = M10RMfm1BState.snapshot();
        M10RMfm1DSourceState.Snapshot sourceProxy = M10RMfm1DSourceState.snapshot();
        M10RMfm1B.Decision raw = mfm1bRawCounterfactual(d);
'''
    s=once(s,state_anchor,state_new,"MFM1D renderer source state")

    old_diag='''                .put("meterRevision", "MFM1C_PREVIEW_DECOMPRESS1A")
                .put("liveInputBeforeProxy",
                        "GL_SurfaceTexture_RGBA8_inverse_sRGB_per_channel_Rec709_luma")
                .put("liveRawProxyTransform", "pow_clamp01_Y_1p90")
                .put("liveRawProxyExponent", M10RMfm1CProxy.EXPONENT)
                .put("liveRawProxyMonotonic", true)
                .put("rawCounterfactualProxyApplied", false)
                .put("rawCounterfactualDomain", "normalized_RAW_green_pre_lens_shading")
                .put("rendererPixelsChangedByMfm1C", false)
'''
    new_diag='''                .put("meterRevision", "MFM1D_SOURCEPROXY1A")
                .put("liveInputBeforeProxy",
                        "GL_SurfaceTexture_RGBA8_inverse_sRGB_per_channel_Rec709_luma")
                .put("sourceProxyStateValid", sourceProxy.valid)
                .put("sourceProxyProfileId", sourceProxy.profileId)
                .put("sourceProxyCalibrationStatus", sourceProxy.calibrationStatus)
                .put("sourceProxyBasis", sourceProxy.basis)
                .put("sourceProxySensorWidthMm", sourceProxy.sensorWidthMm)
                .put("sourceProxyPhysicalFocalMm", sourceProxy.physicalFocalMm)
                .put("sourceProxyAperture", sourceProxy.aperture)
                .put("sourceProxyCfa", sourceProxy.cfa)
                .put("liveRawProxyTransform", "pow_clamp01_Y_sensor_profile_exponent")
                .put("liveRawProxyExponent", sourceProxy.exponent)
                .put("liveRawProxyMonotonic", true)
                .put("unknownSensorFallbackExponent", M10RMfm1DSourceProxy.FALLBACK_EXPONENT)
                .put("rawCounterfactualProxyApplied", false)
                .put("rawCounterfactualDomain", "normalized_RAW_green_pre_lens_shading")
                .put("rendererPixelsChangedByMfm1D", false)
                .put("perLensLeicaMeterTuningApplied", false)
                .put("sourceNormalizationPerPhysicalSensor", true)
'''
    s=once(s,old_diag,new_diag,"MFM1D diagnostics")

    s=once(
        s,
        'd.put("renderLook", "RENDER2G_YATOPOLOGY1A_GAMUT1A_TONECAL1A_MFM1C_EDGE0A");',
        'd.put("renderLook", "RENDER2G_YATOPOLOGY1A_GAMUT1A_TONECAL1A_MFM1D_EDGE0A");',
        "MFM1D renderLook")
    s=once(s,'d.put("m10rMfm1C", o);','d.put("m10rMfm1D", o);',"MFM1D diagnostic key")
    return s

def main():
    if len(sys.argv)!=2:
        raise SystemExit("usage: fix-m10r-render2j-mfm1d-sourceproxy1a.py <PhotonCamera-root>")
    root=Path(sys.argv[1]).resolve()
    repo=Path(__file__).resolve().parents[1]

    iso=root/"app/src/main/java/com/particlesdevs/photoncamera/processing/parameters/IsoExpoSelector.java"
    renderer=root/"app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java"
    cpp=root/"app/src/main/cpp/m10rRender.cpp"
    gradle=root/"app/build.gradle"
    for p in (iso,renderer,cpp,gradle):
        if not p.is_file(): raise RuntimeError("missing "+str(p))

    if hashlib.sha256(cpp.read_bytes()).hexdigest()!=CPP_SHA:
        raise RuntimeError("MFM1D refuses changed validated RENDER2G native renderer")

    iso.write_text(patch_iso(iso.read_text()))
    renderer.write_text(patch_renderer(renderer.read_text()))
    for name in ("M10RMfm1DSourceProxy.java","M10RMfm1DSourceState.java"):
        (renderer.parent/name).write_bytes((repo/"android"/name).read_bytes())

    g=gradle.read_text()
    versions=re.findall(r'versionName\s+[\'"]([^\'"]+)[\'"]',g)
    if len(versions)!=1 or versions[0]!="0.97-m10r2i-port1a-mfm1c":
        raise RuntimeError("unexpected RENDER2I versionName: %r"%versions)
    version="0.97-m10r2j-mfm1d-sourceproxy1a"
    gradle.write_text(g.replace(versions[0],version,1))

    if hashlib.sha256(cpp.read_bytes()).hexdigest()!=CPP_SHA:
        raise RuntimeError("MFM1D changed validated RENDER2G native renderer")

    ii=iso.read_text(); rr=renderer.read_text()
    for needle in [
        'M10RMfm1DSourceProxy.resolve(sensor.getWidth(), focal, aperture, sourceCfa)',
        'M10RMfm1DSourceProxy.transform(',
        'M10RMfm1DSourceState.record(frozen.mfmSourceProfile)',
        'M10RMfm1B.evaluate(mfm1dRawProxyGrid)',
    ]:
        if needle not in ii: raise RuntimeError("MFM1D ISO invariant missing: "+needle)
    for needle in [
        'MFM1D_SOURCEPROXY1A',
        'sourceProxyProfileId',
        'sourceProxyCalibrationStatus',
        'sourceNormalizationPerPhysicalSensor',
        'perLensLeicaMeterTuningApplied", false',
        'RENDER2G_YATOPOLOGY1A_GAMUT1A_TONECAL1A_MFM1D_EDGE0A',
        'd.put("m10rMfm1D", o);',
    ]:
        if needle not in rr: raise RuntimeError("MFM1D renderer invariant missing: "+needle)

    proof={
      "schema":"RENDER2J_MFM1D_SOURCEPROXY1A_PATCH_V1",
      "baseline":"RENDER2I_PORT1A_MFM1C",
      "versionName":version,
      "rendererNativeSha256":CPP_SHA,
      "rendererNativeChanged":False,
      "render2gPixelsChanged":False,
      "port1aChanged":False,
      "mfmDecisionCore":"MFM1B_unchanged",
      "mfmRevision":"MFM1D_SOURCEPROXY1A",
      "sourceNormalizationPerPhysicalSensor":True,
      "profiles":{
        "XIAOMI15U_MAIN24":{
          "sensorWidthMm":13.1072,
          "physicalFocalMm":8.72,
          "aperture":1.63,
          "exponent":1.90,
          "status":"paired_live_raw_validated"
        },
        "XIAOMI15U_SUPERTELE100":{
          "sensorWidthMm":9.1392,
          "physicalFocalMm":25.10,
          "aperture":2.60,
          "exponent":1.00,
          "status":"single_pair_provisional"
        }
      },
      "unknownPhysicalSensorExponent":1.00,
      "unknownPhysicalSensorPolicy":"identity_until_paired_live_RAW_evidence",
      "perLensLeicaMeterTuningApplied":False,
      "perLensPhotographicTuningApplied":False,
      "cobaltRuntimeDependency":False,
      "rawCounterfactualTransformApplied":False,
      "fixedGlobalEvBoost":False,
      "hdrEnabled":False,
      "singleRaw":True,
      "privatePhotoFixtureCommitted":False,
      "privateValidationDataCommitted":False,
      "deviceValidated":False,
      "allLensValidated":False,
      "productionPromoted":False
    }
    (root/"M10R_RENDER2J_MFM1D_SOURCEPROXY1A_PROVENANCE.json").write_text(
        json.dumps(proof,indent=2)+"\n")
    print(json.dumps(proof,indent=2))

if __name__=="__main__":
    main()
