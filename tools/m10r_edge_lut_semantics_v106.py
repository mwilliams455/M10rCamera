#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, re, struct, sys
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN

PFX=4; HDR=PFX+0x10; STRIDE=0xA90
NAMES={0x0F:'HF_CTRL',0x10:'LF_CTRL',0x11:'EDGE_SYNTH',0x1E:'HF_T1',0x1F:'HF_T2',0x20:'HF_T3',0x21:'HF_T4',0x22:'LF_T1',0x23:'LF_T2',0x24:'LF_T3',0x25:'LF_T4'}

def u32(b,o): return struct.unpack_from('<I',b,o)[0]
def s32arr(b): return list(struct.unpack_from('<'+'i'*(len(b)//4),b,0))
def u16arr(b): return list(struct.unpack_from('<'+'H'*(len(b)//2),b,0))

def ascii_runs(b,minlen=6):
    out=[];i=0
    while i<len(b):
        if 32<=b[i]<127:
            j=i
            while j<len(b) and 32<=b[j]<127:j+=1
            if j-i>=minlen: out.append((i,b[i:j].decode('ascii','replace')))
            i=j
        else:i+=1
    return out

def records(data):
    count=u32(data,PFX+8); pbase=HDR+count*STRIDE; out=[]
    for i in range(count):
        h=HDR+i*STRIDE; rid,rel,size=u32(data,h),u32(data,h+4),u32(data,h+8)
        out.append((i,rid,data[h:h+STRIDE],data[pbase+rel:pbase+rel+size]))
    return out

def sels(h):return [s for _,s in ascii_runs(h) if '_B2YMODE:' in s]

def piecewise(vals):
    # Return maximal ranges where first-difference is constant. This makes the
    # 14-bit table's shape visible without dumping all 16k values.
    if len(vals)<2:return []
    out=[]; start=0; d=vals[1]-vals[0]
    for i in range(1,len(vals)-1):
        nd=vals[i+1]-vals[i]
        if nd!=d:
            out.append((start,i,d,vals[start],vals[i]))
            start=i; d=nd
    out.append((start,len(vals)-1,d,vals[start],vals[-1]))
    return out

def get_img_system(sections):
    rows=list(csv.DictReader((sections/'sections.csv').open()))
    r=next(x for x in rows if x['name']=='IMG-System')
    return (sections/r['file']).read_bytes(),int(r['image_base'],16),r['file']

def dump_context(img,base,va,label,before=0x60,after=0x70):
    # Try several even starts; choose the one whose disassembly contains the exact
    # call address. This avoids obvious half-instruction starts in Thumb code.
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN)
    for back in range(before,before+8,2):
        start=max(base,va-back); off=start-base
        ins=list(md.disasm(img[off:off+back+after],start))
        if any(x.address==va for x in ins):
            print(f'V106_CONTEXT={label}|site=0x{va:08x}|start=0x{start:08x}')
            for x in ins:
                if va-before//2 <= x.address <= va+after//2:
                    mark='*' if x.address==va else ' '
                    print(f' {mark}0x{x.address:08x}|{x.mnemonic} {x.op_str}')
            return
    print(f'V106_CONTEXT_FAIL={label}|site=0x{va:08x}')

def main():
    if len(sys.argv)!=3: raise SystemExit('usage: m10r_edge_lut_semantics_v106.py <sections_dir> <b2y>')
    sections=Path(sys.argv[1]); b2y=Path(sys.argv[2]).read_bytes(); rs=records(b2y)
    print(f'V106_B2Y=0x{len(b2y):x}|records={len(rs)}')

    # Exact representative STILL/MEDIUM control records, entire payload.
    print('\n=== V106_FULL_CONTROL_PAYLOADS ===')
    for rid in (0x0F,0x10,0x11):
        for idx,r,h,p in rs:
            ss=sels(h)
            ok=any('STILL_SHARPNESS:MEDIUM_ISO:100' in s for s in ss) if rid in (0x0F,0x10) else any(s=='_B2YMODE:STILL_ISO:100' for s in ss)
            if ok:
                a=s32arr(p)
                print(f'V106_CTRL={NAMES[rid]}|idx={idx}|bytes=0x{len(p):x}|dwords={len(a)}|sha256={hashlib.sha256(p).hexdigest()}')
                print('V106_CTRL_S32='+','.join(f'{i}:{v}' for i,v in enumerate(a)))
                break

    # Full 14-bit edge LUT shape at useful coordinates + exact piecewise runs.
    table={rid:p for _,rid,_,p in rs if 0x1E<=rid<=0x25}
    t1=u16arr(table[0x1E]); t3=u16arr(table[0x20])
    print('\n=== V106_TABLE1_14BIT_SHAPE ===')
    samples=sorted(set(list(range(0,len(t1),256))+[0,512,1024,1280,1284,1536,2048,2560,3072,4096,6144,8192,10240,12288,14336,15360,16000,16383]))
    print('V106_T1_SAMPLES='+','.join(f'{i}:{t1[i]}' for i in samples if i<len(t1)))
    runs=piecewise(t1)
    print(f'V106_T1_DIFF_RUNS_COUNT={len(runs)}')
    # Many constant-difference runs can be 1-5 samples due integer interpolation;
    # print first/last plus long runs and all extrema/plateaus.
    keep=[]
    for j,r in enumerate(runs):
        s,e,d,v0,v1=r
        if j<30 or j>=len(runs)-30 or e-s>=32 or v0 in (358,767,1023) or v1 in (358,767,1023): keep.append(r)
    print('V106_T1_DIFF_RUNS='+';'.join(f'{s}-{e}:d{d}:{v0}->{v1}' for s,e,d,v0,v1 in keep[:300]))
    mx=max(t1); mn=min(t1)
    maxi=[i for i,v in enumerate(t1) if v==mx]; mini=[i for i,v in enumerate(t1) if v==mn]
    print(f'V106_T1_EXTREMA=min={mn}@{mini[0]}..{mini[-1]}|max={mx}@{maxi[0]}..{maxi[-1]}')
    print(f'V106_T1_Q10_HINT=max={mx};1023_is_10bit_fullscale_not_a_claim_of_unity')
    print(f'V106_T3_IDENTITY={all(i==v for i,v in enumerate(t3))}|len={len(t3)}|max={max(t3)}')

    # Show representative caller contexts from v105 direct-call census.
    img,base,imgfile=get_img_system(sections)
    print(f'\nV106_IMG_SYSTEM={imgfile}|base=0x{base:08x}|size=0x{len(img):x}')
    sites=[
      (0x001540D8,'EDGE_SYNTH_CALL'),
      (0x00154202,'HF_CTRL_CALL'),
      (0x0015422C,'HF_T1_CALL'),(0x00154256,'HF_T2_CALL'),(0x00154286,'HF_T3_CALL'),(0x001542B0,'HF_T4_CALL'),
      (0x00154596,'LF_CTRL_CALL'),
      (0x001545C0,'LF_T1_CALL'),(0x001545EA,'LF_T2_CALL'),(0x0015461A,'LF_T3_CALL'),(0x00154644,'LF_T4_CALL'),
    ]
    print('\n=== V106_CALLER_CONTEXTS ===')
    for va,label in sites: dump_context(img,base,va,label)

    # Firmware string census across extracted sections. This can recover API/debug
    # terminology that constrains table semantics without guessing from values.
    print('\n=== V106_EDGE_STRINGS ===')
    pats=('B2Y','HighFreq','LowFreq','Edge','EDGE','Coring','CORING','Synthesis','SYNTHESIS','Sharp','SHARP')
    emitted=0
    for f in sorted(sections.iterdir()):
        if not f.is_file() or f.name=='sections.csv': continue
        try:b=f.read_bytes()
        except Exception:continue
        for off,s in ascii_runs(b,6):
            if any(p in s for p in pats):
                if len(s)>240:s=s[:240]
                print(f'V106_STRING=file={f.name}|off=0x{off:x}|{s}')
                emitted+=1
                if emitted>=1200: break
        if emitted>=1200: break
    print(f'V106_EDGE_STRING_COUNT_EMITTED={emitted}')

    # Hard renderer-relevant conclusions which are structural, not arithmetic guesses.
    print('\n=== V106_STRUCTURAL_VERDICT ===')
    print(f'V106_TABLE1_ALL_HF_LF_IDENTICAL={table[0x1E]==table[0x1F]==table[0x22]==table[0x23]}')
    print(f'V106_TABLE34_ALL_HF_LF_IDENTICAL={table[0x20]==table[0x21]==table[0x24]==table[0x25]}')
    print('V106_TABLE_SIZES=TABLE1_2_14BIT_ADDRESS_SPACE_16384x16;TABLE3_4_13BIT_ADDRESS_SPACE_8192x16')
    print('V106_CAUTION=Address_space_sizes_strongly_constrain_coordinates_but_do_not_by_themselves_prove_signal_semantics_or_Q_scale')
    print('OVERALL_VERDICT=V106_EDGE_LUT_SHAPE_CALLER_AND_STRING_EVIDENCE_EXTRACTED')

if __name__=='__main__':main()
