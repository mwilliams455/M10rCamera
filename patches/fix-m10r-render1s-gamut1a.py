#!/usr/bin/env python3
"""Apply GAMUT1A to exact reconstructed RENDER1R, not capture/production branches."""
from pathlib import Path
import hashlib,json,re,sys
BASE='483a547259615c928a9dce82f88770995cec81f2900177db8439231f32d3baec'
def digest(s):return hashlib.sha256(s.encode()).hexdigest()
def once(s,a,b):
 if s.count(a)!=1:raise RuntimeError('Unique anchor required: '+a[:110]+'; found '+str(s.count(a)))
 return s.replace(a,b,1)
MAP='''            double gamutR=outR, gamutG=outG, gamutB=outB;
            const int gamutStatus=m10r_outputgamut1a::apply(gamutR,gamutG,gamutB);
            cnt.v[8]++;
            cnt.v[9+gamutStatus]++;
            cnt.v[12]+=(outR<0.0); cnt.v[13]+=(outG<0.0); cnt.v[14]+=(outB<0.0);
            cnt.v[15]+=(outR>1.0); cnt.v[16]+=(outG>1.0); cnt.v[17]+=(outB>1.0);
            cnt.v[18]+=(gamutR<0.0); cnt.v[19]+=(gamutG<0.0); cnt.v[20]+=(gamutB<0.0);
            cnt.v[21]+=(gamutR>1.0); cnt.v[22]+=(gamutG>1.0); cnt.v[23]+=(gamutB>1.0);
'''
def patch_cpp(text):
 if digest(text)!=BASE:raise RuntimeError('Refusing unknown RENDER1R native source')
 edits=[('#include "m10rToneCal1A.h"','#include "m10rOutputGamut1A.h"\n#include "m10rToneCal1A.h"'),
 ('int64_t v[8] = {0,0,0,0,0,0,0,0};','int64_t v[24] = {};'),
 ('jlong existing[8];','jlong existing[24] = {};\n    const int returnedCounts=std::min(24,static_cast<int>(env->GetArrayLength(jcounts)));'),
 ('env->GetLongArrayRegion(jcounts, 0, 8, existing);','env->GetLongArrayRegion(jcounts, 0, returnedCounts, existing);'),
 ('            argb[i] = static_cast<jint>(0xff000000u |',MAP+'            argb[i] = static_cast<jint>(0xff000000u |'),
 ('linear8(outR)','linear8(gamutR)'),('linear8(outG)','linear8(gamutG)'),('linear8(outB)','linear8(gamutB)'),
 ('for (int k=0;k<8;k++) existing[k]','for (int k=0;k<returnedCounts;k++) existing[k]'),
 ('env->SetLongArrayRegion(jcounts, 0, 8, existing);','env->SetLongArrayRegion(jcounts, 0, returnedCounts, existing);')]
 out=text
 for old,new in edits:out=once(out,old,new)
 restored=out
 for old,new in reversed(edits):restored=once(restored,new,old)
 assert restored==text
 return out

def patch_java(s):
 s=once(s,'final long[] nativeExactCounts = new long[8];','final long[] nativeExactCounts = new long[24];\n            final JSONArray gamutRowBands = new JSONArray();')
 call='''                nativeProcessTile(
                        bgr, pixels, inverseStorageScale,
                        srcToTargetCamera, ca9, targetToWorking, workingToSrgb,
                        nativeToneTable, nativeDgTable, argb, nativeExactCounts);'''
 s=once(s,call,'''                final long[] gamutBefore = nativeExactCounts.clone();
'''+call+'''
                gamutRowBands.put(new JSONObject()
                        .put("sensorY0", y0).put("sourceRows", rows)
                        .put("mappedPixels", nativeExactCounts[10]-gamutBefore[10])
                        .put("preHighRGB", json(new long[]{nativeExactCounts[15]-gamutBefore[15], nativeExactCounts[16]-gamutBefore[16], nativeExactCounts[17]-gamutBefore[17]}))
                        .put("preLowRGB", json(new long[]{nativeExactCounts[12]-gamutBefore[12], nativeExactCounts[13]-gamutBefore[13], nativeExactCounts[14]-gamutBefore[14]})));''')
 s=once(s,'redTrace.put("cc1Matrix", "1.3895,-0.1693,-0.2202;-0.2288,1.2317,-0.0029;-0.0176,-0.0963,1.1139");','redTrace.put("cc1Matrix", java.util.Arrays.toString(workingToSrgb));\n            redTrace.put("cc1MatrixRowMajor", json(workingToSrgb));\n            redTrace.put("stage", "actual_post_CC1_before_GAMUT1A_and_TONECAL1A");')
 s=once(s,'redTrace.put("cc1RedEquation", "outR=1.3895*postYcR-0.1693*postYcG-0.2202*postYcB");','redTrace.put("cc1RedEquation", "outR=("+workingToSrgb[0]+")*postYcR+("+workingToSrgb[1]+")*postYcG+("+workingToSrgb[2]+")*postYcB");')
 s=once(s,'redTrace1B.put("photographicOutputStillCc1Bypassed", true);','redTrace1B.put("photographicOutputStillCc1Bypassed", false);')
 s=once(s,'redTrace1B.put("counterfactualCc1StillEvaluated", true);','redTrace1B.put("counterfactualCc1StillEvaluated", false);\n            redTrace1B.put("actualPreGamutCc1Evaluated", true);')
 for ch in 'RGB':
  old='"meanCounterfactualPostCc1'+ch+'"';s=once(s,old,'"meanActualPreGamutPostCc1'+ch+'"')
 old='d.put("renderLook", "RENDER1R_TONECAL1A_CC1MAP1A_YBLEND1B_K035_EDGE0A");'
 new='''d.put("renderLook", "RENDER1S_GAMUT1A_TONECAL1A_CC1MAP1A_YBLEND1B_K035_EDGE0A");
            d.put("outputGamut1A", new JSONObject()
                    .put("enabled", true).put("empiricalNotFirmware", true)
                    .put("stage", "post_CC1_before_first_ARGB8_then_unchanged_TONECAL1A")
                    .put("method", "clipped_baseline_code_luma_anchor_unclipped_RGB_opponent_ray")
                    .put("coordinate", "existing_direct_post_CC1_not_asserted_linear_light")
                    .put("perceptualHueOrLstarPreservationClaimed", false)
                    .put("inGamutPixelPolicy", "exact_bypass")
                    .put("captureExposureChanged", false).put("whiteBalanceChanged", false)
                    .put("toneCurveChanged", false).put("chromaKChanged", false)
                    .put("sampleStride", 1).put("nativeExactPixelCounts", true)
                    .put("totalPixels", nativeExactCounts[8])
                    .put("inGamutBypassPixels", nativeExactCounts[9])
                    .put("mappedPixels", nativeExactCounts[10])
                    .put("nonFiniteFallbackPixels", nativeExactCounts[11])
                    .put("preMapBelowZeroRGB", json(new long[]{nativeExactCounts[12],nativeExactCounts[13],nativeExactCounts[14]}))
                    .put("preMapAboveOneRGB", json(new long[]{nativeExactCounts[15],nativeExactCounts[16],nativeExactCounts[17]}))
                    .put("postMapBelowZeroRGB", json(new long[]{nativeExactCounts[18],nativeExactCounts[19],nativeExactCounts[20]}))
                    .put("postMapAboveOneRGB", json(new long[]{nativeExactCounts[21],nativeExactCounts[22],nativeExactCounts[23]}))
                    .put("countPartitionValid", nativeExactCounts[8]==nativeExactCounts[9]+nativeExactCounts[10]+nativeExactCounts[11])
                    .put("framePixelCountValid", nativeExactCounts[8]==(long)frame.width*frame.height)
                    .put("rowBandsCoordinate", "source_sensor_before_cameraRotationDegrees")
                    .put("rowBands", gamutRowBands));'''
 s=once(s,old,new)
 s=once(s,'.put("stage", "after_unchanged_RENDER1Q_ARGB8_publication")','.put("stage", "after_GAMUT1A_ARGB8_publication_same_TONECAL1A_curve")')
 s=once(s,'d.put("cc1RedTraceMatchesPhotographicOutput", true);','d.put("cc1RedTraceMatchesPhotographicOutput", false);\n            d.put("cc1RedTraceMatchesActualPreGamutOutput", true);')
 s=once(s,'d.put("preSrgbStatisticsRole", "actual_post_CC1_photographic_output");','d.put("preSrgbStatisticsRole", "actual_post_CC1_before_GAMUT1A_ARGB8_and_TONECAL1A_not_final_JPEG");')
 s=once(s,'d.put("edge0aOnlyPhotographicVariable", true);','d.put("edge0aOnlyPhotographicVariable", false);')
 s=once(s,'d.put("nativePixelOutputQuantizer", "linear8_post_CC1");','d.put("nativePixelOutputQuantizer", "GAMUT1A_then_linear8_then_unchanged_TONECAL1A");')
 return s

def main():
 if not __debug__:raise RuntimeError('Assertions required')
 root=Path(sys.argv[1]);repo=Path(__file__).resolve().parents[1]
 c=root/'app/src/main/cpp/m10rRender.cpp';j=root/'app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java';g=root/'app/build.gradle'
 before=c.read_text();java=j.read_text();gradle=g.read_text();after=patch_cpp(before);java2=patch_java(java)
 versions=re.findall(r'versionName\s+[\'\"]([^\'\"]+)[\'\"]',gradle)
 if len(versions)!=1 or 'render1r-tonecal1a-' not in versions[0]:raise RuntimeError('Unexpected versionName')
 version=versions[0].replace('render1r-tonecal1a-','render1s-gamut1a-tonecal1a-')
 header=(repo/'native/m10rOutputGamut1A.h').read_bytes()
 c.write_text(after);j.write_text(java2);g.write_text(gradle.replace(versions[0],version));(c.parent/'m10rOutputGamut1A.h').write_bytes(header)
 proof={'schema':'RENDER1S_GAMUT1A_PATCH_V1','baseline_cpp_sha256':digest(before),'candidate_cpp_sha256':digest(after),'header_sha256':hashlib.sha256(header).hexdigest(),'baseline_java_sha256':digest(java),'candidate_java_sha256':digest(java2),'baseline_native_recovered_exact_by_reversing_bounded_edits':True,'versionName':version,'counts_abi':'original_first8_unchanged_optional_24_total','capture_WB_CA9_tone_tables_chroma_k_exposure_demosaic_quality_unchanged':True,'deviceValidated':False,'private_photo_uploaded_to_repository':False}
 (root/'M10R_RENDER1S_GAMUT1A_PROVENANCE.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof,indent=2))
if __name__=='__main__':main()
