#!/usr/bin/env python3
from pathlib import Path
import re,struct,sys

if len(sys.argv)!=3:
    raise SystemExit('usage: fix-m10r-render1e-edge1c-gain1a.py <PhotonCamera-root> <B2Y-calibration-bin>')
root=Path(sys.argv[1]).resolve(); b2y_path=Path(sys.argv[2]).resolve()
if not (root/'app').is_dir(): raise SystemExit('RENDER1E EDGE1C GAIN1A: not a PhotonCamera root')
if not b2y_path.is_file(): raise SystemExit('RENDER1E EDGE1C GAIN1A: missing B2Y calibration')

def rd(rel):
    p=root/rel
    if not p.exists(): raise SystemExit('RENDER1E EDGE1C GAIN1A missing: '+rel)
    return p.read_text()
def wr(rel,s):
    p=root/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(s)
def one(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit('RENDER1E EDGE1C GAIN1A anchor %s count=%d'%(label,n))
    return s.replace(a,b,1)

# Verify the exact Leica STILL/MEDIUM HighEdge scalar records before using them.
# Research v1.21 proves record offset +0x118 is consumed as a 10-bit hardware
# field and +0x11c as another 10-bit field. v1.22 establishes across all 0x0F
# HighEdge records that +0x11c is always 1023, while +0x118 is mode/ISO/
# sharpness dependent. STILL/MEDIUM values are exactly 160,128,80 for
# ISO 100/160, 200..640, and 800+ respectively. Numerically these are exact
# Q8 fractions 0.625, 0.5, 0.3125. GAIN1A tests /256 as a gain interpretation;
# semantic exactness is NOT yet claimed.
PFX=4; HDR=PFX+0x10; STRIDE=0xA90
b=b2y_path.read_bytes()
if len(b)<HDR: raise SystemExit('B2Y too small')
def u32(x,o): return struct.unpack_from('<I',x,o)[0]
count=u32(b,PFX+8); payload_base=HDR+count*STRIDE
seen={}
for idx in range(count):
    o=HDR+idx*STRIDE
    rid,rel,size=u32(b,o),u32(b,o+4),u32(b,o+8)
    if rid!=0x0F or size<0x120: continue
    hdr=b[o:o+STRIDE]
    blob=b[payload_base+rel:payload_base+rel+size]
    txt=' '.join(m.group().decode('ascii','ignore') for m in re.finditer(rb'[ -~]{8,}',hdr))
    for iso in (100,200,800):
        # ISO token must end here: avoid matching ISO:100 inside ISO:100000.
        if re.search(rf'_B2YMODE:STILL_SHARPNESS:MEDIUM_ISO:{iso}(?!\d)',txt):
            seen[iso]=(u32(blob,0x118)&0x3ff,u32(blob,0x11c)&0x3ff,idx)
expect={100:(160,1023),200:(128,1023),800:(80,1023)}
for iso,(g,mx) in expect.items():
    if iso not in seen: raise SystemExit(f'RENDER1E missing STILL/MEDIUM ISO{iso} HF record')
    if seen[iso][:2]!=(g,mx): raise SystemExit(f'RENDER1E HF scalar mismatch ISO{iso}: {seen[iso]}')

# Version / diagnostics.
grad='app/build.gradle'; g=rd(grad)
g=one(g,
      "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1d-edge1b-scale1a'",
      "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1e-edge1c-scale1a-gain1a'",
      'version')
wr(grad,g)

renderer='app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'; r=rd(renderer)
r=one(r,'d.put("renderLook", "RENDER1D_EDGE1B_SCALE1A");','d.put("renderLook", "RENDER1E_EDGE1C_SCALE1A_GAIN1A");','render-look')
anchor='''            d.put("edgeScaleNormalization", "scale_u10_over_1023_EXPERIMENTAL");\n            d.put("edgeStepTableIdentity", true);'''
insert='''            d.put("edgeScaleNormalization", "scale_u10_over_1023_EXPERIMENTAL");\n            d.put("edgeHfRecordGainApplied", true);\n            d.put("edgeHfRecordGainSource", "B2Y_record_0x0F_offset_0x118_10bit");\n            d.put("edgeHfRecordGainValues", "ISO100_160=160,ISO200_640=128,ISO800plus=80");\n            d.put("edgeHfRecordGainNormalization", "value_over_256_Q8_GAIN_CANDIDATE");\n            d.put("edgeHfRecordGainSemanticExactFirmwareParityClaimed", false);\n            d.put("edgeHfRecordMaxField0x11c", 1023);\n            d.put("edgeHfRecordMaxFieldSemantic", "10bit_fullscale_constant_role_not_yet_proven");\n            d.put("edgeStepTableIdentity", true);'''
r=one(r,anchor,insert,'gain-diagnostics')
wr(renderer,r)

cpp='app/src/main/cpp/m10rRender.cpp'; c=rd(cpp)
old='''                double delta=(hp<0.0?-shaped:shaped)*synthGain*edgeScale;'''
new='''                // GAIN1A: exact firmware HighEdge record +0x118 values for\n                // STILL/MEDIUM are 160,128,80 in the same ISO bands used by\n                // calibration selection. The hardware field is 10-bit; /256 is\n                // tested as the strongest data-constrained Q8 gain model. This\n                // interpretation remains explicitly experimental until the B2Y\n                // internal consumer arithmetic is recovered.\n                const double hfRecordGain = iso <= 160 ? (160.0/256.0)\n                                           : (iso <= 640 ? (128.0/256.0)\n                                                         : (80.0/256.0));\n                double delta=(hp<0.0?-shaped:shaped)*synthGain*edgeScale*hfRecordGain;'''
c=one(c,old,new,'hf-record-gain')
wr(cpp,c)

R=rd(renderer); C=rd(cpp)
for m in [
    'LOOK1B_YC1B','RENDER1E_EDGE1C_SCALE1A_GAIN1A',
    'edgeScaleTableApplied", true','edgeHfRecordGainApplied", true',
    'B2Y_record_0x0F_offset_0x118_10bit','value_over_256_Q8_GAIN_CANDIDATE',
    'edgeHfRecordGainSemanticExactFirmwareParityClaimed", false',
    'lowFrequencyEdgeApplied", false','textureEnhancementBlockEnabled", false',
    'hdrEnabled", false','sourceFrameCount", 1']:
    if m not in R: raise SystemExit('RENDER1E renderer invariant missing: '+m)
for m in ['160.0/256.0','128.0/256.0','80.0/256.0','*synthGain*edgeScale*hfRecordGain',
          'kM10RHighEdgeScale[16384]','constexpr int kc=316, ka=-46, kd=-4, kb=-20, ko=-3, kk=-3']:
    if m not in C: raise SystemExit('RENDER1E native invariant missing: '+m)
print('M10-R RENDER1E EDGE1C SCALE1A GAIN1A applied')
print(' - user-validated SCALE1A frozen')
print(' - exact STILL/MEDIUM HighEdge +0x118 values 160/128/80 validated from firmware')
print(' - /256 Q8 gain interpretation added as the only photographic change')
print(' - +0x11c=1023 validated but its semantic role remains unclaimed')
print(' - inherited 450/1001 shaping remains explicitly experimental and unchanged for clean A/B')
print(' - LF and TEXTURE remain OFF; LOOK1B/YC1B, single RAW, HDR-off, 12MP/JPEG quality frozen')
