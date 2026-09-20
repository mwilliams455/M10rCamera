#!/usr/bin/env python3
"""Execute original Thumb register programmers with RAM-backed MMIO; NOT an ISP/pixel emulator.
Requires capstone==5.0.3 and unicorn==2.1.3. Input: verified m10r_sections.py output.
"""
from __future__ import annotations
import argparse, hashlib, json, random, struct
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from capstone.arm import ARM_OP_IMM
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

MMIO=0x20020000; PARAM=0x10000000; STACK=0x11000000; HALT=0x1000000
HASHES={
    '092_IMG-System.bin':'53e307ad2b241e4684f5f9974c1b9780bcbc9e37ac580d8dcaf45cf72aae80d4',
    '100_IMG-SAM7.bin':'c30351bb884ffd66120bf201e9da5e3a1f6eef970e2eb9b8a2400cca04de51ae',
}
PAIRS=[0x20020920,0x20020924,0x20020928,0x20020930,0x20020934,
       0x200210c4,0x200210c8,0x200210cc,0x2002078c,0x20020790,0x20020794]

def pair(old: int, lo: int, hi: int) -> int:
    return (old&0x8000)|(lo&0x7fff)|((hi&0xffff)<<16)

def u32(b: bytes, p: int) -> int:
    return struct.unpack_from('<I',b,p)[0]

def put(b: bytearray, p: int, v: int) -> None:
    struct.pack_into('<I',b,p,v)

def expected_ycc(old: bytes, p: list[int], fallback: bool) -> bytes:
    out=bytearray(old)
    if fallback:
        p=[1224,2403,469,-691,-1357,2048,2048,-1715,-333]+[0x7fff,0x8000]*3
    for i,v in enumerate(p[:9]):
        a=0x900+(i//2)*4; shift=16*(i%2); mask=0x1fff<<shift
        put(out,a,(u32(out,a)&~mask)|((v&0x1fff)<<shift))
    for i in range(3):
        a=0x920+4*i
        put(out,a,pair(u32(out,a),p[9+2*i],p[10+2*i]))
    return bytes(out)

def expected_blend(old: bytes, p: list[int], fallback: bool) -> bytes:
    out=bytearray(old)
    # Original fallback clears BOTH six-bit controls. Normal calibration [0,32]
    # must not be silently substituted for that fallback.
    if fallback:
        p=[0,0,0x7fff,0x8000,0x7fff,0x8000]
    put(out,0x92c,(u32(out,0x92c)&~0x3f3f)|(p[0]&63)|((p[1]&63)<<8))
    for i in range(2):
        a=0x930+4*i
        put(out,a,pair(u32(out,a),p[2+2*i],p[3+2*i]))
    return bytes(out)

def expected_post(old: bytes, p: list[int], fallback: bool) -> bytes:
    out=bytearray(old)
    if fallback:
        p=[0x3fff]*6
    for i in range(3):
        a=0x10c4+4*i
        put(out,a,pair(u32(out,a),p[2*i],p[2*i+1]))
    return bytes(out)

class Programmer:
    def __init__(self, data: bytes, clock_stubs: bool=False):
        self.uc=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
        u=self.uc
        u.mem_map(0,(len(data)+4095)&~4095); u.mem_write(0,data)
        for a,size in [(MMIO,0x4000),(PARAM,0x1000),(STACK,0x10000),(HALT,0x1000)]:
            u.mem_map(a,size)
        self.total_writes=0; self.sites=set(); self.bit15_changes=[]; self.calls=0
        u.hook_add(UC_HOOK_MEM_WRITE,self.write_hook,begin=MMIO,end=MMIO+0x3fff)
        if clock_stubs:
            for pc in (0x4d1b4,0x4d118):
                u.hook_add(UC_HOOK_CODE,self.clock_stub,begin=pc,end=pc)

    def clock_stub(self,u,addr,size,_):
        # Clock-management helpers are intentionally not modeled.
        # The original register-programming instructions remain unchanged.
        u.reg_write(UC_ARM_REG_R0,0)
        u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))

    def write_hook(self,u,access,addr,size,value,_):
        if addr in PAIRS:
            old=int.from_bytes(u.mem_read(addr,size),'little')
            self.total_writes+=1
            self.sites.add(u.reg_read(UC_ARM_REG_PC))
            if (old^value)&0x8000:
                self.bit15_changes.append(dict(pc=hex(u.reg_read(UC_ARM_REG_PC)),
                    address=hex(addr),before=old,after=value))

    def run(self,entry: int,param: bytes,mmio: bytes,fallback: int=0,
            stop: int=HALT,mode_first: bool=False) -> bytes:
        u=self.uc
        u.mem_write(PARAM,param); u.mem_write(MMIO,mmio)
        u.reg_write(UC_ARM_REG_SP,STACK+0xff00); u.reg_write(UC_ARM_REG_LR,HALT|1)
        u.reg_write(UC_ARM_REG_R0,fallback if mode_first else PARAM)
        u.reg_write(UC_ARM_REG_R1,PARAM if mode_first else fallback)
        u.emu_start(entry|1,stop,count=20000)
        if u.reg_read(UC_ARM_REG_PC)!=stop:
            raise RuntimeError(f'Function {entry:x} did not reach stop; PC={u.reg_read(UC_ARM_REG_PC):x}')
        self.calls+=1
        return bytes(u.mem_read(MMIO,0x4000))

def validate_identities(img: bytes, sam: bytes) -> list[dict]:
    """Bind actual ADR references, lookup immediates and BL targets, not nearby strings."""
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB); md.detail=True
    specs=[
        (0x154d82,'WBCLIPLEVEL     String:%s',0x154d8c,4,0x154d90,0x154dac,0xd42e0),
        (0x154e3e,'Y BLEND     String:%s',0x154e48,13,0x154e4c,0x154e68,0xd4480),
        (0x154ef2,'YC CONVERSION     String:%s',0x154efc,12,0x154f00,0x154f1c,0xd4570),
        (0x154894,'POST PROCESSING FILTER     String:%s',0x15489e,23,0x1548a2,0x1548be,0xd34f0),
    ]
    rows=[]
    def ins(data,pc):
        return next(md.disasm(data[pc:pc+4],pc,count=1))
    for adr,text,mov,rid,call,driver_call,driver in specs:
        i=ins(img,adr)
        assert i.mnemonic=='adr' and i.operands[1].type==ARM_OP_IMM
        target=((adr+4)&~3)+i.operands[1].imm
        assert img[target:].split(b'\x00',1)[0].decode('ascii')==text
        i=ins(img,mov)
        assert i.mnemonic=='movs' and i.reg_name(i.operands[0].reg)=='r1' and i.operands[1].imm==rid
        i=ins(img,call)
        assert i.mnemonic=='bl' and i.operands[0].imm==0x1a0fc4
        i=ins(img,driver_call)
        assert i.mnemonic=='bl' and i.operands[0].imm==driver
        rows.append(dict(label=text.split('     ')[0],record=hex(rid),adr_pc=hex(adr),
            string_offset=hex(target),lookup_call=hex(call),driver_call=hex(driver_call),
            driver_offset=hex(driver)))
    for pc,prefix in [(0x503fc,b'I:Im_B2Y_Ctrl_Multi_Axis'),
                       (0x51f0c,b'I:Im_B2Y_Ctrl_Yc_Convert'),
                       (0x52352,b'I:Im_B2Y_Ctrl_PostFilter')]:
        i=ins(sam,pc); assert i.mnemonic=='adr'
        a=((pc+4)&~3)+i.operands[1].imm
        assert sam[a:].startswith(prefix)
    return rows

def main():
    if not __debug__:
        raise RuntimeError('Do not use python -O: audit assertions must remain enabled')
    ap=argparse.ArgumentParser()
    ap.add_argument('sections',type=Path)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--cases',type=int,default=1024)
    args=ap.parse_args()
    if args.cases<7:
        ap.error('--cases must be at least 7 to retain boundary-value cases')
    data={}
    for fn,sha in HASHES.items():
        b=(args.sections/fn).read_bytes()
        if hashlib.sha256(b).hexdigest()!=sha:
            raise ValueError(f'SHA256 mismatch: {fn}')
        data[fn]=b
    identities=validate_identities(data['092_IMG-System.bin'],data['100_IMG-SAM7.bin'])
    img=Programmer(data['092_IMG-System.bin'])
    sam=Programmer(data['100_IMG-SAM7.bin'],True)
    rng=random.Random(0xB2152026)
    passed=0; cross=0; multi=0; central=0
    edges=[0,1,0x1fff,0x3fff,0x7fff,0x8000,0xffff]
    for n in range(args.cases):
        old=rng.randbytes(0x4000)
        c=[edges[(n+i)%len(edges)] if n<len(edges) else rng.randrange(65536) for i in range(15)]
        b=[rng.randrange(65536) for _ in range(6)]
        p=[rng.randrange(65536) for _ in range(6)]
        for fallback in (0,1):
            for entry,values,predict in [(0xd4570,c,expected_ycc),
                                         (0xd4480,b,expected_blend),
                                         (0xd34f0,p,expected_post)]:
                got=img.run(entry,struct.pack('<'+'I'*len(values),*values),old,fallback)
                exp=predict(old,values,bool(fallback))
                if got!=exp:
                    d=next(i for i,(x,y) in enumerate(zip(got,exp)) if x!=y)
                    raise AssertionError(f'{entry:x} fallback={fallback} case={n} MMIO+{d:x} mismatch')
                passed+=1
        # SAM7 has 15 YCC halfwords, two byte controls, then four blend halfwords.
        packed=struct.pack('<15H2B4H',*c,b[0]&255,b[1]&255,*b[2:])
        combined=sam.run(0x51da6,packed,old)
        assert combined==expected_blend(expected_ycc(old,c,False),b,False)
        cross+=1
        post=sam.run(0x522d8,struct.pack('<6H',*p),old)
        assert post==expected_post(old,p,False)
        cross+=1
        # Execute the exact central setup slice; there are no calls in this slice.
        got=img.run(0x155000,b'',old,stop=0x155054)
        exp=bytearray(old)
        for a in (0x78c,0x790,0x794):
            put(exp,a,pair(u32(exp,a),0x3fff,0))
        assert got==bytes(exp)
        central+=1
        # Complete Multi_Axis programmer, real table-copy helper, clock stubs only.
        # Check the three selected paired words, not the full Multi_Axis parameter ABI.
        params=bytearray(rng.randbytes(0x200))
        got=sam.run(0x4fede,bytes(params),old,fallback=n&1,mode_first=True)
        for i,a in enumerate((0x78c,0x790,0x794)):
            lo,hi=struct.unpack_from('<HH',params,0x1c0+4*i)
            assert u32(got,a)==pair(u32(old,a),lo,hi)
        multi+=1
    assert not img.bit15_changes and not sam.bit15_changes
    report={
        'selector_identity_guards':identities,
        'firmware_sections_sha256':HASHES,
        'emulator':'Unicorn 2.1.3, ARM Thumb, RAM-backed MMIO',
        'clock_helpers_stubbed':['SAM7+0x4d1b4','SAM7+0x4d118'],
        'cases':args.cases,'seed':'0xB2152026',
        'original_IMG_driver_calls_checked':passed,'cross_core_checks':cross,
        'central_slice_checks':central,'SAM7_MultiAxis_checks':multi,
        'total_checked_executions':passed+cross+central+multi,
        'pair_register_RMW_writes_observed':img.total_writes+sam.total_writes,
        'pair_register_write_sites':{
            'IMG':[hex(p) for p in sorted(img.sites)],
            'SAM7':[hex(p) for p in sorted(sam.sites)]},
        'bit15_mutations':0,'all_assertions_passed':True,
        'limitations':[
            'This checks software register packing, NOT imaging-hardware pixel arithmetic.',
            'No camera, sensor, ISP, runtime reset side effects, clock gating or image parity is simulated.',
            'The bit15 result is exact for executed programmers; other indirect firmware paths are not excluded.'],
    }
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    main()
