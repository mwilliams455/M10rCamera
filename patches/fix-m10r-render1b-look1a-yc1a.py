#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix-m10r-render1b-look1a-yc1a.py <PhotonCamera-root>')
root = Path(sys.argv[1]).resolve()
if not (root/'app').is_dir():
    raise SystemExit('LOOK1A YC1A: not a PhotonCamera root')

def rd(rel):
    p=root/rel
    if not p.exists(): raise SystemExit('LOOK1A YC1A missing: '+rel)
    return p.read_text()
def wr(rel,s): (root/rel).write_text(s)
def one(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit('LOOK1A YC1A anchor %s count=%d'%(label,n))
    return s.replace(a,b,1)

# LOOK1A is a photographic-domain experiment, not a speed change.
# Keep NATIVE1 topology, exact MEDIUM/DG assets, single-frame/no-HDR policy,
# exposure, source colour and JPEG quality frozen. Replace only the provisional
# Rec.709 luma-gain application with the firmware-proven Yc_Convert matrix:
#   [ 1224,  2404,  467]
#   [ -691, -1357, 2048] / 4096
#   [ 2048, -1715, -333]
# Tone/DG acts on Y; Cb/Cr pass unchanged; RGB is reconstructed by the exact
# mathematical inverse of that matrix. Y_BLEND and six-field local conditioning
# remain deliberately unapplied because their arithmetic semantics are not frozen.

grad='app/build.gradle'
g=rd(grad)
g=one(g,
      "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1'",
      "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1a-yc1a'",
      'version')
wr(grad,g)

renderer='app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'
r=rd(renderer)
r=one(r,
      'd.put("nonlinearApplicationMode", "luma_gain_preserve_linear_rgb_ratios");',
      'd.put("nonlinearApplicationMode", "M10R_Yc_Convert_map_Y_preserve_CbCr_exact_inverse");',
      'mode')
r=one(r,
      'd.put("nonlinearLumaProxy", "linear_sRGB_Rec709_0.2126_0.7152_0.0722_DIAGNOSTIC");',
      '''d.put("nonlinearLumaProxy", "M10R_Yc_Convert_Y_Q12_1224_2404_467");\n        d.put("lookExperiment", "LOOK1A_YC1A");\n        d.put("b2yYcConvertMatrixQ12", "1224,2404,467;-691,-1357,2048;2048,-1715,-333");\n        d.put("b2yYcConvertMatrixDivisor", 4096);\n        d.put("b2yChromaPolicy", "preserve_CbCr_through_MEDIUM_DG_then_exact_matrix_inverse");\n        d.put("b2yYBlendApplied", false);\n        d.put("b2yLocalSixFieldConditioningApplied", false);\n        d.put("toneCoordinateScalingStillProvisional", true);\n        d.put("lumaGainStatisticSemantic", "mappedY_over_inputY_diagnostic_only_not_RGB_pixel_gain");''',
      'metadata')

old='''                    toneDgStats.preTone.add(lr, lg, lb);\n                    double linearY = 0.2126*lr + 0.7152*lg + 0.0722*lb;\n                    int xy = M10RToneDg1A.toInputLumaNoStats(linearY);\n                    toneDgStats.toneInput.add(xy, xy, xy);\n                    int my = M10RToneDg1A.medium(xy);\n                    toneDgStats.postTone.add(my, my, my);\n                    int dy = M10RToneDg1A.dgLumaNoStats(my);\n                    toneDgStats.postDg.add(dy, dy, dy);\n                    double mappedY = dy / (double)M10RToneDg1A.DG_OUT_MAX;\n                    double gain = (linearY > 1.0e-12) ? (mappedY / linearY) : 0.0;\n                    toneDgStats.lumaGain.add(gain);\n                    toneDgStats.preSrgb.add(lr*gain, lg*gain, lb*gain);\n'''
new='''                    toneDgStats.preTone.add(lr, lg, lb);\n                    double ycY = (1224.0*lr + 2404.0*lg + 467.0*lb) / 4096.0;\n                    double ycCb = (-691.0*lr - 1357.0*lg + 2048.0*lb) / 4096.0;\n                    double ycCr = (2048.0*lr - 1715.0*lg - 333.0*lb) / 4096.0;\n                    int xy = M10RToneDg1A.toInputLumaNoStats(ycY);\n                    toneDgStats.toneInput.add(xy, xy, xy);\n                    int my = M10RToneDg1A.medium(xy);\n                    toneDgStats.postTone.add(my, my, my);\n                    int dy = M10RToneDg1A.dgLumaNoStats(my);\n                    toneDgStats.postDg.add(dy, dy, dy);\n                    double mappedY = dy / (double)M10RToneDg1A.DG_OUT_MAX;\n                    double yRatio = (ycY > 1.0e-12) ? (mappedY / ycY) : 0.0;\n                    toneDgStats.lumaGain.add(yRatio);\n                    double nr = 1.000244200244*mappedY - 0.000094115078*ycCb + 1.402166047550*ycCr;\n                    double ng = 1.000244200244*mappedY - 0.344165467666*ycCb - 0.713924433230*ycCr;\n                    double nb = 1.000244200244*mappedY + 1.771925013114*ycCb + 0.000049454572*ycCr;\n                    toneDgStats.preSrgb.add(nr, ng, nb);\n'''
r=one(r,old,new,'sampled-diagnostics-domain')
wr(renderer,r)

cpp='app/src/main/cpp/m10rRender.cpp'
c=rd(cpp)
old_cpp='''            const double lr = outMat[0]*tr + outMat[1]*tg + outMat[2]*tb;\n            const double lg = outMat[3]*tr + outMat[4]*tg + outMat[5]*tb;\n            const double lb = outMat[6]*tr + outMat[7]*tg + outMat[8]*tb;\n            const double y = 0.2126*lr + 0.7152*lg + 0.0722*lb;\n            const int xy = toneInput(y, cnt);\n            const int my = medium(xy, tone);\n            const int dy = dg(my, dgt, cnt);\n            const double mappedY = dy / static_cast<double>(DG_OUT_MAX);\n            const double gain = y > 1.0e-12 ? mappedY / y : 0.0;\n            const double nr = lr * gain;\n            const double ng = lg * gain;\n            const double nb = lb * gain;\n'''
new_cpp='''            const double lr = outMat[0]*tr + outMat[1]*tg + outMat[2]*tb;\n            const double lg = outMat[3]*tr + outMat[4]*tg + outMat[5]*tb;\n            const double lb = outMat[6]*tr + outMat[7]*tg + outMat[8]*tb;\n\n            // LOOK1A YC1A: exact firmware Yc_Convert 3x3 coefficients, Q12.\n            const double y  = (1224.0*lr + 2404.0*lg + 467.0*lb) / 4096.0;\n            const double cb = (-691.0*lr - 1357.0*lg + 2048.0*lb) / 4096.0;\n            const double cr = (2048.0*lr - 1715.0*lg - 333.0*lb) / 4096.0;\n            const int xy = toneInput(y, cnt);\n            const int my = medium(xy, tone);\n            const int dy = dg(my, dgt, cnt);\n            const double mappedY = dy / static_cast<double>(DG_OUT_MAX);\n\n            // Exact mathematical inverse of the Q12 matrix. Chroma is not\n            // multiplied by the tone gain: MEDIUM/DG changes Y only.\n            const double nr = 1.000244200244*mappedY - 0.000094115078*cb + 1.402166047550*cr;\n            const double ng = 1.000244200244*mappedY - 0.344165467666*cb - 0.713924433230*cr;\n            const double nb = 1.000244200244*mappedY + 1.771925013114*cb + 0.000049454572*cr;\n'''
c=one(c,old_cpp,new_cpp,'native-domain')
wr(cpp,c)

R=rd(renderer); C=rd(cpp)
for m in [
    'LOOK1A_YC1A',
    'M10R_Yc_Convert_map_Y_preserve_CbCr_exact_inverse',
    'M10R_Yc_Convert_Y_Q12_1224_2404_467',
    'b2yYBlendApplied", false',
    'b2yLocalSixFieldConditioningApplied", false',
    'toneCoordinateScalingStillProvisional", true',
    'hdrEnabled", false',
    'sourceFrameCount", 1',
    'STABILITY3_NATIVE1_FOUR_THREAD_PIXEL_CORE',
]:
    if m not in R: raise SystemExit('LOOK1A YC1A renderer invariant missing: '+m)
for m in [
    '(1224.0*lr + 2404.0*lg + 467.0*lb) / 4096.0',
    '(-691.0*lr - 1357.0*lg + 2048.0*lb) / 4096.0',
    '(2048.0*lr - 1715.0*lg - 333.0*lb) / 4096.0',
    '1.402166047550*cr',
    '1.771925013114*cb',
]:
    if m not in C: raise SystemExit('LOOK1A YC1A native invariant missing: '+m)
if 'const double y = 0.2126*lr + 0.7152*lg + 0.0722*lb;' in C:
    raise SystemExit('LOOK1A YC1A old Rec709 pixel luma still active')
if 'const double nr = lr * gain;' in C:
    raise SystemExit('LOOK1A YC1A old RGB gain preservation still active')
print('M10-R RENDER1B LOOK1A YC1A applied')
print(' - exact firmware Yc_Convert Q12 matrix now supplies tone Y')
print(' - Cb/Cr preserved through MEDIUM->DG and exact inverse reconstruction')
print(' - no guessed Y_BLEND or six-field conditioning')
print(' - tone coordinate scaling remains explicitly provisional')
print(' - NATIVE1 speed topology, source colour, exposure, JPEG quality and no-HDR frozen')
