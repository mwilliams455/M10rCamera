#!/usr/bin/env python3
"""Y BLEND producer evidence: original selector + lookup + driver, not an ISP emulator.
Usage: script.py SECTIONS REPO_ROOT OUT_DIR [--stress-cases 1024]
Requires the retained BIT15 audit module, Capstone 5.0.3 and Unicorn 2.1.3.
Only file-registry resolution and diagnostic logging are stubbed in these tests.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, random, struct, sys
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_ARM
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_REG_PC
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_PC, UC_ARM_REG_LR

SECTION='074_IMG_Calibration_Data_data_calib_B2Y.bin.bin'
B2Y_SHA='ea935a8006ea3b0a765660bd1d89f6a52c9f60508ee5ba76650005d80372335b'
AUDIT_SHA='95d5d3a0663a73261facc888144afcae784c889b6dd9e7e04d02467ca1481313'
CALIB=0x12000000; REGISTRY=0x13000000; CACHE=0x408cedbf
SELECTOR=0x154e18; LOOKUP=0x1a0fc4; DRIVER=0xd4480

def digest(b): return hashlib.sha256(b).hexdigest()
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise RuntimeError(str(path))
    m=importlib.util.module_from_spec(spec); sys.modules[name]=m; spec.loader.exec_module(m); return m

def main():
    if not __debug__: raise RuntimeError('Assertions must remain enabled; do not use python -O')
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('sections',type=Path); ap.add_argument('repo',type=Path); ap.add_argument('out',type=Path)
    ap.add_argument('--stress-cases',type=int,default=1024)
    args=ap.parse_args()
    if args.stress_cases<7: ap.error('at least seven stress cases required')
    args.out.mkdir(parents=True,exist_ok=True)
    tool=args.repo/'tools/m10r_yblend_bit15_audit1a.py'
    assert digest(tool.read_bytes())==AUDIT_SHA
    audit=load('retained_bit15_audit',tool)
    parser=load('retained_b2y_assets',args.repo/'tools/m10r_b2y_assets.py')
    img=(args.sections/'092_IMG-System.bin').read_bytes()
    sam=(args.sections/'100_IMG-SAM7.bin').read_bytes()
    b2y=(args.sections/SECTION).read_bytes()
    assert digest(img)==audit.HASHES['092_IMG-System.bin']
    assert digest(sam)==audit.HASHES['100_IMG-SAM7.bin']
    assert digest(b2y)==B2Y_SHA
    identities=audit.validate_identities(img,sam)
    records=parser.parse_records(b2y)
    extracted=[]
    for rid in [12,13]:
        selected=[r for r in records if r.record_id==rid]
        assert len(selected)==1
        r=selected[0]; h=0x14+r.index*0xa90
        key_count=audit.u32(b2y,h+12)
        keys=[b2y[h+16+k*64:h+16+(k+1)*64].split(b'\0',1)[0].decode('ascii') for k in range(key_count)]
        blob=b2y[r.payload_offset:r.payload_offset+r.size]
        extracted.append(dict(record_id=rid,index=r.index,header_offset=hex(h),
            header_first16_hex=b2y[h:h+16].hex(),key_count=key_count,keys=keys,
            payload_offset=hex(r.payload_offset),payload_size=r.size,
            payload_hex=blob.hex(),payload_sha256=digest(blob),
            values_u32=list(struct.unpack('<'+'I'*(r.size//4),blob))))
    normal=extracted[1]['values_u32']
    assert normal==[0,32,16383,16383,16383,16383]
    assert extracted[1]['keys']==[''] and img[0x154e74]==0
    r=next(r for r in records if r.record_id==13)
    header=0x14+r.index*0xa90
    payload=CALIB+r.payload_offset-4  # loader strips the extracted section prefix
    original=b2y[4:]
    programmer=audit.Programmer(img); u=programmer.uc
    u.mem_map(CALIB,0x200000);u.mem_write(CALIB,original)
    u.mem_map(REGISTRY,0x1000);u.mem_write(REGISTRY+0x208,struct.pack('<I',CALIB))
    u.mem_map(CACHE&~4095,4096)
    state={'file_available':True,'arg0':0,'events':[],'payload_reads':[],
           'input_reads':0,'calibration_writes':0,'mmio_writes':0}
    def code_hook(uc,address,size,_):
        if address==SELECTOR: uc.reg_write(UC_ARM_REG_R0,state['arg0'])
        elif address==0x1a0c80:
            p=uc.reg_read(UC_ARM_REG_R0)
            assert bytes(uc.mem_read(p,8)).split(b'\0',1)[0]==b'B2Y.bin'
            uc.reg_write(UC_ARM_REG_R0,REGISTRY if state['file_available'] else 0)
            uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
        elif address==0x140154:
            uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
        elif address==LOOKUP:
            assert uc.reg_read(UC_ARM_REG_R1)==13
            assert uc.mem_read(uc.reg_read(UC_ARM_REG_R2),1)==b'\0'
            state['events'].append({'lookup':13,'key':''})
        elif address==DRIVER:
            p=uc.reg_read(UC_ARM_REG_R0);f=uc.reg_read(UC_ARM_REG_R1)
            state['events'].append({'driver_pointer':hex(p),'fallback':f,
                'values':list(struct.unpack('<6I',uc.mem_read(p,24))) if p else None})
    for pc in [SELECTOR,0x1a0c80,0x140154,LOOKUP,DRIVER]:
        u.hook_add(UC_HOOK_CODE,code_hook,begin=pc,end=pc)
    def source_read(uc,access,address,size,value,_):
        pc=uc.reg_read(UC_ARM_REG_PC)
        if DRIVER<=pc<0xd450a:
            state['payload_reads'].append((address-payload,size,pc))
    u.hook_add(UC_HOOK_MEM_READ,source_read,begin=payload,end=payload+23)
    def input_read(*unused): state['input_reads']+=1
    def source_write(*unused): state['calibration_writes']+=1
    def mmio_write(uc,access,address,size,value,_):
        if address in (0x2002092c,0x20020930,0x20020934):state['mmio_writes']+=1
    u.hook_add(UC_HOOK_MEM_READ,input_read,begin=audit.PARAM,end=audit.PARAM+0xfff)
    u.hook_add(UC_HOOK_MEM_WRITE,source_write,begin=CALIB,end=CALIB+len(original)-1)
    u.hook_add(UC_HOOK_MEM_WRITE,mmio_write,begin=audit.MMIO,end=audit.MMIO+0x3fff)
    rng=random.Random(0xD44802026)
    counts={'normal_programming':0,'fallback_programming':0,'cached_skip':0}
    scenarios=[]; payload_loads=set(); checked=0
    expected_loads=[(0,1),(4,4),(8,2),(12,2),(16,2),(20,2)]
    def case(cached,flag,arg0,values,lookup_ok):
        nonlocal checked
        state['arg0']=arg0;state['events']=[];state['payload_reads']=[]
        u.mem_write(CACHE,bytes([cached]))
        u.mem_write(audit.STACK,rng.randbytes(0x10000))
        old=rng.randbytes(0x4000)
        got=programmer.run(SELECTOR,rng.randbytes(512),old,fallback=flag)
        skip=cached==1 and flag==1
        kind='cached_skip' if skip else ('normal_programming' if lookup_ok else 'fallback_programming')
        exp=old if skip else audit.expected_blend(old,values,not lookup_ok)
        assert got==exp,(kind,cached,flag,hex(arg0))
        cache_after=u.mem_read(CACHE,1)[0]
        assert cache_after==(cached if skip else int(lookup_ok))
        if skip:
            assert not state['events'] and not state['payload_reads']
        else:
            assert len(state['events'])==2
            d=state['events'][1]
            assert d['driver_pointer']==hex(payload if lookup_ok else 0)
            assert d['fallback']==int(not lookup_ok)
            assert d['values']==(values if lookup_ok else None)
            assert [(a,n) for a,n,pc in state['payload_reads']]==(expected_loads if lookup_ok else [])
            payload_loads.update(state['payload_reads'])
        counts[kind]+=1;checked+=1
    pointers=[0,1,audit.PARAM,audit.PARAM+1,audit.PARAM+0x100,0xdeadbeef,0xffffffff,0x80000000]
    for scenario in ['original','file_missing','record_id_missing','key_mismatch','key_count_zero','bad_magic']:
        source=bytearray(original)
        state['file_available']=scenario!='file_missing'
        if scenario=='record_id_missing':struct.pack_into('<I',source,header-4,0xffffffff)
        if scenario=='key_mismatch':source[header-4+16]=ord('X')
        if scenario=='key_count_zero':struct.pack_into('<I',source,header-4+12,0)
        if scenario=='bad_magic':source[0]^=1
        u.mem_write(CALIB,bytes(source));before=checked
        for cache in [0,1,2,255]:
            for flag in [0,1,2,0xffffffff]:
                for pointer in pointers:case(cache,flag,pointer,normal,scenario=='original')
        assert bytes(u.mem_read(CALIB,len(source)))==bytes(source)
        scenarios.append({'scenario':scenario,'cases':checked-before,
            'intervention':'none' if scenario=='original' else 'synthetic negative control'})
    u.mem_write(CALIB,original);state['file_available']=True
    edges=[0,1,0x3f,0x3fff,0x7fff,0x8000,0xffffffff]
    for n in range(args.stress_cases):
        vals=[edges[(n+i)%7] if n<7 else rng.getrandbits(32) for i in range(6)]
        u.mem_write(payload,struct.pack('<6I',*vals))
        case(n&1,0 if n&1 else 2,pointers[n%len(pointers)],vals,True)
        assert bytes(u.mem_read(payload,24))==struct.pack('<6I',*vals)
    u.mem_write(payload,struct.pack('<6I',*normal))
    assert bytes(u.mem_read(CALIB,len(original)))==original
    assert state['input_reads']==state['calibration_writes']==0
    assert not programmer.bit15_changes
    assert state['mmio_writes']==6*(counts['normal_programming']+counts['fallback_programming'])
    # Bounded SAM7 entry-reference census: exact branches and conventional pointer encodings only.
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB);md.detail=True
    ma=Cs(CS_ARCH_ARM,CS_MODE_ARM);ma.detail=True
    call_hits=[]
    for a in range(0,len(sam)-3,2):
        h1,h2=struct.unpack_from('<HH',sam,a)
        if h1&0xf800==0xf000 and h2&0xc000==0xc000:
            for ins in md.disasm(sam[a:a+4],a,count=1):
                if ins.mnemonic in ('bl','blx') and ins.operands[0].type==ARM_OP_IMM and ins.operands[0].imm==0x51da6:
                    call_hits.append({'mode':'Thumb','offset':hex(a)})
    for a in range(0,len(sam)-3,4):
        w=audit.u32(sam,a)
        if w&0x0e000000==0x0a000000:
            for ins in ma.disasm(sam[a:a+4],a,count=1):
                if ins.mnemonic in ('bl','blx') and ins.operands[0].type==ARM_OP_IMM and ins.operands[0].imm==0x51da6:
                    call_hits.append({'mode':'ARM','offset':hex(a)})
    pointer_hits=[];scanned=[]
    for f in sorted(args.sections.glob('*.bin')):
        b=f.read_bytes();scanned.append(f.name)
        for value in [0x51da6,0x51da7,0x43051da2,0x43051da3]:
            pattern=struct.pack('<I',value);start=0
            while True:
                off=b.find(pattern,start)
                if off<0:break
                pointer_hits.append({'file':f.name,'offset':hex(off),'value':hex(value)});start=off+1
    # Source-anchored disassembly of the actual producer path, excluding adjacent functions.
    lines=[]
    for label,begin,end in [('IMG selector',0x154e18,0x154e70),('IMG lookup',0x1a0fc4,0x1a1092),('IMG programmer',0xd4480,0xd4566)]:
        lines.append('\n'+label+' (raw section offsets)')
        for ins in md.disasm(img[begin:end],begin):
            text=f'{ins.address:08x}: {ins.bytes.hex():8} {ins.mnemonic:8} {ins.op_str}'
            if ins.mnemonic=='ldr' and len(ins.operands)>1 and ins.operands[1].type==ARM_OP_MEM and ins.operands[1].mem.base==ARM_REG_PC:
                q=((ins.address+4)&~3)+ins.operands[1].mem.disp
                text+=f' ; literal[{q:#x}]={audit.u32(img,q):#x}'
            if ins.mnemonic=='adr':text+=f' ; address={((ins.address+4)&~3)+ins.operands[1].imm:#x}'
            lines.append(text)
    (args.out/'producer_original_instructions.txt').write_text('\n'.join(lines)+'\n')
    report={'status':'PASS_SOFTWARE_PRODUCER_ONLY','gate_c_passed':False,
        'firmware_version':'M10-R-30.22.23.34-Customer.FW',
        'section_sha256':{**audit.HASHES,SECTION:B2Y_SHA},
        'source_script_sha256':digest(Path(__file__).read_bytes()),'seed':'0xD44802026',
        'record_count':len(records),'records':extracted,'identity_guards':identities,
        'test_execution':{'selector_lookup_driver_cases':checked,'scenario_matrix':scenarios,
            'synthetic_full_u32_payload_cases':args.stress_cases,'outcome_counts':counts,
            'full_mmio_window_compared_bytes':0x4000,'watched_mmio_writes':state['mmio_writes'],
            'paired_word_writes':programmer.total_writes,'bit15_mutations':len(programmer.bit15_changes),
            'argument_block_reads':state['input_reads'],'calibration_writes_by_firmware':state['calibration_writes'],
            'payload_loads':[{'offset':a,'bytes':n,'pc':hex(pc)} for a,n,pc in sorted(payload_loads)],
            'stubs':['IMG 0x1a0c80: resolve B2Y.bin to supplied file registry or NULL',
                     'IMG 0x140154: diagnostic logger only'],
            'original_executed':['selector 0x154e18','lookup 0x1a0fc4','string compare 0x4f164','driver 0xd4480']},
        'producer_contract':{
            'file':'B2Y.bin','record':13,'lookup_key':'',
            'first_argument':'stored in r7 but not dereferenced or used by this bounded selector',
            'second_argument':'skip register update only when arg1 == 1 AND cache byte == 1',
            'cache_address':hex(CACHE),'lookup_success':'pass raw calibration payload pointer to D4480 with fallback=0; cache=1',
            'lookup_failure':'pass NULL to D4480 with fallback=1; cache=0',
            'cached_skip':'no lookup, no driver call, no MMIO update; NOT proof of an ISP bypass',
            'field_calculation':'no arithmetic on payload fields between successful lookup and driver'},
        'sam7_entry_reference_census':{'entry':'0x51da6','direct_branch_hits':call_hits,
            'pointer_hits':pointer_hits,'files_scanned':scanned,
            'pointer_encodings':['raw even/Thumb','conventional 0x43000000 base with four-byte section prefix'],
            'scope':'Direct immediate calls within SAM7 and four exact little-endian pointer encodings across extracted .bin sections. No computed-pointer, relocation, indirect-dispatch or alternate-entry completeness claim.'},
        'limitations':[
            'The file-registry helper is stubbed; storage loading, later replacement or outside mutation of calibration memory are not modeled.',
            'Synthetic missing/mismatched records and payload interventions are tests, not observed camera states or Leica presets.',
            'A fixed control record does not prove scene-independent hardware behavior.',
            'Source signals, denominator, paired-field meanings, pixel scaling, rounding, clipping and processing order remain unresolved.',
            'The actual SAM7 compact-structure producer/caller remains unresolved; no dead-code conclusion follows from the bounded negative census.',
            'No renderer or capture source changes; no photographic parity claim.']}
    (args.out/'producer_results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'cases':checked,'outcomes':counts,'mmio_writes':state['mmio_writes'],'sam7_direct_hits':call_hits,'sam7_pointer_hits':pointer_hits},indent=2))
if __name__=='__main__':main()
