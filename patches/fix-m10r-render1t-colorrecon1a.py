#!/usr/bin/env python3
"""Apply isolated COLORRECON1A to exact validated S; reject other sources."""
from pathlib import Path
import hashlib,json,re,sys
BASE='af0d5fb85b5df55a00b7765f58ca96d5484900333e552c1591f99e5cb31f3895'
JAVA='91cc7e5840d746567648447b1f2f149d12090ac42362087e0d32496a52f05bd6'
def digest(s):return hashlib.sha256(s.encode()).hexdigest()
def once(s,a,b):
 if s.count(a)!=1:raise RuntimeError('Unique anchor required: '+a[:120]+'; found '+str(s.count(a)))
 return s.replace(a,b,1)
def patch_cpp(s):
 if digest(s)!=BASE:raise RuntimeError('Refusing unknown RENDER1S native source')
 s=once(s,'#include "m10rOutputGamut1A.h"','#include "m10rColorRecon1A.h"\n#include "m10rOutputGamut1A.h"')
 for a,b in [('int64_t v[24] = {};','int64_t v[32] = {};'),('jlong existing[24] = {};','jlong existing[32] = {};'),('std::min(24,static_cast<int>','std::min(32,static_cast<int>')]:s=once(s,a,b)
 for ch in 'RGB':s=once(s,'const double out'+ch+' =','const double legacyOut'+ch+' =')
 s=once(s,'            double gamutR=outR, gamutG=outG, gamutB=outB;', '''            // The legacy reconstruction supplies only the S lightness anchor.
            // Actual colour is reconstructed from pre-tone working RGB.
            double outR,outG,outB;
            const unsigned colorFlags=m10r_colorrecon1a::apply(
                    lr,lg,lb,outMat,legacyOutR,legacyOutG,legacyOutB,
                    tone,dgt,outR,outG,outB);
            cnt.v[24]++;
            cnt.v[25]+=(colorFlags&1u)!=0;
            cnt.v[26]+=(colorFlags&2u)!=0;
            cnt.v[27]+=(colorFlags&4u)!=0;
            double gamutR=outR, gamutG=outG, gamutB=outB;''')
 return s

def patch_java(s):
 if digest(s)!=JAVA:raise RuntimeError('Refusing unknown RENDER1S Java source')
 s=once(s,'final long[] nativeExactCounts = new long[24];','final long[] nativeExactCounts = new long[32];')
 edits={
 'RENDER1S_GAMUT1A_TONECAL1A_CC1MAP1A_YBLEND1B_K035_EDGE0A':'RENDER1T_COLORRECON1A_GAMUT1A_TONECAL1A_EDGE0A',
 'actual_post_CC1_before_GAMUT1A_and_TONECAL1A':'counterfactual_RENDER1S_post_CC1_for_anchor_not_actual_COLORRECON1A_output',
 'meanActualPreGamutPostCc1':'meanCounterfactualRender1SPostCc1',
 'post_CC1_before_first_ARGB8_then_unchanged_TONECAL1A':'post_COLORRECON1A_sRGB_encoding_before_ARGB8_then_unchanged_TONECAL1A',
 'existing_direct_post_CC1_not_asserted_linear_light':'explicit_sRGB_encoded_COLORRECON1A_output',
 'actual_post_CC1_before_GAMUT1A_ARGB8_and_TONECAL1A_not_final_JPEG':'counterfactual_RENDER1S_output_for_anchor_not_actual_COLORRECON1A_output',
 'GAMUT1A_then_linear8_then_unchanged_TONECAL1A':'COLORRECON1A_sRGB_then_GAMUT1A_then_8bit_then_unchanged_TONECAL1A',
 'YBLEND1B_K035_CONTROLLED_PROBE_AFTER_CC1MAP1A':'COLORRECON1A_LINEAR_COLOUR_WITH_RENDER1S_LIGHTNESS_ANCHOR_AND_CHROMA_DEPENDENT_SHOULDER',
 'post_Yc_exact_inverse_working_RGB':'pre_tone_working_RGB_for_colour_and_legacy_post_Yc_RGB_for_lightness_anchor',
 'post_CC1_output_RGB_direct_linear8':'linear_CC1_RGB_then_COLORRECON1A_gain_and_sRGB_encoding',
 'NATIVEOUT1A_DIRECT_POST_CC1_LINEAR8':'COLORRECON1A_EXPLICIT_SRGB_ENCODING',
 'native_post_CC1_direct_8bit_before_JPEG':'native_after_COLORRECON1A_sRGB_and_GAMUT1A_before_TONECAL1A_and_JPEG',
 'post_CC1_linear_direct_8bit':'COLORRECON1A_explicit_sRGB_encoding',
 'direct_8bit_linear_round_clamp':'sRGB_code_8bit_round_after_COLORRECON1A_and_GAMUT1A'
 }
 for a,b in edits.items():
  if a not in s:raise RuntimeError('Missing diagnostic anchor '+a)
  s=s.replace(a,b)
 for key in ['cc1RedTraceMatchesActualPreGamutOutput','cc1On1ARestoresFinalColourOnly']:
  s=once(s,'d.put("'+key+'", true);','d.put("'+key+'", false);')
 s=once(s,'redTrace1B.put("actualPreGamutCc1Evaluated", true);','redTrace1B.put("actualPreGamutCc1Evaluated", false);\n            redTrace1B.put("counterfactualRender1SAnchorEvaluated", true);')
 s=once(s,'d.put("textbookSrgbOetfApplied", false);','d.put("textbookSrgbOetfApplied", true);')
 s=once(s,'yBlend1A.put("experimentalOnly", true);','yBlend1A.put("experimentalOnly", true);\n            yBlend1A.put("role", "legacy_RENDER1S_lightness_anchor_only_not_actual_colour_reconstruction");')
 s=once(s,'d.put("chromaReconstructionExperiment", "YBLEND1B_K035");','d.put("chromaReconstructionExperiment", "COLORRECON1A");')
 s=once(s,'d.put("yBlend1BExperimentalApplied", true);','d.put("yBlend1BExperimentalApplied", true);\n            d.put("yBlend1BPhotographicRole", "counterfactual_lightness_anchor_only");')
 s=once(s,'.put("toneCurveChanged", false).put("chromaKChanged", false)', '.put("toneCurveChanged", false).put("chromaKChanged", false)\n                    .put("chromaReconstructionChanged", true)')
 marker='            d.put("outputGamut1A", new JSONObject()'
 s=once(s,marker,'''            d.put("colorRecon1A", new JSONObject()
                    .put("enabled", true).put("empiricalNotFirmware", true)
                    .put("method", "linear_CC1_colour_render1s_lightness_anchor_saturation_dependent_shoulder")
                    .put("totalPixels", nativeExactCounts[24])
                    .put("peakLimitedPixels", nativeExactCounts[25])
                    .put("nonFiniteFallbackPixels", nativeExactCounts[26])
                    .put("linearPeakAboveOnePixels", nativeExactCounts[27])
                    .put("framePixelCountValid", nativeExactCounts[24]==(long)frame.width*frame.height)
                    .put("captureExposureChanged", false).put("whiteBalanceChanged", false)
                    .put("sourceProcessingChanged", false).put("toneAssetsChanged", false)
                    .put("toneCalCoefficientsChanged", false).put("spatialFilterAdded", false)
                    .put("legacyK", 0.35).put("legacyKRole", "counterfactual_lightness_anchor_only")
                    .put("outputEncoding", "explicit_sRGB").put("shoulderWidthCoefficient", 0.30)
                    .put("perceptualHuePreservationClaimed", false));
'''+marker)
 return s

def main():
 if not __debug__:raise RuntimeError('Assertions required')
 root=Path(sys.argv[1]);repo=Path(__file__).resolve().parents[1]
 c=root/'app/src/main/cpp/m10rRender.cpp';j=root/'app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java';g=root/'app/build.gradle'
 before=c.read_text();java=j.read_text();gradle=g.read_text();after=patch_cpp(before);java2=patch_java(java)
 versions=re.findall(r'versionName\s+[\'\"]([^\'\"]+)[\'\"]',gradle)
 if len(versions)!=1 or 'render1s-gamut1a-tonecal1a-'not in versions[0]:raise RuntimeError('Unexpected versionName')
 version=versions[0].replace('render1s-gamut1a-tonecal1a-','render1t-colorrecon1a-tonecal1a-')
 header=(repo/'native/m10rColorRecon1A.h').read_bytes()
 c.write_text(after);j.write_text(java2);g.write_text(gradle.replace(versions[0],version));(c.parent/'m10rColorRecon1A.h').write_bytes(header)
 proof={'schema':'RENDER1T_COLORRECON1A_PATCH_V1','baseline_cpp_sha256':digest(before),'candidate_cpp_sha256':digest(after),'header_sha256':hashlib.sha256(header).hexdigest(),'baseline_java_sha256':digest(java),'candidate_java_sha256':digest(java2),'versionName':version,'counts_abi':'first8_legacy_unchanged_gamut8to23_actual_output_color24to27_reserved28to31','capture_WB_CA9_tone_assets_exposure_demosaic_quality_unchanged':True,'deviceValidated':False,'productionPromoted':False}
 (root/'M10R_RENDER1T_COLORRECON1A_PROVENANCE.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof,indent=2))
if __name__=='__main__':main()
