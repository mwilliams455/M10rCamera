#!/usr/bin/env python3
"""GAMMAROUTE1A: execute original gamma upload routing, not ISP pixel processing.
Usage: script.py VERIFIED_SECTIONS REPOSITORY SDK_ROOT OUTPUT_DIR
Requires Capstone 5.0.3 and Unicorn 2.1.3. No binary instructions are patched.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, random, struct, sys
from collections import Counter
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn.arm_const import *

SDK_COMMIT='f5fc84bd5c475f4c15017b7bff749f81c3618287'
SDK_HASHES={'MILB_API/MILB_Header/include/Image/fr2y6a.h': '46901a26cc8e3416e9340a9a280865b8bbb0fa5e76a2361c662d82e09bcdf7c8', 'MILB_API/Project/ImageMacro/src/imr2yctrl2.c': '5dd18f89963ba37e29ecdc527f2d4407eb86648d94ab428412d53dcc8fe2b03d', 'MILB_API/Project/ImageMacro/src/imr2yctrl2.h': '8d886917870687a5af1a512180d5dab52b504c17da861b456a2d022976397dc8', 'MILB_API/Project/ImageMacro/src/imr2yset.c': '972c2c21f2ff334e5b71e51f6daa4cff437da4e41516e4d6db7df0e1ad4af963'}
HASHES={'092_IMG-System.bin':'53e307ad2b241e4684f5f9974c1b9780bcbc9e37ac580d8dcaf45cf72aae80d4',
        '100_IMG-SAM7.bin':'c30351bb884ffd66120bf201e9da5e3a1f6eef970e2eb9b8a2400cca04de51ae',
        '074_IMG_Calibration_Data_data_calib_B2Y.bin.bin':'ea935a8006ea3b0a765660bd1d89f6a52c9f60508ee5ba76650005d80372335b'}
AUDIT_SHA='95d5d3a0663a73261facc888144afcae784c889b6dd9e7e04d02467ca1481313'
PARSER_SHA='8774fa74ad181cf026770a233420cc210abb282acdab0d378df7314835855033'
P=0x10000000;STACK=0x11000000;SRC=0x12000000;CAL=0x13000000;REGISTRY=0x14000000
MMIO=0x20020000;TABLE=0x20a00000;TABLE_BYTES=0x100000;HALT=0x1000000;CACHE=0x408cedbc
IG=[0x20a20000,0x20a21000,0x20a22000,0x20a23000,0x20a24000]
DF=[0x20a40000,0x20a48000,0x20a50000,0x20a58000,0x20a60000]
FL=[0x20a68000,0x20a69000,0x20a6a000,0x20a6b000,0x20a6c000]

def sha(b):return hashlib.sha256(b).hexdigest()
def u32(b,p=0):return struct.unpack_from('<I',b,p)[0]
def put(b,p,v):struct.pack_into('<I',b,p,v&0xffffffff)
def load(name,path,h):
    assert sha(path.read_bytes())==h,path
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s)
    sys.modules[name]=m;s.loader.exec_module(m);return m

def intervals(spec):
    return [{'address':hex(a),'bytes':len(b),'sha256':sha(b)} for a,b in sorted(spec.items())]

class Machine:
    def __init__(self,label,data,calibration):
        self.label=label;self.data=data;self.u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u=self.u
        u.mem_map(0,(len(data)+4095)&~4095);u.mem_write(0,data)
        for a,n in [(P,0x4000),(STACK,0x10000),(SRC,0x40000),(CAL,0x200000),
                    (REGISTRY,0x1000),(MMIO,0x4000),(TABLE,TABLE_BYTES),(HALT,0x1000),(CACHE&~4095,4096)]:u.mem_map(a,n)
        u.mem_write(CAL,calibration);u.mem_write(REGISTRY+0x208,struct.pack('<I',CAL))
        self.original_calibration=calibration;self.file_available=True;self.history=[];self.visited=set()
        for lo,hi in ([(0x5262c,0x5277b),(0x51c42,0x51c6d),(0xb1b78,0xb1b8f)] if label=='SAM7' else
                      [(0x153f64,0x154023),(0xcf45c,0xcf46f),(0xd15ec,0xd16d1),(0x4f21c,0x4f400),(0x1a0fc4,0x1a1091)]):
            u.hook_add(UC_HOOK_CODE,self.trace,begin=lo,end=hi)
        stubs=[0x4d1b4,0x4d118,0x4d1a2,0x4d140,0x4548,0x454a] if label=='SAM7' else [0x140154,0x1a0c80]
        for pc in stubs:u.hook_add(UC_HOOK_CODE,self.stub,begin=pc,end=pc)
        if label=='IMG':
            for pc in [0x4f21c,0x1a0fc4,0xd15ec,0xd164c,0xd1694]:u.hook_add(UC_HOOK_CODE,self.event,begin=pc,end=pc)
        u.hook_add(UC_HOOK_MEM_READ,self.mmio_read,begin=MMIO,end=MMIO+0x3fff)
        u.hook_add(UC_HOOK_MEM_WRITE,self.write,begin=MMIO,end=MMIO+0x3fff)
        u.hook_add(UC_HOOK_MEM_WRITE,self.write,begin=TABLE,end=TABLE+TABLE_BYTES-1)
        u.hook_add(UC_HOOK_MEM_WRITE,self.source_write,begin=SRC,end=CAL+0x1fffff)
    def trace(self,u,a,n,_):self.visited.add((a,n,bool(u.reg_read(UC_ARM_REG_CPSR)&32)))
    def stub(self,u,a,n,_):
        self.stubs.append(hex(a))
        if a==0x1a0c80:
            assert bytes(u.mem_read(u.reg_read(UC_ARM_REG_R0),8)).split(b'\0')[0]==b'B2Y.bin'
            u.reg_write(UC_ARM_REG_R0,REGISTRY if self.file_available else 0)
        else:u.reg_write(UC_ARM_REG_R0,0)
        u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    def event(self,u,a,n,_):
        regs=[u.reg_read(r) for r in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2]]
        e={'pc':hex(a),'r0_r1_r2':regs}
        if a==0x1a0fc4:e.update(record=regs[1],key=bytes(u.mem_read(regs[2],64)).split(b'\0')[0].decode())
        self.events.append(e)
    def mmio_read(self,u,acc,a,n,v,_):self.reads.add((a,n))
    def source_write(self,*_):self.source_writes+=1
    def write(self,u,acc,a,n,v,_):
        pc=u.reg_read(UC_ARM_REG_PC);kind='table' if a>=TABLE else 'mmio'
        self.writes[(kind,pc,n)]+=1
        if kind=='table':self.cover[a-TABLE:a-TABLE+n]=b'\1'*n
    def run(self,tag,entry,regs,old,table,spec,expected_mmio=None,expected_return=None):
        u=self.u;self.events=[];self.stubs=[];self.reads=set();self.writes=Counter();self.source_writes=0;self.cover=bytearray(TABLE_BYTES)
        u.mem_write(MMIO,old);u.mem_write(TABLE,table);u.mem_write(STACK,b'\xa7'*0x10000)
        for r in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11,UC_ARM_REG_R12]:u.reg_write(r,0)
        for r,v in regs.items():u.reg_write(r,v)
        u.reg_write(UC_ARM_REG_SP,STACK+0xff00);u.reg_write(UC_ARM_REG_LR,HALT|1)
        u.emu_start(entry|1,HALT,count=700000)
        assert u.reg_read(UC_ARM_REG_PC)==HALT,(tag,hex(u.reg_read(UC_ARM_REG_PC)))
        got=bytes(u.mem_read(TABLE,TABLE_BYTES));expected=bytearray(table);cover=bytearray(TABLE_BYTES)
        for a,b in spec.items():expected[a-TABLE:a-TABLE+len(b)]=b;cover[a-TABLE:a-TABLE+len(b)]=b'\1'*len(b)
        assert got==expected,(tag,'table values')
        assert self.cover==cover,(tag,'written-byte coverage')
        after=bytes(u.mem_read(MMIO,0x4000));assert after==(old if expected_mmio is None else expected_mmio),(tag,'MMIO')
        ret=u.reg_read(UC_ARM_REG_R0)
        if expected_return is not None:assert ret==expected_return,(tag,hex(ret),hex(expected_return))
        assert self.source_writes==0,(tag,'source mutation')
        self.history.append({'tag':tag,'core':self.label,'entry':hex(entry),'register_arguments':{str(k):v for k,v in regs.items()},
           'return_r0':ret,'mmio_before_sha256':sha(old),'mmio_after_sha256':sha(after),
           'table_before_sha256':sha(table),'table_after_sha256':sha(got),'expected_writes':intervals(spec),
           'bytes_written_union':sum(self.cover),'writes':[{'kind':k,'pc':hex(pc),'width':n,'count':cnt} for (k,pc,n),cnt in sorted(self.writes.items())],
           'mmio_reads':[{'address':hex(a),'bytes':n} for a,n in sorted(self.reads)],'events':self.events,'stubs':self.stubs,
           'cache_u16':int.from_bytes(u.mem_read(CACHE,2),'little'),'source_writes':self.source_writes})
        return after,got

def main():
    if not __debug__:raise RuntimeError('Do not disable assertions')
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ['sections','repo','sdk','out']:ap.add_argument(name,type=Path)
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    binaries={f:(a.sections/f).read_bytes() for f in HASHES}
    for f,b in binaries.items():assert sha(b)==HASHES[f],f
    sdk=[]
    for p,h in SDK_HASHES.items():
        b=(a.sdk/p).read_bytes();assert sha(b)==h,p
        sdk.append({'path':p,'sha256':h,'url':f'https://github.com/ZMlogicL/companyTask/blob/{SDK_COMMIT}/{p}'})
    audit=load('retained_audit',a.repo/'tools/m10r_yblend_bit15_audit1a.py',AUDIT_SHA)
    parser=load('retained_parser',a.repo/'tools/m10r_b2y_assets.py',PARSER_SHA)
    imgdata=binaries['092_IMG-System.bin'];samdata=binaries['100_IMG-SAM7.bin'];raw=binaries['074_IMG_Calibration_Data_data_calib_B2Y.bin.bin']
    identities=audit.validate_identities(imgdata,samdata)
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB);md.detail=True;arm=Cs(CS_ARCH_ARM,CS_MODE_ARM)
    def ins(data,pc):return next(md.disasm(data[pc:pc+4],pc,count=1))
    for pc,text in [(0x153f94,b'DIFFERENTIAL GAMMA     String:%s')]:
        i=ins(imgdata,pc);assert i.mnemonic=='adr';p=((pc+4)&~3)+i.operands[1].imm;assert imgdata[p:].startswith(text)
        identities.append({'label':text.decode(),'pc':hex(pc),'string':hex(p)})
    for pc,rid,driverpc,driver in [(0x153f9e,11,0x153fbe,0xd15ec),(0x153fc4,28,0x153fe4,0xd164c),(0x153fea,29,0x15400a,0xd1694)]:
        assert ins(imgdata,pc).operands[1].imm==rid and ins(imgdata,driverpc).operands[0].imm==driver
    for pc,text in [(0x52650,b'I:Im_B2Y_Set_IGamma_Table'),(0x526e6,b'I:Im_B2Y_Set_DGamma_Table'),(0x526f6,b'I:Im_B2Y_Set_DGamma_Table')]:
        i=ins(samdata,pc);p=((pc+4)&~3)+i.operands[1].imm;assert i.mnemonic=='adr' and samdata[p:].startswith(text)
        identities.append({'label':text.decode(),'pc':hex(pc),'string':hex(p)})
    recs=parser.parse_records(raw);extracted={};records={}
    for rid in [9,11,28,29]:
        rs=[r for r in recs if r.record_id==rid];assert len(rs)==1;r=rs[0];records[rid]=r
        h=0x14+r.index*0xa90;keys=[raw[h+16+k*64:h+16+(k+1)*64].split(b'\0')[0].decode() for k in range(u32(raw,h+12))]
        b=raw[r.payload_offset:r.payload_offset+r.size]
        extracted[rid]={'record':rid,'index':r.index,'header_offset':hex(h),'payload_offset':hex(r.payload_offset),'bytes':r.size,
           'keys':keys,'sha256':sha(b),'active_prefix_bytes':min(r.size,{28:32768,29:4096}.get(rid,r.size)),
           'active_prefix_sha256':sha(b[:{28:32768,29:4096}.get(rid,r.size)])}
        if rid in [9,11]:extracted[rid]['u32_values']=list(struct.unpack('<'+'I'*(r.size//4),b))
    assert extracted[11]['u32_values']==[1,1]
    for rid in [11,28,29]:assert extracted[rid]['keys']==extracted[11]['keys']
    normal_df=raw[records[28].payload_offset:records[28].payload_offset+32768]
    normal_fl=raw[records[29].payload_offset:records[29].payload_offset+4096]
    sam=Machine('SAM7',samdata,raw[4:]);img=Machine('IMG',imgdata,raw[4:]);rng=random.Random(0x6A20260920)
    def old(status=0):
        b=bytearray(rng.randbytes(0x4000));put(b,4,(u32(b,4)&~0x60)|status);return bytes(b)
    def tab():return rng.randbytes(TABLE_BYTES)
    payloads=[('calibration_prefixes',normal_fl,normal_df),('zero',bytes(4096),bytes(32768)),('diagnostic_pattern',rng.randbytes(4096),rng.randbytes(32768))]
    for name,fl,df in payloads:
        sam.u.mem_write(SRC,fl);sam.u.mem_write(SRC+0x10000,df)
        for idx in range(5):
            sam.run(f'IG_index_{idx}_{name}',0x5262c,{UC_ARM_REG_R0:idx,UC_ARM_REG_R1:SRC},old(),tab(),{IG[idx]:fl},expected_return=0)
            sam.run(f'DG_index_{idx}_{name}',0x526bc,{UC_ARM_REG_R0:idx,UC_ARM_REG_R1:SRC,UC_ARM_REG_R2:SRC+0x10000},old(),tab(),{FL[idx]:fl,DF[idx]:df},expected_return=0)
    # The caller's full 32-bit selector is tested, not assumed truncated to an SDK uint16.
    for idx in [5,255,65536,0xffffffff]:
        for entry in [0x5262c,0x526bc]:sam.run(f'invalid_index_{idx}_{entry:x}',entry,{UC_ARM_REG_R0:idx,UC_ARM_REG_R1:SRC,UC_ARM_REG_R2:SRC+0x10000},old(),tab(),{},expected_return=0xb000001)
    fl,df=payloads[-1][1:]
    for idx in range(5):
        for entry,bit in [(0x5262c,5),(0x526bc,6)]:
            sam.run(f'busy_{idx}_{entry:x}',entry,{UC_ARM_REG_R0:idx,UC_ARM_REG_R1:SRC,UC_ARM_REG_R2:SRC+0x10000},old(1<<bit),tab(),{},expected_return=0xb000005)
    for entry,full,diff in [(0x5262c,0,SRC+0x10000),(0x526bc,0,SRC+0x10000),(0x526bc,SRC,0)]:
        sam.run(f'null_{entry:x}_{full}_{diff}',entry,{UC_ARM_REG_R0:4,UC_ARM_REG_R1:full,UC_ARM_REG_R2:diff},old(),tab(),{},expected_return=0xb000001)
    # Control bits are varied; routing still comes solely from the setter index.
    for bits in range(16):
        b=bytearray(old())
        for j,bit in enumerate([16,17,24,25]):put(b,0x800,(u32(b,0x800)&~(1<<bit))|(((bits>>j)&1)<<bit))
        for idx in [0,4]:sam.run(f'controls_{bits}_index_{idx}',0x526bc,{UC_ARM_REG_R0:idx,UC_ARM_REG_R1:SRC,UC_ARM_REG_R2:SRC+0x10000},bytes(b),tab(),{FL[idx]:fl,DF[idx]:df},expected_return=0)
    assert all(x['mmio_reads']==[{'address':'0x20020004','bytes':4}] for x in sam.history if x['tag'].startswith(('IG_index','DG_index','controls_')))
    # Full IMG selector + key copying + original lookup + original ARM memcpy.
    def select(tag,key,flag=0,cached=0,mode=17,busy=False,missing=None):
        src=bytearray(raw[4:])
        if missing is not None:put(src,0x14+records[missing].index*0xa90-4,0xffffffff)
        img.u.mem_write(CAL,bytes(src));img.u.mem_write(CACHE,struct.pack('<H',cached))
        img.u.mem_write(P,struct.pack('<H',mode)+key.encode()+b'\0')
        b=old(0x40 if busy else 0);expected=bytearray(b)
        skip=(cached==mode and flag==1);success=not skip and not busy and img.file_available and missing is None
        if success:put(expected,0x800,u32(expected,0x800)|(3<<24))
        elif not skip and not busy:put(expected,0x800,u32(expected,0x800)&~(3<<24))
        spec={} if not success else {DF[0]:normal_df,FL[0]:normal_fl}
        # Missing anchor occurs after a successful differential copy, which is not rolled back.
        if not skip and not busy and img.file_available and missing==29:spec={DF[0]:normal_df}
        img.run(tag,0x153f64,{UC_ARM_REG_R0:P,UC_ARM_REG_R1:flag},b,tab(),spec,bytes(expected))
        h=img.history[-1]
        assert h['cache_u16']==(cached if skip else (mode if success else 0)),tag
        calls=[e for e in h['events'] if e['pc']=='0x1a0fc4']
        assert [e['record'] for e in calls]==([] if skip or busy else [11,28,29])
        if calls:assert all(e['key']==key for e in calls)
        assert bytes(img.u.mem_read(CAL,len(src)))==bytes(src)
    for key in extracted[11]['keys']:
        select('IMG_normal_'+key,key)
        select('IMG_cached_'+key,key,flag=1,cached=17)
        select('IMG_forced_'+key,key,flag=0,cached=17)
        select('IMG_busy_'+key,key,busy=True)
    key=extracted[11]['keys'][0]
    for rid in [11,28,29]:select('IMG_missing_record_'+str(rid),key,missing=rid)
    img.file_available=False;select('IMG_missing_file',key);img.file_available=True
    select('IMG_busy_cached',key,flag=1,cached=17,busy=True)
    # Compare actual calibration upload bytes at the matching SAM7 index zero.
    sam.u.mem_write(SRC,normal_fl);sam.u.mem_write(SRC+0x10000,normal_df)
    sam.run('SAM_matching_normal_IMG_apertures',0x526bc,{UC_ARM_REG_R0:0,UC_ARM_REG_R1:SRC,UC_ARM_REG_R2:SRC+0x10000},old(),tab(),{FL[0]:normal_fl,DF[0]:normal_df},expected_return=0)
    histories=img.history+sam.history
    listings=[]
    for m in [img,sam]:
        listings.append(m.label+' executed instruction addresses; inline switch data is excluded')
        for pc,n,thumb in sorted(m.visited):
            i=next((md if thumb else arm).disasm(m.data[pc:pc+n],pc,count=1))
            listings.append(f'{pc:08x} {"Thumb" if thumb else "ARM":5} {i.bytes.hex():8} {i.mnemonic:8} {i.op_str}')
    (a.out/'original_executed_instructions.txt').write_text('\n'.join(listings)+'\n')
    (a.out/'execution_history.json').write_text(json.dumps(histories,indent=2)+'\n')
    assert (0xb1b78,4,False) in sam.visited and (0x4f21c,4,False) in img.visited
    report={'status':'PASS_GAMMA_UPLOAD_ROUTING_ONLY','gate_c_passed':False,'renderer_changed':False,
      'section_sha256':HASHES,'script_sha256':sha(Path(__file__).read_bytes()),'seed':'0x6A20260920',
      'identity_guards':identities,'calibration_records':list(extracted.values()),'sdk_sources':sdk,
      'aperture_map':[{'selector':i,'igamma':hex(IG[i]),'dgamma_difference':hex(DF[i]),'dgamma_anchors':hex(FL[i]),
                       'related_sdk_gamma_name':['RGB common','R','G','B','Yb'][i],
                       'name_status':'cross-revision correspondence; no recovered Leica signal name'} for i in range(5)],
      'tests':{'original_entry_executions':len(histories),'img_entries':len(img.history),'sam7_entries':len(sam.history),
               'table_aperture_window_compared_bytes':TABLE_BYTES,'mmio_window_compared_bytes':0x4000,
               'source_writes_by_executed_firmware':sum(x['source_writes'] for x in histories),
               'table_writes':sum(w['count'] for x in histories for w in x['writes'] if w['kind']=='table'),
               'control_writes':sum(w['count'] for x in histories for w in x['writes'] if w['kind']=='mmio'),
               'all_full_window_and_write_coverage_assertions_passed':True},
      'new_constraints':[
        'SAM7 IGamma and DGamma each provide five distinct CPU-visible upload selections.',
        'IMG normal DG selector executes record 11/28/29 lookup and uploads the same destinations as SAM7 selector zero.',
        'Normal record 11 stores [1,1], programming bits 24 and 25; these are not identified as Yb enable bits.',
        'SAM7 table upload choice does not read the four gamma configuration fields. Tested routes only read activity status at 0x20020004.',
        'Matched cache plus update-argument 1 skips even the busy test; an uncached busy call clears selector cache and performs no upload.',
        'A missing anchor record leaves the earlier differential bytes uploaded; fallback changes control bits rather than rolling back the table write.',
        'Related SDK labels selection zero RGB common, selection four Yb, and documents a separate simultaneous Yb table-writing control.',
        'Therefore common-aperture-only CPU writes do not prove a Yb table is unwritten or a Yb signal bypasses gamma.'],
      'stubs':{'IMG':['file registry resolver 0x1A0C80','diagnostic logging 0x140154'],
               'SAM7':['clock helpers 0x4D1B4/0x4D118/0x4D1A2/0x4D140','diagnostic logging 0x4548/0x454A']},
      'original_not_stubbed':['IMG selector 0x153F64','IMG busy check 0xCF45C','IMG key copy 0x4EFD8','IMG record lookup 0x1A0FC4',
          'IMG register/table drivers 0xD15EC/0xD164C/0xD1694','IMG ARM memcpy 0x4F21C and aligned body',
          'SAM7 IGamma 0x5262C and DGamma 0x526BC','SAM7 activity checks 0x51C42/0x51C58','SAM7 ARM table switch 0xB1B78'],
      'limitations':[
        'RAM-backed apertures cannot model hardware table broadcast, aliasing, write enables or reset states.',
        'The SDK is a third-party port for a different revision, not an exact Leica datasheet.',
        'The SDK GAMSW field is at bit 8 of its GMCTL; no equivalent Leica writer is established.',
        'No proof of which pixel signal reads any uploaded table, or of internal signal routing into Y BLEND.',
        'No per-pixel blend equation, denominator, paired-field semantics, rounding or clipping recovered.',
        'No complete camera pipeline or startup is emulated; synthetic negative controls are not observed camera failures.',
        'Gamma payloads supplied to IGamma tests are deliberate byte-transfer fixtures, not Leica IGamma presets.']}
    (a.out/'gammaroute_results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'tests':report['tests']},indent=2))
if __name__=='__main__':main()
