#!/usr/bin/env python3
"""COLORRECON1B POSTYC1A isolated A/B on top of RENDER2B/SKINTRACE1A.

Single photographic variable vs RENDER2B:
- COLORRECON colour direction is taken from reconstructed post-MEDIUM/DG
  working RGB (nr/ng/nb), then transformed by the recovered CC1 matrix.
- The existing RENDER1S-derived lightness anchor, COLORRECON shoulder,
  GAMUT1A, TONECAL1A, MFM1B, capture/WB/source processing are unchanged.

This restores the recovered CC1 placement relative to the nonlinear Yc stage.
It does NOT claim exact Y_BLEND parity because YBLEND1B k=0.35 remains empirical.
"""
from pathlib import Path
import hashlib,json,re,sys

BASE_CPP_SHA=None  # guarded structurally because SKINTRACE1A changes diagnostics only.

def once(s,a,b):
    n=s.count(a)
    if n!=1:
        raise RuntimeError("Unique anchor required (%d): %s" % (n,a[:180]))
    return s.replace(a,b,1)

def patch_cpp(s):
    old='''            const unsigned colorFlags=m10r_colorrecon1a::apply(
                    lr,lg,lb,outMat,legacyOutR,legacyOutG,legacyOutB,
                    tone,dgt,outR,outG,outB,&skinTraceColor);
'''
    new='''            // COLORRECON1B POSTYC1A: restore recovered CC1 placement.
            // Use the nonlinear Yc reconstruction (nr/ng/nb) as CC1 input
            // instead of COLORRECON1A's empirical pre-tone working RGB.
            const unsigned colorFlags=m10r_colorrecon1a::apply(
                    nr,ng,nb,outMat,legacyOutR,legacyOutG,legacyOutB,
                    tone,dgt,outR,outG,outB,&skinTraceColor);
'''
    return once(s,old,new)

def patch_java(s):
    edits={
      '"RENDER1T_COLORRECON1A_GAMUT1A_TONECAL1A_EDGE0A"':
        '"RENDER2C_COLORRECON1B_POSTYC1A_GAMUT1A_TONECAL1A_EDGE0A"',
      '"linear_CC1_colour_render1s_lightness_anchor_saturation_dependent_shoulder"':
        '"post_Yc_working_CC1_colour_render1s_lightness_anchor_saturation_dependent_shoulder"',
      '"pre_tone_working_RGB_for_colour_and_legacy_post_Yc_RGB_for_lightness_anchor"':
        '"post_MEDIUM_DG_Yc_exact_inverse_working_RGB_for_colour_and_legacy_post_Yc_RGB_for_lightness_anchor"',
      '"COLORRECON1A_LINEAR_COLOUR_WITH_RENDER1S_LIGHTNESS_ANCHOR_AND_CHROMA_DEPENDENT_SHOULDER"':
        '"COLORRECON1B_POSTYC1A_CC1_AFTER_YC_INVERSE_WITH_RENDER1S_LIGHTNESS_ANCHOR_AND_SHOULDER"',
      '"COLORRECON1A"':'"COLORRECON1B_POSTYC1A"',
      '"linear_CC1_RGB_then_COLORRECON1A_gain_and_sRGB_encoding"':
        '"post_Yc_CC1_RGB_then_COLORRECON1B_gain_and_sRGB_encoding"',
      '"post_COLORRECON1A_sRGB_encoding_before_ARGB8_then_unchanged_TONECAL1A"':
        '"post_COLORRECON1B_sRGB_encoding_before_ARGB8_then_unchanged_TONECAL1A"',
      '"explicit_sRGB_encoded_COLORRECON1A_output"':
        '"explicit_sRGB_encoded_COLORRECON1B_output"',
      '"COLORRECON1A_sRGB_then_GAMUT1A_then_8bit_then_unchanged_TONECAL1A"':
        '"COLORRECON1B_sRGB_then_GAMUT1A_then_8bit_then_unchanged_TONECAL1A"',
      '"COLORRECON1A_EXPLICIT_SRGB_ENCODING"':
        '"COLORRECON1B_EXPLICIT_SRGB_ENCODING"',
      '"native_after_COLORRECON1A_sRGB_and_GAMUT1A_before_TONECAL1A_and_JPEG"':
        '"native_after_COLORRECON1B_sRGB_and_GAMUT1A_before_TONECAL1A_and_JPEG"',
      '"COLORRECON1A_explicit_sRGB_encoding"':
        '"COLORRECON1B_explicit_sRGB_encoding"'
    }
    for a,b in edits.items():
        if a in s:
            s=s.replace(a,b)
    # Rename main diagnostic object while preserving SKINTRACE1A.
    s=once(s,'d.put("colorRecon1A", new JSONObject()','d.put("colorRecon1B", new JSONObject()')
    s=once(s,'.put("empiricalNotFirmware", true)
                    .put("method", "post_Yc_working_CC1_colour_render1s_lightness_anchor_saturation_dependent_shoulder")',
           '.put("empiricalNotFirmware", true)
                    .put("method", "post_Yc_working_CC1_colour_render1s_lightness_anchor_saturation_dependent_shoulder")
                    .put("postYc1A", true)
                    .put("onlyPhotographicVariableVsRender2B", "CC1_input_preTone_working_to_postYc_reconstructed_working")
                    .put("cc1PlacementRestoredToRecoveredBoundary", true)
                    .put("exactYBlendParityClaimed", false)')
    return s

def main():
    if len(sys.argv)!=2:
        raise SystemExit("usage: fix-m10r-render2c-colorrecon1b-postyc1a.py <PhotonCamera-root>")
    root=Path(sys.argv[1]).resolve()
    cpp=root/"app/src/main/cpp/m10rRender.cpp"
    java=root/"app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java"
    gradle=root/"app/build.gradle"
    for p in [cpp,java,gradle]:
        if not p.is_file(): raise RuntimeError("missing "+str(p))
    cb=cpp.read_text(); jb=java.read_text()
    if "SKINTRACE1A" not in cb or '"skinTrace1A"' not in jb:
        raise RuntimeError("RENDER2B/SKINTRACE1A baseline anchors missing")
    ca=patch_cpp(cb); ja=patch_java(jb)
    cpp.write_text(ca); java.write_text(ja)
    g=gradle.read_text()
    versions=re.findall(r'versionName\s+[\'\"]([^\'\"]+)[\'\"]',g)
    if len(versions)!=1 or versions[0]!="0.97-m10r2b-skintrace1a":
        raise RuntimeError("unexpected RENDER2B versionName: %r" % versions)
    version="0.97-m10r2c-postyc1a"
    gradle.write_text(g.replace(versions[0],version,1))
    proof={
      "schema":"RENDER2C_COLORRECON1B_POSTYC1A_PATCH_V1",
      "baseline":"RENDER2B_SKINTRACE1A_on_RENDER2A_MFM1B",
      "versionName":version,
      "photographicChange":"COLORRECON_CC1_input_preTone_working_to_postYc_reconstructed_working",
      "cc1PlacementRestoredToRecoveredBoundary":True,
      "exactYBlendParityClaimed":False,
      "yBlendCarrier":"YBLEND1B_k0.35_empirical",
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
    (root/"M10R_RENDER2C_COLORRECON1B_POSTYC1A_PROVENANCE.json").write_text(json.dumps(proof,indent=2)+"\n")
    print(json.dumps(proof,indent=2))
if __name__=="__main__": main()
