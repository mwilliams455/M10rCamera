#!/usr/bin/env python3
"""Execute original IMG Y BLEND calibration-source paths; NOT an ISP emulator.
Usage: script.py SECTIONS REPO_ROOT OUT_DIR [--rounds 32]
Requires capstone==5.0.3, unicorn==2.1.3 and the retained BIT15 audit module.
File I/O, heap operations and logging are stubbed. The resolver, NOR metadata
lookup, record lookup, registration helper and register driver execute unchanged.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, random, struct, sys
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB
from capstone.arm import ARM_OP_MEM, ARM_REG_PC
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE, UC_ARCH_ARM, UC_MODE_ARM, Uc
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_LR, UC_ARM_REG_PC

CALIB_FILE='074_IMG_Calibration_Data_data_calib_B2Y.bin.bin'
CALIB_SHA='ea935a8006ea3b0a765660bd1d89f6a52c9f60508ee5ba76650005d80372335b'
AUDIT_SHA='95d5d3a0663a73261facc888144afcae784c889b6dd9e7e04d02467ca1481313'
PRE=0x12000000; REG=0x13000000; PATHBUF=0x14000000; ALT=0x15000000
NOR_BASE=0x02000000; NOR_DATA=0x02400000; NOR_META=0x026ffe00
COUNT=0x408d5028; REGPTR=0x408d5024; CACHE=0x408cedbf; NOR_GLOBAL=0x408eebc0
PAYLOAD_OFF=0x131870; NORMAL=[0,32,16383,16383,16383,16383]
SELECTOR=0x154e18; RESOLVER=0x1a0c80; DRIVER=0xd4480; UPSERT=0x1a270c
SEED=0xCA11B2026

def sha(b: bytes) -> str: return hashlib.sha256(b).hexdigest()
def put32(u,a,v): u.mem_write(a,struct.pack('<I',v))
def read32(u,a): return struct.unpack('<I',u.mem_read(a,4))[0]
def module(path):
    spec=importlib.util.spec_from_file_location('retained_bit15',path)
    if spec is None or spec.loader is None: raise RuntimeError(str(path))
    m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m

def descriptor(length, pointer, name=b'B2Y.bin'):
    assert len(name)<256
    b=bytearray(0x210);struct.pack_into('<Q',b,0,length);b[8:8+len(name)]=name
    b[0x108:0x114]=b'/data/calib/'
    struct.pack_into('<I',b,0x208,pointer);return bytes(b)

class SourceHarness:
    def __init__(self,audit,img,source):
        self.audit=audit;self.img=img;self.original=source;self.prog=audit.Programmer(img);u=self.u=self.prog.uc
        u.mem_map(0x42000000,(len(img)+4095)&~4095);u.mem_write(0x42000000,img[4:])
        for a,n in [(0x408d5000,4096),(0x408ce000,4096),(0x408ee000,4096),
                    (PRE,0x200000),(REG,0x4000),(PATHBUF,4096),(ALT,0x200000),(NOR_DATA,0x300000)]:u.mem_map(a,n)
        self.metadata=img[0x7f641c:0x7f661c]
        assert self.metadata[:19]==b'/data/calib/B2Y.bin'
        assert struct.unpack_from('<II',self.metadata,504)==(0x400000,0x300000)
        self.history=[];self.events=[];self.writes=[];self.source_writes=[];self.entries=[]
        self.allocations=[];self.logs=[];self.total_source_writes=0
        self.hook_points=[SELECTOR,RESOLVER,0x142508,0x13de50,0x1a3128,0x1a0fc4,
                          0x14254c,0x143170,0x147038,0x1a2154,0x140154,DRIVER,UPSERT,0x1a29d4,0x4f2f0]
        for a in self.hook_points:u.hook_add(UC_HOOK_CODE,self.code,begin=a,end=a)
        u.hook_add(UC_HOOK_MEM_WRITE,self.write,begin=REG,end=REG+0x3fff)
        for a,n in [(PRE,len(source)),(ALT,len(source)),(NOR_DATA,0x300000)]:
            u.hook_add(UC_HOOK_MEM_WRITE,self.source_write,begin=a,end=a+n-1)
    def cstr(self,a): return bytes(self.u.mem_read(a,256)).split(b'\0')[0].decode('ascii')
    def ret(self,v=None):
        if v is not None:self.u.reg_write(UC_ARM_REG_R0,v)
        self.u.reg_write(UC_ARM_REG_PC,self.u.reg_read(UC_ARM_REG_LR))
    def code(self,u,a,size,_):
        self.entries.append(hex(a))
        if a==0x14254c:
            assert u.reg_read(UC_ARM_REG_R0)==256
            self.allocations.append({'kind':'path','bytes':256});self.ret(PATHBUF)
        elif a==0x143170:
            n=u.reg_read(UC_ARM_REG_R0);assert n==len(self.file_bytes)
            self.allocations.append({'kind':'payload','bytes':n});self.ret(ALT)
        elif a==0x147038:
            old=u.reg_read(UC_ARM_REG_R0);n=u.reg_read(UC_ARM_REG_R1)
            assert old in (0,REG) and n<=0x4000
            self.allocations.append({'kind':'registry_reallocation','bytes':n})
            self.ret(REG)  # synthetic in-place heap reallocation, retains existing bytes
        elif a==0x1a2154:
            p=self.cstr(u.reg_read(UC_ARM_REG_R0));dst=u.reg_read(UC_ARM_REG_R1)
            n=u.reg_read(UC_ARM_REG_R2);high=u.reg_read(UC_ARM_REG_R3)
            assert p=='/data/calib/B2Y.bin' and n==len(self.file_bytes) and high==0
            u.mem_write(dst,self.file_bytes)  # explicit external I/O fixture, not a firmware instruction
            self.events.append({'file_read':p,'destination':hex(dst),'bytes':n});self.ret(n)
        elif a==0x140154:
            self.logs.append(self.cstr(u.reg_read(UC_ARM_REG_R1)));self.ret()
        elif a==DRIVER:
            ptr=u.reg_read(UC_ARM_REG_R0);fb=u.reg_read(UC_ARM_REG_R1)
            self.events.append({'driver_pointer':hex(ptr),'fallback':fb,
                'values_u32':list(struct.unpack('<6I',u.mem_read(ptr,24))) if ptr else None})
    def write(self,u,access,a,n,v,_):
        self.writes.append({'pc':hex(u.reg_read(UC_ARM_REG_PC)),'address':hex(a),'bytes':n,'value':hex(v)})
    def source_write(self,u,access,a,n,v,_):
        self.total_source_writes+=1
        self.source_writes.append({'pc':hex(u.reg_read(UC_ARM_REG_PC)),'address':hex(a),'bytes':n})
    def setup(self,mode,values=NORMAL):
        u=self.u;source=bytearray(self.original);struct.pack_into('<6I',source,PAYLOAD_OFF,*values)
        source=bytes(source);self.file_bytes=source
        for a in [PRE,ALT,NOR_DATA]:u.mem_write(a,source)
        u.mem_write(NOR_META,self.metadata)
        put32(u,NOR_GLOBAL,0 if mode=='nor_default_base' else NOR_BASE)
        u.mem_write(REG,b'\xaf'*0x4000)
        name=b'other.bin' if mode=='registry_name_mismatch' else b'B2Y.bin'
        u.mem_write(REG,descriptor(len(source),PRE if mode=='preloaded' else 0,name))
        put32(u,REGPTR,REG);put32(u,COUNT,0 if mode=='registry_absent' else 1);u.mem_write(CACHE,b'\0')
        if mode=='nor_name_mismatch':u.mem_write(NOR_META,b'X')
        if mode=='nor_offset_mismatch':put32(u,NOR_META+504,0x400004)
        if mode=='nor_size_mismatch':put32(u,NOR_META+508,0x300004)
        return source
    def run(self,label,entry,param,old,flag=0):
        self.events=[];self.writes=[];self.source_writes=[];self.entries=[];self.allocations=[];self.logs=[]
        out=self.prog.run(entry,param,old,fallback=flag)
        item={'label':label,'entry':hex(entry),'flag':flag,'events':self.events,
              'registry_write_count':len(self.writes),'registry_write_pcs':sorted(set(x['pc'] for x in self.writes)),
              'source_write_count':len(self.source_writes),'allocations':self.allocations,
              'original_entry_visits':sorted(set(self.entries)),'cache_after':self.u.mem_read(CACHE,1)[0]}
        self.history.append(item)
        assert not self.source_writes
        return out,item

def instruction_evidence(img):
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB);md.detail=True
    scopes=[('selector',0x154e18,0x154e70),('resolver',0x1a0c80,0x1a0e42),
            ('NOR metadata search',0x142508,0x142546),('NOR base helper',0x13de50,0x13de74),
            ('record lookup',0x1a0fc4,0x1a1092),('file loader',0x1a3128,0x1a3186),
            ('descriptor upsert',0x1a270c,0x1a275e),('descriptor index lookup',0x1a29d4,0x1a2a40),
            ('calibration enumeration caller slice',0x1a2b98,0x1a2be2),
            ('write-handler calibration-registration slice',0x1baa48,0x1baa70)]
    lines=[]
    for label,a,z in scopes:
        lines.append('\n'+label+' [raw IMG offsets]')
        for i in md.disasm(img[a:z],a):
            text=f'{i.address:08x}: {i.bytes.hex():8} {i.mnemonic:8} {i.op_str}'
            if i.mnemonic=='ldr' and len(i.operands)>1 and i.operands[1].type==ARM_OP_MEM and i.operands[1].mem.base==ARM_REG_PC:
                p=((i.address+4)&~3)+i.operands[1].mem.disp
                text+=f' ; literal[{p:#x}]={struct.unpack_from("<I",img,p)[0]:#x}'
            lines.append(text)
    return '\n'.join(lines)+'\n'

def sam_scatter(sam):
    """Run the original ARM scatter loader and copy/zero helpers at real addresses.
    Stops before the next startup stage. This does not emulate camera boot or ISP.
    """
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
    for a,n in [(0x43000000,0x110000),(0,0x1000),(0x43400000,0x2b4000),(0x43800000,0x75000)]:u.mem_map(a,n)
    u.mem_write(0x43000000,sam[4:]);sentinel=b'\xa5'
    for a,n in [(0,0x1000),(0x43400000,0x2b4000),(0x43800000,0x75000)]:u.mem_write(a,sentinel*n)
    start=0xf58+struct.unpack_from('<I',sam,0xf58)[0];end=0xf58+struct.unpack_from('<I',sam,0xf5c)[0]
    assert (start,end)==(0x103748,0x1037a8)
    rows=[]
    for o in range(start,end,16):
        src,dst,n,fn=struct.unpack_from('<4I',sam,o)
        assert fn in (0x43000f5c,0x43000f84)
        rows.append({'table_raw_offset':hex(o),'source':hex(src),'destination':hex(dst),
                     'bytes':n,'helper':hex(fn),'operation':'copy' if fn==0x43000f5c else 'zero'})
    # The final initialized region reads four bytes beyond the supplied section.
    # Declare those bytes as a synthetic fixture; do not invent firmware contents.
    source_end=0x43000000+len(sam)-4
    required_end=max(int(r['source'],16)+r['bytes'] for r in rows if r['operation']=='copy')
    assert required_end-source_end==4
    tail_fixture=b'\x12\x34\xab\xcd'
    u.mem_write(source_end,tail_fixture)
    u.emu_start(0x43000f20,0x430010a0,count=2500000)
    assert u.reg_read(UC_ARM_REG_PC)==0x430010a0
    for r in rows:
        a=int(r['source'],16)-0x43000000+4;n=r['bytes']
        expected=sam[a:a+n] if r['operation']=='copy' else b'\0'*n
        missing=n-len(expected)
        r['bytes_not_present_in_section']=missing
        if missing:
            assert missing==4
            expected+=tail_fixture
        assert bytes(u.mem_read(int(r['destination'],16),n))==expected
        r['destination_sha256']=sha(expected)
    entry=0x43051da2
    assert all(not (int(r['source'],16)<=entry<int(r['source'],16)+r['bytes']) for r in rows if r['operation']=='copy')
    return {'status':'PASS_SCATTER_WITH_DECLARED_4BYTE_TAIL_FIXTURE','synthetic_source_tail_bytes':4,'original_entry':hex(0x43000f20),
            'stop_before_next_stage':hex(0x430010a0),'rows':rows,'yc_programmer_virtual_entry':hex(entry),
            'yc_programmer_in_any_copy_source':False,
            'scope':'The six entries of this startup scatter table only. Four source tail bytes absent from the supplied section are an explicit synthetic fixture. Not camera boot, arbitrary later relocation or dispatch.'}

def main():
    if not __debug__:raise RuntimeError('Do not disable assertions')
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('sections',type=Path);ap.add_argument('repo',type=Path);ap.add_argument('out',type=Path)
    ap.add_argument('--rounds',type=int,default=32);args=ap.parse_args()
    if args.rounds<8:ap.error('--rounds must be at least eight')
    args.out.mkdir(parents=True,exist_ok=True)
    tool=args.repo/'tools/m10r_yblend_bit15_audit1a.py';assert sha(tool.read_bytes())==AUDIT_SHA
    audit=module(tool);data={}
    for name,h in {**audit.HASHES,CALIB_FILE:CALIB_SHA}.items():
        b=(args.sections/name).read_bytes();assert sha(b)==h;data[name]=b
    img=data['092_IMG-System.bin'];sam=data['100_IMG-SAM7.bin'];source=data[CALIB_FILE][4:]
    assert list(struct.unpack_from('<6I',source,PAYLOAD_OFF))==NORMAL
    audit.validate_identities(img,sam)
    h=SourceHarness(audit,img,source);u=h.u;rng=random.Random(SEED)
    modes=['preloaded','nor_valid','nor_default_base','nor_name_mismatch','nor_offset_mismatch',
           'nor_size_mismatch','registry_absent','registry_name_mismatch']
    source_cases=state_cases=append_cases=0
    values_edges=[0,1,63,0x3fff,0x7fff,0x8000,0xffffffff]
    for n in range(args.rounds):
        values=NORMAL if n==0 else ([values_edges[(n+i)%7] for i in range(6)] if n<8 else [rng.getrandbits(32) for _ in range(6)])
        for mode in modes:
            s=h.setup(mode,values);u.mem_write(audit.STACK,rng.randbytes(0x10000));old=rng.randbytes(0x4000)
            out,row=h.run(f'source:{mode}:{n}',SELECTOR,rng.randbytes(64),old)
            absent=mode in ('registry_absent','registry_name_mismatch')
            assert out==audit.expected_blend(old,values,absent)
            assert row['cache_after']==int(not absent)
            d=next(x for x in row['events'] if 'driver_pointer' in x)
            route='absent' if absent else ('preloaded' if mode=='preloaded' else ('file' if 'mismatch' in mode else 'NOR'))
            base={'absent':0,'preloaded':PRE,'file':ALT,'NOR':NOR_DATA}[route]
            assert d['driver_pointer']==hex(base+PAYLOAD_OFF if base else 0)
            assert d['fallback']==int(absent)
            expected_site={'absent':[],'preloaded':[],'file':['0x1a0dc0'],'NOR':['0x1a0d66']}[route]
            assert row['registry_write_pcs']==expected_site
            if route=='NOR':assert read32(u,NOR_GLOBAL)==NOR_BASE and hex(0x142508) in row['original_entry_visits']
            if route=='file':assert any('file_read' in e for e in row['events'])
            for a in [PRE,NOR_DATA]:assert bytes(u.mem_read(a,len(s)))==s
            source_cases+=1
    # Two independent caches: replacing/invalidating a descriptor does not clear the selector cache.
    for n in range(args.rounds):
        h.setup('preloaded');old=rng.randbytes(0x4000)
        old,_=h.run(f'state:prime:{n}',SELECTOR,b'\0'*64,old)
        different=[rng.getrandbits(32) for _ in range(6)]
        u.mem_write(ALT+PAYLOAD_OFF,struct.pack('<6I',*different))
        for pointer,tag in [(ALT,'replace_loaded'),(0,'invalidate_loaded')]:
            desc=descriptor(len(source),pointer)
            result,row=h.run(f'state:{tag}:{n}',UPSERT,desc,old)
            assert result==old and read32(u,COUNT)==1 and u.reg_read(UC_ARM_REG_R0)==1
            assert bytes(u.mem_read(REG,0x210))==desc and row['cache_after']==1
            assert not row['allocations'] and hex(0x4f2f0) in row['original_entry_visits']
            result,row=h.run(f'state:cached_skip:{tag}:{n}',SELECTOR,b'\0'*64,old,1)
            assert result==old and row['original_entry_visits']==[hex(SELECTOR)]
            assert not row['events'] and not row['registry_write_count']
            expected=different if pointer else NORMAL
            result,row=h.run(f'state:forced_reload:{tag}:{n}',SELECTOR,b'\0'*64,old,0)
            assert result==audit.expected_blend(old,expected,False)
            old=result;state_cases+=1
    # Execute original append branch (heap resize stub only), then consume appended descriptor.
    for n in range(args.rounds):
        h.setup('registry_name_mismatch');old=rng.randbytes(0x4000)
        before=bytes(u.mem_read(REG,0x210));desc=descriptor(len(source),PRE)
        out,row=h.run(f'append:register:{n}',UPSERT,desc,old)
        assert out==old and read32(u,COUNT)==2
        assert bytes(u.mem_read(REG,0x210))==before and bytes(u.mem_read(REG+0x210,0x210))==desc
        assert row['allocations']==[{'kind':'registry_reallocation','bytes':0x420}]
        out,row=h.run(f'append:select:{n}',SELECTOR,b'\0'*64,old)
        assert out==audit.expected_blend(old,NORMAL,False)
        append_cases+=1
    assert h.total_source_writes==0 and not h.prog.bit15_changes
    scatter=sam_scatter(sam)
    report={'status':'PASS_CALIBRATION_SOURCE_SOFTWARE_ONLY','gate_c_passed':False,
        'firmware_version':'M10-R-30.22.23.34-Customer.FW','source_script_sha256':sha(Path(__file__).read_bytes()),
        'seed':hex(SEED),'section_sha256':{**audit.HASHES,CALIB_FILE:CALIB_SHA},
        'tests':{'source_route_cases':source_cases,'source_modes':modes,'dual_cache_transitions':state_cases,
            'append_cases':append_cases,'total_original_entry_executions':h.prog.calls,
            'selector_executions':sum(x['entry']==hex(SELECTOR) for x in h.history),
            'upsert_executions':sum(x['entry']==hex(UPSERT) for x in h.history),
            'source_memory_writes_by_executed_firmware':h.total_source_writes,'bit15_mutations':len(h.prog.bit15_changes)},
        'NOR_metadata':{'IMG_raw_offset':'0x7f641c','IMG_virtual_address':'0x427f6418',
            'path':'/data/calib/B2Y.bin','payload_region_offset':'0x400000','allocated_region_bytes':'0x300000',
            'metadata_record_bytes':512,'descriptor_sha256':sha(h.metadata),'metadata_record_hex':h.metadata.hex(),
            'header_rule':'base + region_offset + region_size - 0x200',
            'normal_default_base':'0x02000000','normal_default_data':'0x02400000','normal_default_header':'0x026ffe00',
            'scope':'The path, offset, size and metadata lookup table are original firmware bytes. A matching NOR cache header and its memory contents are explicit test fixtures, not a device dump.'},
        'concrete_writers':{'NOR_pointer_install':'0x1a0d66','allocated_file_pointer_install':'0x1a0dc0',
            'descriptor_replacement':'original memcpy called at 0x1a2756, copying all 0x210 descriptor bytes including +0x208',
            'registry_pointer':'0x408d5024','registry_count':'0x408d5028','payload_pointer_field':'+0x208',
            'record_cache_byte':'0x408cedbf'},
        'original_executed':['IMG selector 0x154e18','resolver 0x1a0c80','NOR metadata lookup 0x142508',
            'NOR base helper 0x13de50','file allocation/read wrapper 0x1a3128','record lookup 0x1a0fc4',
            'descriptor upsert 0x1a270c','descriptor index lookup 0x1a29d4','copy 0x4f2f0',
            'original string helpers','Y BLEND driver 0xd4480'],
        'stubs':['path allocator 0x14254c','payload allocator 0x143170','registry reallocator 0x147038 (in-place fixture)',
                 'file I/O 0x1a2154 (injects declared source bytes and reports full read)','diagnostic logger 0x140154'],
        'SAM7_scatter':scatter,
        'execution_history_sha256':sha((json.dumps(h.history,indent=2)+'\n').encode()),
        'sample_traces':h.history[:8]+h.history[source_cases:source_cases+7]+h.history[-2:],
        'limitations':['No physical NOR dump, filesystem, camera boot, scene-adaptive calibration mutation or real-camera runtime trace is supplied.',
            'The registry fixtures and altered Y BLEND fields are deliberate interventions, not discovered Leica presets.',
            'Zero observed source writes excludes external writers, stubs, other threads and unexecuted firmware paths.',
            'The registration tests establish complete descriptor copying but not all filename collision rules, allocation failures or concurrency behavior.',
            'The caller slices are static anchors only; the surrounding directory enumeration and file-write command handlers were not executed end-to-end.',
            'SAM7 startup scatter copying does not relocate this programmer in its six entries; later relocation and indirect dispatch remain open.',
            'No source-signal roles, paired-field semantics, pixel equation, denominator, rounding, clipping or image-stage order is recovered.',
            'No renderer or capture changes, no APK, no photographic parity claim.']}
    (args.out/'execution_history.json').write_text(json.dumps(h.history,indent=2)+'\n')
    (args.out/'calibsource_results.json').write_text(json.dumps(report,indent=2)+'\n')
    (args.out/'original_instruction_evidence.txt').write_text(instruction_evidence(img))
    print(json.dumps({'status':report['status'],'tests':report['tests'],'SAM7_scatter':scatter['status']},indent=2))
if __name__=='__main__':main()
