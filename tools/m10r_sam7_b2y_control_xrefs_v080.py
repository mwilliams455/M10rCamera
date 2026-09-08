#!/usr/bin/env python3
"""v0.80: recover IMG-SAM7 B2Y control string xrefs correctly.

v0.79 searched pointers to the stable `Im_B2Y...` substring, but the actual C
strings have short prefixes such as `I:` / `CI:`.  This probe first recovers
the complete printable run start for each diagnostic string, then:

  1. searches exact offset pointers (base==0 control),
  2. infers a common runtime/link base from 32-bit pointer words that resolve
     to three or more of the seven target strings, and
  3. resolves ARM and Thumb PC-relative literal loads to those pointer slots.

No function identity is promoted from proximity alone.  Candidate bases are
reported with cross-target support so relocation evidence stays auditable.
"""
from __future__ import annotations
import collections,csv,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_MEM,ARM_REG_PC

TARGETS={
 'GAMMA':'Im_B2Y_Ctrl_Gamma error. b2y_ctrl_gamma = NULL',
 'CC1':'Im_B2Y_Ctrl_CC_Matrix error. b2y_ctrl_cc1 = NULL',
 'YCC':'Im_B2Y_Ctrl_Yc_Convert error. b2y_ctrl_ycc = NULL',
 'CHROMA_SUPPRESS':'Im_B2Y_Ctrl_Chroma_Suppress error. b2y_ctrl_cs = NULL',
 'COLOR_NR':'Im_B2Y_Ctrl_Color_NR error. b2y_ctrl_clpf = NULL',
 'POSTFILTER':'Im_B2Y_Ctrl_PostFilter error. b2y_ctrl_post_filter = NULL',
 'EDGEBLEND':'Im_B2Y_Ctrl_EdgeBlend error. b2y_ctrl_edge_blend = NULL',
}

def printable(b:int)->bool:return 32<=b<127

def full_run(data:bytes,inside:int)->tuple[int,int,str]:
    lo=inside
    while lo>0 and printable(data[lo-1]):lo-=1
    hi=inside
    while hi<len(data) and printable(data[hi]):hi+=1
    return lo,hi,data[lo:hi].decode('ascii','replace')

def u32(data:bytes,o:int)->int:return struct.unpack_from('<I',data,o)[0]

def ptr_offsets(data:bytes,value:int)->list[int]:
    pat=struct.pack('<I',value&0xffffffff);out=[];p=0
    while True:
        q=data.find(pat,p)
        if q<0:break
        out.append(q);p=q+1
    return out

def literal_refs(data:bytes,base:int,lit:int):
    out=[]
    for mode_name,mode,step in [('ARM',CS_MODE_ARM,4),('THUMB',CS_MODE_THUMB,2)]:
        md=Cs(CS_ARCH_ARM,mode|CS_MODE_LITTLE_ENDIAN);md.detail=True
        start=max(0,lit-0x5000);end=min(len(data)-4,lit+0x100)
        for off in range(start,end,step):
            ins=next(md.disasm(data[off:off+4],(base+off)&0xffffffff,count=1),None)
            if ins is None:continue
            try:ops=ins.operands
            except Exception:continue
            for op in ops:
                if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
                    pc=((ins.address+8)&0xffffffff) if mode_name=='ARM' else (((ins.address+4)&~3)&0xffffffff)
                    target=((pc+int(op.mem.disp))-base)&0xffffffff
                    if target==lit:
                        out.append((mode_name,off,ins.mnemonic,ins.op_str));break
    return out

def main():
    if len(sys.argv)!=2:raise SystemExit('usage: m10r_sam7_b2y_control_xrefs_v080.py <sections_dir>')
    root=Path(sys.argv[1]);rows=list(csv.DictReader((root/'sections.csv').open()));row=next(r for r in rows if r['name']=='IMG-SAM7')
    data=(root/row['file']).read_bytes();declared=int(row['image_base'],16)
    strings={}
    print(f'V080_SAM7=file={row["file"]}|size=0x{len(data):x}|declared_image_base=0x{declared:08x}|kind={row["kind"]}')
    for label,needle in TARGETS.items():
        inside=data.find(needle.encode('ascii'))
        if inside<0:
            print(f'V080_STRING={label}|NOT_FOUND');continue
        lo,hi,text=full_run(data,inside);strings[label]=lo
        print(f'V080_STRING={label}|substring=0x{inside:x}|run_start=0x{lo:x}|prefix_delta={inside-lo}|run_end=0x{hi:x}|text={text}')

    # Infer a common base: an aligned 32-bit word W is a pointer to target T if
    # W == base + target_run_start.  A real link/load base should recur across
    # several independent target strings.
    support=collections.defaultdict(lambda:collections.defaultdict(list))
    for off in range(0,len(data)-3,4):
        w=u32(data,off)
        for label,soff in strings.items():
            base=(w-soff)&0xffffffff
            # ARM images are normally at least 4 KiB aligned. Keep base 0 too.
            if base==0 or (base&0xfff)==0:
                support[base][label].append(off)
    ranked=[]
    for base,bylabel in support.items():
        if len(bylabel)>=2:
            ranked.append((len(bylabel),sum(len(v) for v in bylabel.values()),base,bylabel))
    ranked.sort(reverse=True)
    print('\n=== V080 COMMON BASE CANDIDATES ===')
    for nlab,nptr,base,bylabel in ranked[:20]:
        print(f'V080_BASE=0x{base:08x}|targets={nlab}|ptrs={nptr}|labels={",".join(sorted(bylabel))}')
    strong=[x for x in ranked if x[0]>=3]
    bases=[]
    if any(x[2]==declared for x in strong):bases.append(declared)
    for x in strong:
        if x[2] not in bases:bases.append(x[2])
    if not bases:
        bases=[declared]
    print(f'V080_SELECTED_BASES={",".join(f"0x{x:08x}" for x in bases[:8])}')

    print('\n=== V080 POINTERS AND CODE XREFS ===')
    xcount=0
    for base in bases[:8]:
        for label,soff in strings.items():
            value=(base+soff)&0xffffffff
            ptrs=ptr_offsets(data,value)
            if ptrs:print(f'V080_PTR={label}|base=0x{base:08x}|value=0x{value:08x}|count={len(ptrs)}|offs={",".join(hex(x) for x in ptrs)}')
            for lit in ptrs:
                refs=literal_refs(data,base,lit)
                for mode,code,mn,ops in refs:
                    print(f'V080_XREF={label}|base=0x{base:08x}|mode={mode}|code_off=0x{code:x}|va=0x{(base+code)&0xffffffff:08x}|literal_off=0x{lit:x}|{mn} {ops}')
                    xcount+=1
    print(f'V080_XREF_COUNT={xcount}')
    print('OVERALL_VERDICT=SAM7_FULL_STRING_POINTER_AND_RUNTIME_BASE_XREFS_ENUMERATED')
if __name__=='__main__':main()
