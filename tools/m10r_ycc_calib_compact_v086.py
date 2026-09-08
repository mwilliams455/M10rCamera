#!/usr/bin/env python3
"""v0.86: prove B2Y calibration records 0x0C/0x0D -> SAM7 b2y_ctrl_ycc layout.

Uses only parsed calibration payloads and the exact field packing recovered from
SAM7 Im_B2Y_Ctrl_Yc_Convert in v0.85. No fitted values or semantic renaming.
"""
from __future__ import annotations
import importlib.util,json,struct,sys
from pathlib import Path

REGA=(0x00,0x04,0x08,0x0c,0x10)

def load_parser(repo:Path):
 p=repo/'tools'/'m10r_b2y_assets.py';s=importlib.util.spec_from_file_location('m10r_b2y_assets_v086',p)
 if s is None or s.loader is None:raise RuntimeError('parser spec')
 m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m

def u32s(blob):return list(struct.unpack('<'+'I'*(len(blob)//4),blob))
def s32(v):return v-0x100000000 if v&0x80000000 else v

def pack13pair(a,b):return (a&0x1fff)|((b&0x1fff)<<16)
def pack15pair(a,b):return (a&0x7fff)|((b&0xffff)<<16)

def main():
 if len(sys.argv)!=3:raise SystemExit('usage: m10r_ycc_calib_compact_v086.py <sections_dir> <repo_root>')
 root=Path(sys.argv[1]);repo=Path(sys.argv[2]);mod=load_parser(repo)
 p=root/'074_IMG_Calibration_Data_data_calib_B2Y.bin.bin';data=p.read_bytes();records=mod.parse_records(data)
 cands=[r for r in records if r.record_id in (0x0c,0x0d)]
 print(f'V086_RECORDS_0C0D={[(r.index,hex(r.record_id),hex(r.payload_offset),hex(r.size)) for r in cands]}')
 r0c=next(r for r in records if r.record_id==0x0c);r0d=next(r for r in records if r.record_id==0x0d)
 b0c=data[r0c.payload_offset:r0c.payload_offset+r0c.size];b0d=data[r0d.payload_offset:r0d.payload_offset+r0d.size]
 a=u32s(b0c);d=u32s(b0d)
 print('V086_0C_U32='+','.join(str(x) for x in a))
 print('V086_0C_S32='+','.join(str(s32(x)) for x in a))
 print('V086_0D_U32='+','.join(str(x) for x in d))
 if len(a)!=15 or len(d)!=6:raise SystemExit(f'unexpected lengths 0C={len(a)} 0D={len(d)}')

 # v0.85 SAM7 compact struct: 15 halfwords at 0x00..0x1c,
 # two u8 controls at 0x1e/0x1f, then four halfwords at 0x20..0x26.
 st=bytearray(0x28)
 for i,v in enumerate(a):struct.pack_into('<H',st,2*i,v&0xffff)
 st[0x1e]=d[0]&0xff;st[0x1f]=d[1]&0xff
 for i,v in enumerate(d[2:]):struct.pack_into('<H',st,0x20+2*i,v&0xffff)
 print('V086_COMPACT_HEX='+st.hex())
 print('V086_COMPACT_HALFWORDS_00_1C='+','.join(str(struct.unpack_from('<H',st,2*i)[0]) for i in range(15)))
 print(f'V086_COMPACT_U8_1E_1F={st[0x1e]},{st[0x1f]}')
 print('V086_COMPACT_HALFWORDS_20_26='+','.join(str(struct.unpack_from('<H',st,0x20+2*i)[0]) for i in range(4)))

 # Exact register image implied by v0.85 packing. Matrix = 9 13-bit signed
 # coefficients in 5 registers (last register has coeff8 low; upper preserved
 # by hardware RMW, so report only the controlled mask/value there).
 regs={}
 for k in range(4):regs[REGA[k]]=pack13pair(a[2*k],a[2*k+1])
 regs[0x10]=a[8]&0x1fff
 regs[0x20]=pack15pair(a[9],a[10]);regs[0x24]=pack15pair(a[11],a[12]);regs[0x28]=pack15pair(a[13],a[14])
 regs[0x2c]=(d[0]&0x3f)|((d[1]&0x3f)<<8)
 regs[0x30]=(d[2]&0x7fff)|((d[3]&0xffff)<<16)
 regs[0x34]=(d[4]&0x7fff)|((d[5]&0xffff)<<16)
 for off in sorted(regs):print(f'V086_REG=0x200209{off:02x}|offset=0x{off:02x}|value=0x{regs[off]&0xffffffff:08x}')

 # Structural invariants useful for promotion of evidence, not renderer behavior.
 matrix=a[:9];extra=a[9:]
 inv={
  'record0c_count':len(a),'record0d_count':len(d),
  'matrix_signed':[s32(x) for x in matrix],
  'record0c_tail_u32':extra,'record0d_u32':d,
  'record0c_tail_all_16383':all(x==0x3fff for x in extra),
  'record0d_expected':d==[0,32,0x3fff,0x3fff,0x3fff,0x3fff],
  'compact_size':len(st),
  'registers':{f'0x{k:02x}':v&0xffffffff for k,v in regs.items()},
 }
 print('V086_JSON='+json.dumps(inv,sort_keys=True))
 if not inv['record0c_tail_all_16383'] or not inv['record0d_expected']:
  raise SystemExit('calibration payload differs from frozen evidence expectation')
 print('OVERALL_VERDICT=RECORD_0C_0D_EXACTLY_COMPACT_TO_SAM7_YCC_CONTROL_LAYOUT')
if __name__=='__main__':main()
