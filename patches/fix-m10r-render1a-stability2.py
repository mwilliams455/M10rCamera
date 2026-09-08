#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix-m10r-render1a-stability2.py <PhotonCamera-root>')
root = Path(sys.argv[1]).resolve()
if not (root / 'app').is_dir():
    raise SystemExit('RENDER1A STABILITY2: not a PhotonCamera root')

def rd(rel):
    p=root/rel
    if not p.exists(): raise SystemExit('RENDER1A STABILITY2 missing: '+rel)
    return p.read_text()
def wr(rel,s): (root/rel).write_text(s)
def one(s,a,b,label):
    if s.count(a)!=1: raise SystemExit('RENDER1A STABILITY2 anchor %s count=%d'%(label,s.count(a)))
    return s.replace(a,b,1)

# Speed-only overlay. Photographic arithmetic and single-frame/no-HDR policy stay frozen.
grad='app/build.gradle'
g=rd(grad)
g=one(g,
      "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability1'",
      "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability2'",
      'version')
wr(grad,g)

renderer='app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'
r=rd(renderer)
# 256 rows halves OpenCV invocation count versus STABILITY1 while keeping the tile BGR
# allocation near 6 MiB instead of the original ~72 MiB full-frame BGR Mat.
r=one(r,'            final int blockRows = 128;\n','            final int blockRows = 256;\n','tile-rows')

# Per-pixel diagnostic histograms are research instrumentation, not image formation.
# Sample 1/64 pixels for distribution statistics while exact clipping counters remain
# inside toInputLuma()/dgLuma(). This removes hundreds of millions of Java histogram
# updates per 12 MP frame without changing any pixel arithmetic.
old='''                    toneDgStats.preTone.add(lr, lg, lb);\n                    double linearY = 0.2126*lr + 0.7152*lg + 0.0722*lb;\n                    int xy = M10RToneDg1A.toInputLuma(linearY, toneDgStats);\n                    toneDgStats.toneInput.add(xy, xy, xy);\n                    int my = M10RToneDg1A.medium(xy);\n                    toneDgStats.postTone.add(my, my, my);\n                    int dy = M10RToneDg1A.dgLuma(my, toneDgStats);\n                    toneDgStats.postDg.add(dy, dy, dy);\n                    double mappedY = dy / (double)M10RToneDg1A.DG_OUT_MAX;\n                    double gain = (linearY > 1.0e-12) ? (mappedY / linearY) : 0.0;\n                    toneDgStats.lumaGain.add(gain);\n                    double nr = lr * gain;\n                    double ng = lg * gain;\n                    double nb = lb * gain;\n                    toneDgStats.preSrgb.add(nr, ng, nb);\n'''
new='''                    final boolean sampleDiagnostics = (i & 63) == 0;\n                    if (sampleDiagnostics) toneDgStats.preTone.add(lr, lg, lb);\n                    double linearY = 0.2126*lr + 0.7152*lg + 0.0722*lb;\n                    int xy = M10RToneDg1A.toInputLuma(linearY, toneDgStats);\n                    if (sampleDiagnostics) toneDgStats.toneInput.add(xy, xy, xy);\n                    int my = M10RToneDg1A.medium(xy);\n                    if (sampleDiagnostics) toneDgStats.postTone.add(my, my, my);\n                    int dy = M10RToneDg1A.dgLuma(my, toneDgStats);\n                    if (sampleDiagnostics) toneDgStats.postDg.add(dy, dy, dy);\n                    double mappedY = dy / (double)M10RToneDg1A.DG_OUT_MAX;\n                    double gain = (linearY > 1.0e-12) ? (mappedY / linearY) : 0.0;\n                    if (sampleDiagnostics) toneDgStats.lumaGain.add(gain);\n                    double nr = lr * gain;\n                    double ng = lg * gain;\n                    double nb = lb * gain;\n                    if (sampleDiagnostics) toneDgStats.preSrgb.add(nr, ng, nb);\n'''
r=one(r,old,new,'sample-diagnostics')

meta='''            d.put("renderStabilityFix", "STABILITY1_TILED_EA_DEMOSAIC_DIRECT_ORIENTATION");\n            d.put("demosaicTileRows", blockRows);\n'''
meta_new='''            d.put("renderStabilityFix", "STABILITY2_TILED_EA_DEMOSAIC_SAMPLED_DIAGNOSTICS");\n            d.put("diagnosticSamplingStride", 64);\n            d.put("diagnosticSamplingAffectsPixels", false);\n            d.put("demosaicTileRows", blockRows);\n'''
r=one(r,meta,meta_new,'metadata')
wr(renderer,r)

R=rd(renderer)
for marker in [
    'nonlinearRenderer", "TONEDG1B"',
    'nonlinearOrder", "MEDIUM_THEN_DIFFERENTIAL_GAMMA"',
    'nonlinearApplicationMode", "luma_gain_preserve_linear_rgb_ratios"',
    'hdrEnabled", false',
    'sourceFrameCount", 1',
    'final int blockRows = 256',
    'final boolean sampleDiagnostics = (i & 63) == 0',
    'STABILITY2_TILED_EA_DEMOSAIC_SAMPLED_DIAGNOSTICS',
    'diagnosticSamplingStride", 64',
    'fullFrameBgrMatAllocated", false',
    'secondRotationBitmapAllocated", false',
]:
    if marker not in R: raise SystemExit('RENDER1A STABILITY2 invariant missing: '+marker)
for forbidden in [
    'new Mat(frame.height, frame.width, CvType.CV_16UC1)',
    'Bitmap rotated = Bitmap.createBitmap(bitmap',
    'bgr16 = new Mat()',
]:
    if forbidden in R: raise SystemExit('RENDER1A STABILITY2 peak-memory regression: '+forbidden)
print('M10-R RENDER1A STABILITY2 applied')
print(' - 256-row CFA-phase-preserving EA demosaic tiles')
print(' - diagnostic distributions sampled 1/64; exact clip counters retained')
print(' - image arithmetic, firmware MEDIUM/DG, colour, exposure and JPEG quality unchanged')
print(' - single-frame and HDR-disabled policies unchanged')
