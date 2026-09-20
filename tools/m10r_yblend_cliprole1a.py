#!/usr/bin/env python3
"""Same-firmware named clip controls; NOT a Y BLEND pixel equation.
Usage: m10r_yblend_cliprole1a.py VERIFIED_SECTIONS OUT [--cases 128]
Requires adjacent retained m10r_yblend_bit15_audit1a.py, capstone 5.0.3, unicorn 2.1.3.
"""
from __future__ import annotations
import argparse, hashlib, json, random, struct
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_REG_PC
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_PC, UC_ARM_REG_SP, UC_ARM_REG_LR
import m10r_yblend_bit15_audit1a as audit

AUDIT_SHA='95d5d3a0663a73261facc888144afcae784c889b6dd9e7e04d02467ca1481313'
B2Y_NAME='074_IMG_Calibration_Data_data_calib_B2Y.bin.bin'
B2Y_SHA='ea935a8006ea3b0a765660bd1d89f6a52c9f60508ee5ba76650005d80372335b'
SUP=0x20070000
LABELS=['Cb positive direction level clip: %d','Cr positive direction level clip: %d',
        'Cb negative direction level clip: %d','Cr negative direction level clip: %d']
REGS=[UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R4,UC_ARM_REG_R5]

def sha(b): return hashlib.sha256(b).hexdigest()
def u32(b,a): return struct.unpack_from('<I',b,a)[0]
def put(b,a,v): struct.pack_into('<I',b,a,v)
def text(b,a): return b[a:].split(b'\0',1)[0].decode('ascii')

def main():
    if not __debug__: raise RuntimeError('Do not disable assertions')
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('sections',type=Path); ap.add_argument('out',type=Path)
    ap.add_argument('--cases',type=int,default=128); args=ap.parse_args()
    if args.cases<8: ap.error('at least eight cases required')
    args.out.mkdir(parents=True,exist_ok=True)
    assert sha(Path(audit.__file__).read_bytes())==AUDIT_SHA
    data={n:(args.sections/n).read_bytes() for n in audit.HASHES}
    for n,h in audit.HASHES.items(): assert sha(data[n])==h,n
    img=data['092_IMG-System.bin']; sam=data['100_IMG-SAM7.bin']
    b2y=(args.sections/B2Y_NAME).read_bytes(); assert sha(b2y)==B2Y_SHA
    identity=audit.validate_identities(img,sam)
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB);md.detail=True
    def ins(b,pc): return next(md.disasm(b[pc:pc+4],pc,count=1))
    guards=[]
    specs=[('SAM7',sam,0x4f326,'I:Im_B2Y_Ctrl_RGB_OutClip error. jyw_no > MAX\n'),
           ('SAM7',sam,0x4f42c,'I:Im_B2Y_Ctrl_JpegXR_OutClip error. jyw_no > MAX\n')]
    specs += [('IMG',img,p,s) for p,s in zip([0x110efe,0x110f0c,0x110f1a,0x110f28],LABELS)]
    specs += [('IMG',img,p,s.replace('%d','0x7FFF' if n<2 else '0x8000'))
              for n,(p,s) in enumerate(zip([0x111974,0x11197c,0x111984,0x11198c],LABELS))]
    for section,b,pc,want in specs:
        i=ins(b,pc);assert i.mnemonic=='adr' and i.operands[1].type==ARM_OP_IMM
        off=((pc+4)&~3)+i.operands[1].imm
        assert text(b,off)==want
        guards.append({'section':section,'adr':hex(pc),'string_offset':hex(off),'text':want})
    # Raw calibration extraction, independent of the retained report.
    count=u32(b2y,12);payload_base=0x14+count*0xa90
    records=[]
    for ix in range(count):
        h=0x14+ix*0xa90
        if u32(b2y,h)==13:
            off=payload_base+u32(b2y,h+4);size=u32(b2y,h+8)
            assert size==24
            vals=list(struct.unpack_from('<6I',b2y,off))
            records.append({'index':ix,'payload_offset':hex(off),'values':vals,'sha256':sha(b2y[off:off+size])})
    assert len(records)==1 and records[0]['values']==[0,32,16383,16383,16383,16383]
    samrun=audit.Programmer(sam,True); imgrun=audit.Programmer(img)
    ui=imgrun.uc;us=samrun.uc
    ui.mem_map(SUP,0x20000)
    histories=[];logs=[];source_writes=0;sup_writes=0;sam_writes=0
    read_log=[]
    def logger(uc,address,size,_):
        p=uc.reg_read(UC_ARM_REG_R1);s=bytes(uc.mem_read(p,128)).split(b'\0',1)[0].decode('ascii')
        logs.append({'label':s,'value_u32':uc.reg_read(UC_ARM_REG_R2),'call_return':hex(uc.reg_read(UC_ARM_REG_LR))})
        # AAPCS caller-saved registers are intentionally clobbered.
        for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2):uc.reg_write(r,0xa55aa55a)
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    ui.hook_add(UC_HOOK_CODE,logger,begin=0x140154,end=0x140154)
    def sourcewrite(*_):
        nonlocal source_writes;source_writes+=1
    for u in [ui,us]:u.hook_add(UC_HOOK_MEM_WRITE,sourcewrite,begin=audit.PARAM,end=audit.PARAM+0xfff)
    def supwrite(*_):
        nonlocal sup_writes;sup_writes+=1
    def samwrite(*_):
        nonlocal sam_writes;sam_writes+=1
    ui.hook_add(UC_HOOK_MEM_WRITE,supwrite,begin=SUP,end=SUP+0x1ffff)
    us.hook_add(UC_HOOK_MEM_WRITE,samwrite,begin=audit.MMIO,end=audit.MMIO+0x3fff)
    def sr(uc,access,address,size,value,_):read_log.append([address-audit.PARAM,size,hex(uc.reg_read(UC_ARM_REG_PC))])
    ui.hook_add(UC_HOOK_MEM_READ,sr,begin=audit.PARAM,end=audit.PARAM+0xfff)
    def slice_run(start,end,pipe,params,old):
        logs.clear();read_log.clear()
        ui.mem_write(audit.PARAM,params);ui.mem_write(SUP,old)
        ui.mem_write(audit.STACK,b'\xa5'*0x10000)
        for r in REGS:ui.reg_write(r,0x5a5a5a5a)
        ui.reg_write(UC_ARM_REG_R4,pipe);ui.reg_write(UC_ARM_REG_R5,audit.PARAM)
        ui.reg_write(UC_ARM_REG_SP,audit.STACK+0xff00);ui.reg_write(UC_ARM_REG_LR,audit.HALT|1)
        ui.emu_start(start|1,end,count=10000)
        assert ui.reg_read(UC_ARM_REG_PC)==end
        assert bytes(ui.mem_read(audit.PARAM,len(params)))==params
        return bytes(ui.mem_read(SUP,len(old)))
    rng=random.Random(0xC11F2026);edges=[0,1,0x1fff,0x3fff,0x4000,0x7fff,0x8000,0xffff]
    full_calls=0;slices=0
    for case in range(args.cases):
        vals=[edges[(case+j)%8] if case<8 else rng.randrange(65536) for j in range(6)]
        old=rng.randbytes(0x4000)
        for entry,name,base0,base1 in [(0x4f30e,'RGB_OutClip',0x2548,0x2580),(0x4f414,'JpegXR_OutClip',0x2554,0x258c)]:
            for pipe,base in [(0,base0),(1,base1)]:
                got=samrun.run(entry,struct.pack('<6H',*vals),old,fallback=pipe,mode_first=True)
                exp=bytearray(old)
                for j in range(3):put(exp,base+4*j,audit.pair(u32(old,base+4*j),vals[2*j],vals[2*j+1]))
                assert got==bytes(exp)
                histories.append({'kind':'complete_SAM7_named_clip','case':case,'name':name,'pipe_selector':pipe,
                    'fields':vals,'base_register':hex(audit.MMIO+base),'result_words':[u32(got,base+4*j) for j in range(3)]})
                full_calls+=1
        fields=vals[:4]
        params=bytearray(rng.randbytes(0x180));struct.pack_into('<4H',params,0x10e,*fields)
        for bank in (0,1):
            oldsup=rng.randbytes(0x20000);o=bank*0x10000
            got=slice_run(0x110c7e,0x110d2a,bank,bytes(params),oldsup)
            exp=bytearray(oldsup)
            put(exp,o+0x350,(u32(oldsup,o+0x350)&0x80008000)|(fields[0]&0x7fff)|((fields[1]&0x7fff)<<16))
            put(exp,o+0x354,fields[2]|(fields[3]<<16))
            assert got==bytes(exp)
            assert [(a,n) for a,n,p in read_log]==[(0x10e,2),(0x110,2),(0x112,2),(0x114,2)]
            g=slice_run(0x110ef8,0x110f30,bank,bytes(params),got)
            assert g==got and [x['label'] for x in logs]==LABELS
            assert [x['value_u32'] for x in logs]==fields
            histories.append({'kind':'SUPPRE_bounded_program_and_diagnostics','case':case,'bank_fixture':bank,
                'fields':fields,'positive_word':u32(g,o+0x350),'negative_word':u32(g,o+0x354),'diagnostics':list(logs)})
            slices+=2
    # Matched fallback programming and literal diagnostic slices, separately bounded.
    defaults=[]
    for bank in (0,1):
        old=rng.randbytes(0x20000);params=rng.randbytes(0x180);o=bank*0x10000
        got=slice_run(0x111840,0x1118cc,bank,params,old)
        exp=bytearray(old);put(exp,o+0x350,(u32(old,o+0x350)&0x80008000)|0x7fff7fff);put(exp,o+0x354,0x80008000)
        assert got==bytes(exp) and not read_log
        keep=slice_run(0x111974,0x111994,bank,params,got)
        assert keep==got
        assert [x['label'] for x in logs]==[s.replace('%d','0x7FFF' if j<2 else '0x8000') for j,s in enumerate(LABELS)]
        defaults.append({'bank_fixture':bank,'positive_word':u32(got,o+0x350),'negative_word':u32(got,o+0x354),'labels':[x['label'] for x in logs]})
        slices+=2
    # A distinct existing Y BLEND fallback is checked for numerical comparison, not connected to SUPPRE.
    old=rng.randbytes(0x4000)
    got=imgrun.run(0xd4480,struct.pack('<6I',*records[0]['values']),old,fallback=1)
    assert got==audit.expected_blend(old,records[0]['values'],True)
    yfallback=[u32(got,0x930+4*j) for j in range(2)]
    assert source_writes==0
    # Candidate arithmetic only: no original instruction computes these samples.
    model_rows=[];samples=[-32768,-20000,-16383,-1,0,1,16383,20000,32767]
    for name,p,n in [('normal',0x3fff,0x3fff),('fallback',0x7fff,0x8000)]:
        model_rows.append({'configuration':name,'assumed_positive_limit':p,'assumed_negative_magnitude':n,
            'samples_in':samples,'candidate_samples_out':[min(p,max(-n,x)) for x in samples]})
    assert all(min(32767,max(-32768,x))==x for x in range(-32768,32768))
    result={'status':'PASS_NAMED_CLIP_ANALOGUE_ONLY','gate_c_passed':False,'renderer_changed':False,
        'source_sha256':sha(Path(__file__).read_bytes()),'firmware_sections_sha256':{**audit.HASHES,B2Y_NAME:B2Y_SHA},
        'seed':'0xC11F2026','identity_guards':identity,'new_label_guards':guards,'yblend_record':records[0],
        'tests':{'parameter_cases':args.cases,'complete_SAM7_clip_entries':full_calls,
            'bounded_SUPPRE_slice_entries':slices,'original_YBLEND_fallback_entries':1,
            'SAM7_MMIO_writes':sam_writes,'SUPPRE_MMIO_writes':sup_writes,'source_parameter_writes':source_writes,
            'full_compared_windows':{'SAM7_bytes':0x4000,'SUPPRE_bytes':0x20000},
            'stubbed':['SAM7 clock helpers 0x4d1b4 / 0x4d118','IMG 0x140154 logger; captures raw arguments then clobbers caller-saved registers'],
            'SUPPRE_fixture_boundary':'r4 is a chosen bank index 0/1; r5 is chosen parameter pointer. Four bounded slices, not the complete selector or routine.'},
        'semantic_bridge':{
            'own_firmware_clip_names':['Im_B2Y_Ctrl_RGB_OutClip','Im_B2Y_Ctrl_JpegXR_OutClip'],
            'named_B2Y_clip_contract':'same low15 / preserved bit15 / high16 interleaved packing as Y BLEND',
            'SUPPRE_positive_source_offsets':['0x10e','0x110'],'SUPPRE_negative_source_offsets':['0x112','0x114'],
            'SUPPRE_positive_register':'0x20070350 + (bank<<16), two 15-bit fields, bits15/31 preserved',
            'SUPPRE_negative_register':'0x20070354 + (bank<<16), two full16-bit fields',
            'SUPPRE_negative_diagnostic':'ldrh zero-extends source values; 0x8000 is passed as 32768, not -32768',
            'hardware_connection_to_YBLEND':'NOT established; different register banks and routines'},
        'SUPPRE_defaults':defaults,'YBLEND_fallback_pair_words':yfallback,
        'candidate_only':{'equation':'min(P,max(-N,x))','normal_limits':[-16383,16383],'fallback_limits':[-32768,32767],
            'model_rows':model_rows,'fallback_identity_over_assumed_signed16_domain':True,
            'sample_tests_execute_ISP':False,'countermodel':'Raw signed-endpoint interpretations and ignored/disabled fields are not globally excluded; no hardware output was measured.',
            'scope':'P/N magnitude interpretation is now a same-firmware-supported candidate, not an established Y BLEND equation or channel assignment.'},
        'remaining':['Y BLEND source signals and ratio direction/denominator','Y BLEND pair identities and activation','edge controls 0x20020e00 value2 meanings','pixel ordering scaling rounding and clipping','physical camera or exact-revision hardware oracle']}
    assert full_calls==4*args.cases and slices==4*args.cases+4
    assert sam_writes==24*args.cases and sup_writes==8*args.cases+8
    listing=[]
    ranges=[('SAM7 RGB_OutClip',sam,0x4f30e,0x4f414),('SAM7 JpegXR_OutClip',sam,0x4f414,0x4f51a),
            ('IMG SUPPRE clip programmer slice',img,0x110c7e,0x110d2a),('IMG SUPPRE clip logger slice',img,0x110ef8,0x110f30),
            ('IMG SUPPRE default clip slice',img,0x111840,0x1118cc),('IMG SUPPRE default logger slice',img,0x111974,0x111994)]
    for name,b,a,z in ranges:
        listing.append('\n'+name)
        for i in md.disasm(b[a:z],a):
            s=f'{i.address:08x}: {i.bytes.hex():8} {i.mnemonic:8} {i.op_str}'
            if i.mnemonic=='adr':
                q=((i.address+4)&~3)+i.operands[1].imm;s+=f' ; [{q:#x}] {text(b,q)!r}'
            if i.mnemonic=='ldr' and i.operands[1].type==ARM_OP_MEM and i.operands[1].mem.base==ARM_REG_PC:
                q=((i.address+4)&~3)+i.operands[1].mem.disp;s+=f' ; literal[{q:#x}]={u32(b,q):#x}'
            listing.append(s)
    (args.out/'cliprole_results.json').write_text(json.dumps(result,indent=2)+'\n')
    (args.out/'execution_histories.json').write_text(json.dumps(histories,indent=2)+'\n')
    (args.out/'original_instruction_anchors.txt').write_text('\n'.join(listing)+'\n')
    print(json.dumps({'status':result['status'],'tests':result['tests']},indent=2))

if __name__=='__main__':main()
