#!/usr/bin/env python3
from pathlib import Path
import struct,sys

if len(sys.argv)!=3:
    raise SystemExit('usage: fix-m10r-render1f-yc2a-matrix1a.py <PhotonCamera-root> <B2Y-calibration-bin>')
root=Path(sys.argv[1]).resolve(); b2y_path=Path(sys.argv[2]).resolve()
if not (root/'app').is_dir(): raise SystemExit('RENDER1F YC2A MATRIX1A: not a PhotonCamera root')
if not b2y_path.is_file(): raise SystemExit('RENDER1F YC2A MATRIX1A: missing B2Y calibration')

def rd(rel):
    p=root/rel
    if not p.exists(): raise SystemExit('RENDER1F YC2A MATRIX1A missing: '+rel)
    return p.read_text()
def wr(rel,s):
    p=root/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(s)
def one(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit('RENDER1F YC2A MATRIX1A anchor %s count=%d'%(label,n))
    return s.replace(a,b,1)

def u32(b,o): return struct.unpack_from('<I',b,o)[0]
def s32(x): return x-0x100000000 if x&0x80000000 else x

# Firmware-first gate. B2Y record 0x0C is the sole YC_CONVERSION record.
# v1.23 also proved the IMG-System setter's reset/default path reconstructs
# these same nine matrix coefficients, so this is a canonical firmware fix,
# not a visual tuning operation.
PFX=4; HDR=PFX+0x10; STRIDE=0xA90
b=b2y_path.read_bytes()
if len(b)<HDR: raise SystemExit('RENDER1F B2Y too small')
count=u32(b,PFX+8); payload_base=HDR+count*STRIDE
hits=[]
for idx in range(count):
    o=HDR+idx*STRIDE
    rid,rel,size=u32(b,o),u32(b,o+4),u32(b,o+8)
    if rid==0x0C:
        blob=b[payload_base+rel:payload_base+rel+size]
        hits.append((idx,size,blob))
if len(hits)!=1: raise SystemExit(f'RENDER1F expected one YC_CONVERSION record, got {len(hits)}')
idx,size,blob=hits[0]
if size!=0x3c or len(blob)<0x3c: raise SystemExit(f'RENDER1F YC_CONVERSION size mismatch idx={idx} size=0x{size:x}')
vals=[s32(u32(blob,i*4)) for i in range(15)]
expected=[1224,2403,469,-691,-1357,2048,2048,-1715,-333,16383,16383,16383,16383,16383,16383]
if vals!=expected: raise SystemExit(f'RENDER1F YC_CONVERSION values mismatch: {vals}')
if sum(vals[0:3])!=4096 or sum(vals[3:6])!=0 or sum(vals[6:9])!=0:
    raise SystemExit('RENDER1F YC matrix row-sum invariant failed')

# Exact inverse of integer-Q12 matrix [1224 2403 469; -691 -1357 2048;
# 2048 -1715 -333] / 4096. The first inverse column is exactly 1 because
# the luma row sums to 4096 and both chroma rows sum to zero.
IR='1.000000000000'
ICB_R='-0.001043337611'; ICR_R='1.401991725445'
ICB_G='-0.345114690199'; ICR_G='-0.714098755336'
ICB_B='1.770975790582'; ICR_B='-0.000124867533'

grad='app/build.gradle'; g=rd(grad)
g=one(g,
      "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1e-edge1c-scale1a-gain1a'",
      "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1f-yc2a-matrix1a'",
      'version')
wr(grad,g)

renderer='app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'; r=rd(renderer)
r=one(r,'d.put("renderLook", "RENDER1E_EDGE1C_SCALE1A_GAIN1A");','d.put("renderLook", "RENDER1F_YC2A_MATRIX1A");','render-look')
r=one(r,'d.put("nonlinearLumaProxy", "M10R_Yc_Convert_Y_Q12_1224_2404_467");','d.put("nonlinearLumaProxy", "M10R_Yc_Convert_Y_Q12_1224_2403_469");','luma-proxy')
r=one(r,'d.put("b2yYcConvertMatrixQ12", "1224,2404,467;-691,-1357,2048;2048,-1715,-333");','d.put("b2yYcConvertMatrixQ12", "1224,2403,469;-691,-1357,2048;2048,-1715,-333");','matrix-metadata')
anchor='''        d.put("b2yYBlendApplied", false);'''
insert='''        d.put("yc2aMatrixCorrectionApplied", true);\n        d.put("yc2aMatrixSource", "B2Y_record_0x0C_plus_IMG_System_driver_default_v123");\n        d.put("yc2aMatrixRowSums", "4096,0,0");\n        d.put("yc2aExactInverseApplied", true);\n        d.put("yc2aYBlendStillDeferred", true);\n        d.put("yc2aTrailingBoundaryPairsStillDeferred", true);\n        d.put("b2yYBlendApplied", false);'''
r=one(r,anchor,insert,'yc2a-diagnostics')
r=one(r,
      'double ycY = (1224.0*lr + 2404.0*lg + 467.0*lb) / 4096.0;',
      'double ycY = (1224.0*lr + 2403.0*lg + 469.0*lb) / 4096.0;',
      'java-forward-y')
r=one(r,
      'double nr = 1.000244200244*mappedY - 0.000094115078*mappedCb + 1.402166047550*mappedCr;',
      'double nr = 1.000000000000*mappedY - 0.001043337611*mappedCb + 1.401991725445*mappedCr;',
      'java-inverse-r')
r=one(r,
      'double ng = 1.000244200244*mappedY - 0.344165467666*mappedCb - 0.713924433230*mappedCr;',
      'double ng = 1.000000000000*mappedY - 0.345114690199*mappedCb - 0.714098755336*mappedCr;',
      'java-inverse-g')
r=one(r,
      'double nb = 1.000244200244*mappedY + 1.771925013114*mappedCb + 0.000049454572*mappedCr;',
      'double nb = 1.000000000000*mappedY + 1.770975790582*mappedCb - 0.000124867533*mappedCr;',
      'java-inverse-b')
wr(renderer,r)

cpp='app/src/main/cpp/m10rRender.cpp'; c=rd(cpp)
c=one(c,
      'const double y  = (1224.0*lr + 2404.0*lg + 467.0*lb) / 4096.0;',
      'const double y  = (1224.0*lr + 2403.0*lg + 469.0*lb) / 4096.0;',
      'native-forward-y')
c=one(c,
      'const double nr = 1.000244200244*mappedY - 0.000094115078*mappedCb + 1.402166047550*mappedCr;',
      'const double nr = 1.000000000000*mappedY - 0.001043337611*mappedCb + 1.401991725445*mappedCr;',
      'native-inverse-r')
c=one(c,
      'const double ng = 1.000244200244*mappedY - 0.344165467666*mappedCb - 0.713924433230*mappedCr;',
      'const double ng = 1.000000000000*mappedY - 0.345114690199*mappedCb - 0.714098755336*mappedCr;',
      'native-inverse-g')
c=one(c,
      'const double nb = 1.000244200244*mappedY + 1.771925013114*mappedCb + 0.000049454572*mappedCr;',
      'const double nb = 1.000000000000*mappedY + 1.770975790582*mappedCb - 0.000124867533*mappedCr;',
      'native-inverse-b')
# Deliberately DO NOT alter the post-LOOK1B EDGE1C luma expression in this
# candidate. RENDER1E's validated edge stage is frozen for a clean colour/tone A/B.
wr(cpp,c)

R=rd(renderer); C=rd(cpp)
for m in [
    'RENDER1F_YC2A_MATRIX1A',
    'M10R_Yc_Convert_Y_Q12_1224_2403_469',
    '1224,2403,469;-691,-1357,2048;2048,-1715,-333',
    'yc2aMatrixCorrectionApplied", true',
    'B2Y_record_0x0C_plus_IMG_System_driver_default_v123',
    'yc2aYBlendStillDeferred", true',
    'b2yYBlendApplied", false',
    'edgeScaleTableApplied", true',
    'edgeHfRecordGainApplied", true',
    'lowFrequencyEdgeApplied", false',
    'textureEnhancementBlockEnabled", false',
    'hdrEnabled", false','sourceFrameCount", 1']:
    if m not in R: raise SystemExit('RENDER1F renderer invariant missing: '+m)
for m in [
    '(1224.0*lr + 2403.0*lg + 469.0*lb) / 4096.0',
    '1.000000000000*mappedY - 0.001043337611*mappedCb + 1.401991725445*mappedCr',
    '1.000000000000*mappedY - 0.345114690199*mappedCb - 0.714098755336*mappedCr',
    '1.000000000000*mappedY + 1.770975790582*mappedCb - 0.000124867533*mappedCr',
    '*synthGain*edgeScale*hfRecordGain',
    'kM10RHighEdgeScale[16384]']:
    if m not in C: raise SystemExit('RENDER1F native invariant missing: '+m)
if '(1224.0*lr + 2404.0*lg + 467.0*lb) / 4096.0' in C:
    raise SystemExit('RENDER1F old primary Yc forward matrix remains active')
print('M10-R RENDER1F YC2A MATRIX1A applied')
print(' - exact firmware Yc_Convert matrix corrected to 1224,2403,469 / -691,-1357,2048 / 2048,-1715,-333')
print(' - mathematical inverse updated consistently; inverse Y column is exactly unity')
print(' - user-validated RENDER1E EDGE1C/SCALE1A/GAIN1A stage frozen byte-for-byte in its edge arithmetic')
print(' - Y_BLEND and three trailing boundary pairs remain deferred; no guessed colour operation added')
print(' - LOOK1B relative chroma policy, single RAW, HDR-off, 12MP and JPEG quality preserved')
