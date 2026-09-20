#!/usr/bin/env python3
"""GAMUT1A: bounds/identity tests plus fixed-reference regression, NOT phone validation.
No private phone image is uploaded. No new fitting, exposure/WB or chroma-k changes.
"""
from pathlib import Path
import argparse,ctypes,hashlib,importlib.util,json,os,shutil,subprocess,sys
import numpy as np
import cv2
from PIL import Image,ImageDraw
import m10r_photoaudit_measure1a as a
import m10r_tonecal1a_validate as t

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(name,p):
 sp=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m

def oracle(x):
 # Independently expressed unnormalized projection for bounded test/photographic inputs.
 w=np.array([.2126,.7152,.0722]);base=np.clip(x,0,1);anchor=base@w;d=x-(x@w)[:,None]
 candidates=np.full_like(x,np.inf);np.divide(1-anchor[:,None],d,out=candidates,where=d>0)
 np.divide(-anchor[:,None],d,out=candidates,where=d<0)
 scale=np.maximum(0,np.minimum(1,candidates.min(1)));out=np.clip(anchor[:,None]+scale[:,None]*d,0,1)
 mask=((x>=0)&(x<=1)).all(1);out[mask]=x[mask]
 return out

def host_header(repo,out):
 p=out/'header.cpp';p.write_text('#include "'+str(repo/'native/m10rOutputGamut1A.h')+'"\n#include "'+str(repo/'native/m10rToneCal1A.h')+'"\nextern "C" void project(const double*x,double*y,unsigned char*s,int n){for(int i=0;i<n;i++){double r=x[i*3],g=x[i*3+1],b=x[i*3+2];s[i]=m10r_outputgamut1a::apply(r,g,b);y[i*3]=r;y[i*3+1]=g;y[i*3+2]=b;}}\nextern "C" void tone(const unsigned char*x,unsigned char*y,int n){for(int i=0;i<n;i++){int k=3*i;unsigned q=m10r_tonecal1a::apply(0xff000000u|(unsigned(x[k])<<16)|(unsigned(x[k+1])<<8)|x[k+2]);y[k]=q>>16;y[k+1]=q>>8;y[k+2]=q;}}\n')
 so=out/'header.so';subprocess.run(['g++','-O3','-std=c++17','-ffp-contract=off','-fPIC','-shared',str(p),'-o',str(so)],check=True)
 dll=ctypes.CDLL(str(so));dll.project.argtypes=[ctypes.c_void_p]*3+[ctypes.c_int];dll.tone.argtypes=[ctypes.c_void_p]*2+[ctypes.c_int]
 def project(x):
  x=np.ascontiguousarray(x,dtype=np.float64);y=np.empty_like(x);status=np.empty(x.size//3,np.uint8);dll.project(x.ctypes.data,y.ctypes.data,status.ctypes.data,len(status));return y,status
 def tone(x):
  x=np.ascontiguousarray(x,dtype=np.uint8);y=np.empty_like(x);dll.tone(x.ctypes.data,y.ctypes.data,x.size//3);return y
 return project,tone

def unit(project,tone):
 rng=np.random.default_rng(0x6A4A2026)
 g=np.linspace(0,1,33);grid=np.stack(np.meshgrid(g,g,g,indexing='ij'),-1).reshape(-1,3)
 inside=np.concatenate([rng.random((200000,3)),grid,np.repeat(np.arange(256)[:,None]/255,3,axis=1)])
 o,s=project(inside);assert np.array_equal(o,inside) and (s==0).all()
 outside=rng.uniform(-2,4,(300000,3));o,s=project(outside);exp=oracle(outside)
 err=float(np.max(abs(o-exp)));assert err<1e-12 and np.isfinite(o).all() and ((o>=0)&(o<=1)).all()
 w=np.array([.2126,.7152,.0722]);lerr=float(np.max(abs(o@w-np.clip(outside,0,1)@w)));assert lerr<2e-12
 d=outside-(outside@w)[:,None];e=o-(o@w)[:,None];cross=np.linalg.norm(np.cross(d,e),axis=1);good=np.linalg.norm(e,axis=1)>1e-9
 assert (cross[good]<1e-11).all() and ((d*e).sum(1)[good]>0).all()
 ramps=[]
 for ch in range(3):
  x=np.repeat(np.array([[.2,.4,.6]]),4097,axis=0);x[:,ch]=np.linspace(.7,3,4097);y,_=project(x)
  assert np.max(abs(np.diff(y,axis=0)))<.005
  ramps.append({'channel':ch,'max_step':float(np.max(abs(np.diff(y,axis=0))))})
 x=np.repeat(np.array([[.2,.4,1.]]),4097,axis=0);x[:,2]=np.linspace(1,3,4097);y,_=project(x)
 q=lambda z:np.floor(np.clip(z,0,1)*255+.5).astype(np.uint8)
 old=tone(q(x));new=tone(q(y));nu=len(np.unique(new,axis=0));assert len(np.unique(old,axis=0))==1 and nu>1
 extreme=np.array([[1e308,-1e308,1e308],[-1e308,1e308,-1e308],[1e308]*3,[-1e308]*3,[np.nan,.5,np.inf],[-np.inf,np.nan,.2],[1.000001]*3,[-.000001]*3])
 y,s=project(extreme);assert np.isfinite(y).all() and ((y>=0)&(y<=1)).all();assert (s[4:6]==2).all()
 gray=np.repeat(np.arange(256)[:,None],3,axis=1).astype(np.uint8);mapped,_=project(gray/255.)
 assert np.array_equal(tone(q(mapped)),tone(gray))
 return {'in_gamut_exact_cases':len(inside),'extended_RGB_cases':len(outside),'independent_oracle_max_error':err,'code_luma_max_error':lerr,'extreme_finite_and_nonfinite_cases':len(extreme),'channel_ramps':ramps,'synthetic_blue_plateau_old_unique':1,'synthetic_blue_plateau_new_unique':nu,'grayscale_final_output_unchanged':True,'perceptual_hue_claimed':False}

def compile_native(repo,out,text,name,tap=False):
 d=out/name;d.mkdir();src=d/'src';src.mkdir()
 if tap:
  text='#include <fstream>\n#include <cstdlib>\n'+text
  anchor='    auto work = [&](int tid, int begin, int end) {'
  assert text.count(anchor)==1;text=text.replace(anchor,'    std::vector<double> auditTap(static_cast<size_t>(pixels)*3);\n'+anchor)
  anchor='            argb[i] = static_cast<jint>(0xff000000u |'
  assert text.count(anchor)==1;text=text.replace(anchor,'            auditTap[i*3]=outR; auditTap[i*3+1]=outG; auditTap[i*3+2]=outB;\n'+anchor)
  anchor='    for (auto& th : workers) th.join();'
  text=text.replace(anchor,anchor+'\n    if(const char* p=std::getenv("M10R_AUDIT_TAP")){std::ofstream f(p,std::ios::binary);f.write(reinterpret_cast<const char*>(auditTap.data()),auditTap.size()*sizeof(double));}')
 (src/'m10rRender.cpp').write_text(text)
 for f in ['m10rToneCal1A.h','m10rOutputGamut1A.h']:shutil.copy2(repo/'native'/f,d/f)
 lib,info=a.make_native(src,d)
 j=d/'M10RNativeRenderer.java';s=j.read_text();assert s.count('long[] counts=new long[8];')==1
 s=s.replace('long[] counts=new long[8];','long[] counts=new long[24];')
 call='  nativeProcessTile(rgb,out.length,inv,src,ca9,work,dst,tone,dg,out,counts);'
 assert s.count(call)==1
 s=s.replace(call,'''  int chunk=a.length>3?Integer.parseInt(a[3]):out.length;
  for(int start=0;start<out.length;start+=chunk){int n=Math.min(chunk,out.length-start);short[] ri=Arrays.copyOfRange(rgb,3*start,3*(start+n));int[] oi=new int[n];nativeProcessTile(ri,n,inv,src,ca9,work,dst,tone,dg,oi,counts);System.arraycopy(oi,0,out,start,n);}''')
 j.write_text(s);subprocess.run(['javac','-d',str(d),str(j)],check=True)
 return lib

def run(lib,rgb,src,ca9,work,dst,tone,dg,scratch):
 return t.run_native(rgb,src,ca9,work,dst,tone,dg,scratch,lib)

def main():
 if not __debug__:raise RuntimeError('Assertions must be enabled')
 ap=argparse.ArgumentParser();ap.add_argument('inputs',type=Path);ap.add_argument('out',type=Path);args=ap.parse_args()
 cv2.setNumThreads(1);assert cv2.__version__=='4.13.0'
 inp=args.inputs.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);repo=Path(__file__).resolve().parents[1]
 for e in json.loads((inp/'manifest.json').read_text()):
  p=inp/e['path'];assert p.stat().st_size==e['bytes'] and sha(p)==e['sha256']
 oldpatch=load('oldpatch',repo/'patches/fix-m10r-render1r-tonecal1a.py');patch=load('newpatch',repo/'patches/fix-m10r-render1s-gamut1a.py')
 orig=(inp/'source/m10rRender.cpp').read_text();rtext=oldpatch.patch_cpp(orig);stext=patch.patch_cpp(rtext)
 baseline=compile_native(repo,out,rtext,'baseline');candidate=compile_native(repo,out,stext,'candidate');taplib=compile_native(repo,out,rtext,'baseline_tap',True)
 project,tonepost=host_header(repo,out)
 result={'schema':'RENDER1S_GAMUT1A_VALIDATION_V1','status':'RUNNING','source_commit':os.getenv('GITHUB_SHA'),'run_id':os.getenv('GITHUB_RUN_ID'),'unit':unit(project,tonepost),'phone_dng_replayed':False,'private_phone_data_uploaded':False,'new_fit_performed':False,'baseline_cpp_sha256':hashlib.sha256(rtext.encode()).hexdigest(),'candidate_cpp_sha256':hashlib.sha256(stext.encode()).hexdigest(),'header_sha256':sha(repo/'native/m10rOutputGamut1A.h'),'cases':{},'gate_limits':{'mean_L_mae_increase':.15,'mean_ab_error_increase':.15,'mean_DE76_increase':.15,'max_scene_DE76_increase':.5},'limitations':['Empirical output projection, not recovered Leica Y BLEND arithmetic.','Replay of private phone RAW unavailable in this execution environment.','Same ten publisher scenes reused for regression, not fresh independent validation.','Leica DNG matrix adapter is not Camera2 frontend equivalence.','Code-luma and RGB opponent direction are not perceptual lightness and hue.','The mapping cannot recover upstream CA9 clipping or sensor clipping.','CPU tests cannot validate Android ARM output or runtime speed.']}
 js=(inp/'source/M10RNativeRenderer.java').read_text();A=a.constant(js,'M10_CM_A').reshape(3,3);D=a.constant(js,'M10_CM_D65').reshape(3,3);pcs=a.constant(js,'PCS_TO_INTERNAL').reshape(3,3);dst=a.constant(js,'DEFAULT_SRGB_CC1').reshape(3,3);br=a.constant(js,'BRADFORD').reshape(3,3);xy=a.constant(js,'D50_XY');d50=np.array([xy[0]/xy[1],1,(1-xy.sum())/xy[1]])
 tone=np.fromfile(inp/'assets/tone_medium_q15.u32le',dtype='<u4');dg=np.fromfile(inp/'assets/dg_expanded_u16le.bin',dtype='<u2');assert len(tone)==10240 and len(dg)==32768
 # Exercise native counter accumulation across tiles and the four-worker path.
 rng=np.random.default_rng(932061);syn=rng.integers(0,65536,(600,1000,3),dtype=np.uint16);I=np.eye(3);ca9=np.array([256,256,256]);scratch=out/'scratch'
 si,sc,_=run(candidate,syn,I,ca9,I,dst,tone,dg,scratch)
 args2=['java','-Xmx512m','-XX:+UseSerialGC','-Daudit.library='+str(candidate),'-cp',str(candidate.parent),'com.particlesdevs.photoncamera.m10r.M10RNativeRenderer',str(scratch/'rgb.u16'),str(scratch/'params.bin'),str(scratch/'chunked.bin'),'40000']
 cc=json.loads(subprocess.check_output(args2,timeout=120));z=np.fromfile(scratch/'chunked.bin',dtype='<u4');cq=np.stack([(z>>16)&255,(z>>8)&255,z&255],-1).astype(np.uint8).reshape(syn.shape)
 assert np.array_equal(si,cq) and sc==cc and sc[8]==600000 and sc[9]+sc[10]+sc[11]==sc[8] and sum(sc[18:24])==0
 result['native_tiling']={'pixels':600000,'chunk_size':40000,'pixel_and_counter_equality':True,'counts':sc}
 pictures=[]
 for sid in [f'{i:02}' for i in range(1,11)]:
  print('BEGIN',sid,flush=True)
  if int(sid)<=6:
   meta=json.loads((inp/'samples'/f'{sid}_metadata.json').read_text());raw=np.load(inp/'samples'/f'{sid}_raw.npz')['raw'];jpg=inp/'samples'/f'{sid}.jpg'
  else:meta,raw,jpg=t.fresh(sid,inp)
  j,d=meta['metadata'];keys=['Model','SerialNumber','ImageUniqueID','DateTimeOriginal','ISO','ExposureTime','FNumber','FocalLength'];assert all(j.get(k)==d.get(k) and j.get(k) is not None for k in keys)
  assert meta['raw_pattern']==[[3,2],[0,1]] and all(v==0 for v in meta['black_level_per_channel']) and meta['white_level']==15000
  asn=a.nums(d['AsShotNeutral']);ca9=np.clip(np.rint(256/asn),1,2000).astype(int);kelvin=float(d['CorrelatedColorTemp']);xy=a.nums(d['WhitePoint']);white=np.array([xy[0]/xy[1],1,(1-xy.sum())/xy[1]]);f=np.clip((1/kelvin-1/6504)/(1/2856-1/6504),0,1);cm=f*A+(1-f)*D;ad=np.linalg.inv(br)@np.diag((br@d50)/(br@white))@br;work=pcs@ad@np.linalg.inv(cm);whiteY=float((np.linalg.inv(cm)@asn)[1])
  ref=np.asarray(Image.open(jpg).convert('RGB'));H,W=sorted(ref.shape[:2]);rh,rw=raw.shape;top,left=(rh-H)//2,(rw-W)//2;assert min(top,left)>=0
  lut=np.floor(np.clip(np.arange(65536)/15000.,0,1)*65535+.5).astype(np.uint16);norm=lut[raw];del raw
  sample=np.empty(((H+3)//4,(W+3)//4,3),np.uint16)
  for y0 in range(0,rh,256):
   y1=min(rh,y0+256);hs=max(0,y0-4);he=min(rh,y1+4);tile=cv2.cvtColor(norm[hs:he],cv2.COLOR_BayerGB2BGR_EA);ys=np.arange(max(y0,top),min(y1,top+H));ys=ys[(ys-top)%4==0]
   if len(ys):sample[(ys-top)//4]=tile[ys-hs,left:left+W:4]
  del norm;ref=ref[::4,::4]
  for mode,scale in [('target_native',1.),('white_normalized_control',1/whiteY)]:
   sm=np.eye(3)*scale;bi,bc,bs=run(baseline,sample,sm,ca9,work,dst,tone,dg,scratch);ci,cc,cs=run(candidate,sample,sm,ca9,work,dst,tone,dg,scratch)
   tap=out/'prequant.f64';os.environ['M10R_AUDIT_TAP']=str(tap)
   ti,tc,_=run(taplib,sample,sm,ca9,work,dst,tone,dg,scratch);del os.environ['M10R_AUDIT_TAP']
   assert np.array_equal(ti,bi) and tc==bc and cc[:8]==bc[:8]
   x=np.fromfile(tap,dtype='<f8').reshape(-1,3);assert len(x)==sample.shape[0]*sample.shape[1] and np.isfinite(x).all()
   y,status=project(x);expected=tonepost(np.floor(np.clip(y,0,1)*255+.5).astype(np.uint8)).reshape(ci.shape)
   assert np.array_equal(ci,expected),'native integration mismatch'
   mask=status==0;assert np.array_equal(ci.reshape(-1,3)[mask],bi.reshape(-1,3)[mask])
   assert cc[8]==len(x) and cc[9]==int(mask.sum()) and cc[10]==int((status==1).sum()) and cc[11]==0
   assert cc[12:15]==(x<0).sum(0).tolist() and cc[15:18]==(x>1).sum(0).tolist() and sum(cc[18:24])==0
   oracle_error=float(np.max(abs(y-oracle(x))));assert oracle_error<2e-12
   if mode=='target_native':al=t.align(bi,ref)
   ba,rr=t.view(bi,ref,al);ca,_=t.view(ci,ref,al);bp,rp,ps=a.patch_values(ba,rr);cp,rp2,ps2=a.patch_values(ca,rr);assert np.array_equal(rp,rp2) and ps==ps2
   rec={'id':sid,'condition':mode,'baseline':a.groups(bp,rp),'candidate':a.groups(cp,rp),'alignment':al,'selection':ps,'native_counts':cc,'in_gamut_identical_pixels':int(mask.sum()),'integrated_pixel_exact':True,'independent_oracle_max_error':oracle_error,'host_seconds_including_JVM':{'baseline':bs,'candidate':cs},'changed_output_pixels':int(np.any(bi!=ci,axis=2).sum()),'dng_sha256':meta['dng_sha256'],'jpg_sha256':meta['jpg_sha256']}
   result['cases'][sid+'_'+mode]=rec
   print(sid,mode,'mapped',cc[10],'of',len(x),'L',rec['baseline']['all']['L_mae'],'->',rec['candidate']['all']['L_mae'],'DE',rec['baseline']['all']['DE76_mean'],'->',rec['candidate']['all']['DE76_mean'],flush=True)
   if mode=='target_native':
    thumbs=[]
    for name,img in [('reference',rr),('tonecal1a',ba),('gamut1a',ca)]:
     p=Image.fromarray(img);p.thumbnail((400,270));p.save(out/f'{sid}_{name}.jpg',quality=95);thumbs.append(p)
    pictures.append((sid,thumbs))
   (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
 summaries={};passed=True
 for mode in ['target_native','white_normalized_control']:
  records=[v for v in result['cases'].values() if v['condition']==mode];deltas={}
  for metric in ['L_mae','ab_error_mean','DE76_mean']:
   b=float(np.mean([r['baseline']['all'][metric] for r in records]));c=float(np.mean([r['candidate']['all'][metric] for r in records]));deltas[metric]={'baseline':b,'candidate':c,'delta':c-b};passed=passed and c-b<=.15
  worst=max(r['candidate']['all']['DE76_mean']-r['baseline']['all']['DE76_mean'] for r in records);passed=passed and worst<=.5
  summaries[mode]={'metrics':deltas,'max_scene_DE76_increase':worst,'total_pixels':sum(r['native_counts'][8] for r in records),'mapped_pixels':sum(r['native_counts'][10] for r in records),'identical_in_gamut_pixels':sum(r['native_counts'][9] for r in records)}
 result['summary']=summaries;result['apk_gate_passed']=bool(passed);result['status']='PASS_GAMUT1A_REGRESSION_TEST_CANDIDATE' if passed else 'FAIL_PHOTOGRAPHIC_REGRESSION_NO_APK'
 sheet=Image.new('RGB',(1230,len(pictures)*300+32),'white');draw=ImageDraw.Draw(sheet);draw.text((8,8),'Public references | RENDER1R TONECAL1A | RENDER1S GAMUT1A (not private phone replay)',fill='black')
 for row,(sid,imgs) in enumerate(pictures):
  for col,img in enumerate(imgs):sheet.paste(img,(col*410,32+row*300));draw.text((col*410+6,35+row*300),sid,fill='white')
 sheet.save(out/'comparison.jpg',quality=94)
 (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
 (out/'REPORT.md').write_text('# RENDER1S GAMUT1A validation\n\n'+result['status']+'\n\n```json\n'+json.dumps(summaries,indent=2)+'\n```\n\nPrivate phone DNG replay was not possible. No phone input was published. This validates the isolated mapping, counts and existing reference regression, not device colour fidelity.\n')
 print('FINAL_RESULT',json.dumps({'status':result['status'],'unit':result['unit'],'summary':summaries,'phone_dng_replayed':False}),flush=True)
 if not passed:raise SystemExit('Photographic gate failed; do not build APK')
if __name__=='__main__':main()
