#!/usr/bin/env python3
"""RENDER2K MFM1D SOURCEPROXY1B generic physical-camera fingerprints.

Supersedes SOURCEPROXY1A's device/lens labels without changing:
- validated RENDER2G native photographic pixels;
- PORT1A CFA/source portability;
- shared MFM1B Leica scene decision.

A physical source is identified from Camera2/RAW characteristics only:
active-array dimensions, CFA, physical sensor width, current physical focal
length/aperture, RAW white level, and calibration illuminants. The canonical
descriptor is SHA-256 fingerprinted. Calibration registry keys are fingerprints,
not manufacturer/model/lens names. Unknown sensors use identity until paired
live/RAW evidence exists.
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
    old='''        Integer sourceCfaObj = characteristics.get(
                CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT);
        int sourceCfa = sourceCfaObj != null ? sourceCfaObj : -1;
        M10RMfm1DSourceProxy.Profile mfmSourceProfile =
                M10RMfm1DSourceProxy.resolve(sensor.getWidth(), focal, aperture, sourceCfa);
'''
    new='''        M10RMfm1DSourceProxy.Profile mfmSourceProfile =
                M10RMfm1DSourceProxy.resolve(characteristics, focal, aperture);
'''
    s=once(s,old,new,"generic fingerprint resolve")
    return s

def patch_renderer(s):
    s=once(s,
        '.put("meterRevision", "MFM1D_SOURCEPROXY1A")',
        '.put("meterRevision", "MFM1D_SOURCEPROXY1B_GENERIC_FINGERPRINT")',
        "meter revision")

    anchor='''                .put("sourceProxyProfileId", sourceProxy.profileId)
                .put("sourceProxyCalibrationStatus", sourceProxy.calibrationStatus)
                .put("sourceProxyBasis", sourceProxy.basis)
                .put("sourceProxySensorWidthMm", sourceProxy.sensorWidthMm)
'''
    repl='''                .put("sourceProxyProfileId", sourceProxy.profileId)
                .put("sourceProxyPhysicalFingerprint", sourceProxy.fingerprint)
                .put("sourceProxyCanonicalDescriptor", sourceProxy.canonicalDescriptor)
                .put("sourceProxyCalibrationStatus", sourceProxy.calibrationStatus)
                .put("sourceProxyCalibrationEvidenceId", sourceProxy.calibrationEvidenceId)
                .put("sourceProxyBasis", sourceProxy.basis)
                .put("sourceProxyActiveWidth", sourceProxy.activeWidth)
                .put("sourceProxyActiveHeight", sourceProxy.activeHeight)
                .put("sourceProxySensorWidthMm", sourceProxy.sensorWidthMm)
'''
    s=once(s,anchor,repl,"generic source diagnostics")

    anchor2='''                .put("sourceProxyCfa", sourceProxy.cfa)
                .put("liveRawProxyTransform", "pow_clamp01_Y_sensor_profile_exponent")
'''
    repl2='''                .put("sourceProxyCfa", sourceProxy.cfa)
                .put("sourceProxyWhiteLevel", sourceProxy.whiteLevel)
                .put("sourceProxyReferenceIlluminant1", sourceProxy.referenceIlluminant1)
                .put("sourceProxyReferenceIlluminant2", sourceProxy.referenceIlluminant2)
                .put("sourceProxyIdentitySemantic",
                        "generic_Camera2_RAW_characteristics_fingerprint_not_brand_model_lens_name")
                .put("liveRawProxyTransform", "pow_clamp01_Y_sensor_profile_exponent")
'''
    s=once(s,anchor2,repl2,"generic identity diagnostics")
    return s

def main():
    if len(sys.argv)!=2:
        raise SystemExit("usage: fix-m10r-render2k-mfm1d-sourceproxy1b.py <PhotonCamera-root>")
    root=Path(sys.argv[1]).resolve()
    repo=Path(__file__).resolve().parents[1]

    iso=root/"app/src/main/java/com/particlesdevs/photoncamera/processing/parameters/IsoExpoSelector.java"
    renderer=root/"app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java"
    cpp=root/"app/src/main/cpp/m10rRender.cpp"
    gradle=root/"app/build.gradle"
    for p in (iso,renderer,cpp,gradle):
        if not p.is_file(): raise RuntimeError("missing "+str(p))

    if hashlib.sha256(cpp.read_bytes()).hexdigest()!=CPP_SHA:
        raise RuntimeError("SOURCEPROXY1B refuses changed validated RENDER2G native renderer")

    iso.write_text(patch_iso(iso.read_text()))
    renderer.write_text(patch_renderer(renderer.read_text()))

    # Replace SOURCEPROXY1A classes with generic-fingerprint SOURCEPROXY1B classes.
    for name in ("M10RMfm1DSourceProxy.java","M10RMfm1DSourceState.java"):
        (renderer.parent/name).write_bytes((repo/"android"/name).read_bytes())

    g=gradle.read_text()
    versions=re.findall(r'versionName\s+[\'"]([^\'"]+)[\'"]',g)
    if len(versions)!=1 or versions[0]!="0.97-m10r2j-mfm1d-sourceproxy1a":
        raise RuntimeError("unexpected RENDER2J versionName: %r"%versions)
    version="0.97-m10r2k-mfm1d-sourceproxy1b"
    gradle.write_text(g.replace(versions[0],version,1))

    if hashlib.sha256(cpp.read_bytes()).hexdigest()!=CPP_SHA:
        raise RuntimeError("SOURCEPROXY1B changed validated RENDER2G native renderer")

    ii=iso.read_text(); rr=renderer.read_text()
    proxy=(renderer.parent/"M10RMfm1DSourceProxy.java").read_text()
    state=(renderer.parent/"M10RMfm1DSourceState.java").read_text()

    for needle in [
        'M10RMfm1DSourceProxy.resolve(characteristics, focal, aperture)',
        'M10RMfm1B.evaluate(mfm1dRawProxyGrid)',
    ]:
        if needle not in ii: raise RuntimeError("SOURCEPROXY1B ISO invariant missing: "+needle)
    for needle in [
        'MFM1D_SOURCEPROXY1B_GENERIC_FINGERPRINT',
        'sourceProxyPhysicalFingerprint',
        'sourceProxyCanonicalDescriptor',
        'sourceProxyCalibrationEvidenceId',
        'sourceProxyIdentitySemantic',
        'generic_Camera2_RAW_characteristics_fingerprint_not_brand_model_lens_name',
        'perLensLeicaMeterTuningApplied", false',
    ]:
        if needle not in rr: raise RuntimeError("SOURCEPROXY1B renderer invariant missing: "+needle)
    for needle in [
        'SENSOR_INFO_ACTIVE_ARRAY_SIZE',
        'SENSOR_INFO_COLOR_FILTER_ARRANGEMENT',
        'SENSOR_INFO_PHYSICAL_SIZE',
        'SENSOR_INFO_WHITE_LEVEL',
        'SENSOR_REFERENCE_ILLUMINANT1',
        'SENSOR_REFERENCE_ILLUMINANT2',
        'sha256Prefix16',
        'CAL_FP_A = "03d973b6411b4879"',
        'CAL_FP_B = "f76d00db34b9480f"',
        'FALLBACK_EXPONENT = 1.00',
    ]:
        if needle not in proxy: raise RuntimeError("SOURCEPROXY1B proxy invariant missing: "+needle)

    # Active implementation must not encode manufacturer/model/lens-name identities.
    for bad in ['XIAOMI','Xiaomi','15U','SUPERTELE','MAIN24']:
        if bad in proxy or bad in state or bad in ii or bad in rr:
            raise RuntimeError("SOURCEPROXY1B active code contains device-specific identity: "+bad)

    proof={
      "schema":"RENDER2K_MFM1D_SOURCEPROXY1B_PATCH_V1",
      "baseline":"RENDER2J_MFM1D_SOURCEPROXY1A",
      "versionName":version,
      "rendererNativeSha256":CPP_SHA,
      "rendererNativeChanged":False,
      "render2gPixelsChanged":False,
      "port1aChanged":False,
      "mfmDecisionCore":"MFM1B_unchanged",
      "mfmRevision":"MFM1D_SOURCEPROXY1B_GENERIC_FINGERPRINT",
      "identityMechanism":"SHA256_prefix16_of_quantized_Camera2_RAW_characteristics",
      "fingerprintInputs":[
        "activeArrayWidth","activeArrayHeight","cfaPattern",
        "sensorPhysicalWidthMm","physicalFocalMm","aperture",
        "rawWhiteLevel","referenceIlluminant1","referenceIlluminant2"
      ],
      "calibrationRegistry":{
        "03d973b6411b4879":{"exponent":1.90,"status":"paired_live_raw_validated","evidenceId":"PAIR_A_20260926"},
        "f76d00db34b9480f":{"exponent":1.00,"status":"single_pair_provisional","evidenceId":"PAIR_B_20260926"}
      },
      "manufacturerModelLensNameMatching":False,
      "unknownPhysicalSensorExponent":1.00,
      "unknownPhysicalSensorPolicy":"identity_until_paired_live_RAW_evidence",
      "sourceNormalizationPerPhysicalSensor":True,
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
    (root/"M10R_RENDER2K_MFM1D_SOURCEPROXY1B_PROVENANCE.json").write_text(
        json.dumps(proof,indent=2)+"\n")
    print(json.dumps(proof,indent=2))

if __name__=="__main__":
    main()
