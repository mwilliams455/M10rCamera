#!/usr/bin/env python3
"""v0.73 dump B2Y record header keys for tone/WBCLIP/Y_BLEND/YC conversion.

The common lookup at 0x421a0fc4 proves the 0xA90 header layout uses:
  +0x00 record id, +0x04 payload relative offset, +0x08 payload size,
  +0x0c accepted-key count, +0x10 N x 64-byte accepted keys.
This probe records those exact keys and small payload values. No new semantic
mapping is inferred solely from numeric similarity.
"""
from pathlib import Path
import csv, importlib.util, struct, sys

HEADER_OFF=4+0x10
STRIDE=0xA90
TARGET_IDS={0x04:'WBCLIPLEVEL_candidate',0x0D:'Y_BLEND',0x0C:'YC_CONVERSION',0x19:'TONE_TBL0',0x1A:'TONE_TBL1'}

def load_assets(root):
    p=root/'tools'/'m10r_b2y_assets.py';spec=importlib.util.spec_from_file_location('assets_v073',p)
    mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod);return mod

def u32(b,o):return struct.unpack_from('<I',b,o)[0]
def s32s(blob):return list(struct.unpack('<'+'i'*(len(blob)//4),blob[:len(blob)//4*4]))
def u32s(blob):return list(struct.unpack('<'+'I'*(len(blob)//4),blob[:len(blob)//4*4]))
def key_text(raw):
    q=raw.split(b'\0',1)[0]
    return q.decode('ascii','backslashreplace')

def main():
    if len(sys.argv)!=3:raise SystemExit('usage: script <sections_dir> <repo_root>')
    sec=Path(sys.argv[1]);root=Path(sys.argv[2]);assets=load_assets(root)
    exact=sec/'074_IMG_Calibration_Data_data_calib_B2Y.bin.bin';cands=sorted(sec.glob('*data_calib_B2Y*.bin*'))
    p=exact if exact.exists() else (cands[0] if len(cands)==1 else None)
    if p is None:raise SystemExit('B2Y auxiliary missing/ambiguous')
    data=p.read_bytes();records=assets.parse_records(data)
    print(f'V073_B2Y={p}|records={len(records)}')
    for rec in records:
        if rec.record_id not in TARGET_IDS:continue
        ho=HEADER_OFF+rec.index*STRIDE
        rid=u32(data,ho);rel=u32(data,ho+4);size=u32(data,ho+8);kc=u32(data,ho+0xc)
        print(f'\nV073_HEADER=label={TARGET_IDS[rid]}|index={rec.index}|id=0x{rid:x}|rel=0x{rel:x}|size=0x{size:x}|key_count={kc}')
        if kc>42:raise RuntimeError(f'implausible key count {kc} at record {rec.index}')
        for i in range(kc):
            raw=data[ho+0x10+i*0x40:ho+0x10+(i+1)*0x40]
            print(f'V073_KEY=index={rec.index}|slot={i}|text={key_text(raw)!r}|hex={raw.hex()}')
        blob=data[rec.payload_offset:rec.payload_offset+rec.size]
        if rec.size<=0x100:
            print(f'V073_PAYLOAD_HEX=index={rec.index}|{blob.hex()}')
            print(f'V073_PAYLOAD_U32=index={rec.index}|'+','.join(str(x) for x in u32s(blob)))
            print(f'V073_PAYLOAD_S32=index={rec.index}|'+','.join(str(x) for x in s32s(blob)))
    print('\nOVERALL_VERDICT=RECORD_KEYS_AND_SMALL_PAYLOADS_RECORDED_FROM_FROZEN_LOOKUP_LAYOUT')
if __name__=='__main__':main()
