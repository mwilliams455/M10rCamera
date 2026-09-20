#!/usr/bin/env python3
"""Execute Leica's edge selector/lookup/programmers; not an ISP pixel emulator.

Usage: python script.py SECTIONS OUTDIR [--stress-cases 128]
Requires original capstone==5.0.3, unicorn==2.1.3. No network access is used.
"""
from __future__ import annotations
import argparse, hashlib, itertools, json, random, struct
from collections import Counter
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_REG_PC
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

HASHES={
 '092_IMG-System.bin':'53e307ad2b241e4684f5f9974c1b9780bcbc9e37ac580d8dcaf45cf72aae80d4',
 '100_IMG-SAM7.bin':'c30351bb884ffd66120bf201e9da5e3a1f6eef970e2eb9b8a2400cca04de51ae',
 '074_IMG_Calibration_Data_data_calib_B2Y.bin.bin':'ea935a8006ea3b0a765660bd1d89f6a52c9f60508ee5ba76650005d80372335b',
}
MMIO=0x20020000; PARAM=0x10000000; STACK=0x11000000; HALT=0x01000000
CALIB=0x12000000; REGISTRY=0x13000000; CACHE=0x408ce000
EDGE_SELECTOR=0x154064; EDGE_DRIVER=0xd16dc; SAM_EDGE=0x51342
Y_SELECTOR=0x154e18; Y_DRIVER=0xd4480
EDGE_REGS=[0xe00,0xe10,0xe14,0xe18,0xe20,0xe24,0xe28,0xe30,0xe34,0xe38,0xe40]
Y_REGS=[0x92c,0x930,0x934]
FALLBACK=[0,0]+[0]*12+[0x8000]*5+[0x1fff]*2

def sha(b): return hashlib.sha256(b).hexdigest()
def u32(b,p): return struct.unpack_from('<I',b,p)[0]
def cstr(b,p): return b[p:].split(b'\0',1)[0].decode('ascii')
def update(b,p,value,shift,width):
 mask=((1<<width)-1)<<shift
 struct.pack_into('<I',b,p,(u32(b,p)&~mask)|((value<<shift)&mask))
def edge_model(old,values,fallback=False):
 p=FALLBACK if fallback else values;out=bytearray(old)
 update(out,0xe00,p[0],0,2);update(out,0xe00,p[1],4,2)
 for first,base in [(2,0xe10),(8,0xe20)]:
  for i in range(6):update(out,base+(i//2)*4,p[first+i],16*(i%2),14)
 for i in range(5):update(out,0xe30+(i//2)*4,p[14+i],16*(i%2),16)
 update(out,0xe40,p[19],16,13);update(out,0xe40,p[20],0,13)
 return bytes(out)
def y_model(old,values):
 out=bytearray(old);update(out,0x92c,values[0],0,6);update(out,0x92c,values[1],8,6)
 for i in range(2):
  update(out,0x930+4*i,values[2+2*i],0,15);update(out,0x930+4*i,values[3+2*i],16,16)
 return bytes(out)
def pack_edge(p):
 # Analysis-side compact structure, not a recovered constructor.
 return struct.pack('<2B19H',p[0]&255,p[1]&255,*[v&65535 for v in p[2:19]],p[20]&65535,p[19]&65535)
def records(b):
 n=u32(b,12);out=[]
 for index in range(n):
  h=0x14+index*0xa90;rid,rel,size,nkeys=struct.unpack_from('<4I',b,h)
  off=0x14+n*0xa90+rel
  if off+size>len(b) or nkeys>42 or size%4:raise ValueError('Unexpected calibration bounds')
  blob=b[off:off+size]
  out.append(dict(index=index,record_id=rid,header_offset=hex(h),payload_offset=hex(off),payload_size=size,
   keys=[cstr(b,h+16+k*64) for k in range(nkeys)],payload_sha256=sha(blob),values=list(struct.unpack('<'+'I'*(size//4),blob))))
 return out

class Machine:
 def __init__(self,b,sam=False,calibration=None):
  self.u=Uc(UC_ARCH_ARM,UC_MODE_THUMB);u=self.u;self.sam=sam
  u.mem_map(0,(len(b)+4095)&~4095);u.mem_write(0,b)
  for a,n in [(MMIO,0x4000),(PARAM,0x1000),(STACK,0x10000),(HALT,0x1000),(CACHE,0x1000)]:u.mem_map(a,n)
  if calibration is not None:
   u.mem_map(CALIB,0x200000);u.mem_write(CALIB,calibration[4:]);u.mem_map(REGISTRY,0x1000)
   u.mem_write(REGISTRY+0x208,struct.pack('<I',CALIB))
  self.file_available=True;self.history=[];self.current={};self.all_writes=Counter()
  pcs=[0x4d1b4,0x4d118] if sam else [0x1a0c80,0x140154,0x1a0fc4,EDGE_DRIVER,Y_DRIVER,0x4efd8,0x4f1f8,0x4f164]
  for pc in pcs:u.hook_add(UC_HOOK_CODE,self.code,begin=pc,end=pc)
  u.hook_add(UC_HOOK_MEM_WRITE,self.write,begin=MMIO,end=MMIO+0x3fff)
  u.hook_add(UC_HOOK_MEM_READ,self.read,begin=MMIO,end=MMIO+0x3fff)
  u.hook_add(UC_HOOK_MEM_WRITE,self.source_write,begin=CALIB,end=CALIB+0x1fffff)
 def string(self,p):
  out=bytearray()
  while len(out)<256:
   x=bytes(self.u.mem_read(p+len(out),1))
   if x==b'\0':return out.decode('ascii')
   out+=x
  raise ValueError('Unterminated emulated string')
 def code(self,u,pc,size,_):
  if self.sam:
   u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
  if pc==0x1a0c80:
   assert self.string(u.reg_read(UC_ARM_REG_R0))=='B2Y.bin'
   u.reg_write(UC_ARM_REG_R0,REGISTRY if self.file_available else 0)
   u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));self.current['resolver_calls']+=1
  elif pc==0x140154:u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
  elif pc==0x1a0fc4:self.current['lookups'].append(dict(record=u.reg_read(UC_ARM_REG_R1),key=self.string(u.reg_read(UC_ARM_REG_R2))))
  elif pc in [EDGE_DRIVER,Y_DRIVER]:
   p=u.reg_read(UC_ARM_REG_R0);n=21 if pc==EDGE_DRIVER else 6
   self.current['drivers'].append(dict(entry=hex(pc),pointer=hex(p),fallback=u.reg_read(UC_ARM_REG_R1),
     payload=list(struct.unpack('<'+'I'*n,u.mem_read(p,4*n))) if p else None))
  else:self.current['string_helpers'][hex(pc)]+=1
 def write(self,u,access,p,n,v,_):
  self.current['writes'].append(dict(pc=hex(u.reg_read(UC_ARM_REG_PC)),address=hex(p),bytes=n,value=v))
  self.all_writes[hex(p)]+=1
 def read(self,u,access,p,n,v,_):self.current['read_addresses'].add(p)
 def source_write(self,*unused):self.current['calibration_writes']+=1
 def invalidate(self):
  self.u.mem_write(0x408cede0,b'\xff\xff');self.u.mem_write(0x408cede4,b'\xff'*4)
  self.u.mem_write(0x408cedbf,b'\0')
 def run(self,tag,entry,param,old,flag=0):
  self.current=dict(tag=tag,entry=hex(entry),lookups=[],drivers=[],resolver_calls=0,string_helpers=Counter(),writes=[],read_addresses=set(),calibration_writes=0)
  u=self.u;u.mem_write(PARAM,param);u.mem_write(MMIO,old);u.mem_write(STACK,b'\xa5'*0x10000)
  u.reg_write(UC_ARM_REG_R0,PARAM);u.reg_write(UC_ARM_REG_R1,flag)
  u.reg_write(UC_ARM_REG_SP,STACK+0xff00);u.reg_write(UC_ARM_REG_LR,HALT|1)
  u.emu_start(entry|1,HALT,count=300000)
  assert u.reg_read(UC_ARM_REG_PC)==HALT,(tag,hex(u.reg_read(UC_ARM_REG_PC)))
  got=bytes(u.mem_read(MMIO,0x4000));self.current['read_addresses']=[hex(p) for p in sorted(self.current['read_addresses'])]
  self.current['string_helpers']=dict(self.current['string_helpers']);self.current['result_mmio_sha256']=sha(got)
  assert self.current['calibration_writes']==0
  self.history.append(self.current);return got

def params(key,sharp='MEDIUM'):
 mode,iso=key.removeprefix('_B2YMODE:').split('_ISO:')
 # Numerical IDs are deliberate harness fixtures, not recovered Leica enumerations.
 mid={'STILL':1,'STILLLINK':2,'SLIVE':3,'SMAGNI':4}.get(mode,77)
 p=bytearray(512);struct.pack_into('<H',p,0,mid);struct.pack_into('<I',p,0xb0,int(iso))
 for at,text in [(2,'_B2YMODE:'+mode),(0xb4,'_ISO:'+iso),(0x140,'_SHARPNESS:'+sharp)]:
  x=text.encode()+b'\0';p[at:at+len(x)]=x
 return bytes(p)

def main():
 if not __debug__:raise RuntimeError('Do not disable assertions')
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('sections',type=Path);ap.add_argument('out',type=Path);ap.add_argument('--stress-cases',type=int,default=128);a=ap.parse_args()
 if a.stress_cases<8:ap.error('At least eight stress cases required')
 a.out.mkdir(parents=True,exist_ok=True);data={}
 for name,h in HASHES.items():
  data[name]=(a.sections/name).read_bytes();assert sha(data[name])==h,name
 img=data['092_IMG-System.bin'];sam=data['100_IMG-SAM7.bin'];b=data['074_IMG_Calibration_Data_data_calib_B2Y.bin.bin']
 rr=records(b);edge=[r for r in rr if r['record_id']==17];yb=[r for r in rr if r['record_id']==13]
 assert len(yb)==1 and yb[0]['keys']==[''] and yb[0]['values']==[0,32,16383,16383,16383,16383]
 assert len(edge)==15 and all(r['payload_size']==84 for r in edge)
 md=Cs(CS_ARCH_ARM,CS_MODE_THUMB);md.detail=True
 def ins(blob,pc):return next(md.disasm(blob[pc:pc+4],pc,count=1))
 def adr_text(blob,pc):
  i=ins(blob,pc);assert i.mnemonic=='adr';p=((pc+4)&~3)+i.operands[1].imm;return p,cstr(blob,p)
 et,es=adr_text(img,0x1540aa);st,ss=adr_text(sam,0x5149c)
 assert es.startswith('EDGE SYNTHESIS') and ss.startswith('I:Im_B2Y_Ctrl_EdgeBlend')
 assert ins(img,0x1540b4).op_str=='r1, #0x11'
 for pc,dst in [(0x1540b8,0x1a0fc4),(0x1540d8,EDGE_DRIVER)]:assert ins(img,pc).mnemonic=='bl' and ins(img,pc).operands[0].imm==dst
 m=Machine(img,calibration=b);s=Machine(sam,True);rng=random.Random(0xED6E2026);key_results=[]
 keys=[(key,r) for r in edge for key in r['keys']];assert len(keys)==len({k for k,r in keys})
 for key,r in keys:
  m.invalidate();p=params(key);old=rng.randbytes(0x4000)
  y=m.run('set_y:'+key,Y_SELECTOR,p,old,0);assert y==y_model(old,yb[0]['values'])
  got=m.run('edge_key:'+key,EDGE_SELECTOR,p,y,0);h=m.history[-1]
  assert got==edge_model(y,r['values'])
  assert h['lookups']==[dict(record=17,key=key)]
  assert h['drivers']==[dict(entry=hex(EDGE_DRIVER),pointer=hex(CALIB+int(r['payload_offset'],16)-4),fallback=0,payload=r['values'])]
  assert h['string_helpers'].get('0x4efd8')==1 and h['string_helpers'].get('0x4f1f8')==1
  assert all(int(x['address'],16)-MMIO in EDGE_REGS for x in h['writes'])
  assert set(h['read_addresses']).isdisjoint({hex(MMIO+x) for x in Y_REGS})
  assert all(u32(got,x)==u32(y,x) for x in Y_REGS)
  q=s.run('sam_key:'+key,SAM_EDGE,pack_edge(r['values']),y);assert q==got
  skip=m.run('cached_edge:'+key,EDGE_SELECTOR,p,got,1)
  assert skip==got and not m.history[-1]['lookups'] and not m.history[-1]['writes']
  key_results.append(dict(key=key,record_index=r['index'],fields_2_through_7=r['values'][2:8],edge_registers={hex(MMIO+x):u32(got,x) for x in EDGE_REGS},yblend_unchanged=True))
 # Full-width source parameters verify actual masks, independent from source storage width.
 boundary=[0,1,3,0x1fff,0x3fff,0x7fff,0x8000,0xffffffff]
 for n in range(a.stress_cases):
  p=[boundary[(n+i)%len(boundary)] if n<len(boundary) else rng.getrandbits(32) for i in range(21)];old=rng.randbytes(0x4000)
  for fb in [0,1]:assert m.run(f'img_stress:{n}:{fb}',EDGE_DRIVER,struct.pack('<21I',*p),old,fb)==edge_model(old,p,fb)
  assert s.run(f'sam_stress:{n}',SAM_EDGE,pack_edge(p),old)==edge_model(old,p)
 # Actual-key transition: cached input changes force a lookup without changing the Y BLEND bank.
 transitions=[];m.invalidate();old=rng.randbytes(0x4000)
 old=m.run('transition_y',Y_SELECTOR,params('_B2YMODE:STILL_ISO:100'),old,0)
 for key in ['_B2YMODE:STILL_ISO:100','_B2YMODE:STILL_ISO:200','_B2YMODE:STILL_ISO:800','_B2YMODE:SLIVE_ISO:800','_B2YMODE:SMAGNI_ISO:800']:
  r=next(r for k,r in keys if k==key);got=m.run('transition:'+key,EDGE_SELECTOR,params(key),old,1)
  assert got==edge_model(old,r['values']);assert len(m.history[-1]['lookups'])==1
  transitions.append(dict(key=key,changed_registers=[hex(MMIO+x) for x in range(0,0x4000,4) if u32(got,x)!=u32(old,x)],field2=r['values'][2]));old=got
 # Synthetic failed key invokes the real fallback; do not call this a photographic preset.
 m.invalidate();p=params('_B2YMODE:STILL_ISO:101');old=rng.randbytes(0x4000)
 got=m.run('synthetic_missing_key',EDGE_SELECTOR,p,old,0);assert got==edge_model(old,[],True)
 assert m.history[-1]['drivers'][0]['fallback']==1 and m.history[-1]['drivers'][0]['pointer']=='0x0'
 assert bytes(m.u.mem_read(0x408cede0,2))==b'\0\0' and bytes(m.u.mem_read(0x408cede4,4))==b'\0'*4
 # Explicit commutation: configuration independence, not signal-path order or pixel independence.
 commute=[]
 for r in edge:
  old=rng.randbytes(0x4000);yp=struct.pack('<6I',*yb[0]['values']);ep=struct.pack('<21I',*r['values'])
  left=m.run('commute_y_then_edge_a',Y_DRIVER,yp,old);left=m.run('commute_y_then_edge_b',EDGE_DRIVER,ep,left)
  right=m.run('commute_edge_then_y_a',EDGE_DRIVER,ep,old);right=m.run('commute_edge_then_y_b',Y_DRIVER,yp,right)
  assert left==right;commute.append(r['index'])
 histories=m.history+s.history
 (a.out/'execution_histories.json').write_text(json.dumps(histories,indent=2)+'\n')
 text=[]
 for label,blob,lo,hi in [('IMG edge selector',img,EDGE_SELECTOR,0x1540e0),('IMG edge programmer',img,EDGE_DRIVER,0xd19e6),('SAM edge programmer',sam,SAM_EDGE,0x514aa)]:
  text.append('\n'+label+'; raw section offsets')
  for i in md.disasm(blob[lo:hi],lo):
   z=f'{i.address:08x}: {i.bytes.hex():8s} {i.mnemonic:8s} {i.op_str}'
   if i.mnemonic=='ldr' and len(i.operands)>1 and i.operands[1].type==ARM_OP_MEM and i.operands[1].mem.base==ARM_REG_PC:
    q=((i.address+4)&~3)+i.operands[1].mem.disp;z+=f' ; literal {q:#x} -> {u32(blob,q):#x}'
   if i.mnemonic=='adr':
    q=((i.address+4)&~3)+i.operands[1].imm;z+=f' ; address {q:#x}'
   text.append(z)
 (a.out/'original_instruction_anchors.txt').write_text('\n'.join(text)+'\n')
 report=dict(status='PASS_EDGE_CONFIGURATION_ISOLATION_ONLY',gate_c_passed=False,renderer_changed=False,section_sha256=HASHES,script_sha256=sha(Path(__file__).read_bytes()),seed='0xED6E2026',
  identities=dict(img_selector=hex(EDGE_SELECTOR),record='0x11',img_driver=hex(EDGE_DRIVER),img_label=es,img_label_offset=hex(et),sam_entry=hex(SAM_EDGE),sam_label=ss,sam_label_offset=hex(st)),
  calibration=dict(total_records=len(rr),edge_records=edge,edge_key_count=len(keys),normal_yblend=yb[0]),key_results=key_results,
  tests=dict(original_entry_executions=len(histories),img_entries=len(m.history),sam_entries=len(s.history),stress_parameter_sets=a.stress_cases,actual_key_cases=len(keys),cached_skips=len(keys),mode_iso_transitions=transitions,commutation_record_indexes=commute,watched_mmio_writes=sum(len(h['writes']) for h in histories),calibration_writes=sum(h['calibration_writes'] for h in histories)),
  source_contract=dict(key='caller mode string at +2 concatenated with ISO string at +0xB4',cache='mode halfword at +0 and ISO word at +0xB0, plus selector arg1==1',numeric_mode_ids='Synthetic distinct harness IDs; true Leica enum values not recovered here',img_format='21 little-endian uint32 storage slots',sam_format='2 bytes + 19 halfwords, with last two fields exchanged relative to IMG slots',fallback_values=FALLBACK),
  limitations=['No input pixels, ISP datapath, physical clock behavior or reset effects are modeled.','File-registry resolver and IMG logging, or SAM clock helpers, are stubbed. Original selector, string copy/concatenation/comparison, record lookup and register writers execute.','Disjoint register operations and commutation do not prove independent pixel signals or hardware stage order.','Field meanings, fixed-point denominators, edge input signal and Y BLEND routing remain unresolved.','Keys with high ISO or internal mode names are calibration entries, not proof of selectable user-facing camera modes.','Compact structure is a tested analysis-side packing, not a recovered firmware producer.','No new hardware measurement, photographic validation, remote commit or CI result is implied.'])
 (a.out/'edgeisolation_results.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['status','tests']},indent=2))
if __name__=='__main__':main()
