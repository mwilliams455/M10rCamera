#!/usr/bin/env python3
"""POSTYC1A native validation on the fixed public Leica references. No private RAWs."""
from pathlib import Path
import argparse,ctypes,hashlib,importlib.util,json,os,shutil,subprocess,time
import numpy as np,cv2
from PIL import Image,ImageDraw
import m10r_photoaudit_measure1a as a
import m10r_tonecal1a_validate as t
import m10r_gamut1a_validate as g
GATE={'mean_L_mae_increase_max':.15,'mean_neutral_L_mae_increase_max':.15,'worst_scene_DE76_increase_max':.5,'mean_ab_error_reduction_min':.2,'mean_DE76_reduction_min':.2}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(n,p):
 sp=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m

def compile_native(repo,out,text,name,tap=False):
 d=out/name;d.mkdir(parents=True,exist_ok=True)
 for p in (repo/'native').glob('m10r*.h'):shutil.copy2(p,d/p.name)
 pre=text.split('extern "C" JNIEXPORT void JNICALL')[0].replace('#include <jni.h>','using jint=int;using jshort=short;using jlong=long long;').replace('#include <android/bitmap.h>','')
 start=text.index('    const int nthreads =');end=text.index('    for (auto& th : workers) th.join();',start)+len('    for (auto& th : workers) th.join();');loop=text[start:end]
 if tap:
  anchor='            argb[i] = static_cast<jint>(0xff000000u |';assert loop.count(anchor)==1
  loop=loop.replace(anchor,'            if(taps){double v[12]={lr,lg,lb,nr,ng,nb,outR,outG,outB,y,mappedY,yRatio};for(int j=0;j<12;j++)taps[i*12+j]=v[j];}\n'+anchor)
 count=32 if 'v[32]'in pre else 24 if 'v[24]'in pre else 8
 body='extern "C" void process(const short* rgb,int pixels,double inverseStorageScale,const double* src,const int* ca9,const double* workingMat,const double* outMat,const int* tone,const int* dgt,int* argb,long long* existing,double* taps){\n'+loop+f'\nfor(const Counts& c:local)for(int k=0;k<{count};k++)existing[k]+=c.v[k];\n}}\n'
 cpp=d/'host.cpp';cpp.write_text(pre+body);so=d/'host.so';subprocess.run(['g++','-O3','-std=c++17','-ffp-contract=off','-fPIC','-shared','-pthread',str(cpp),'-o',str(so)],check=True)
 lib=ctypes.CDLL(str(so));lib.process.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_double]+[ctypes.c_void_p]*9;return lib

def native(lib,rgb,src,ca,work,dst,tone,dg,inv=1.,tap=False,chunk=None):
 rgb=np.ascontiguousarray(rgb,np.uint16);n=rgb.size//3;shape=rgb.shape;z=np.empty(n,np.int32);cnt=np.zeros(32,np.int64);taps=np.empty((n,12))if tap else None
 rr=rgb.reshape(-1,3);chunk=chunk or n;start=time.perf_counter()
 for off in range(0,n,chunk):
  stop=min(n,off+chunk);lib.process(rr[off:stop].ctypes.data,stop-off,inv,src.ctypes.data,ca.ctypes.data,work.ctypes.data,dst.ctypes.data,tone.ctypes.data,dg.ctypes.data,z[off:stop].ctypes.data,cnt.ctypes.data,taps[off:stop].ctypes.data if tap else None)
 im=np.stack([(z>>16)&255,(z>>8)&255,z&255],-1).astype(np.uint8).reshape(shape)
 return im,cnt,taps,time.perf_counter()-start

def decode(x):return np.where(x<=.04045,x/12.92,np.maximum((x+.055)/1.055,0)**2.4)
def encode(x):return np.where(x<=.0031308,x*12.92,1.055*np.maximum(x,0)**(1/2.4)-.055)
def oracle(taps,dst,tone,dg,post):
 # Independent NumPy expression of the fixed saturation-dependent shoulder.
 lin=a.xform(taps[:,3:6],dst);w=np.array([.2126,.7152,.0722]);lum=np.maximum(lin@w,1e-12);peak=np.maximum(lin.max(1),1e-12)
 baseline=g.oracle(taps[:,6:9]);anchor=decode(baseline)@w;gain=anchor/lum
 sat=np.clip((peak-lin.min(1))/peak,0,1);width=.3*sat;knee=1-width;mx=encode(np.maximum(peak*gain,0));above=np.maximum(mx-knee,0)
 cap=np.where(mx>knee,knee+width*above/np.maximum(above+width,1e-12),mx)
 gain=np.minimum(gain,decode(cap)/peak);coded=encode(lin*gain[:,None]);mapped=g.oracle(coded)
 neutral=(taps[:,0]==taps[:,1])&(taps[:,1]==taps[:,2]);mapped[neutral]=baseline[neutral]
 return post(np.floor(np.clip(mapped,0,1)*255+.5).astype(np.uint8)),coded

def data(sid,inp,js):
 if (inp/'samples'/f'{sid}_metadata.json').exists():
  meta=json.loads((inp/'samples'/f'{sid}_metadata.json').read_text());raw=np.load(inp/'samples'/f'{sid}_raw.npz')['raw'];jpg=inp/'samples'/f'{sid}.jpg'
 else:meta,raw,jpg=t.fresh(sid,inp)
 j,d=meta['metadata'];keys=['Model','SerialNumber','ImageUniqueID','DateTimeOriginal','ISO','ExposureTime','FNumber','FocalLength'];assert all(j.get(k)==d.get(k) and j.get(k)is not None for k in keys)
 assert all(j.get(k)==0 for k in ['Contrast','Saturation','Sharpness'])and j['ColorSpace']==1
 assert meta['raw_pattern']==[[3,2],[0,1]]and all(v==0 for v in meta['black_level_per_channel'])and meta['white_level']==15000
 A=a.constant(js,'M10_CM_A').reshape(3,3);D=a.constant(js,'M10_CM_D65').reshape(3,3);PCS=a.constant(js,'PCS_TO_INTERNAL').reshape(3,3);BR=a.constant(js,'BRADFORD').reshape(3,3);xy50=a.constant(js,'D50_XY');D50=np.array([xy50[0]/xy50[1],1,(1-xy50.sum())/xy50[1]])
 assert np.max(abs(a.nums(d['ColorMatrix1']).reshape(3,3)-A))<1e-7 and np.max(abs(a.nums(d['ColorMatrix2']).reshape(3,3)-D))<1e-7
 asn=a.nums(d['AsShotNeutral']);ca=np.clip(np.rint(256/asn),1,2000).astype(np.int32);kelvin=float(d['CorrelatedColorTemp']);xy=a.nums(d['WhitePoint']);white=np.array([xy[0]/xy[1],1,(1-xy.sum())/xy[1]]);f=np.clip((1/kelvin-1/6504)/(1/2856-1/6504),0,1);cm=f*A+(1-f)*D;work=np.ascontiguousarray(PCS@np.linalg.inv(BR)@np.diag((BR@D50)/(BR@white))@BR@np.linalg.inv(cm));whiteY=float((np.linalg.inv(cm)@asn)[1])
 ref=np.array(Image.open(jpg).convert('RGB'));H,W=sorted(ref.shape[:2]);rh,rw=raw.shape;top,left=(rh-H)//2,(rw-W)//2
 lut=np.floor(np.clip(np.arange(65536)/15000,0,1)*65535+.5).astype(np.uint16);norm=lut[raw];del raw
 sample=np.empty(((H+3)//4,(W+3)//4,3),np.uint16)
 for y0 in range(0,rh,256):
  y1=min(rh,y0+256);hs=max(0,y0-4);he=min(rh,y1+4);tile=cv2.cvtColor(norm[hs:he],cv2.COLOR_BayerGB2BGR_EA);ys=np.arange(max(y0,top),min(y1,top+H));ys=ys[(ys-top)%4==0]
  if len(ys):sample[(ys-top)//4]=tile[ys-hs,left:left+W:4]
 return sample,ref[::4,::4],ca,work,whiteY,{'jpg_sha256':meta['jpg_sha256'],'dng_sha256':meta['dng_sha256'],'ISO':j['ISO'],'pair_identity_checked':True}

def main():
 if not __debug__:raise RuntimeError('Assertions required')
 ap=argparse.ArgumentParser();ap.add_argument('inputs',type=Path);ap.add_argument('out',type=Path);args=ap.parse_args();inp=args.inputs.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);repo=Path(__file__).resolve().parents[1];cv2.setNumThreads(1)
 q=(inp/'source/m10rRender.cpp').read_text();r=load('rp',repo/'patches/fix-m10r-render1r-tonecal1a.py').patch_cpp(q);s=load('sp',repo/'patches/fix-m10r-render1s-gamut1a.py').patch_cpp(r);tbase=load('tp',repo/'patches/fix-m10r-render1t-colorrecon1a.py').patch_cpp(s);old='''            const unsigned colorFlags=m10r_colorrecon1a::apply(\n                    lr,lg,lb,outMat,legacyOutR,legacyOutG,legacyOutB,\n                    tone,dgt,outR,outG,outB);\n''';new='''            const bool postYcNeutralPreserve=(lr==lg && lg==lb);\n            const unsigned colorFlags=m10r_colorrecon1a::apply(\n                    postYcNeutralPreserve?lr:nr,\n                    postYcNeutralPreserve?lg:ng,\n                    postYcNeutralPreserve?lb:nb,\n                    outMat,legacyOutR,legacyOutG,legacyOutB,\n                    tone,dgt,outR,outG,outB);\n''';assert tbase.count(old)==1;tcontrol=tbase;candidate=tbase.replace(old,new,1)
 R=compile_native(repo,out,r,'host_r',True);S=compile_native(repo,out,s,'host_s');T=compile_native(repo,out,tcontrol,'host_t');P=compile_native(repo,out,candidate,'host_p')
 _,post=g.host_header(repo,out);js=(inp/'source/M10RNativeRenderer.java').read_text();dst=a.constant(js,'DEFAULT_SRGB_CC1').reshape(3,3);tone=np.fromfile(inp/'assets/tone_medium_q15.u32le',dtype='<u4').astype(np.int32);dg=np.fromfile(inp/'assets/dg_expanded_u16le.bin',dtype='<u2').astype(np.int32)
 result={'schema':'POSTYC1A_REFERENCE_VALIDATION_V1','candidate_cpp_sha256':hashlib.sha256(candidate.encode()).hexdigest(),'header_sha256':sha(repo/'native/m10rColorRecon1A.h'),'render1t_cpp_sha256':hashlib.sha256(tcontrol.encode()).hexdigest(),'source_commit':os.getenv('GITHUB_SHA'),'gate_limits':GATE,'private_inputs_uploaded':False,'new_independent_reference_scenes':0,'selection_development_ids':['01','03','05'],'reused_regression_ids':['02','04','06','07','08','09','10'],'cases':{},'unit':{}}
 rng=np.random.default_rng(20260921);rgb=rng.integers(0,65536,(600,1000,3),dtype=np.uint16);eye=np.eye(3);ca=np.array([256]*3,np.int32)
 old,oc,tap,_=native(R,rgb,eye,ca,eye,dst,tone,dg,tap=True);actual,cnt,_,secs=native(P,rgb,eye,ca,eye,dst,tone,dg);expected,_=oracle(tap,dst,tone,dg,post)
 error=np.max(abs(actual.reshape(-1,3).astype(int)-expected.astype(int)));assert error<=1,error
 changed=int(np.any(actual.reshape(-1,3)!=expected,1).sum());assert changed/len(expected)<.0001
 chunks,cc,_,_=native(P,rgb,eye,ca,eye,dst,tone,dg,chunk=40000);assert np.array_equal(chunks,actual)and np.array_equal(cc,cnt)
 assert np.array_equal(oc[:8],cnt[:8])and cnt[24]==rgb.size//3 and cnt[26]==0 and cnt[18:24].sum()==0
 result['unit'].update(random_pixels=len(expected),oracle_max_code_error=int(error),oracle_different_pixels=changed,chunk_pixel_and_counter_identity=True,original_first8_counts_unchanged=True)
 gray=np.repeat(np.arange(65536,dtype=np.uint16)[:,None],3,1);base,_,_,_=native(S,gray,eye,ca,eye,dst,tone,dg);new,_,_,_=native(P,gray,eye,ca,eye,dst,tone,dg)
 gray_error=int(abs(new.astype(int)-base.astype(int)).max());assert gray_error<=1,gray_error
 assert np.diff(new[:,0].astype(int)).min()>=0 and (new[0]==0).all()and(new[-1]==255).all()
 result['unit']['gray_max_code_difference']=gray_error
 boards=[]
 for sid in [f'{i:02}'for i in range(1,11)]:
  sample,ref,ca,work,wy,meta=data(sid,inp,js);scene={'metadata':meta,'conditions':{}}
  for mode,scale in [('target_native',1.),('white_normalized_control',1/wy)]:
   src=eye*scale;rr,rc,taps,_=native(R,sample,src,ca,work,dst,tone,dg,tap=True);base,bc,_,_=native(S,sample,src,ca,work,dst,tone,dg);timg,tc,_,_=native(T,sample,src,ca,work,dst,tone,dg);new,nc,_,_=native(P,sample,src,ca,work,dst,tone,dg)
   assert np.array_equal(bc[:8],nc[:8])and nc[24]==sample.size//3 and nc[26]==0 and nc[18:24].sum()==0
   ex,_=oracle(taps[::64],dst,tone,dg,post);ac=new.reshape(-1,3)[::64];maxerr=int(abs(ex.astype(int)-ac.astype(int)).max());assert maxerr<=1 and np.mean(np.any(ex!=ac,1))<.0001
   if mode=='target_native':al=t.align(rr,ref);scene['alignment']=al
   ba,rf=t.view(base,ref,al);im,_=t.view(new,ref,al);bp,rp,ps=a.patch_values(ba,rf);cp,rp2,ps2=a.patch_values(im,rf);assert np.array_equal(rp,rp2)and ps==ps2
   tpv,_,_=a.patch_values(t.view(timg,ref,al)[0],rf);rec={'baseline':a.groups(bp,rp),'render1t':a.groups(tpv,rp),'candidate':a.groups(cp,rp),'patches':ps,'counts':nc.tolist(),'render1t_counts':tc.tolist(),'oracle_max_code_error':maxerr};scene['conditions'][mode]=rec
   print(sid,mode,'DE S/T/P',rec['baseline']['all']['DE76_mean'],rec['render1t']['all']['DE76_mean'],rec['candidate']['all']['DE76_mean'],'L S/T/P',rec['baseline']['all']['L_mae'],rec['render1t']['all']['L_mae'],rec['candidate']['all']['L_mae'],flush=True)
   if mode=='target_native':
    thumbs=[]
    for label,img in [('reference',rf),('S',ba),('T',t.view(timg,ref,al)[0]),('P',im)]:
     z=Image.fromarray(img);z.thumbnail((450,300));z.save(out/f'{sid}_{label}.jpg',quality=95);thumbs.append(z)
    boards.append((sid,thumbs))
  result['cases'][sid]=scene;(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
 summaries={};passed=True
 for split,ids in [('historical_holdouts_reused',['02','04','06','07','08','09','10']),('all_reused',[f'{i:02}'for i in range(1,11)])]:
  summaries[split]={}
  for mode in ['target_native','white_normalized_control']:
   rows=[result['cases'][i]['conditions'][mode]for i in ids];m={}
   for key in ['L_mae','ab_error_mean','DE76_mean']:
    for v in ['baseline','candidate']:m[v+'_'+key]=float(np.mean([r[v]['all'][key]for r in rows]))
   for v in ['baseline','candidate']:m[v+'_neutral_L_mae']=float(np.mean([r[v]['neutral']['L_mae']for r in rows]))
   m['worst_scene_DE76_increase']=max(r['candidate']['all']['DE76_mean']-r['baseline']['all']['DE76_mean']for r in rows)
   m['gate_passed']=m['candidate_L_mae']<=m['baseline_L_mae']+.15 and m['candidate_neutral_L_mae']<=m['baseline_neutral_L_mae']+.15 and m['worst_scene_DE76_increase']<=.5 and m['candidate_ab_error_mean']<=.8*m['baseline_ab_error_mean'] and m['candidate_DE76_mean']<=.8*m['baseline_DE76_mean']
   passed=passed and m['gate_passed'];summaries[split][mode]=m
 result['summary']=summaries;result['apk_gate_passed']=bool(passed);result['status']='PASS_POSTYC1A_REFERENCE_CANDIDATE'if passed else'FAIL_COLORRECON1A_GATE';result['production_promoted']=False
 board=Image.new('RGB',(1380,335*len(boards)+40),'white');dr=ImageDraw.Draw(board);dr.text((10,10),'Reference | RENDER1S | COLORRECON1A; Photography Blog references, reused regression.',fill='black')
 for row,(sid,imgs)in enumerate(boards):
  for col,im in enumerate(imgs):board.paste(im,(col*460+5,row*335+60));dr.text((col*460+5,row*335+40),sid,fill='black')
 board.save(out/'COMPARISON.jpg',quality=94);(out/'results.json').write_text(json.dumps(result,indent=2)+'\n');(out/'REPORT.md').write_text('# COLORRECON1A validation\n\n'+result['status']+'\n\n```json\n'+json.dumps(summaries,indent=2)+'\n```\n\nMatrix-only Leica adapter; not phone frontend equivalence. No new independent reference scenes. Host tests do not establish Android latency or device stability.\n')
 print(json.dumps(summaries,indent=2));assert passed,result['status']
if __name__=='__main__':main()
