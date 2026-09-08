#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix-m10r-render1b-look1b-yc1b.py <PhotonCamera-root>')
root = Path(sys.argv[1]).resolve()
if not (root/'app').is_dir():
    raise SystemExit('LOOK1B YC1B: not a PhotonCamera root')

def rd(rel):
    p=root/rel
    if not p.exists(): raise SystemExit('LOOK1B YC1B missing: '+rel)
    return p.read_text()
def wr(rel,s): (root/rel).write_text(s)
def one(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit('LOOK1B YC1B anchor %s count=%d'%(label,n))
    return s.replace(a,b,1)

# LOOK1B corrects the clearly desaturated LOOK1A experiment without returning
# to generic Rec.709. Keep exact M10-R Yc_Convert for the tone coordinate and
# preserve Cb/Y and Cr/Y ratios while MEDIUM->DG changes Y. This is a bounded
# bridge until Y_BLEND/local YC conditioning arithmetic is proven.

grad='app/build.gradle'
g=rd(grad)
g=one(g,
      "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1a-yc1a'",
      "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b'",
      'version')
wr(grad,g)

renderer='app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'
r=rd(renderer)
r=one(r,
      'd.put("nonlinearApplicationMode", "M10R_Yc_Convert_map_Y_preserve_CbCr_exact_inverse");',
      'd.put("nonlinearApplicationMode", "M10R_Yc_Convert_map_Y_preserve_relative_chroma_exact_inverse");',
      'mode')
r=one(r,
      'd.put("lookExperiment", "LOOK1A_YC1A");',
      'd.put("lookExperiment", "LOOK1B_YC1B");',
      'look-id')
r=one(r,
      'd.put("b2yChromaPolicy", "preserve_CbCr_through_MEDIUM_DG_then_exact_matrix_inverse");',
      'd.put("b2yChromaPolicy", "preserve_Cb_over_Y_and_Cr_over_Y_through_MEDIUM_DG_then_exact_matrix_inverse");',
      'chroma-policy')
r=one(r,
      'd.put("lumaGainStatisticSemantic", "mappedY_over_inputY_diagnostic_only_not_RGB_pixel_gain");',
      'd.put("lumaGainStatisticSemantic", "mappedY_over_inputY_also_used_as_relative_chroma_scale");',
      'gain-semantic')

old='''                    double mappedY = dy / (double)M10RToneDg1A.DG_OUT_MAX;\n                    double yRatio = (ycY > 1.0e-12) ? (mappedY / ycY) : 0.0;\n                    toneDgStats.lumaGain.add(yRatio);\n                    double nr = 1.000244200244*mappedY - 0.000094115078*ycCb + 1.402166047550*ycCr;\n                    double ng = 1.000244200244*mappedY - 0.344165467666*ycCb - 0.713924433230*ycCr;\n                    double nb = 1.000244200244*mappedY + 1.771925013114*ycCb + 0.000049454572*ycCr;\n                    toneDgStats.preSrgb.add(nr, ng, nb);\n'''
new='''                    double mappedY = dy / (double)M10RToneDg1A.DG_OUT_MAX;\n                    double yRatio = (ycY > 1.0e-12) ? (mappedY / ycY) : 0.0;\n                    toneDgStats.lumaGain.add(yRatio);\n                    double mappedCb = ycCb * yRatio;\n                    double mappedCr = ycCr * yRatio;\n                    double nr = 1.000244200244*mappedY - 0.000094115078*mappedCb + 1.402166047550*mappedCr;\n                    double ng = 1.000244200244*mappedY - 0.344165467666*mappedCb - 0.713924433230*mappedCr;\n                    double nb = 1.000244200244*mappedY + 1.771925013114*mappedCb + 0.000049454572*mappedCr;\n                    toneDgStats.preSrgb.add(nr, ng, nb);\n'''
r=one(r,old,new,'sampled-relative-chroma')
wr(renderer,r)

cpp='app/src/main/cpp/m10rRender.cpp'
c=rd(cpp)
old_cpp='''            const double mappedY = dy / static_cast<double>(DG_OUT_MAX);\n\n            // Exact mathematical inverse of the Q12 matrix. Chroma is not\n            // multiplied by the tone gain: MEDIUM/DG changes Y only.\n            const double nr = 1.000244200244*mappedY - 0.000094115078*cb + 1.402166047550*cr;\n            const double ng = 1.000244200244*mappedY - 0.344165467666*cb - 0.713924433230*cr;\n            const double nb = 1.000244200244*mappedY + 1.771925013114*cb + 0.000049454572*cr;\n'''
new_cpp='''            const double mappedY = dy / static_cast<double>(DG_OUT_MAX);\n\n            // LOOK1B YC1B: until Y_BLEND is decoded, preserve chroma relative\n            // to Y rather than freezing absolute Cb/Cr. LOOK1A demonstrated\n            // that absolute preservation strongly desaturates when tone raises Y.\n            const double yRatio = y > 1.0e-12 ? mappedY / y : 0.0;\n            const double mappedCb = cb * yRatio;\n            const double mappedCr = cr * yRatio;\n            const double nr = 1.000244200244*mappedY - 0.000094115078*mappedCb + 1.402166047550*mappedCr;\n            const double ng = 1.000244200244*mappedY - 0.344165467666*mappedCb - 0.713924433230*mappedCr;\n            const double nb = 1.000244200244*mappedY + 1.771925013114*mappedCb + 0.000049454572*mappedCr;\n'''
c=one(c,old_cpp,new_cpp,'native-relative-chroma')
wr(cpp,c)

R=rd(renderer); C=rd(cpp)
for m in [
    'LOOK1B_YC1B',
    'M10R_Yc_Convert_map_Y_preserve_relative_chroma_exact_inverse',
    'preserve_Cb_over_Y_and_Cr_over_Y_through_MEDIUM_DG_then_exact_matrix_inverse',
    'mappedY_over_inputY_also_used_as_relative_chroma_scale',
    'b2yYBlendApplied", false',
    'b2yLocalSixFieldConditioningApplied", false',
    'toneCoordinateScalingStillProvisional", true',
    'hdrEnabled", false',
    'sourceFrameCount", 1',
    'STABILITY3_NATIVE1_FOUR_THREAD_PIXEL_CORE',
]:
    if m not in R: raise SystemExit('LOOK1B YC1B renderer invariant missing: '+m)
for m in [
    'const double yRatio = y > 1.0e-12 ? mappedY / y : 0.0;',
    'const double mappedCb = cb * yRatio;',
    'const double mappedCr = cr * yRatio;',
    '1.402166047550*mappedCr',
    '1.771925013114*mappedCb',
]:
    if m not in C: raise SystemExit('LOOK1B YC1B native invariant missing: '+m)
if '1.402166047550*cr;' in C:
    raise SystemExit('LOOK1B YC1B absolute chroma path still active')
print('M10-R RENDER1B LOOK1B YC1B applied')
print(' - exact firmware Yc_Convert still supplies tone Y')
print(' - relative Cb/Y and Cr/Y preserved through MEDIUM->DG')
print(' - no arbitrary saturation multiplier')
print(' - Y_BLEND/local conditioning still explicitly unresolved')
print(' - NATIVE1 speed, exposure, source colour, JPEG quality and HDR-off unchanged')
