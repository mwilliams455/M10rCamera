#!/usr/bin/env python3
"""v0.72 targeted B2Y lookup trace.

Avoids the v0.71 whole-image Thumb sweep. The relevant selector functions are
already constrained by v0.67/v0.68, so inspect only those caller bodies plus
the common lookup at 0x421a0fc4, then enumerate the frozen B2Y calibration
record table. No selector-ID -> record-ID mapping is assumed.
"""
from pathlib import Path
import csv, hashlib, importlib.util, struct, sys
from collections import Counter, defaultdict
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_REG_PC

BASE=0x42000000
LOOKUP_OFF=0x1A0FC4
LOOKUP_VA=BASE+LOOKUP_OFF
CALLERS=[('TONE',0x154d5c),('WBCLIP',0x154e18),('Y_BLEND',0x154ecc)]


def load_module(path: Path, name: str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise RuntimeError(f'cannot load {path}')
    mod=importlib.util.module_from_spec(spec); sys.modules[name]=mod; spec.loader.exec_module(mod); return mod

def md_thumb():
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.detail=True; return md

def u32(b,o): return struct.unpack_from('<I',b,o)[0] if 0<=o<=len(b)-4 else None

def litrefs(ins,data):
    out=[]
    try:ops=list(ins.operands)
    except Exception:return out
    for op in ops:
        if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
            po=(((ins.address+4)&~3)+int(op.mem.disp))-BASE
            if 0<=po<=len(data)-4: out.append((po,u32(data,po)))
    return out

def body(md,data,start,span=0x500):
    out=[]
    for ins in md.disasm(data[start:min(len(data),start+span)],BASE+start):
        out.append(ins); off=ins.address-BASE; m=ins.mnemonic.lower()
        if off>start+2 and ((m=='pop' and 'pc' in ins.op_str.lower()) or (m=='bx' and 'lr' in ins.op_str.lower())): break
    return out

def ascii_near(data,off,r=0x400):
    lo=max(0,off-r);hi=min(len(data),off+r);out=[];i=lo
    while i<hi:
        if 32<=data[i]<127:
            j=i
            while j<hi and 32<=data[j]<127:j+=1
            if j-i>=8:out.append((i,data[i:j].decode('ascii','replace')))
            i=j
        else:i+=1
    return out

def print_ins(prefix,ins,data):
    off=ins.address-BASE; ex=[]
    for po,v in litrefs(ins,data): ex.append(f'LIT=0x{po:x}->0x{v:08x}')
    if ins.mnemonic.lower().startswith('bl'):
        try:op=ins.operands[0]
        except Exception:op=None
        if op is not None and op.type==ARM_OP_IMM:ex.append(f'CALL=0x{op.imm:08x}|target_off=0x{op.imm-BASE:x}')
    print(f'{prefix}=0x{off:x}|{ins.mnemonic} {ins.op_str}'+(('|'+'|'.join(ex)) if ex else ''))

def trace_code(img):
    md=md_thumb()
    print('=== V072 COMMON LOOKUP BODY ===')
    print(f'V072_LOOKUP=off=0x{LOOKUP_OFF:x}|va=0x{LOOKUP_VA:08x}')
    for so,s in ascii_near(img,LOOKUP_OFF,0x500):
        if any(k in s.lower() for k in ('para','calib','table','record','select','b2y')):print(f'V072_LOOKUP_ASCII=0x{so:x}|{s}')
    bins=body(md,img,LOOKUP_OFF,0x600)
    print(f'V072_LOOKUP_INS_COUNT={len(bins)}')
    for ins in bins:print_ins('V072_LOOKUP_INS',ins,img)
    print('\n=== V072 TARGETED CALLERS ===')
    for label,start in CALLERS:
        insns=body(md,img,start,0x180)
        print(f'V072_CALLER={label}|start=0x{start:x}|va=0x{BASE+start:08x}|ins={len(insns)}')
        hits=0
        for idx,ins in enumerate(insns):
            target=None
            if ins.mnemonic.lower().startswith('bl'):
                try:op=ins.operands[0]
                except Exception:op=None
                if op is not None and op.type==ARM_OP_IMM:target=int(op.imm)
            if target!=LOOKUP_VA: continue
            hits+=1
            print(f'V072_LOOKUP_CALL={label}|off=0x{ins.address-BASE:x}')
            for q in insns[max(0,idx-10):min(len(insns),idx+5)]:print_ins('  V072_CTX',q,img)
        print(f'V072_LOOKUP_CALL_COUNT={label}|{hits}')

def record_manifest(repo_root:Path,b2y:Path):
    assets=load_module(repo_root/'tools'/'m10r_b2y_assets.py','m10r_b2y_assets_v072')
    data=b2y.read_bytes(); records=assets.parse_records(data); by=defaultdict(list); sizes=Counter()
    print('\n=== V072 B2Y RECORD MANIFEST ===')
    print(f'V072_B2Y_FILE={b2y}|sha256={hashlib.sha256(data).hexdigest()}|records={len(records)}')
    for r in records:
        blob=data[r.payload_offset:r.payload_offset+r.size];by[r.record_id].append(r);sizes[r.size]+=1
        print(f'V072_RECORD=index={r.index}|id=0x{r.record_id:x}|rel=0x{r.rel_offset:x}|size=0x{r.size:x}|sha256={hashlib.sha256(blob).hexdigest()}|head32={blob[:32].hex()}')
    for rid in sorted(by):
        rs=by[rid];print(f'V072_ID=id=0x{rid:x}|count={len(rs)}|indices={",".join(str(r.index) for r in rs)}|sizes={",".join(hex(r.size) for r in rs)}')
    print('V072_SIZE_SUMMARY='+','.join(f'0x{s:x}:{n}' for s,n in sorted(sizes.items())))
    for label,rid in [('TONE',assets.ID_TONE_TBL0),('DG_MAIN',assets.ID_DG_MAIN),('DG_FL',assets.ID_DG_FL)]:
        rs=by.get(rid,[]); print(f'V072_KNOWN={label}|id=0x{rid:x}|indices={",".join(str(r.index) for r in rs) or "-"}')
    print('\n=== V072 NONLINEAR-UNKNOWN RECORD HEADS ===')
    known={assets.ID_TONE_TBL0,assets.ID_DG_MAIN,assets.ID_DG_FL}
    for r in records:
        if r.record_id in known:continue
        blob=data[r.payload_offset:r.payload_offset+r.size]
        if r.size>=0x20 and any(blob[:min(len(blob),0x40)]):
            u8=list(blob[:min(32,len(blob))]); u16=[struct.unpack_from('<H',blob,o)[0] for o in range(0,min(32,len(blob)-1),2)]
            print(f'V072_CAND=index={r.index}|id=0x{r.record_id:x}|size=0x{r.size:x}|u8={",".join(map(str,u8))}|u16={",".join(map(str,u16))}')

def main():
    if len(sys.argv)!=3:raise SystemExit('usage: script <sections_dir> <repo_root>')
    sec=Path(sys.argv[1]);root=Path(sys.argv[2]);rows=list(csv.DictReader((sec/'sections.csv').open()))
    ir=next(r for r in rows if r['name']=='IMG-System');img=(sec/ir['file']).read_bytes()
    exact=sec/'074_IMG_Calibration_Data_data_calib_B2Y.bin.bin'; cands=sorted(sec.glob('*data_calib_B2Y*.bin*'))
    b2y=exact if exact.exists() else (cands[0] if len(cands)==1 else None)
    if b2y is None:raise SystemExit('B2Y auxiliary file missing/ambiguous')
    trace_code(img);record_manifest(root,b2y)
    print('\nOVERALL_VERDICT=TARGETED_LOOKUP_AND_RECORD_EVIDENCE_RECORDED_NO_FORCED_ID_MAPPING')
if __name__=='__main__':main()
