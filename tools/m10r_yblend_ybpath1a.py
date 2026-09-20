#!/usr/bin/env python3
"""M10-R YBPATH1A: original mixed ARM/Thumb control-path execution, NOT ISP pixels.
Usage: script.py SECTIONS REPO_ROOT SDK_SOURCE_ROOT OUT_DIR [--cases 256]
External SDK text is evidence of a related implementation, not executed Leica code.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, random, re, struct, sys
from collections import Counter
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB
from capstone.arm import ARM_OP_IMM
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn.arm_const import *

SDK_COMMIT='f5fc84bd5c475f4c15017b7bff749f81c3618287'
SDK_HASHES={
'MILB_API/Project/ImageMacro/src/imr2yctrl.h':'eb4d28ecfddba5165f7fb69e6b66a7e25e5d3d612ad722d5281fd62150fd73d1',
'MILB_API/Project/ImageMacro/src/imr2yctrl2.h':'8d886917870687a5af1a512180d5dab52b504c17da861b456a2d022976397dc8',
'MILB_API/Project/ImageMacro/src/imr2yctrl2.c':'5dd18f89963ba37e29ecdc527f2d4407eb86648d94ab428412d53dcc8fe2b03d',
'MILB_API/MILB_Header/include/Image/fr2y6a.h':'46901a26cc8e3416e9340a9a280865b8bbb0fa5e76a2361c662d82e09bcdf7c8',
'MILB_API/Project/ImageMacro/src/imr2y.h':'2a23e54a55f1e44978fa41e9c597e371489f3d76cbaa4d9e54392db4198447f8'}
AUDIT_SHA='95d5d3a0663a73261facc888144afcae784c889b6dd9e7e04d02467ca1481313'
PARSER_SHA='8774fa74ad181cf026770a233420cc210abb282acdab0d378df7314835855033'
B2Y_FILE='074_IMG_Calibration_Data_data_calib_B2Y.bin.bin'
B2Y_SHA='ea935a8006ea3b0a765660bd1d89f6a52c9f60508ee5ba76650005d80372335b'
MMIO=0x20020000; P=0x10000000; AUX=P+0x1000; STACK=0x11000000
SRC=0x12000000; TABLE=0x20a00000; HALT=0x1000000
# (IMG uint32 slot, SAM byte offset, SAM load bytes, MMIO offset, bit shift, width)
TONE_FIELDS=[
(0,0,1,0x800,0,1),(1,1,1,0x800,1,1),
(2,2,1,0x804,0,2),(3,3,1,0x804,4,2),(4,4,1,0x804,8,2),
(5,5,1,0x804,16,1),(6,6,1,0x804,24,6),
(7,8,2,0x808,0,12),(8,10,2,0x808,16,12),(9,12,2,0x80c,0,12),
(10,0x10,4,0x810,0,18),(11,0x14,4,0x814,0,18),
(12,0x20,4,0x818,0,26),(13,0x24,4,0x81c,0,26),(14,0x30,2,0x820,0,16),
(15,0x18,4,0x828,0,18),(16,0x1c,4,0x82c,0,18),
(17,0x28,4,0x830,0,26),(18,0x2c,4,0x834,0,26),(19,0x32,2,0x838,0,16),
(20,0x34,4,0x840,0,18),(21,0x38,4,0x844,0,18),
(22,0x44,4,0x848,0,26),(23,0x48,4,0x84c,0,26),(24,0x54,2,0x850,0,16),
(25,0x3c,4,0x858,0,18),(26,0x40,4,0x85c,0,18),
(27,0x4c,4,0x860,0,26),(28,0x50,4,0x864,0,26),(29,0x56,2,0x868,0,16)]
TONE_FIELDS += [(30+i,0x58+2*i,2,0x86c+4*(i//2),16*(i%2),16 if i%2 else 15) for i in range(8)]

def sha(b):return hashlib.sha256(b).hexdigest()
def u32(b,p):return struct.unpack_from('<I',b,p)[0]
def put(b,p,v):struct.pack_into('<I',b,p,v&0xffffffff)
def words(v):return struct.pack('<'+'I'*len(v),*[x&0xffffffff for x in v])
def load(name,path,expected):
    assert sha(path.read_bytes())==expected,str(path)
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None:raise RuntimeError(str(path))
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

def setfield(b,off,value,shift,width):
    mask=((1<<width)-1)<<shift;put(b,off,(u32(b,off)&~mask)|((value<<shift)&mask))
def tone_expected(old,vals):
    b=bytearray(old)
    for i,s,n,o,shift,width in TONE_FIELDS:setfield(b,o,vals[i],shift,width)
    return bytes(b)
def tone_compact(vals):
    b=bytearray(0x68)
    for i,s,n,o,shift,width in TONE_FIELDS:b[s:s+n]=(vals[i]&((1<<(n*8))-1)).to_bytes(n,'little')
    return bytes(b)
def cc_expected(old,vals,matrix,precision):
    b=bytearray(old);setfield(b,0x100,vals[0],0,1);setfield(b,0x100,precision,4,2)
    for i,v in enumerate(matrix):setfield(b,0x120+4*(i//2),v,16*(i%2),12)
    for i,v in enumerate(vals[11:14]):setfield(b,0x140,v,i*8,8)
    setfield(b,0x144,vals[14],16,16);setfield(b,0x144,vals[15],0,15)
    return bytes(b)
def cc_compact(vals,matrix,precision):
    b=bytearray(28);b[0]=vals[0]&255;b[1]=precision&255
    for i,v in enumerate(matrix):struct.pack_into('<H',b,2+i*2,v&65535)
    b[20:23]=bytes(v&255 for v in vals[11:14])
    struct.pack_into('<HH',b,24,vals[15]&65535,vals[14]&65535)
    return bytes(b)
def gamma_expected(old,g):
    b=bytearray(old)
    for value,bit in zip(g,[16,17,24,25]):setfield(b,0x800,value,bit,1)
    return bytes(b)

class Machine:
    def __init__(self,data,label):
        self.label=label;self.u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u=self.u
        u.mem_map(0,(len(data)+4095)&~4095);u.mem_write(0,data)
        for a,n in [(MMIO,0x4000),(P,0x4000),(STACK,0x10000),(SRC,0x40000),(TABLE,0x40000),(HALT,0x1000)]:u.mem_map(a,n)
        self.count=Counter();self.history=[];self.visited=set();self.capture=False;self.reads=set();self.mmio_writes=0;self.copies=[]
        self.bit15_changes=[];self.protected={0x144,0x86c,0x870,0x874,0x878,0x920,0x924,0x928,0x930,0x934}
        u.hook_add(UC_HOOK_MEM_WRITE,self.write,begin=MMIO,end=MMIO+0x3fff)
        u.hook_add(UC_HOOK_MEM_READ,self.read,begin=P,end=P+0x1fff)
        for pc in ([0x4d1b4,0x4d118] if label=='SAM7' else [0x140154]):u.hook_add(UC_HOOK_CODE,self.stub,begin=pc,end=pc)
        if label=='IMG':u.hook_add(UC_HOOK_CODE,self.copy,begin=0x4f2f0,end=0x4f2f0)
        # Limit optional instruction evidence to small programmers, not memory-copy loops.
        lo,hi=(0x4fdb6,0x53e4c) if label=='SAM7' else (0xd0c74,0xd4690)
        u.hook_add(UC_HOOK_CODE,self.code,begin=lo,end=hi)
    def code(self,u,a,n,_):
        if self.capture:self.visited.add((a,n,bool(u.reg_read(UC_ARM_REG_CPSR)&32)))
    def stub(self,u,a,n,_):u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    def copy(self,u,a,n,_):
        self.copies.append([u.reg_read(r) for r in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2]])
        # Original ARM memcpy executes unchanged; it is NOT substituted.
    def read(self,u,access,a,n,v,_):
        if self.capture:self.reads.add((u.reg_read(UC_ARM_REG_PC),a-P,n))
    def write(self,u,access,a,n,v,_):
        self.mmio_writes+=1
        for off in self.protected:
            adr=MMIO+off
            if a<=adr and adr+4<=a+n:
                old=u32(bytes(u.mem_read(adr,4)),0);new=(v>>(8*(adr-a)))&0xffffffff
                if (old^new)&0x8000:self.bit15_changes.append([u.reg_read(UC_ARM_REG_PC),adr,old,new])
    def run(self,tag,entry,param,old,regs=None,arm=False,capture=False,aux=None):
        u=self.u;self.capture=capture;self.copies=[];u.mem_write(P,param);u.mem_write(MMIO,old)
        if aux is not None:u.mem_write(AUX,aux)
        u.mem_write(STACK+0xf000,b'\xa7'*0x1000)
        for reg in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11,UC_ARM_REG_R12]:u.reg_write(reg,0)
        for r,v in (regs or {UC_ARM_REG_R0:P}).items():u.reg_write(r,v)
        u.reg_write(UC_ARM_REG_SP,STACK+0xff00);u.reg_write(UC_ARM_REG_LR,HALT|1)
        u.emu_start(entry if arm else entry|1,HALT,count=300000)
        assert u.reg_read(UC_ARM_REG_PC)==HALT,(tag,hex(u.reg_read(UC_ARM_REG_PC)))
        got=bytes(u.mem_read(MMIO,0x4000));self.count[tag]+=1
        self.history.append({'tag':tag,'entry':hex(entry),'mode':'ARM' if arm else 'Thumb','parameter_sha256':sha(param),'mmio_before_sha256':sha(old),'mmio_after_sha256':sha(got),'return_r0':u.reg_read(UC_ARM_REG_R0),'original_copy_calls':list(self.copies)})
        return got

def main():
    if not __debug__:raise RuntimeError('Assertions must be enabled')
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ['sections','repo','sdk','out']:ap.add_argument(name,type=Path)
    ap.add_argument('--cases',type=int,default=256);a=ap.parse_args()
    if a.cases<8:ap.error('At least eight cases required')
    a.out.mkdir(parents=True,exist_ok=True)
    audit=load('audit',a.repo/'tools/m10r_yblend_bit15_audit1a.py',AUDIT_SHA)
    parser=load('assets',a.repo/'tools/m10r_b2y_assets.py',PARSER_SHA)
    images={name:(a.sections/name).read_bytes() for name in audit.HASHES}
    for name,b in images.items():assert sha(b)==audit.HASHES[name]
    img=images['092_IMG-System.bin'];sam=images['100_IMG-SAM7.bin']
    guards=audit.validate_identities(img,sam)
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB);md.detail=True;ma=Cs(CS_ARCH_ARM,CS_MODE_ARM);ma.detail=True
    def ins(b,pc,arm=False):return next((ma if arm else md).disasm(b[pc:pc+4],pc,count=1))
    for adr,label,mov,rid,call,drivercall,driver in [(0x153d4e,'COLORCORRECTION0     String:%s',0x153d58,6,0x153d5c,0x153d7c,0xd0c74),(0x154bfc,'TONE     String:%s',0x154c06,8,0x154c0a,0x154c90,0xd3c20)]:
        i=ins(img,adr);assert i.mnemonic=='adr';p=((adr+4)&~3)+i.operands[1].imm
        assert img[p:].split(b'\0')[0].decode()==label
        i=ins(img,mov);assert i.operands[1].imm==rid and i.reg_name(i.operands[0].reg)=='r1'
        assert ins(img,call).operands[0].imm==0x1a0fc4
        assert ins(img,drivercall).operands[0].imm==driver
        guards.append({'label':label,'record':rid,'adr':hex(adr),'driver':hex(driver),'call_mode':ins(img,drivercall).mnemonic})
    for pc,target,prefix,arm in [(0x4fed0,0x50138,b'I:Im_B2Y_Ctrl_CC_Matrix',False),(0x53e38,0x53e50,b'I:Im_B2Y_Ctrl_Tone',True),(0x51c34,0x51f8c,b'I:Im_B2Y_Ctrl_Gamma',False)]:
        i=ins(sam,pc,arm);computed=pc+8+i.operands[-1].imm if arm else ((pc+4)&~3)+i.operands[-1].imm
        assert computed==target and sam[target:].startswith(prefix)
        guards.append({'sam_diagnostic':prefix.decode(),'pc':hex(pc),'string_offset':hex(target),'mode':'ARM' if arm else 'Thumb'})
    raw=(a.sections/B2Y_FILE).read_bytes();assert sha(raw)==B2Y_SHA
    records=parser.parse_records(raw);extracted=[];normal={};tables={}
    for r in records:
        if r.record_id not in [6,8,9,11,12,13,25,26]:continue
        h=0x14+r.index*0xa90;nk=u32(raw,h+12)
        keys=[raw[h+16+k*64:h+16+(k+1)*64].split(b'\0')[0].decode() for k in range(nk)]
        b=raw[r.payload_offset:r.payload_offset+r.size]
        d={'id':r.record_id,'index':r.index,'offset':hex(r.payload_offset),'size':r.size,'keys':keys,'sha256':sha(b)}
        if r.record_id in [25,26]:tables[(r.record_id,next(k.split('_CONTRAST:')[-1] for k in keys))]=b
        else:
            assert r.record_id not in normal
            normal[r.record_id]=list(struct.unpack('<'+'I'*(len(b)//4),b));d.update(values=normal[r.record_id],payload_hex=b.hex())
        extracted.append(d)
    assert normal[6][11:14]==[77,150,29]
    assert normal[8][:10]==[1,0,1,1,0,0,0,1024,2661,410]
    assert normal[12][:3]==[1224,2403,469] and normal[13][:2]==[0,32]
    ip=Machine(img,'IMG');sp=Machine(sam,'SAM7');rng=random.Random(0xB1A2026)
    source0=tables[(25,'MEDIUM')];source1=tables[(26,'MEDIUM')]
    ip.u.mem_write(SRC,source0);ip.u.mem_write(SRC+0x20000,source1)
    def oldstate():
        b=bytearray(rng.randbytes(0x4000));put(b,4,u32(b,4)&~0x30);return bytes(b)
    def compare(got,expected,tag):
        if got!=expected:
            dif=[(hex(i),hex(u32(got,i)),hex(u32(expected,i))) for i in range(0,0x4000,4) if got[i:i+4]!=expected[i:i+4]]
            raise AssertionError((tag,dif))
    def runcc(vals,matrix,precision,old,tag,capture=False):
        aux=bytearray(0x34)
        for i,v in enumerate(matrix):put(aux,12+4*i,v)
        put(aux,0x30,precision)
        exp=cc_expected(old,vals,matrix,precision)
        g=ip.run(tag,0xd0c74,words(vals),old,{UC_ARM_REG_R0:P,UC_ARM_REG_R1:0,UC_ARM_REG_R2:AUX},capture=capture,aux=bytes(aux))
        compare(g,exp,tag+'IMG')
        h=sp.run(tag,0x4fdb6,cc_compact(vals,matrix,precision),old,capture=capture);compare(h,exp,tag+'SAM7')
        return g
    def runtone(vals,old,tag,capture=False):
        exp=tone_expected(old,vals)
        ip.u.mem_write(TABLE,b'\xa5'*0x40000)
        g=ip.run(tag,0xd3c20,words(vals),old,{UC_ARM_REG_R0:P,UC_ARM_REG_R1:SRC,UC_ARM_REG_R2:SRC+0x20000,UC_ARM_REG_R3:0},arm=True,capture=capture)
        compare(g,exp,tag+'IMG');assert ip.u.reg_read(UC_ARM_REG_R0)==0
        n=0x14000 if vals[2]==0 else 0xa000 if vals[2]==1 else 0x5000
        expect_table=bytearray(b'\xa5'*0x40000);expect_table[:n]=source0[:n];copies=[[TABLE,SRC,n]]
        if vals[5]==0 and vals[3]==1:expect_table[0xa000:0xa000+n]=source1[:n];copies.append([TABLE+0xa000,SRC+0x20000,n])
        assert ip.copies==copies and bytes(ip.u.mem_read(TABLE,0x40000))==bytes(expect_table)
        h=sp.run(tag,0x5398c,tone_compact(vals),old,arm=True,capture=capture);compare(h,exp,tag+'SAM7')
        return g
    def rungamma(vals,old,tag,capture=False):
        g=ip.run(tag+'_interpolation',0xd25a8,words([vals[0],vals[1],0,0,0,0]),old,capture=capture)
        compare(g,gamma_expected(old,[vals[0],vals[1],(u32(old,0x800)>>24)&1,(u32(old,0x800)>>25)&1]),tag+'IMGinterp')
        h=ip.run(tag+'_dg',0xd15ec,words(vals[2:]),g,capture=capture);exp=gamma_expected(old,vals);compare(h,exp,tag+'IMGdg')
        j=sp.run(tag,0x51bcc,bytes(v&255 for v in vals),old,capture=capture);compare(j,exp,tag+'SAM7')
        return h
    # Fresh calibration setup in a common register state; CC0 matrix is a synthetic auxiliary input.
    m=[512,0,0,0,512,0,0,0,512];base=oldstate()
    base=runcc(normal[6],m,0,base,'normal_cc0',True)
    base=runtone(normal[8],base,'normal_tone',True)
    base=rungamma(normal[9][:2]+normal[11],base,'normal_gamma',True)
    for driver,values,expected in [(0xd4570,normal[12],audit.expected_ycc),(0xd4480,normal[13],audit.expected_blend)]:
        got=ip.run('normal_yc_blend',driver,words(values),base,capture=True);compare(got,expected(base,values,False),'normal_yc_blend');base=got
    # Demonstrate independent configuration, not independent ISP pixels or equal RGB domains.
    isolation=[]
    for family,start,width in [('CC0',11,8),('TONE',7,12),('YC',0,13)]:
        rid={'CC0':6,'TONE':8,'YC':12}[family]
        for channel in range(3):
            for value in [0,1,(1<<width)-1,1<<width,0xffffffff]:
                vals=normal[rid].copy();vals[start+channel]=value
                if family=='CC0':got=runcc(vals,m,0,base,'isolation_cc0')
                elif family=='TONE':got=runtone(vals,base,'isolation_tone')
                else:
                    got=ip.run('isolation_yc',0xd4570,words(vals),base)
                    compare(got,audit.expected_ycc(base,vals,False),'isolation_yc')
                    combined=struct.pack('<15H2B4H',*[x&65535 for x in vals],*[x&255 for x in normal[13][:2]],*[x&65535 for x in normal[13][2:]])
                    h=sp.run('isolation_yc',0x51da6,combined,base);compare(h,audit.expected_blend(got,normal[13],False),'isolation_ycSAM')
                allowed={0x140} if family=='CC0' else {0x808,0x80c} if family=='TONE' else {0x900,0x904}
                changed=[i for i in range(0,0x4000,4) if got[i:i+4]!=base[i:i+4]]
                assert set(changed)<=allowed
                isolation.append({'family':family,'component':channel,'test_value':value,'changed_registers':[hex(MMIO+x) for x in changed]})
    controls=[]
    for rgb in range(2):
        for second in range(2):
            for select in range(2):
                v=normal[8].copy();v[0]=rgb;v[1]=second;v[5]=select
                got=runtone(v,base,'tone_controls',True)
                assert u32(got,0x800)&3==rgb+2*second and (u32(got,0x804)>>16)&1==select
                controls.append({'first_enable':rgb,'second_enable':second,'selector':select,'mmio_20800':hex(u32(got,0x800)),'mmio_20804':hex(u32(got,0x804)),'copy_calls':list(ip.copies)})
    for flags in range(16):rungamma([(flags>>i)&1 for i in range(4)],base,'gamma_boolean')
    # Full-width synthetic field interventions across both layouts. No new presets are asserted.
    edges=[0,1,0xff,0xfff,0x3fff,0x7fff,0x8000,0xffffffff]
    for n in range(a.cases):
        old=oldstate();cv=[edges[(n+i)%len(edges)] if n<8 else rng.getrandbits(32) for i in range(16)]
        matrix=[rng.getrandbits(32) for _ in range(9)];precision=rng.getrandbits(32)
        runcc(cv,matrix,precision,old,'stress_cc0')
        tv=[edges[(n+i)%len(edges)] if n<8 else rng.getrandbits(32) for i in range(44)]
        runtone(tv,old,'stress_tone')
    # Hold CCYC and auxiliary matrix fixed; changing unused record-6 matrix slots cannot change MMIO.
    cc_unused=[]
    for i in range(1,11):
        v=normal[6].copy();v[i]^=0xffffffff
        g=runcc(v,m,0,base,'cc0_record_matrix_negative')
        compare(g,base,'record CC0 matrix slots do not supply current aux matrix')
        cc_unused.append(i)
    # Actual LOW/MEDIUM/HIGH table records, original copying, same control payload.
    tone_uploads=[]
    for level in ['LOW','MEDIUM','HIGH']:
        source0=tables[(25,level)];source1=tables[(26,level)]
        ip.u.mem_write(SRC,source0);ip.u.mem_write(SRC+0x20000,source1)
        g=runtone(normal[8],base,'contrast_table_upload',True)
        compare(g,base,'table selection does not change control registers')
        tone_uploads.append({'contrast_key':level,'copies':list(ip.copies),'prefix_sha256':[sha(source0[:0xa000]),sha(source1[:0xa000])],'table_output_sha256':sha(bytes(ip.u.mem_read(TABLE,0x40000)))})
    assert not ip.bit15_changes and not sp.bit15_changes
    # Related-SDK evidence is hash-verified text only. Preserve different layouts/field widths.
    sources=[];texts={}
    for path,digest in SDK_HASHES.items():
        b=(a.sdk/path).read_bytes();assert sha(b)==digest,path
        texts[Path(path).name]=b.decode();sources.append({'path':path,'sha256':digest,'url':f'https://github.com/ZMlogicL/companyTask/blob/{SDK_COMMIT}/{path}'})
    sdk_anchors=[]
    for name,needle,meaning in [('imr2yctrl2.h','Coefficient of Yb convert (8bits)','SDK CCYC role'),('imr2yctrl.h','TC luminance Yb enable','SDK second tone enable'),('imr2yctrl.h','YTc = Y(coefficient "TCYC")','SDK selector 0'),('imr2yctrl.h','YTc = Yb(coefficient "CCYC")','SDK selector 1'),('imr2yctrl2.h','Gamma correction Yb Table simultaneous writing selection','SDK gamma field is not directly the M10-R 4-byte ABI'),('imr2y.h','Chroma referenced luminance blend control common','Separate SDK YBCRV block, not YYBLND/YBBLND')]:
        text=texts[name];assert needle in text;sdk_anchors.append({'file':name,'line':text[:text.index(needle)].count('\n')+1,'meaning':meaning})
    anchors=[]
    for machine,b in [(ip,img),(sp,sam)]:
        for pc,n,thumb in sorted(machine.visited):
            i=ins(b,pc,not thumb);anchors.append(f'{machine.label} {"Thumb" if thumb else "ARM"} {pc:08x}: {i.bytes.hex():8} {i.mnemonic} {i.op_str}')
    (a.out/'original_executed_instructions.txt').write_text('\n'.join(anchors)+'\n')
    (a.out/'execution_history.json').write_text(json.dumps({'IMG':ip.history,'SAM7':sp.history},indent=2)+'\n')
    rows=[normal[6][11:14],normal[8][7:10],normal[12][:3]]
    det=rows[0][0]*(rows[1][1]*rows[2][2]-rows[1][2]*rows[2][1])-rows[0][1]*(rows[1][0]*rows[2][2]-rows[1][2]*rows[2][0])+rows[0][2]*(rows[1][0]*rows[2][1]-rows[1][1]*rows[2][0])
    report={'status':'PASS_CONTROL_PATHS_ONLY','gate_c_passed':False,'source_script_sha256':sha(Path(__file__).read_bytes()),'seed':'0xB1A2026','firmware_sha256':{**audit.HASHES,B2Y_FILE:B2Y_SHA},'identity_guards':guards,'calibration_records':extracted,
      'coefficient_rows':{'cc0_trailing':rows[0],'tone':rows[1],'final_yc_first_row':rows[2],'sums':[sum(x) for x in rows],'determinant':det,'mathematical_scope':'Nonzero determinant is an algebraic fact about stored rows, not proof they operate on the same RGB samples or of a physical denominator.'},
      'normal_tone_controls':{'record8_first_enable':normal[8][0],'record8_second_enable':normal[8][1],'record8_selector':normal[8][5],'destinations':['0x20020800 bit0','0x20020800 bit1','0x20020804 bit16'],'signal_names_in_leica':'not established by these instructions','related_sdk_hypothesis':['RGB tone enabled','Yb tone disabled','YTc selected from TCYC-derived Y']},
      'tone_field_map':[{'record_slot':i,'sam_offset':hex(s),'sam_load_bytes':n,'register':hex(MMIO+o),'shift':shift,'width':width} for i,s,n,o,shift,width in TONE_FIELDS],
      'tests':{'per_machine_counts':{'IMG':dict(ip.count),'SAM7':dict(sp.count)},'original_entry_executions':sum(ip.count.values())+sum(sp.count.values()),'comparison_window_bytes':0x4000,'mmio_writes':ip.mmio_writes+sp.mmio_writes,'paired_bit15_changes':0,'isolation_cases':isolation,'tone_control_cases':controls,'contrast_table_uploads':tone_uploads,'unused_record6_matrix_slots_tested':cc_unused,'source_reads':{m.label:[{'pc':hex(pc),'offset_from_parameter':hex(p),'bytes':n} for pc,p,n in sorted(m.reads)] for m in [ip,sp]},'stubs':['SAM7 0x4d1b4 and 0x4d118 clock helpers','IMG 0x140154 diagnostic logger'],'original_memcpy':'IMG ARM 0x4f2f0 executes unchanged, complete 0x40000-byte table window compared','external_sdk_code_executed':False},
      'sdk':{'commit':SDK_COMMIT,'sources':sources,'anchors':sdk_anchors},
      'scope':['No physical sensor, ISP pixel arithmetic, clock side effects, camera state or photograph is emulated.','SAM7 28-byte CC0 and 104-byte Tone structures are analysis-side packing reconstructions validated through the original programmers, not recovered firmware constructors.','CC0 normal matrix/precision in these tests are explicit auxiliary inputs; the caller-derived state block is not claimed to equal the static record-6 matrix.','The distinct coefficient rows, independently programmed controls, table-copy condition and record provenance are original-firmware facts. Their Y/Yb signal names and connection to Y BLEND remain related-SDK hypotheses.','Shared physical RGB input domains, denominator, rounding, stage order, paired-field meaning and final Y BLEND per-pixel equation remain unproved.','The related SDK tone/gamma ABI differs; no assumption that M10-R gamma bit25 is a Yb enable is permitted.','No application source or photographic output changes.']}
    (a.out/'ybpath_results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'executions':report['tests']['original_entry_executions'],'counts':report['tests']['per_machine_counts'],'rows':rows,'determinant':det},indent=2))
if __name__=='__main__':main()
