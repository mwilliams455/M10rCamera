#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix-m10r-render1g-working1a.py <PhotonCamera-root>')
root = Path(sys.argv[1]).resolve()
if not (root/'app').is_dir():
    raise SystemExit('RENDER1G WORKING1A: not a PhotonCamera root')

def rd(rel):
    p=root/rel
    if not p.exists(): raise SystemExit('RENDER1G WORKING1A missing: '+rel)
    return p.read_text()
def wr(rel,s): (root/rel).write_text(s)
def one(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit('RENDER1G WORKING1A anchor %s count=%d'%(label,n))
    return s.replace(a,b,1)

# WORKING1A is one bounded structural A/B authorized by the v270A/T1 device gate.
# Frozen firmware architecture places the nonlinear B2Y/tone path in Leica's
# internal working RGB between CC0 and CC1. RENDER1F instead collapsed the
# fixed internal-basis conversion and DEFAULT_SRGB_CC1 into targetToSrgb before
# MEDIUM/DG. Because MEDIUM/DG is nonlinear, those orders are not equivalent.
#
# Change ONLY this placement:
#   target camera --CA9--> internal working RGB --Yc/MEDIUM/DG--> working RGB
#                 --DEFAULT_SRGB_CC1--> linear sRGB --OETF--> JPEG
# All matrices, Yc coefficients, MEDIUM/DG assets/arithmetic, edge stage,
# source model, CA9, exposure, JPEG quality, 12 MP, and single-RAW/HDR-off
# behavior are frozen.

grad='app/build.gradle'; g=rd(grad)
g=one(g,
      "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1f-yc2a-matrix1a-diag1c-saf1'",
      "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1g-working1a-diag1c-saf1'",
      'version')
wr(grad,g)

renderer='app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'; r=rd(renderer)

old_decl='''    private static native void nativeProcessTile(\n            short[] rgb16, int pixels, double inverseStorageScale,\n            double[] srcToTargetCamera, int[] ca9, double[] targetToSrgb,\n            int[] toneTable, int[] dgTable, int[] argbOut, long[] exactCounts);\n'''
new_decl='''    private static native void nativeProcessTile(\n            short[] rgb16, int pixels, double inverseStorageScale,\n            double[] srcToTargetCamera, int[] ca9, double[] targetToWorking,\n            double[] workingToSrgb, int[] toneTable, int[] dgTable,\n            int[] argbOut, long[] exactCounts);\n'''
r=one(r,old_decl,new_decl,'jni-declaration')

old_matrix='''        double[] targetToSrgb = matMul(DEFAULT_SRGB_CC1,\n                matMul(PCS_TO_INTERNAL, matMul(sceneToD50, inverse3(targetProfile))));\n'''
new_matrix='''        // WORKING1A: keep Leica's fixed internal basis on the input side of\n        // nonlinear B2Y processing; apply output CC1 only after MEDIUM/DG.\n        double[] targetToWorking = matMul(PCS_TO_INTERNAL,\n                matMul(sceneToD50, inverse3(targetProfile)));\n        double[] workingToSrgb = DEFAULT_SRGB_CC1.clone();\n'''
r=one(r,old_matrix,new_matrix,'matrix-split')

# Make the diagnostic identity explicit. This replaces the old placement string
# rather than adding a second contradictory field.
r=one(r,
      '        d.put("nonlinearPlacement", "after_M10R_target_to_linear_sRGB_before_sRGB_OETF");\n',
      '''        d.put("nonlinearPlacement", "M10R_internal_working_RGB_between_CC0_CC1");\n        d.put("workingBasisPlacementFix", "WORKING1A");\n        d.put("cc0WorkingBasisPlacement", "pre_MEDIUM_DG");\n        d.put("cc1Placement", "post_MEDIUM_DG_before_sRGB_OETF");\n        d.put("workingBasisFirmwareEvidence", "v232_CC0_internal_tone_CC1_output");\n        d.put("workingBasisPlacementExactHardwareParityClaimed", false);\n''',
      'placement-metadata')

# Update the render identity without changing any later edge metadata.
r=one(r,
      '            d.put("renderLook", "RENDER1F_YC2A_MATRIX1A");\n',
      '            d.put("renderLook", "RENDER1G_WORKING1A_YC2A_MATRIX1A");\n',
      'render-look')

old_call='''                nativeProcessTile(\n                        bgr, pixels, inverseStorageScale,\n                        srcToTargetCamera, ca9, targetToSrgb,\n                        nativeToneTable, nativeDgTable, argb, nativeExactCounts);\n'''
new_call='''                nativeProcessTile(\n                        bgr, pixels, inverseStorageScale,\n                        srcToTargetCamera, ca9, targetToWorking, workingToSrgb,\n                        nativeToneTable, nativeDgTable, argb, nativeExactCounts);\n'''
r=one(r,old_call,new_call,'jni-call')

# Sampled diagnostics must observe the same domains as the native pixel path.
old_sample_rgb='''                    double lr = targetToSrgb[0]*tr + targetToSrgb[1]*tg + targetToSrgb[2]*tb;\n                    double lg = targetToSrgb[3]*tr + targetToSrgb[4]*tg + targetToSrgb[5]*tb;\n                    double lb = targetToSrgb[6]*tr + targetToSrgb[7]*tg + targetToSrgb[8]*tb;\n                    toneDgStats.preTone.add(lr, lg, lb);\n'''
new_sample_rgb='''                    double wr = targetToWorking[0]*tr + targetToWorking[1]*tg + targetToWorking[2]*tb;\n                    double wg = targetToWorking[3]*tr + targetToWorking[4]*tg + targetToWorking[5]*tb;\n                    double wb = targetToWorking[6]*tr + targetToWorking[7]*tg + targetToWorking[8]*tb;\n                    toneDgStats.preTone.add(wr, wg, wb);\n'''
r=one(r,old_sample_rgb,new_sample_rgb,'sample-working-rgb')

for old,new,label in [
    ('double ycY = (1224.0*lr + 2403.0*lg + 469.0*lb) / 4096.0;',
     'double ycY = (1224.0*wr + 2403.0*wg + 469.0*wb) / 4096.0;', 'sample-y'),
    ('double ycCb = (-691.0*lr - 1357.0*lg + 2048.0*lb) / 4096.0;',
     'double ycCb = (-691.0*wr - 1357.0*wg + 2048.0*wb) / 4096.0;', 'sample-cb'),
    ('double ycCr = (2048.0*lr - 1715.0*lg - 333.0*lb) / 4096.0;',
     'double ycCr = (2048.0*wr - 1715.0*wg - 333.0*wb) / 4096.0;', 'sample-cr')]:
    r=one(r,old,new,label)

old_presrgb='''                    double nr = 1.000000000000*mappedY - 0.001043337611*mappedCb + 1.401991725445*mappedCr;\n                    double ng = 1.000000000000*mappedY - 0.345114690199*mappedCb - 0.714098755336*mappedCr;\n                    double nb = 1.000000000000*mappedY + 1.770975790582*mappedCb - 0.000124867533*mappedCr;\n                    toneDgStats.preSrgb.add(nr, ng, nb);\n'''
new_presrgb='''                    double nr = 1.000000000000*mappedY - 0.001043337611*mappedCb + 1.401991725445*mappedCr;\n                    double ng = 1.000000000000*mappedY - 0.345114690199*mappedCb - 0.714098755336*mappedCr;\n                    double nb = 1.000000000000*mappedY + 1.770975790582*mappedCb - 0.000124867533*mappedCr;\n                    double outR = workingToSrgb[0]*nr + workingToSrgb[1]*ng + workingToSrgb[2]*nb;\n                    double outG = workingToSrgb[3]*nr + workingToSrgb[4]*ng + workingToSrgb[5]*nb;\n                    double outB = workingToSrgb[6]*nr + workingToSrgb[7]*ng + workingToSrgb[8]*nb;\n                    toneDgStats.preSrgb.add(outR, outG, outB);\n'''
r=one(r,old_presrgb,new_presrgb,'sample-post-cc1')
wr(renderer,r)

cpp='app/src/main/cpp/m10rRender.cpp'; c=rd(cpp)

old_sig='''        jshortArray jrgb, jint pixels, jdouble inverseStorageScale,\n        jdoubleArray jsrc, jintArray jca9, jdoubleArray joutMat,\n        jintArray jtone, jintArray jdg, jintArray jargb, jlongArray jcounts) {\n    if (!jrgb || !jsrc || !jca9 || !joutMat || !jtone || !jdg || !jargb || !jcounts || pixels <= 0) return;\n    if (env->GetArrayLength(jsrc) < 9 || env->GetArrayLength(joutMat) < 9 ||\n        env->GetArrayLength(jca9) < 3 || env->GetArrayLength(jtone) < TONE_ENTRIES ||\n'''
new_sig='''        jshortArray jrgb, jint pixels, jdouble inverseStorageScale,\n        jdoubleArray jsrc, jintArray jca9, jdoubleArray jworkingMat,\n        jdoubleArray joutMat, jintArray jtone, jintArray jdg,\n        jintArray jargb, jlongArray jcounts) {\n    if (!jrgb || !jsrc || !jca9 || !jworkingMat || !joutMat || !jtone || !jdg || !jargb || !jcounts || pixels <= 0) return;\n    if (env->GetArrayLength(jsrc) < 9 || env->GetArrayLength(jworkingMat) < 9 || env->GetArrayLength(joutMat) < 9 ||\n        env->GetArrayLength(jca9) < 3 || env->GetArrayLength(jtone) < TONE_ENTRIES ||\n'''
c=one(c,old_sig,new_sig,'native-signature')

old_copy='''    jdouble src[9], outMat[9];\n    jint ca9[3];\n    jlong existing[8];\n    env->GetDoubleArrayRegion(jsrc, 0, 9, src);\n    env->GetDoubleArrayRegion(joutMat, 0, 9, outMat);\n'''
new_copy='''    jdouble src[9], workingMat[9], outMat[9];\n    jint ca9[3];\n    jlong existing[8];\n    env->GetDoubleArrayRegion(jsrc, 0, 9, src);\n    env->GetDoubleArrayRegion(jworkingMat, 0, 9, workingMat);\n    env->GetDoubleArrayRegion(joutMat, 0, 9, outMat);\n'''
c=one(c,old_copy,new_copy,'native-matrix-copy')

old_work='''            const double lr = outMat[0]*tr + outMat[1]*tg + outMat[2]*tb;\n            const double lg = outMat[3]*tr + outMat[4]*tg + outMat[5]*tb;\n            const double lb = outMat[6]*tr + outMat[7]*tg + outMat[8]*tb;\n'''
new_work='''            // WORKING1A: nonlinear B2Y input is Leica internal working RGB.\n            const double lr = workingMat[0]*tr + workingMat[1]*tg + workingMat[2]*tb;\n            const double lg = workingMat[3]*tr + workingMat[4]*tg + workingMat[5]*tb;\n            const double lb = workingMat[6]*tr + workingMat[7]*tg + workingMat[8]*tb;\n'''
c=one(c,old_work,new_work,'native-working-input')

old_oetf='''            argb[i] = static_cast<jint>(0xff000000u |\n                    (static_cast<uint32_t>(srgb8(nr)) << 16) |\n                    (static_cast<uint32_t>(srgb8(ng)) << 8) |\n                    static_cast<uint32_t>(srgb8(nb)));\n'''
new_oetf='''            // WORKING1A: CC1 is the output transform and therefore follows\n            // the nonlinear working-domain reconstruction.\n            const double outR = outMat[0]*nr + outMat[1]*ng + outMat[2]*nb;\n            const double outG = outMat[3]*nr + outMat[4]*ng + outMat[5]*nb;\n            const double outB = outMat[6]*nr + outMat[7]*ng + outMat[8]*nb;\n            argb[i] = static_cast<jint>(0xff000000u |\n                    (static_cast<uint32_t>(srgb8(outR)) << 16) |\n                    (static_cast<uint32_t>(srgb8(outG)) << 8) |\n                    static_cast<uint32_t>(srgb8(outB)));\n'''
c=one(c,old_oetf,new_oetf,'native-post-cc1')
wr(cpp,c)

R=rd(renderer); C=rd(cpp); G=rd(grad)
required_r=[
    'RENDER1G_WORKING1A_YC2A_MATRIX1A',
    'M10R_internal_working_RGB_between_CC0_CC1',
    'workingBasisPlacementFix", "WORKING1A"',
    'cc1Placement", "post_MEDIUM_DG_before_sRGB_OETF"',
    'double[] targetToWorking = matMul(PCS_TO_INTERNAL,',
    'double[] workingToSrgb = DEFAULT_SRGB_CC1.clone();',
    'srcToTargetCamera, ca9, targetToWorking, workingToSrgb,',
    'toneDgStats.preTone.add(wr, wg, wb);',
    'toneDgStats.preSrgb.add(outR, outG, outB);',
    'yc2aMatrixCorrectionApplied", true',
    'edgeScaleTableApplied", true',
    'edgeHfRecordGainApplied", true',
    'b2yYBlendApplied", false',
    'textureEnhancementBlockEnabled", false',
    'lowFrequencyEdgeApplied", false',
    'hdrEnabled", false',
    'sourceFrameCount", 1',
    'DIAG1C_SAF_ABSPATH'
]
for x in required_r:
    if x not in R: raise SystemExit('RENDER1G WORKING1A renderer invariant missing: '+x)
required_c=[
    'jdoubleArray jworkingMat',
    'jdouble src[9], workingMat[9], outMat[9];',
    'workingMat[0]*tr + workingMat[1]*tg + workingMat[2]*tb',
    '(1224.0*lr + 2403.0*lg + 469.0*lb) / 4096.0',
    '1.000000000000*mappedY - 0.001043337611*mappedCb + 1.401991725445*mappedCr',
    'const double outR = outMat[0]*nr + outMat[1]*ng + outMat[2]*nb;',
    'srgb8(outR)',
    '*synthGain*edgeScale*hfRecordGain',
    'kM10RHighEdgeScale[16384]'
]
for x in required_c:
    if x not in C: raise SystemExit('RENDER1G WORKING1A native invariant missing: '+x)
if 'double[] targetToSrgb = matMul(DEFAULT_SRGB_CC1' in R:
    raise SystemExit('RENDER1G WORKING1A collapsed pre-tone CC1 matrix remains')
if 'const double lr = outMat[0]*tr + outMat[1]*tg + outMat[2]*tb;' in C:
    raise SystemExit('RENDER1G WORKING1A CC1 still active before nonlinear stage')
if '-render1g-working1a-diag1c-saf1' not in G:
    raise SystemExit('RENDER1G WORKING1A version marker missing')

print('M10-R RENDER1G WORKING1A applied')
print(' - Leica internal working-basis transform moved before Yc/MEDIUM/DG')
print(' - unchanged DEFAULT_SRGB_CC1 moved after nonlinear reconstruction')
print(' - exact YC2A matrix, MEDIUM/DG, CA9, source model and edge arithmetic preserved')
print(' - DIAG1C SAF diagnostics preserved and sampled domains updated consistently')
print(' - single RAW, HDR off, exposure, JPEG quality and 12MP output unchanged')
