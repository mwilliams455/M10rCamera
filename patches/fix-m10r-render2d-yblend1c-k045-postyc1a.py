#!/usr/bin/env python3
"""RENDER2D YBLEND1C K045 controlled chroma-carrier A/B on POSTYC1A.

Single photographic variable vs RENDER2C:
- YBLEND excess chroma-gain inheritance k 0.35 -> 0.45.

Frozen:
- post-Yc CC1 placement (COLORRECON1B POSTYC1A)
- lightness anchor
- shoulder
- GAMUT1A / TONECAL1A
- MFM1B / exposure
- WB / source processing
- single RAW / HDR off

This is an empirical interpolation probe, not a Leica firmware formula claim.
"""
from pathlib import Path
import json,re,sys

def once(s,a,b):
    n=s.count(a)
    if n!=1:
        raise RuntimeError("Unique anchor required (%d): %s" % (n,a[:180]))
    return s.replace(a,b,1)

def patch_cpp(s):
    s=once(s,
        'const double yBlendChromaScale = y > 1.0e-12 ? 1.0 + 0.35 * (yRatio - 1.0) : 0.0;',
        'const double yBlendChromaScale = y > 1.0e-12 ? 1.0 + 0.45 * (yRatio - 1.0) : 0.0;')
    return s

def patch_java(s):
    s=once(s,
        'double yBlendChromaScale = (ycY > 1.0e-12) ? (1.0 + 0.35 * (yRatio - 1.0)) : 0.0;',
        'double yBlendChromaScale = (ycY > 1.0e-12) ? (1.0 + 0.45 * (yRatio - 1.0)) : 0.0;')

    replacements={
      'M10R_Yc_Convert_map_Y_YBLEND1B_k035_chroma_exact_inverse':
        'M10R_Yc_Convert_map_Y_YBLEND1C_k045_chroma_exact_inverse',
      'YBLEND1B_k035_between_absolute_and_relative_chroma_then_exact_matrix_inverse':
        'YBLEND1C_k045_between_absolute_and_relative_chroma_then_exact_matrix_inverse',
      'YBLEND1B applies k0p35 excess gain to chroma only':
        'YBLEND1C applies k0p45 excess gain to chroma only',
      '1_plus_0.35_times_(mappedY_over_inputY_minus_1)':
        '1_plus_0.45_times_(mappedY_over_inputY_minus_1)',
      'YBLEND1B_K035':
        'YBLEND1C_K045',
      'YBLEND1B_K035_CONTROLLED_PROBE_AFTER_CC1MAP1A':
        'YBLEND1C_K045_POSTYC1A_CONTROLLED_PROBE',
      'YBLEND1B_k0p35':
        'YBLEND1C_k0p45'
    }
    for a,b in replacements.items():
        s=s.replace(a,b)

    # Promote explicit probe metadata while preserving historical fields where useful.
    s=s.replace('d.put("yBlend1BProbeK", 0.35);',
                'd.put("yBlend1CProbeK", 0.45);')
    s=s.replace('d.put("yBlend1BK", 0.35);',
                'd.put("yBlend1CK", 0.45);')
    s=s.replace('d.put("yBlend1BExperimentalApplied", true);',
                'd.put("yBlend1CExperimentalApplied", true);')
    s=s.replace('d.put("yBlend1BFirmwareClaim", false);',
                'd.put("yBlend1CFirmwareClaim", false);')
    s=s.replace('d.put("yBlend1BInputY", "pre_MEDIUM_DG_Yc_Y");',
                'd.put("yBlend1CInputY", "pre_MEDIUM_DG_Yc_Y");')
    s=s.replace('d.put("yBlend1BMappedY", "unchanged_dy_over_DG_OUT_MAX");',
                'd.put("yBlend1CMappedY", "unchanged_dy_over_DG_OUT_MAX");')
    s=s.replace('d.put("yBlend1BPreviousScale", "YBLEND1A_k0p50");',
                'd.put("yBlend1CPreviousScale", "YBLEND1B_k0p35");')
    s=s.replace('d.put("yBlend1BNewChromaScale", "1_plus_0.45_times_(mappedY_over_inputY_minus_1)");',
                'd.put("yBlend1CNewChromaScale", "1_plus_0.45_times_(mappedY_over_inputY_minus_1)");')
    s=s.replace('d.put("yBlend1BLumaArithmeticChanged", false);',
                'd.put("yBlend1CLumaArithmeticChanged", false);')
    s=s.replace('d.put("yBlend1BMediumDgChanged", false);',
                'd.put("yBlend1CMediumDgChanged", false);')

    s=s.replace('"meanYBlend1BAppliedChromaScale"',
                '"meanYBlend1CAppliedChromaScale"')
    s=s.replace('d.put("yBlend1B", yBlend1A);',
                'd.put("yBlend1C", yBlend1A);')

    # Add isolated experiment block beside POSTYC1A diagnostics.
    marker='            d.put("outputGamut1A", new JSONObject()'
    s=once(s,marker,'''            d.put("yBlend1CPostYc1A", new JSONObject()
                    .put("enabled", true)
                    .put("probeK", 0.45)
                    .put("previousK", 0.35)
                    .put("onlyPhotographicVariableVsRender2C", "YBLEND_excess_chroma_gain_k_0p35_to_0p45")
                    .put("postYcCc1PlacementChanged", false)
                    .put("lightnessAnchorChanged", false)
                    .put("shoulderChanged", false)
                    .put("gamutMappingChanged", false)
                    .put("toneCalChanged", false)
                    .put("mfm1bChanged", false)
                    .put("firmwareFormulaClaimed", false));
'''+marker)
    return s

def main():
    if len(sys.argv)!=2:
        raise SystemExit("usage: fix-m10r-render2d-yblend1c-k045-postyc1a.py <PhotonCamera-root>")
    root=Path(sys.argv[1]).resolve()
    cpp=root/"app/src/main/cpp/m10rRender.cpp"
    java=root/"app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java"
    gradle=root/"app/build.gradle"
    for p in [cpp,java,gradle]:
        if not p.is_file(): raise RuntimeError("missing "+str(p))

    cb=cpp.read_text(); jb=java.read_text()
    if "COLORRECON1B POSTYC1A" not in cb or '"colorRecon1BPostYc1A"' not in jb:
        raise RuntimeError("RENDER2C POSTYC1A baseline anchors missing")
    cpp.write_text(patch_cpp(cb))
    java.write_text(patch_java(jb))

    g=gradle.read_text()
    versions=re.findall(r'versionName\s+[\'\"]([^\'\"]+)[\'\"]',g)
    if len(versions)!=1 or versions[0]!="0.97-m10r2c-postyc1a":
        raise RuntimeError("unexpected RENDER2C versionName: %r" % versions)
    version="0.97-m10r2d-yb1c-k045"
    gradle.write_text(g.replace(versions[0],version,1))

    proof={
      "schema":"RENDER2D_YBLEND1C_K045_POSTYC1A_PATCH_V1",
      "baseline":"RENDER2C_COLORRECON1B_POSTYC1A",
      "versionName":version,
      "photographicChange":"YBLEND_excess_chroma_gain_k_0.35_to_0.45",
      "previousK":0.35,
      "probeK":0.45,
      "firmwareFormulaClaimed":False,
      "postYcCc1PlacementChanged":False,
      "lightnessAnchorChanged":False,
      "shoulderChanged":False,
      "gamutMappingChanged":False,
      "toneCalChanged":False,
      "captureExposureChanged":False,
      "mfm1bChanged":False,
      "whiteBalanceChanged":False,
      "sourceProcessingChanged":False,
      "skinTraceRetained":True,
      "privatePhotoFixtureCommitted":False,
      "deviceValidated":False,
      "productionPromoted":False
    }
    (root/"M10R_RENDER2D_YBLEND1C_K045_POSTYC1A_PROVENANCE.json").write_text(json.dumps(proof,indent=2)+"\n")
    print(json.dumps(proof,indent=2))

if __name__=="__main__": main()
