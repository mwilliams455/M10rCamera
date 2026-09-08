#!/usr/bin/env python3
from pathlib import Path
import hashlib, struct, sys

if len(sys.argv) != 3:
    raise SystemExit('usage: fix-m10r-render1d-edge1b-scale1a.py <PhotonCamera-root> <B2Y-calibration-bin>')
root=Path(sys.argv[1]).resolve()
b2y_path=Path(sys.argv[2]).resolve()
if not (root/'app').is_dir(): raise SystemExit('RENDER1D EDGE1B SCALE1A: not a PhotonCamera root')
if not b2y_path.is_file(): raise SystemExit('RENDER1D EDGE1B SCALE1A: missing B2Y calibration')

def rd(rel):
    p=root/rel
    if not p.exists(): raise SystemExit('RENDER1D EDGE1B SCALE1A missing: '+rel)
    return p.read_text()
def wr(rel,s):
    p=root/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(s)
def one(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit('RENDER1D EDGE1B SCALE1A anchor %s count=%d'%(label,n))
    return s.replace(a,b,1)

# Extract the exact record 0x1E payload from Leica M10-R B2Y calibration.
# v1.05-v1.08 research establishes:
#   0x1E/0x1F = identical 16,384-entry HighEdge scale-table bank payloads
#   0x20/0x21 = identical 8,192-entry identity HighEdge step tables
#   0x22/0x23 mirror the same scale table for LowEdge
#   0x24/0x25 mirror the same identity step table for LowEdge
# Firmware SDK strings explicitly name HighEdge/LowEdge Scale_Table and Step_Table APIs.
b=b2y_path.read_bytes()
PFX=4; HDR=PFX+0x10; STRIDE=0xA90
if len(b)<HDR: raise SystemExit('B2Y too small')
count=struct.unpack_from('<I',b,PFX+8)[0]
payload_base=HDR+count*STRIDE
scale=None
for i in range(count):
    o=HDR+i*STRIDE
    rid,rel,size=struct.unpack_from('<III',b,o)
    if rid==0x1E:
        scale=b[payload_base+rel:payload_base+rel+size]
        break
if scale is None: raise SystemExit('record 0x1E not found')
sha=hashlib.sha256(scale).hexdigest()
if len(scale)!=0x8000: raise SystemExit('record 0x1E unexpected size 0x%x'%len(scale))
if sha!='e4e8da0735a8847d4cc3c3766b58818ec29fe31d42d0710880a880e4ba7b8d1a':
    raise SystemExit('record 0x1E SHA mismatch '+sha)
vals=list(struct.unpack('<16384H',scale))
if min(vals)!=358 or max(vals)!=1023: raise SystemExit('scale range mismatch')

# Version is deliberately a new candidate; LOOK1B/YC1B and EDGE1A remain reproducible.
grad='app/build.gradle'
g=rd(grad)
g=one(g,
      "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1c-edge1a'",
      "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1d-edge1b-scale1a'",
      'version')
wr(grad,g)

renderer='app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'
r=rd(renderer)
r=one(r,'d.put("renderLook", "RENDER1C_EDGE1A");','d.put("renderLook", "RENDER1D_EDGE1B_SCALE1A");','render-look')
r=one(r,
'''            d.put("edgeArithmeticExactFirmwareParityClaimed", false);\n            d.put("edgePlacement", "post_LOOK1B_sRGB_decode_linear_Y_reencode_EXPERIMENTAL");\n            d.put("textureEnhancementBlockEnabled", false);''',
'''            d.put("edgeArithmeticExactFirmwareParityClaimed", false);\n            d.put("edgeScaleTableApplied", true);\n            d.put("edgeScaleTableSource", "B2Y_record_0x1E_HighEdge_Scale_Table_exact_16384_u16");\n            d.put("edgeScaleTableSha256", "e4e8da0735a8847d4cc3c3766b58818ec29fe31d42d0710880a880e4ba7b8d1a");\n            d.put("edgeScaleTableEntries", 16384);\n            d.put("edgeScaleTableMin", 358);\n            d.put("edgeScaleTableMax", 1023);\n            d.put("edgeScaleCoordinate", "center_Y14_INFERRED_FROM_14BIT_SCALE_DOMAIN_EXPERIMENTAL");\n            d.put("edgeScaleNormalization", "scale_u10_over_1023_EXPERIMENTAL");\n            d.put("edgeStepTableIdentity", true);\n            d.put("edgeStepTableAppliedSeparately", false);\n            d.put("edgeStepTableReason", "firmware_HighEdge_Step_Table_is_exact_identity_0_to_8191");\n            d.put("edgePlacement", "post_LOOK1B_sRGB_decode_linear_Y_reencode_EXPERIMENTAL");\n            d.put("textureEnhancementBlockEnabled", false);''',
'edge-scale-diagnostics')
wr(renderer,r)

cpp='app/src/main/cpp/m10rRender.cpp'
c=rd(cpp)
# Embed exact firmware scale table in the native renderer. This avoids Java/Bitmap
# copies and guarantees this candidate uses the calibration bytes byte-for-byte.
arr=[]
for i in range(0,len(vals),32):
    arr.append('    '+','.join(str(v) for v in vals[i:i+32])+',')
array='''\n\n// Exact Leica M10-R B2Y record 0x1E HighEdge Scale_Table payload.\n// 16,384 x uint16, SHA256 e4e8da0735a8847d4cc3c3766b58818ec29fe31d42d0710880a880e4ba7b8d1a.\n// The table coordinate and normalization are still explicitly experimental in SCALE1A.\nstatic constexpr uint16_t kM10RHighEdgeScale[16384] = {\n'''+"\n".join(arr)+'''\n};\n'''
anchor='''\n\nextern "C" JNIEXPORT jlong JNICALL\nJava_com_particlesdevs_photoncamera_m10r_M10RNativeRenderer_nativeEdgePass('''
if anchor not in c: raise SystemExit('nativeEdgePass anchor missing')
c=c.replace(anchor,array+anchor,1)

old='''                double shaped=std::min(mag,limit)-core;\n                if (shaped<=0.0) continue;\n                double delta=(hp<0.0?-shaped:shaped)*synthGain;\n                const double oldY=Y(0,0);\n                if (oldY<=1.0) continue;'''
new='''                double shaped=std::min(mag,limit)-core;\n                if (shaped<=0.0) continue;\n                const double oldY=Y(0,0);\n                if (oldY<=1.0) continue;\n                // SCALE1A: the firmware scale table has exactly 16,384 address\n                // positions while the B2Y image/tone domain is 14-bit. The SDK\n                // names it HighEdge Scale_Table; the associated 8,192-entry\n                // HighEdge Step_Table is identity. We therefore test the most\n                // constrained coordinate model: center Y14 -> 10-bit scale.\n                // Normalizing 1023 to 1.0 is experimental and is NOT claimed as\n                // exact hardware multiplication/rounding yet.\n                const int scaleIdx=std::max(0,std::min(16383,static_cast<int>(oldY)));\n                const double edgeScale=kM10RHighEdgeScale[scaleIdx]/1023.0;\n                double delta=(hp<0.0?-shaped:shaped)*synthGain*edgeScale;'''
c=one(c,old,new,'scale-application')
wr(cpp,c)

R=rd(renderer); C=rd(cpp)
for m in [
    'LOOK1B_YC1B','RENDER1D_EDGE1B_SCALE1A',
    'edgeScaleTableApplied", true',
    'edgeScaleTableSha256", "e4e8da0735a8847d4cc3c3766b58818ec29fe31d42d0710880a880e4ba7b8d1a"',
    'edgeScaleCoordinate", "center_Y14_INFERRED_FROM_14BIT_SCALE_DOMAIN_EXPERIMENTAL"',
    'edgeStepTableIdentity", true','lowFrequencyEdgeApplied", false',
    'textureEnhancementBlockEnabled", false','hdrEnabled", false','sourceFrameCount", 1']:
    if m not in R: raise SystemExit('renderer invariant missing: '+m)
for m in [
    'kM10RHighEdgeScale[16384]','kM10RHighEdgeScale[scaleIdx]/1023.0',
    'constexpr int kc=316, ka=-46, kd=-4, kb=-20, ko=-3, kk=-3',
    '5400.0/4096.0','3700.0/4096.0','constexpr double core=450.0','constexpr double limit=1001.0']:
    if m not in C: raise SystemExit('native invariant missing: '+m)
print('M10-R RENDER1D EDGE1B SCALE1A applied')
print(' - LOOK1B/YC1B colour and tone frozen')
print(' - EDGE1A HF kernel, current coring/limit experiment, and ISO synthesis map frozen')
print(' - exact firmware HighEdge Scale_Table record 0x1E added as the only photographic change')
print(' - 14-bit center-Y coordinate and /1023 normalization explicitly marked experimental')
print(' - HighEdge Step_Table not separately applied because recovered table is exact identity')
print(' - LF remains OFF for clean A/B; firmware evidence says it is active but combination math is not yet constrained')
print(' - TEXTURE remains OFF; HDR/multiframe remain OFF; 12 MP/JPEG quality unchanged')
