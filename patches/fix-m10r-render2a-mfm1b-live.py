#!/usr/bin/env python3
"""MFM1B rotation-invariant positive backlight proxy on top of MFM1A.

Photographic change vs MFM1A:
- replace the MFM1A live-grid proxy with MFM1B;
- preserve the exact Leica Integral mask, recovered 4x6/24-region topology,
  AE1B allocator, RENDER1T renderer, single-RAW capture and no-HDR policy.

MFM1B removes the orientation-sensitive lower-half penalty from positive assist
and recognizes the brightest frame side against the inner field. It also
requires a mixed bright/dark regional population. The phone-domain gain and
thresholds remain explicitly empirical and are not claimed as Leica firmware
constants.
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
    if "M10RMfm1A" not in s or "M10RMfm1AState" not in s:
        raise RuntimeError("MFM1A anchors missing in IsoExpoSelector")
    s=s.replace("M10RMfm1AState","M10RMfm1BState")
    s=s.replace("M10RMfm1A","M10RMfm1B")
    s=s.replace("M10R MFM1A correction=","M10R MFM1B correction=")
    if "M10RMfm1A" in s or "M10RMfm1AState" in s:
        raise RuntimeError("stale MFM1A capture reference after replacement")
    return s

def patch_renderer(s):
    if "M10RMfm1A" not in s or '"m10rMfm1A"' not in s:
        raise RuntimeError("MFM1A renderer anchors missing")
    s=s.replace("M10RMfm1AState","M10RMfm1BState")
    s=s.replace("M10RMfm1A","M10RMfm1B")
    s=s.replace("mfm1a","mfm1b")
    s=s.replace("Mfm1A","Mfm1B")
    s=s.replace('"m10rMfm1A"','"m10rMfm1B"')

    # Extend per-decision diagnostics with the MFM1B geometry that motivated
    # this change. Existing fields are deliberately retained for A/B review.
    anchor='''                    .put("innerVsEdgeEv", x.innerVsEdgeEv)
                    .put("positiveCandidateEv", x.positiveCandidateEv)
'''
    repl='''                    .put("innerVsEdgeEv", x.innerVsEdgeEv)
                    .put("left4Y", x.left4Y)
                    .put("right4Y", x.right4Y)
                    .put("bottom6Y", x.bottom6Y)
                    .put("brightestSideY", x.brightestSideY)
                    .put("brightestSideVsInnerEv", x.brightestSideVsInnerEv)
                    .put("positiveBaseEv", x.positiveBaseEv)
                    .put("sideGeometryConfidence", x.sideGeometryConfidence)
                    .put("integralDominanceConfidence", x.integralDominanceConfidence)
                    .put("positiveBaseConfidence", x.positiveBaseConfidence)
                    .put("positiveCandidateEv", x.positiveCandidateEv)
'''
    s=once(s,anchor,repl)

    anchor2='''                .put("deadBandEv", M10RMfm1B.DEAD_BAND_EV)
                .put("stateValid", s.valid)
'''
    repl2='''                .put("deadBandEv", M10RMfm1B.DEAD_BAND_EV)
                .put("positiveGain", M10RMfm1B.POSITIVE_GAIN)
                .put("positiveGeometrySemantic",
                        "rotation_invariant_brightest_side_vs_inner_integral_dominance_telemetry_only")
                .put("positiveMagnitudeSemantic",
                        "0p65_integral_vs_median_plus_0p35_integral_vs_center_no_lower_half_penalty")
                .put("positiveBaseGate", "smoothstep_positive_base_ev_0p16_to_0p32")
                .put("stateValid", s.valid)
'''
    s=once(s,anchor2,repl2)

    if "M10RMfm1A" in s or '"m10rMfm1A"' in s:
        raise RuntimeError("stale MFM1A renderer reference after replacement")
    return s

def main():
    if len(sys.argv)!=2:
        raise SystemExit("usage: fix-m10r-render2a-mfm1b-live.py <PhotonCamera-root>")
    root=Path(sys.argv[1]).resolve()
    repo=Path(__file__).resolve().parents[1]

    iso=root/"app/src/main/java/com/particlesdevs/photoncamera/processing/parameters/IsoExpoSelector.java"
    renderer=root/"app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java"
    cpp=root/"app/src/main/cpp/m10rRender.cpp"
    gradle=root/"app/build.gradle"
    for p in [iso,renderer,cpp,gradle]:
        if not p.is_file(): raise RuntimeError("missing "+str(p))

    if hashlib.sha256(cpp.read_bytes()).hexdigest()!=CPP_SHA:
        raise RuntimeError("MFM1B refuses changed native renderer")

    iso.write_text(patch_iso(iso.read_text()))
    renderer.write_text(patch_renderer(renderer.read_text()))

    for name in ["M10RMfm1B.java","M10RMfm1BState.java"]:
        (renderer.parent/name).write_bytes((repo/"android"/name).read_bytes())

    g=gradle.read_text()
    versions=re.findall(r"versionName\s+['\"]([^'\"]+)['\"]",g)
    if len(versions)!=1 or versions[0]!="0.97-m10r1z-mfm1a":
        raise RuntimeError("unexpected MFM1A versionName: %r" % versions)
    version="0.97-m10r2a-mfm1b"
    gradle.write_text(g.replace(versions[0],version,1))

    if hashlib.sha256(cpp.read_bytes()).hexdigest()!=CPP_SHA:
        raise RuntimeError("MFM1B changed native renderer")

    proof={
        "schema":"RENDER2A_MFM1B_LIVE_PATCH_V1",
        "baseline":"RENDER1Z_MFM1A_on_METER1B_GRIDMAP1A_on_AE1B_FREEZE1_on_RENDER1T",
        "versionName":version,
        "activeCaptureCorrection":True,
        "sourceGrid":"validated_live_22x16_GRIDMAP1A_linear_preview",
        "integralMask":"exact_recovered_0x4001349c",
        "regionalTopology":"recovered_4x6_24_regions",
        "exactCa9ThirteenFeatureParityClaimed":False,
        "mfm1bChange":"rotation_invariant_positive_backlight_geometry",
        "positiveMagnitude":"0.65_integral_vs_median_plus_0.35_integral_vs_center",
        "positiveGeometry":"brightest_side_vs_inner_directional_gate",
        "positiveBaseGate":"0.16_to_0.32_ev_smoothstep",
        "positiveGain":1.50,
        "positiveGainFirmwareClaimed":False,
        "positiveLimitEv":0.75,
        "negativeLimitEv":-0.50,
        "deadBandEv":0.08,
        "fixedGlobalEvBoost":False,
        "rawCounterfactualValidationIncluded":True,
        "rendererNativeChanged":False,
        "hdrEnabled":False,
        "singleRaw":True,
        "privatePhotoFixtureCommitted":False,
        "privateValidationDataCommitted":False,
        "deviceValidated":False,
        "productionPromoted":False
    }
    (root/"M10R_RENDER2A_MFM1B_LIVE_PROVENANCE.json").write_text(json.dumps(proof,indent=2)+"\n")
    print(json.dumps(proof,indent=2))

if __name__=="__main__":
    main()
