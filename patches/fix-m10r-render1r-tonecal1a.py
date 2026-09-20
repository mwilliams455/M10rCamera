#!/usr/bin/env python3
"""Add only the empirical output-lightness pass to reconstructed RENDER1Q.
Not Leica Y BLEND arithmetic. Baseline and capture branches are not modified.
"""
from pathlib import Path
import sys,hashlib,json,re
BASE_CPP='27d42e3090435732bba6331380d2110227d3b713f59d3917b659d19cbea0f934'
ANCHOR='                    static_cast<uint32_t>(linear8(outB)));'
CALL='\n            argb[i] = static_cast<jint>(m10r_tonecal1a::apply(static_cast<uint32_t>(argb[i])));'
INCLUDE='#include "m10rToneCal1A.h"\n'
def patch_cpp(text):
 if hashlib.sha256(text.encode()).hexdigest()!=BASE_CPP:raise RuntimeError('Unexpected RENDER1Q native source; refusing approximate patch')
 if text.count(ANCHOR)!=1:raise RuntimeError('Unique original publication anchor required')
 result=INCLUDE+text.replace(ANCHOR,ANCHOR+CALL)
 assert result.replace(INCLUDE,'',1).replace(CALL,'',1)==text
 return result

def main():
 root=Path(sys.argv[1]);repo=Path(__file__).resolve().parents[1]
 c=root/'app/src/main/cpp/m10rRender.cpp';r=root/'app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java';g=root/'app/build.gradle'
 before=c.read_text();js=r.read_text();gradle=g.read_text()
 old='d.put("renderLook", "RENDER1Q_CC1MAP1A_YBLEND1B_K035_REDTRACE1B_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A");'
 if js.count(old)!=1:raise RuntimeError('Unexpected RENDER1Q Java diagnostic anchor')
 new='''d.put("renderLook", "RENDER1R_TONECAL1A_CC1MAP1A_YBLEND1B_K035_EDGE0A");
            d.put("toneCal1A", new JSONObject()
                    .put("enabled", true)
                    .put("model", "fixed_smooth_Lstar_residual_v1")
                    .put("stage", "after_unchanged_RENDER1Q_ARGB8_publication")
                    .put("trainingScenes", "PhotographyBlog_M10R_01_03_05_neutral_only")
                    .put("coefficients", new JSONArray(new double[]{-3.229545380578171,-0.25128474545011054,-0.17860038493017244}))
                    .put("empiricalNotFirmware", true)
                    .put("captureExposureChanged", false)
                    .put("whiteBalanceChanged", false)
                    .put("chromaGainChanged", false)
                    .put("upstreamDiagnosticsArePreCorrection", true));'''
 js=js.replace(old,new).replace('d.put("yBlend1BOnlyPhotographicVariable", true);','d.put("yBlend1BOnlyPhotographicVariable", false);').replace('d.put("cc1RestoreOnlyPhotographicVariable", true);','d.put("cc1RestoreOnlyPhotographicVariable", false);')
 # Do not change device policy, output quality, exposure, DNG, matrices, or any sampled B2Y arithmetic.
 versions=re.findall(r"versionName\s+['\"]([^'\"]+)['\"]",gradle)
 if len(versions)!=1 or 'render1q-' not in versions[0]:raise RuntimeError('Unexpected versionName')
 gradle=gradle.replace(versions[0],versions[0].replace('render1q-','render1r-tonecal1a-'))
 header=(repo/'native/m10rToneCal1A.h').read_bytes()
 (c.parent/'m10rToneCal1A.h').write_bytes(header);c.write_text(patch_cpp(before));r.write_text(js);g.write_text(gradle)
 proof={'schema':'RENDER1R_TONECAL1A_PATCH_V1','baseline_cpp_sha256':BASE_CPP,'candidate_cpp_sha256':hashlib.sha256(c.read_bytes()).hexdigest(),'header_sha256':hashlib.sha256(header).hexdigest(),'baseline_pixel_body_recovered_exact_by_removing_include_and_call':True,'versionName':versions[0].replace('render1q-','render1r-tonecal1a-'),'capture_exposure_wb_chroma_policy_changed':False,'empirical_not_firmware':True,'new_apk_is_candidate_not_production_promotion':True}
 (root/'M10R_RENDER1R_TONECAL1A_PROVENANCE.json').write_text(json.dumps(proof,indent=2)+'\n')
 print(json.dumps(proof,indent=2))
if __name__=='__main__':main()
