#!/usr/bin/env python3
"""M10-R v0.70: trace CI:Im_B2Y_Set_WB_Clip_Level and close fallback arithmetic.

Research-only. No renderer/application files are modified.
"""
from __future__ import annotations
from pathlib import Path
import re, struct, sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_REG_PC
from m10r_wb_direct_consumer_v056 import get_img_section, derive_mapping, u32, read_cstr_va

TARGET_S = b"CI:Im_B2Y_Set_WB_Clip_Level"
FAMILY_PREFIX = b"CI:Im_B2Y_Set_"
WBCLIP_DRIVER = 0x420D42DC
WB_PAGE = 0x20020080


def cstr_at(data: bytes, off: int, lim=200):
    if not (0 <= off < len(data)): return None
    e=data.find(b'\0',off,min(len(data),off+lim))
    if e<0: return None
    try: s=data[off:e].decode('ascii')
    except Exception: return None
    return s if s and all(32<=ord(c)<127 for c in s) else None


def all_cstrings(data: bytes, prefix: bytes):
    out=[]; p=0
    while True:
        p=data.find(prefix,p)
        if p<0: break
        s=cstr_at(data,p)
        if s: out.append((p,s))
        p+=1
    # de-dupe embedded prefix hits at same start/string
    seen=set(); ret=[]
    for x in out:
        if x not in seen: seen.add(x); ret.append(x)
    return ret


def pc_literal(ins,data,bias):
    try: ops=list(ins.operands)
    except Exception: return None
    for op in ops:
        if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
            p=((ins.address+4)&~3)+int(op.mem.disp)
            v=u32(data,p-bias)
            if v is not None:return p,v
    return None


def branch_target(ins):
    if ins.mnemonic.lower() not in ('bl','blx'): return None
    try:
        for op in ins.operands:
            if op.type==ARM_OP_IMM:return int(op.imm)&0xffffffff
    except Exception: pass
    return None


def adr_target(ins):
    if ins.mnemonic.lower()!='adr': return None
    # Match the convention already validated by the v056 probe.
    m=re.search(r'#(0x[0-9a-f]+|\d+)',ins.op_str.lower())
    if not m:return None
    imm=int(m.group(1),0)
    return ((ins.address+4)&~3)+imm


def disasm_window(md,data,bias,st,maxlen=0x180):
    st &= ~1; off=st-bias
    if not (0<=off<len(data)):return []
    out=[]
    for ins in md.disasm(data[off:min(len(data),off+maxlen)],st):
        out.append(ins)
        m=ins.mnemonic.lower(); o=ins.op_str.lower()
        if (m=='pop' and 'pc' in o) or (m=='bx' and o.strip()=='lr'):break
    return out


def plausible_func(md,data,bias,va):
    st=va&~1; off=st-bias
    if not (0<=off<len(data)-4):return False
    ins=next(md.disasm(data[off:off+4],st,count=1),None)
    if not ins:return False
    m=ins.mnemonic.lower(); op=ins.op_str.lower()
    return (m=='push' and 'lr' in op) or m in ('cmp','mov','movs','ldr','sub','subs')


def direct_code_xrefs(md,data,bias,target_va):
    x=[]
    # Full IMG scan, aligned Thumb starts. We deliberately recognize only
    # exact PC-literal and ADR references; no speculative MOVW/MOVT folding.
    for off in range(0,len(data)-4,2):
        ins=next(md.disasm(data[off:off+4],bias+off,count=1),None)
        if not ins: continue
        lv=pc_literal(ins,data,bias)
        if lv and lv[1]==target_va:x.append((ins.address,'LDR_LITERAL',lv[0]))
        at=adr_target(ins)
        if at==target_va:x.append((ins.address,'ADR',None))
    return x


def pointer_table_hits(data,bias,target_va):
    n=struct.pack('<I',target_va); out=[]; p=0
    while True:
        p=data.find(n,p)
        if p<0:break
        out.append(p); p+=1
    return out


def dump_table_context(md,data,bias,off,tag):
    print(f'V070_TABLE_CONTEXT_BEGIN={tag}|ptr_va=0x{bias+off:08x}')
    candidates=[]
    a=max(0,off-0x30); b=min(len(data),off+0x34)
    a &= ~3
    for q in range(a,b,4):
        v=u32(data,q)
        if v is None:continue
        cls='VALUE'; s=None
        vv=v&~1
        if 0x42000000<=v<0x43000000:
            s=read_cstr_va(data,bias,v)
            if s:cls='STRING'
            else:cls='IMG_PTR'
        elif 0x42000000<=vv<0x43000000:
            cls='IMG_THUMB_PTR'
        print(f'V070_TABLE_WORD={tag}|rel={q-off:+#x}|word_va=0x{bias+q:08x}|value=0x{v:08x}|{cls}|str={s!r}')
        if cls in ('IMG_PTR','IMG_THUMB_PTR') and plausible_func(md,data,bias,v):
            candidates.append(v)
    # De-dupe candidate handlers and decode tightly.
    seen=set()
    for v in candidates:
        st=v&~1
        if st in seen:continue
        seen.add(st)
        seq=disasm_window(md,data,bias,st,0x180)
        calls=[(i.address,branch_target(i)) for i in seq if branch_target(i) is not None]
        uses_driver=any(t==WBCLIP_DRIVER for _,t in calls)
        # Basic parser clues: halfword/byte loads, compares, immediate masks.
        ldrh=sum(i.mnemonic.lower()=='ldrh' for i in seq)
        ldrsh=sum(i.mnemonic.lower()=='ldrsh' for i in seq)
        cmp_imms=[]
        for i in seq:
            if i.mnemonic.lower() in ('cmp','cmn') and '#' in i.op_str:
                cmp_imms.append(i.op_str)
        print(f'V070_HANDLER_CANDIDATE={tag}|0x{st:08x}|insns={len(seq)}|calls_driver={int(uses_driver)}|ldrh={ldrh}|ldrsh={ldrsh}|cmps={";".join(cmp_imms[:16]) or "-"}')
        for i in seq[:96]:
            bt=branch_target(i)
            tail=f' ; call=0x{bt:08x}' if bt is not None else ''
            print(f'V070_HANDLER_DISASM={tag}|{i.address:08x}: {i.mnemonic:<8} {i.op_str}{tail}'.rstrip())


def fallback_literals(md,data,bias):
    seq=disasm_window(md,data,bias,WBCLIP_DRIVER,0xa0)
    vals=[]
    for i in seq:
        lv=pc_literal(i,data,bias)
        if lv:
            vals.append((i.address,lv[0],lv[1]))
            print(f'V070_WBCLIP_LITERAL=0x{i.address:08x}|pool=0x{lv[0]:08x}|value=0x{lv[1]:08x}')
    has_page=any(v==WB_PAGE for _,_,v in vals)
    has_ffff=any(v==0x0000ffff for _,_,v in vals)
    # Exact instruction pattern from the verified firmware:
    by={i.address:(i.mnemonic.lower(),i.op_str.lower().replace(' ','')) for i in seq}
    p1=(by.get(0x420d4338)==('ldr','r2,[r2,#0x14]') and
        by.get(0x420d433a)==('lsrs','r2,r2,#0x10') and
        by.get(0x420d433c)==('lsls','r2,r2,#0x10') and
        by.get(0x420d4340)==('adds','r3,r2,r3') and
        by.get(0x420d4346)==('ldr','r2,[r2,#0x14]') and
        by.get(0x420d4348)==('lsls','r2,r2,#0x10') and
        by.get(0x420d434a)==('lsrs','r2,r2,#0x10') and
        by.get(0x420d434c)==('movs','r3,#1') and
        by.get(0x420d434e)==('lsls','r3,r3,#0x10') and
        by.get(0x420d4350)==('subs','r3,r2,r3') and
        by.get(0x420d4354)==('str','r3,[r2,#0x14]'))
    p2=(by.get(0x420d4356)==('ldr','r2,[r2,#0x18]') and
        by.get(0x420d4358)==('lsrs','r2,r2,#0x10') and
        by.get(0x420d435a)==('lsls','r2,r2,#0x10') and
        by.get(0x420d435e)==('adds','r3,r2,r3') and
        by.get(0x420d4364)==('ldr','r2,[r2,#0x18]') and
        by.get(0x420d4366)==('lsls','r2,r2,#0x10') and
        by.get(0x420d4368)==('lsrs','r2,r2,#0x10') and
        by.get(0x420d436a)==('movs','r3,#1') and
        by.get(0x420d436c)==('lsls','r3,r3,#0x10') and
        by.get(0x420d436e)==('subs','r3,r2,r3') and
        by.get(0x420d4372)==('str','r3,[r2,#0x18]'))
    proven=has_page and has_ffff and p1 and p2
    print(f'V070_FFFF_LITERAL_PRESENT={int(has_ffff)}')
    print(f'V070_WB_PAGE_LITERAL_PRESENT={int(has_page)}')
    print(f'V070_FALLBACK_PATTERN_REG14={int(p1)}')
    print(f'V070_FALLBACK_PATTERN_REG18={int(p2)}')
    print(f'V070_FFFF_FALLBACK_SYMBOLIC={"BOTH_REGISTERS_FORCE_0xffffffff" if proven else "UNRESOLVED"}')
    return proven


def main():
    if len(sys.argv)!=2:raise SystemExit(f'usage: {sys.argv[0]} sections_dir')
    root=Path(sys.argv[1]); imgs=get_img_section(root)
    print(f'V070_IMG_SECTIONS={len(imgs)}')
    if len(imgs)!=1:
        print('OVERALL_VERDICT=UNRESOLVED_IMG');return
    _,data=imgs[0]; _,bias=derive_mapping(data)
    if bias is None:
        print('OVERALL_VERDICT=UNRESOLVED_MAP');return
    print(f'V070_MAP_BIAS=0x{bias:08x}')
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True

    fam=all_cstrings(data,FAMILY_PREFIX)
    print(f'V070_CI_B2Y_SET_FAMILY={len(fam)}')
    for off,s in fam:
        print(f'V070_CI_FAMILY_STRING=0x{bias+off:08x}|{s}')

    hits=[]; p=0
    while True:
        p=data.find(TARGET_S,p)
        if p<0:break
        hits.append(p);p+=1
    print(f'V070_CI_WBCLIP_STRING_HITS={len(hits)}')
    all_handlers=[]
    for idx,off in enumerate(hits):
        va=bias+off
        print(f'V070_CI_WBCLIP_STRING={idx}|va=0x{va:08x}|off=0x{off:x}')
        xrefs=direct_code_xrefs(md,data,bias,va)
        print(f'V070_CI_WBCLIP_CODE_XREFS={idx}|count={len(xrefs)}')
        for a,k,pool in xrefs:
            print(f'V070_CI_WBCLIP_CODE_XREF={idx}|0x{a:08x}|{k}|pool={"0x%08x"%pool if pool else "-"}')
        ptrs=pointer_table_hits(data,bias,va)
        print(f'V070_CI_WBCLIP_PTR_HITS={idx}|count={len(ptrs)}')
        for j,q in enumerate(ptrs[:16]):
            dump_table_context(md,data,bias,q,f'{idx}.{j}')

    fb=fallback_literals(md,data,bias)
    # The CI string can prove interface/handler semantics only if we find a
    # concrete table/code edge. FFFF meaning is intentionally left unresolved
    # unless such code names it.
    print('V070_FFFF_DISABLE_OR_MAX_PROVEN=0')
    print('V070_SIGNED_MINUS2001_SUPPORTED=0')
    if hits and fb:
        print('OVERALL_VERDICT=CI_WBCLIP_EDGE_TRACED_AND_FFFF_HARDWARE_STATE_PROVEN_SEMANTIC_MEANING_OPEN')
    else:
        print('OVERALL_VERDICT=CI_WBCLIP_TRACE_INCOMPLETE')
if __name__=='__main__':main()
