#!/usr/bin/env python3
"""Native TONECAL1A candidate validation. Fit is fixed; fresh scenes 07..10 are test-only.
Original RENDER1Q native core vs same core + empirical post-ARGB lightness correction.
No full Camera2 equivalence or capture-metering claim. Requires PHOTOAUDIT1A input artifact.
"""
from pathlib import Path
import argparse,ctypes,hashlib,importlib.util,json,os,shutil,struct,subprocess,sys,time,urllib.request
import numpy as np
import cv2
from PIL import Image,ImageDraw
import m10r_photoaudit_measure1a as a

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def module(p):
 spec=importlib.util.spec_from_file_location('tonepatch',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def align(base,ref):
 h,w=base.shape[:2];ga=cv2.GaussianBlur(base.astype(np.float32).mean(2),(0,0),2);ga-=cv2.GaussianBlur(ga,(0,0),12)
 template=np.ascontiguousarray(ga[16:-16,16:-16]);best=None
 for k in range(4):
  rb=np.rot90(ref,k).copy()
  if rb.shape[:2]!=(h,w):continue
  gb=cv2.GaussianBlur(rb.astype(np.float32).mean(2),(0,0),2);gb-=cv2.GaussianBlur(gb,(0,0),12)
  mat=cv2.matchTemplate(np.ascontiguousarray(gb[10:-10,10:-10]),template,cv2.TM_CCORR_NORMED)
  assert mat.shape==(13,13)
  _,s,_,loc=cv2.minMaxLoc(mat);dx,dy=loc[0]-6,loc[1]-6
  if best is None or s>best[0]:best=(s,k,dx,dy)
 assert best is not None and best[0]>.75,best
 return {'correlation':best[0],'rot90':best[1],'dx':best[2],'dy':best[3],'radius':6,'margin':16,'on_boundary':abs(best[2])==6 or abs(best[3])==6}

def view(img,ref,al):
 h,w=img.shape[:2];m=al['margin'];r=np.rot90(ref,al['rot90']);dx,dy=al['dx'],al['dy']
 return img[m:h-m,m:w-m],r[m+dy:h-m+dy,m+dx:w-m+dx]

def fresh(sid,inputs):
 import rawpy
 d=inputs/'fresh';d.mkdir(exist_ok=True)
 paths=[]
 for ext in ['jpg','dng']:
  p=d/f'{sid}.{ext}';u=f'https://img.photographyblog.com/reviews/leica_m10_r/sample_images/leica_m10_r_{sid}.{ext}'
  if not p.exists():
   req=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'})
   with urllib.request.urlopen(req,timeout=120) as r,p.open('wb') as out:shutil.copyfileobj(r,out)
  paths.append(p)
 meta=json.loads(subprocess.check_output(['exiftool','-j','-n',*map(str,paths)]))
 with rawpy.imread(str(paths[1])) as r:
  raw=r.raw_image.copy();pattern=r.raw_pattern.tolist();black=r.black_level_per_channel;white=r.white_level
 return {'id':sid,'metadata':meta,'raw_pattern':pattern,'black_level_per_channel':black,'white_level':white,'jpg_sha256':sha(paths[0]),'dng_sha256':sha(paths[1])},raw,paths[0]

def run_native(rgb,src,ca9,work,dst,tone,dg,root,lib):
 root.mkdir(exist_ok=True);rgb.astype('<u2').tofile(root/'rgb.u16')
 with (root/'params.bin').open('wb') as f:
  f.write(struct.pack('<d',1));f.write(src.astype('<f8').tobytes());f.write(ca9.astype('<i4').tobytes())
  for m in [work,dst]:f.write(m.astype('<f8').tobytes())
  f.write(tone.astype('<i4').tobytes());f.write(dg.astype('<i4').tobytes())
 cmd=['java','-Xmx512m','-XX:+UseSerialGC','-Daudit.library='+str(lib),'-cp',str(lib.parent),'com.particlesdevs.photoncamera.m10r.M10RNativeRenderer',str(root/'rgb.u16'),str(root/'params.bin'),str(root/'out.bin')]
 start=time.perf_counter();counts=json.loads(subprocess.check_output(cmd,timeout=90));elapsed=time.perf_counter()-start
 v=np.fromfile(root/'out.bin',dtype='<u4');out=np.stack([(v>>16)&255,(v>>8)&255,v&255],-1).astype(np.uint8).reshape(rgb.shape)
 return out,counts,elapsed

def main():
 if not __debug__:raise RuntimeError('Assertions required')
 ap=argparse.ArgumentParser();ap.add_argument('inputs',type=Path);ap.add_argument('out',type=Path);ap.add_argument('--fresh',action='store_true');ap.add_argument('--ids',default='01,02,03,04,05,06');args=ap.parse_args()
 cv2.setNumThreads(1);assert cv2.__version__=='4.13.0'
 inp=args.inputs.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);repo=Path(__file__).resolve().parents[1]
 patch=module(repo/'patches/fix-m10r-render1r-tonecal1a.py');header=repo/'native/m10rToneCal1A.h'
 for e in json.loads((inp/'manifest.json').read_text()):
  p=inp/e['path'];assert p.stat().st_size==e['bytes'] and sha(p)==e['sha256']
 source=inp/'source';base=out/'baseline';candidate=out/'candidate';base.mkdir(exist_ok=True);candidate.mkdir(exist_ok=True)
 blib,binfo=a.make_native(source,base)
 cs=out/'candidate_source';cs.mkdir(exist_ok=True);original=(source/'m10rRender.cpp').read_text();changed=patch.patch_cpp(original);(cs/'m10rRender.cpp').write_text(changed)
 shutil.copy2(header,candidate/header.name);clib,cinfo=a.make_native(cs,candidate)
 # Standalone header wrapper tests integration against the same output from the original core.
 host=out/'header_host.cpp';host.write_text('#include "'+str(header)+'"\nextern "C" void apply(const unsigned char*x,unsigned char*y,int n){for(int i=0;i<n;i++){int k=3*i;unsigned q=m10r_tonecal1a::apply(0xff000000u|(unsigned(x[k])<<16)|(unsigned(x[k+1])<<8)|x[k+2]);y[k]=q>>16;y[k+1]=q>>8;y[k+2]=q;}}\n')
 so=out/'libheader.so';subprocess.run(['g++','-O3','-std=c++17','-ffp-contract=off','-fPIC','-shared',str(host),'-o',str(so)],check=True);dll=ctypes.CDLL(str(so));dll.apply.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int]
 def post(img):
  x=np.ascontiguousarray(img);y=np.empty_like(x);dll.apply(x.ctypes.data,y.ctypes.data,x.size//3);return y
 gray=np.repeat(np.arange(256,dtype=np.uint8)[:,None],3,axis=1);q=post(gray);assert np.all(q[:,0]==q[:,1]) and np.all(q[:,0]==q[:,2]) and np.all(np.diff(q[:,0].astype(int))>=0) and (q[0]==0).all() and (q[-1]==255).all()
 js=(source/'M10RNativeRenderer.java').read_text();A=a.constant(js,'M10_CM_A').reshape(3,3);D=a.constant(js,'M10_CM_D65').reshape(3,3);pcs=a.constant(js,'PCS_TO_INTERNAL').reshape(3,3);dst=a.constant(js,'DEFAULT_SRGB_CC1').reshape(3,3);br=a.constant(js,'BRADFORD').reshape(3,3);xy=a.constant(js,'D50_XY');d50=np.array([xy[0]/xy[1],1,(1-xy.sum())/xy[1]])
 tone=np.fromfile(inp/'assets/tone_medium_q15.u32le',dtype='<u4');dg=np.fromfile(inp/'assets/dg_expanded_u16le.bin',dtype='<u2')
 assert len(tone)==10240 and len(dg)==32768
 result={'schema':'RENDER1R_TONECAL1A_VALIDATION_V1','status':'RUNNING','baseline_cpp_sha256':sha(source/'m10rRender.cpp'),'header_sha256':sha(header),'executed_commit':os.getenv('GITHUB_SHA'),'run_id':os.getenv('GITHUB_RUN_ID'),'empirical_not_firmware':True,'training_scenes':['01','03','05'],'old_validation':['02','04','06'],'fresh_validation':['07','08','09','10'] if args.fresh else [],'scenes':{},'neutral_ramp_tests':'PASS','integrated_matches_postprocessing_baseline':True,'capture_exposure_changed':False,'white_balance_changed':False,'k_changed':False,'fitted_coefficients':[-3.229545380578171,-0.25128474545011054,-0.17860038493017244],'limitations':['Source adapter remains matrix-only Leica DNG; not actual Camera2 frontend validation.','Reference firmware 10.20.27.20 differs from extracted 30.22.23.34.','Fresh scenes are from the same publication/camera/lens family, not independent hardware.','All candidate decisions apply to fixed global tone calibration only, not chroma or exposure.','Flat patch scoring downweights demosaic/optical differences but does not eliminate them.','Analytical double CIELAB may differ from OpenCV float CIELAB by rounding. Candidate pixels are measured directly.']}
 ids=args.ids.split(',')+(['07','08','09','10'] if args.fresh else []);training=[];pictures=[]
 for sid in ids:
  print('BEGIN',sid,flush=True)
  if int(sid)<=6:
   meta=json.loads((inp/'samples'/f'{sid}_metadata.json').read_text());raw=np.load(inp/'samples'/f'{sid}_raw.npz')['raw'];jpg=inp/'samples'/f'{sid}.jpg'
  else:meta,raw,jpg=fresh(sid,inp)
  j,d=meta['metadata'];keys=['Model','SerialNumber','ImageUniqueID','DateTimeOriginal','ISO','ExposureTime','FNumber','FocalLength'];matches={k:j.get(k)==d.get(k) and j.get(k) is not None for k in keys};assert all(matches.values()),matches
  assert all(j.get(k)==0 for k in ['Contrast','Saturation','Sharpness']) and j['ColorSpace']==1
  assert meta['raw_pattern']==[[3,2],[0,1]] and all(v==0 for v in meta['black_level_per_channel']) and meta['white_level']==15000
  assert np.max(abs(a.nums(d['ColorMatrix1']).reshape(3,3)-A))<1e-7 and np.max(abs(a.nums(d['ColorMatrix2']).reshape(3,3)-D))<1e-7
  asn=a.nums(d['AsShotNeutral']);ca9=np.clip(np.rint(256/asn),1,2000).astype(int);kelvin=float(d['CorrelatedColorTemp']);xy=a.nums(d['WhitePoint']);white=np.array([xy[0]/xy[1],1,(1-xy.sum())/xy[1]]);f=np.clip((1/kelvin-1/6504)/(1/2856-1/6504),0,1);cm=f*A+(1-f)*D;ad=np.linalg.inv(br)@np.diag((br@d50)/(br@white))@br;work=pcs@ad@np.linalg.inv(cm);whiteY=float((np.linalg.inv(cm)@asn)[1])
  ref=np.asarray(Image.open(jpg).convert('RGB'));H,W=sorted(ref.shape[:2]);rh,rw=raw.shape;top,left=(rh-H)//2,(rw-W)//2;assert min(top,left)>=0
  lut=np.floor(np.clip(np.arange(65536)/15000.,0,1)*65535+.5).astype(np.uint16);norm=lut[raw];del raw
  sample=np.empty(((H+3)//4,(W+3)//4,3),np.uint16)
  for y0 in range(0,rh,256):
   y1=min(rh,y0+256);hs=max(0,y0-4);he=min(rh,y1+4);tile=cv2.cvtColor(norm[hs:he],cv2.COLOR_BayerGB2BGR_EA);ys=np.arange(max(y0,top),min(y1,top+H));ys=ys[(ys-top)%4==0]
   if len(ys):sample[(ys-top)//4]=tile[ys-hs,left:left+W:4]
  del norm;ref=ref[::4,::4];scene={'id':sid,'ISO':j['ISO'],'pair_checks':matches,'dng_sha256':meta['dng_sha256'],'jpg_sha256':meta['jpg_sha256'],'whiteY':whiteY,'normalization_EV':float(np.log2(1/whiteY)),'conditions':{}}
  for mode,scale in [('target_native',1.),('white_normalized_control',1/whiteY)]:
   sm=np.eye(3)*scale;image,counts,secs=run_native(sample,sm,ca9,work,dst,tone,dg,out/'scratch',blib);cand,ccounts,csecs=run_native(sample,sm,ca9,work,dst,tone,dg,out/'scratch',clib)
   assert counts==ccounts and np.array_equal(cand,post(image)),'integrated candidate does not equal standalone lightness pass'
   if mode=='target_native':al=align(image,ref);scene['alignment']=al
   ba,rr=view(image,ref,al);ca,rr2=view(cand,ref,al);assert np.array_equal(rr,rr2)
   bp,rp,ps=a.patch_values(ba,rr);cp,rp2,ps2=a.patch_values(ca,rr);assert np.array_equal(rp,rp2) and ps==ps2
   rec={'baseline':a.groups(bp,rp),'candidate':a.groups(cp,rp),'patches':ps,'baseline_counts':counts,'candidate_counts':ccounts,'host_wall_seconds_including_JVM':{'baseline':secs,'candidate':csecs}}
   h,w=ba.shape[:2];s1,s2=slice(h//4,3*h//4),slice(w//4,3*w//4);bp2,rp2,_=a.patch_values(ba[s1,s2],rr[s1,s2]);cp2,_,_=a.patch_values(ca[s1,s2],rr[s1,s2]);rec['central_baseline']=a.groups(bp2,rp2);rec['central_candidate']=a.groups(cp2,rp2)
   rec['clipping_before_rgb']=(ba==0).mean((0,1)).tolist();rec['clipping_after_rgb']=(ca==0).mean((0,1)).tolist()
   cr=np.linalg.norm(rp[:,1:],axis=1);cb=np.linalg.norm(bp[:,1:],axis=1);ct=np.linalg.norm(cp[:,1:],axis=1);chrom=(cr>=20)&(cb>=5);rec['baseline_chroma_ratio']=float(np.median(cb[chrom]/cr[chrom])) if chrom.any() else None;rec['candidate_chroma_ratio']=float(np.median(ct[chrom]/cr[chrom])) if chrom.any() else None
   if sid in ['01','03','05'] and mode=='target_native':training.append((bp,rp))
   if mode=='target_native':
    thumbs=[]
    for name,im in [('reference',rr),('baseline',ba),('candidate',ca)]:
     img=Image.fromarray(im);img.thumbnail((450,300));img.save(out/f'{sid}_{name}.jpg',quality=95);thumbs.append(img)
    pictures.append((sid,thumbs))
   scene['conditions'][mode]=rec
   print(sid,mode,rec['baseline']['all']['L_mae'],'->',rec['candidate']['all']['L_mae'],flush=True)
  result['scenes'][sid]=scene;(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
 # Confirm the fixed parameter fit uses only the original three development scenes.
 if len(training)==3:
  X=[];Y=[];weights=[]
  for aa,bb in training:
   mask=np.linalg.norm(bb[:,1:],axis=1)<8;t=aa[mask,0]/100;X.append(4*t[:,None]*(1-t[:,None])*np.stack([np.ones_like(t),2*t-1,6*t*t-6*t+1],-1));Y.append(bb[mask,0]-aa[mask,0]);weights.append(np.ones(mask.sum())/mask.sum())
  X=np.concatenate(X);Y=np.concatenate(Y);w=np.concatenate(weights);coef=np.linalg.solve(X.T@(w[:,None]*X)+.01*np.eye(3),X.T@(w*Y));assert np.max(abs(coef-result['fitted_coefficients']))<1e-8,coef;result['training_fit_reproduced']=True
 summaries={}
 for split,sids in [('original_validation',['02','04','06']),('fresh_validation',['07','08','09','10'])]:
  if not all(sid in result['scenes'] for sid in sids):continue
  summaries[split]={}
  for mode in ['target_native','white_normalized_control']:
   ss=[result['scenes'][sid]['conditions'][mode] for sid in sids];m={}
   for key in ['L_mae','ab_error_mean','DE76_mean']:
    m['baseline_'+key]=float(np.mean([r['baseline']['all'][key] for r in ss]));m['candidate_'+key]=float(np.mean([r['candidate']['all'][key] for r in ss]))
   m['wins']=sum(r['candidate']['all']['L_mae']<r['baseline']['all']['L_mae'] for r in ss);m['count']=len(ss);m['L_reduction']=1-m['candidate_L_mae']/m['baseline_L_mae'];summaries[split][mode]=m
 result['summary']=summaries
 passed=all(m['L_reduction']>0 and m['wins']>=m['count']-1 and m['candidate_ab_error_mean']<m['baseline_ab_error_mean']+.15 for split in summaries.values() for m in split.values())
 result['status']='PASS_NATIVE_TONECAL1A_TEST_CANDIDATE' if passed else 'FAIL_PHOTOGRAPHIC_GATE';result['apk_gate_passed']=passed and args.fresh and len(result['scenes'])==10;result['production_promoted']=False
 # No host wall-time measurement is an Android performance claim.
 board=Image.new('RGB',(1380,335*len(pictures)+40),'white');dr=ImageDraw.Draw(board);dr.text((10,10),'TONECAL1A: reference | baseline | native tone candidate. Source: Photography Blog.',fill='black')
 for row,(sid,thumbs) in enumerate(pictures):
  for col,im in enumerate(thumbs):dr.text((col*460+5,row*335+40),sid,fill='black');board.paste(im,(col*460+5,row*335+60))
 board.save(out/'COMPARISON.jpg',quality=94)
 (out/'results.json').write_text(json.dumps(result,indent=2)+'\n');lines=['# RENDER1R TONECAL1A native validation','',result['status'],'','Fixed empirical lightness correction; not Y BLEND decoding, not capture exposure correction.','','| Scene | Input | Baseline L* MAE | Candidate L* MAE | Baseline a*b* error | Candidate a*b* error |','|---|---|---:|---:|---:|---:|']
 for sid,s in result['scenes'].items():
  for mode,r in s['conditions'].items():lines.append(f"| {sid} | {mode} | {r['baseline']['all']['L_mae']:.4f} | {r['candidate']['all']['L_mae']:.4f} | {r['baseline']['all']['ab_error_mean']:.4f} | {r['candidate']['all']['ab_error_mean']:.4f} |")
 lines+=['','## Limits']+['- '+x for x in result['limitations']]+['','## Summary','```json',json.dumps(summaries,indent=2),'```'];(out/'REPORT.md').write_text('\n'.join(lines)+'\n')
 # Package only results and reduced comparison images, not original photos or binaries.
 for d in ['baseline','candidate','candidate_source','scratch']:shutil.rmtree(out/d,ignore_errors=True)
 host.unlink();so.unlink()
 manifest=[{'path':str(p.relative_to(out)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(out.rglob('*')) if p.is_file()];(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 print(json.dumps(summaries,indent=2));assert passed,result['status']
if __name__=='__main__':main()
