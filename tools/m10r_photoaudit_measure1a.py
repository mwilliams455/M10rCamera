#!/usr/bin/env python3
"""PHOTOAUDIT1A: genuine M10-R RAW target-boundary audit, NOT Android frontend parity.
Original nativeProcessTile is compiled unchanged. A matrix-only DNG adapter and a
second normalization condition are disclosed; no per-scene exposure/WB fitting.
Odd scene IDs diagnose a shared L* residual; even scene IDs are held out.
"""
from pathlib import Path
import sys, re, json, hashlib, subprocess, shutil, os, struct
import numpy as np
import cv2
from PIL import Image, ImageDraw

TRAIN={'01','03','05'}
TEST={'02','04','06'}
STEP=4
PATCH=16

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def nums(v):
    if isinstance(v,str): return np.array([float(x) for x in v.split()],dtype=np.float64)
    return np.asarray(v,dtype=np.float64)
def constant(s,name):
    m=re.search(r'\b'+name+r'\s*=\s*\{(.*?)\};',s,re.S)
    if not m: raise ValueError('missing constant '+name)
    return np.array([float(x) for x in re.findall(r'[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?',m.group(1))])
def xform(a,m):
    return np.stack([a[...,0]*m[i,0]+a[...,1]*m[i,1]+a[...,2]*m[i,2] for i in range(3)],axis=-1)
def lab(rgb): return cv2.cvtColor(np.ascontiguousarray(rgb,dtype=np.float32).reshape(-1,1,3),cv2.COLOR_RGB2LAB).reshape(-1,3).astype(float)
def invlab(a): return cv2.cvtColor(np.ascontiguousarray(a,dtype=np.float32).reshape(-1,1,3),cv2.COLOR_LAB2RGB).reshape(-1,3)
def metric(a,b):
    if not len(a): return {'n':0}
    d=a-b
    return {'n':len(a),'L_bias_median':float(np.median(d[:,0])), 'L_mae':float(np.mean(abs(d[:,0]))),
        'ab_error_mean':float(np.mean(np.linalg.norm(d[:,1:],axis=1))),
        'DE76_mean':float(np.mean(np.linalg.norm(d,axis=1)))}
def groups(a,b):
    C=np.linalg.norm(b[:,1:],axis=1)
    masks={'all':np.ones(len(b),bool),'neutral':C<8,'chromatic':C>=20,'shadow':b[:,0]<35,
           'midtone':(b[:,0]>=35)&(b[:,0]<75),'highlight':b[:,0]>=75,'warm':(b[:,1]>5)&(b[:,2]>5)}
    return {k:metric(a[v],b[v]) for k,v in masks.items()}

def make_native(source,out):
    full=(source/'m10rRender.cpp').read_text()
    core=full.split('\n\n// Exact Leica M10-R B2Y record 0x1E')[0]
    assert core.count('Java_com_particlesdevs_photoncamera_m10r_M10RNativeRenderer_nativeProcessTile(')==1
    assert 'nativeEdgePass' not in core
    # Only remove an unused Android bitmap header; original pixel-function bytes remain intact.
    core=core.replace('#include <android/bitmap.h>\n','')
    (out/'native_core.cpp').write_text(core)
    java=r'''package com.particlesdevs.photoncamera.m10r;
import java.nio.*; import java.nio.file.*; import java.util.*;
public class M10RNativeRenderer {
 static {System.load(System.getProperty("audit.library"));}
 private static native void nativeProcessTile(short[] rgb,int pixels,double inv,double[] src,int[] ca9,double[] work,double[] dst,int[] tone,int[] dg,int[] out,long[] counts);
 static ByteBuffer read(String s) throws Exception {return ByteBuffer.wrap(Files.readAllBytes(Path.of(s))).order(ByteOrder.LITTLE_ENDIAN);}
 static double[] ds(ByteBuffer b,int n) {double[] a=new double[n];for(int i=0;i<n;i++)a[i]=b.getDouble();return a;}
 static int[] is(ByteBuffer b,int n) {int[] a=new int[n];for(int i=0;i<n;i++)a[i]=b.getInt();return a;}
 public static void main(String[] a) throws Exception {
  ByteBuffer r=read(a[0]),p=read(a[1]); short[] rgb=new short[r.remaining()/2];r.asShortBuffer().get(rgb);
  double inv=p.getDouble(); double[] src=ds(p,9);int[] ca9=is(p,3);double[] work=ds(p,9),dst=ds(p,9);
  int[] tone=is(p,10240),dg=is(p,32768),out=new int[rgb.length/3];long[] counts=new long[8];
  nativeProcessTile(rgb,out.length,inv,src,ca9,work,dst,tone,dg,out,counts);
  ByteBuffer result=ByteBuffer.allocate(out.length*4).order(ByteOrder.LITTLE_ENDIAN);result.asIntBuffer().put(out);
  Files.write(Path.of(a[2]),result.array());System.out.println(Arrays.toString(counts));
 }
}'''
    (out/'M10RNativeRenderer.java').write_text(java)
    jhome=Path(shutil.which('javac')).resolve().parent.parent
    lib=(out/'libaudit.so').resolve()
    subprocess.run(['g++','-O3','-std=c++17','-ffp-contract=off','-fPIC','-shared','-pthread',
      '-I'+str(jhome/'include'),'-I'+str(jhome/'include/linux'),str(out/'native_core.cpp'),'-o',str(lib)],check=True)
    subprocess.run(['javac','-d',str(out),str(out/'M10RNativeRenderer.java')],check=True)
    return lib, {'full_cpp_sha256':sha(source/'m10rRender.cpp'),'host_prefix_sha256':sha(out/'native_core.cpp'),
      'changes':'Unused Android bitmap include removed; disabled edge/inverse-transfer functions excluded; nativeProcessTile body unchanged.',
      'compiler':subprocess.check_output(['g++','--version']).decode().splitlines()[0],
      'java_home':str(jhome)}

def native(rgb,src,ca9,work,dst,tone,dg,root,lib):
    root.mkdir(exist_ok=True)
    rgb.astype('<u2').tofile(root/'rgb.u16')
    with (root/'params.bin').open('wb') as f:
        f.write(struct.pack('<d',1.0));f.write(src.astype('<f8').tobytes());f.write(ca9.astype('<i4').tobytes())
        for m in [work,dst]:f.write(m.astype('<f8').tobytes())
        f.write(tone.astype('<i4').tobytes());f.write(dg.astype('<i4').tobytes())
    s=subprocess.check_output(['java','-Xmx512m','-Daudit.library='+str(lib),'-cp',str(lib.parent),
       'com.particlesdevs.photoncamera.m10r.M10RNativeRenderer',str(root/'rgb.u16'),str(root/'params.bin'),str(root/'argb.bin')]).decode()
    v=np.fromfile(root/'argb.bin',dtype='<u4')
    result=np.stack([(v>>16)&255,(v>>8)&255,v&255],-1).astype(np.uint8).reshape(rgb.shape)
    for name in ['rgb.u16','argb.bin']: (root/name).unlink()
    return result,json.loads(s)

def mirror(rgb,src,ca9,work,dst,tone,dg):
    tr=xform(rgb.astype(float)/65535.,src)
    clips=(tr*ca9/256.>1).mean((0,1)).tolist()
    tr=np.clip(tr*ca9/256.,0,1)*256./ca9
    w=xform(tr,work)
    y=(1224*w[...,0]+2403*w[...,1]+469*w[...,2])/4096.
    cb=(-691*w[...,0]-1357*w[...,1]+2048*w[...,2])/4096.
    cr=(2048*w[...,0]-1715*w[...,1]-333*w[...,2])/4096.
    xy=np.floor(np.clip(y,0,1)*16383+0.5).astype(np.int64)
    my=(xy*tone[xy>>1].astype(np.int64))>>15
    mapped=dg[np.clip(my,0,32767)]/16383.
    ratio=np.divide(mapped,y,out=np.zeros_like(y),where=y>1e-12)
    scale=np.where(y>1e-12,1+0.35*(ratio-1),0)
    cb*=scale;cr*=scale
    n=np.stack([mapped-.001043337611*cb+1.401991725445*cr,
        mapped-.345114690199*cb-.714098755336*cr,
        mapped+1.770975790582*cb-.000124867533*cr],-1)
    out=xform(n,dst)
    q=np.floor(np.clip(out,0,1)*255+.5).astype(np.uint8)
    stats={'ca9_high_fraction_rgb':clips,'tone_input_high_fraction':float(np.mean(y>1)),
      'working_negative_fraction_rgb':(w<0).mean((0,1)).tolist(),
      'post_cc1_low_fraction_rgb':(out<0).mean((0,1)).tolist(),'post_cc1_high_fraction_rgb':(out>1).mean((0,1)).tolist(),
      'working_Y_quantiles':np.quantile(y,[.01,.1,.5,.9,.99]).tolist(),
      'mapped_Y_quantiles':np.quantile(mapped,[.01,.1,.5,.9,.99]).tolist()}
    return q,stats

def align(a,b):
    # Search actual pixel layout, independent of metadata's display-orientation convention.
    h,w=a.shape[:2]; best=None
    ga=cv2.GaussianBlur(a.astype(np.float32).mean(2),(0,0),2)
    ga=ga-cv2.GaussianBlur(ga,(0,0),12)
    for k in range(4):
        rb=np.rot90(b,k).copy()
        if rb.shape[:2]!=(h,w): continue
        gb=cv2.GaussianBlur(rb.astype(np.float32).mean(2),(0,0),2)
        gb-=cv2.GaussianBlur(gb,(0,0),12)
        for dy in range(-3,4):
            for dx in range(-3,4):
                aa=ga[12:-12,12:-12].ravel();bb=gb[12+dy:h-12+dy,12+dx:w-12+dx].ravel()
                score=float(np.dot(aa,bb)/np.sqrt(np.dot(aa,aa)*np.dot(bb,bb)))
                if best is None or score>best[0]:best=(score,k,dx,dy,rb)
    if best is None: raise ValueError('no exact dimension/orientation alignment')
    score,k,dx,dy,rb=best
    # A conservative interior common window avoids roll-filled borders.
    margin=16
    return a[margin:h-margin,margin:w-margin],rb[margin+dy:h-margin+dy,margin+dx:w-margin+dx],{
       'gradient_correlation':score,'reference_rot90_k':k,'dx_sample_pixels':dx,'dy_sample_pixels':dy,'margin_sample_pixels':margin}

def patch_values(a,b):
    h,w=a.shape[:2];h=h//PATCH*PATCH;w=w//PATCH*PATCH
    def block(x):return x[:h,:w].reshape(h//PATCH,PATCH,w//PATCH,PATCH,3).transpose(0,2,1,3,4).reshape(-1,PATCH*PATCH,3)/255.
    aa,bb=block(a),block(b)
    ma,mb=aa.mean(1),bb.mean(1)
    sd=bb.std(1).max(1)
    good=(sd<.035)&(mb.mean(1)>.02)&(mb.mean(1)<.98)
    return lab(ma[good]),lab(mb[good]),{'selected':int(good.sum()),'total':len(good),'selection':'Reference RGB max-channel patch SD <0.035; mean code in (0.02,0.98); no baseline-dependent mask.'}

def fit_tone(train):
    X=[];Y=[];W=[]
    for a,b in train:
        mask=np.linalg.norm(b[:,1:],axis=1)<8
        if mask.sum()<20:raise ValueError('insufficient neutral training patches')
        X.extend(a[mask,0]);Y.extend(b[mask,0]);W.extend(np.full(mask.sum(),1./mask.sum()))
    X,Y,W=map(np.array,[X,Y,W])
    xp=np.arange(0.,101.,5.); sums=np.zeros(len(xp));weights=np.zeros(len(xp))
    ix=np.clip(np.floor(X/5+.5).astype(int),0,len(xp)-1)
    np.add.at(sums,ix,Y*W);np.add.at(weights,ix,W)
    # Small identity prior only for weakly supported bins; endpoint anchors are explicit.
    prior=.01
    yp=(sums+prior*xp)/(weights+prior);ww=weights+prior
    yp[0]=0;yp[-1]=100;ww[0]=ww[-1]=1000
    blocks=[]
    for i,(v,w) in enumerate(zip(yp,ww)):
        blocks.append([i,i,float(v*w),float(w)])
        while len(blocks)>1 and blocks[-2][2]/blocks[-2][3]>blocks[-1][2]/blocks[-1][3]:
            p=blocks.pop();q=blocks.pop();blocks.append([q[0],p[1],q[2]+p[2],q[3]+p[3]])
    for l,r,s,w in blocks:yp[l:r+1]=s/w
    return xp,yp,{'neutral_training_patches':len(X),'scene_weighting':'equal total weight per training scene','knots_input_L':xp.tolist(),'knots_output_L':yp.tolist(),'identity_prior_per_bin':prior}

def corrected_lab(a,xp,yp):
    candidate=a.copy();candidate[:,0]=np.interp(a[:,0],xp,yp)
    # Score an actual bounded RGB conversion, not impossible out-of-gamut Lab values.
    return lab(invlab(candidate))

def main():
    inputs,out=map(Path,sys.argv[1:]);out.mkdir(parents=True,exist_ok=True)
    for e in json.loads((inputs/'manifest.json').read_text()):
        p=inputs/e['path'];assert p.stat().st_size==e['bytes'] and sha(p)==e['sha256']
    source=inputs/'source';js=(source/'M10RNativeRenderer.java').read_text()
    cmA=constant(js,'M10_CM_A').reshape(3,3);cmD=constant(js,'M10_CM_D65').reshape(3,3)
    pcs=constant(js,'PCS_TO_INTERNAL').reshape(3,3);dst=constant(js,'DEFAULT_SRGB_CC1').reshape(3,3)
    br=constant(js,'BRADFORD').reshape(3,3);d50xy=constant(js,'D50_XY')
    d50=np.array([d50xy[0]/d50xy[1],1,(1-sum(d50xy))/d50xy[1]])
    tone=np.fromfile(inputs/'assets/tone_medium_q15.u32le',dtype='<u4')
    dg=np.fromfile(inputs/'assets/dg_expanded_u16le.bin',dtype='<u2')
    assert len(tone)==10240 and len(dg)==32768
    lib,native_info=make_native(source,out)
    result={'status':'STARTED','baseline_commit':'a66b73cc339ebcb863d345c7a9ee7ff631fc86f0',
      'executed_commit':os.environ.get('GITHUB_SHA'),'run_id':os.environ.get('GITHUB_RUN_ID'),
      'native':native_info,'opencv_version':cv2.__version__,'numpy_version':np.__version__,
      'development_scenes':sorted(TRAIN),'held_out_scenes':sorted(TEST),'sample_stride':STEP,'scenes':[],
      'scope':'Original native colour/tone core on genuine M10-R RAW data. Matrix-only target-domain DNG adapter; NOT an end-to-end Android Camera2 frontend equivalence claim.',
      'limitations':['References are from firmware 10.20.27.20; current tables are extracted from 30.22.23.34.',
       'No phone metering or shutter/ISO policy evaluated. RAW exposure and recorded camera WB held fixed.',
       'No DNG GainMap was supplied by these metadata exports; no lens-shading correction added. Centre-region sensitivity must be checked before target attribution.',
       'Reference JPEGs and native output have different demosaic, optical/lens corrections and sharpening. Flat patches reduce but do not eliminate those confounds.',
       'L* residual is an empirical diagnostic fitted to three scenes, not recovered firmware arithmetic or an approved app change.',
       'Target-native and white-normalized source-adapter conditions are both reported; normalization sensitivity prevents a full-pipeline attribution.']}
    cached={}
    for sid in sorted(TRAIN|TEST):
        meta=json.loads((inputs/'samples'/f'{sid}_metadata.json').read_text());j,d=meta['metadata']
        keys=['Model','SerialNumber','ImageUniqueID','DateTimeOriginal','ISO','ExposureTime','FNumber','FocalLength']
        matched={k:j.get(k)==d.get(k) and j.get(k) is not None for k in keys};assert all(matched.values()),matched
        assert all(j.get(k)==0 for k in ['Contrast','Saturation','Sharpness'])
        assert j.get('ColorSpace')==1
        assert np.max(abs(nums(d['ColorMatrix1']).reshape(3,3)-cmA))<1e-7
        assert np.max(abs(nums(d['ColorMatrix2']).reshape(3,3)-cmD))<1e-7
        asn=nums(d['AsShotNeutral']);ca9=np.clip(np.rint(256/asn),1,2000).astype(int)
        kelvin=float(d['CorrelatedColorTemp']);xy=nums(d['WhitePoint'])
        f=np.clip((1/kelvin-1/6504)/(1/2856-1/6504),0,1);cm=f*cmA+(1-f)*cmD
        white=np.array([xy[0]/xy[1],1,(1-xy.sum())/xy[1]])
        adaptation=np.linalg.inv(br)@np.diag((br@d50)/(br@white))@br
        work=pcs@adaptation@np.linalg.inv(cm)
        whiteY=float((np.linalg.inv(cm)@asn)[1])
        raw=np.load(inputs/'samples'/f'{sid}_raw.npz')['raw']
        assert meta['color_desc']=='RGBG' and meta['raw_pattern']==[[3,2],[0,1]]
        assert all(v==0 for v in meta['black_level_per_channel']) and meta['white_level']==15000
        rawstats={'raw_dimensions':list(raw.shape),'hard_clip_fraction':float(np.mean(raw>=15000)),
          'green_quantiles_fraction_white':(np.quantile(raw[0::2,0::2],[.01,.1,.5,.9,.99])/15000.).tolist()}
        normalized=np.floor(np.clip(raw.astype(np.float64)/15000.,0,1)*65535+.5).astype(np.uint16);del raw
        ref=np.asarray(Image.open(inputs/'samples'/f'{sid}.jpg').convert('RGB'))
        # Camera JPEG is a smaller centred raster than the exported RAW; search orientation below.
        H,W=min(ref.shape[:2]),max(ref.shape[:2]);rh,rw=normalized.shape
        top=(rh-H)//2;left=(rw-W)//2;assert top>=0 and left>=0
        # Full-resolution demosaic with the same EA code and four-row tile halo as Android.
        sample=np.empty(((H+STEP-1)//STEP,(W+STEP-1)//STEP,3),dtype=np.uint16)
        for y0 in range(0,rh,256):
            y1=min(rh,y0+256);hs=max(0,y0-4);he=min(rh,y1+4)
            tile=cv2.cvtColor(normalized[hs:he],cv2.COLOR_BayerGB2BGR_EA)
            ys=np.arange(max(y0,top),min(y1,top+H));ys=ys[(ys-top)%STEP==0]
            if len(ys):sample[(ys-top)//STEP]=tile[ys-hs,left:left+W:STEP]
        del normalized
        ref=ref[::STEP,::STEP]
        scene={'id':sid,'split':'development' if sid in TRAIN else 'held_out','pair_identity_checks':matched,
          'dng_sha256':meta['dng_sha256'],'jpg_sha256':meta['jpg_sha256'],'ISO':j['ISO'],'ExposureTime':j['ExposureTime'],
          'reference_firmware':j['Software'],'recorded_kelvin':kelvin,'recorded_whitepoint_xy':xy.tolist(),
          'AsShotNeutral':asn.tolist(),'CA9_gains':ca9.tolist(),'whiteY_normalization_control':whiteY,
          'source_crop_top_left':[top,left],'raw_exposure':rawstats,'conditions':{}}
        for mode,factor in [('target_native',1.),('white_normalized_control',1./whiteY)]:
            src=np.eye(3)*factor
            image,counts=native(sample,src,ca9,work,dst,tone,dg,out/'scratch',lib)
            # Independent expression is used only for tracing; native bytes form the photographs.
            mirrored,stats=mirror(sample,src,ca9,work,dst,tone,dg)
            diff=np.abs(image.astype(np.int16)-mirrored.astype(np.int16));assert diff.max()<=1
            aa,bb,al=align(image,ref);assert al['gradient_correlation']>.75,al
            a,b,ps=patch_values(aa,bb);assert len(a)>50
            rec={'alignment':al,'patches':ps,'baseline':groups(a,b),'native_counts':counts,'stage_stats':stats,
               'mirror_exact_pixel_fraction':float(np.mean(np.all(diff==0,axis=2))),'mirror_max_code_difference':int(diff.max()),
               'src_matrix':src.tolist(),'working_matrix':work.tolist(),'output_matrix':dst.tolist()}
            scene['conditions'][mode]=rec;cached[(sid,mode)]=(a,b,aa,bb)
            Image.fromarray(aa).save(out/f'{sid}_{mode}_baseline.jpg',quality=95)
            if mode=='target_native':Image.fromarray(bb).save(out/f'{sid}_reference.jpg',quality=95)
            print(sid,mode,rec['baseline']['all'],flush=True)
        result['scenes'].append(scene)
        (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    result['tone_diagnostic']={}
    for mode in ['target_native','white_normalized_control']:
        xp,yp,fit=fit_tone([cached[(sid,mode)][:2] for sid in sorted(TRAIN)])
        held=[]
        for scene in result['scenes']:
            sid=scene['id'];a,b,aa,bb=cached[(sid,mode)]
            cc=corrected_lab(a,xp,yp);m=groups(cc,b);scene['conditions'][mode]['tone_only_diagnostic']=m
            if sid in TEST:held.append((scene['conditions'][mode]['baseline']['all'],m['all']))
            l=lab(aa.reshape(-1,3)/255.);l[:,0]=np.interp(l[:,0],xp,yp)
            rgb=np.floor(np.clip(invlab(l),0,1)*255+.5).astype(np.uint8).reshape(aa.shape)
            Image.fromarray(rgb).save(out/f'{sid}_{mode}_tone_diagnostic.jpg',quality=95)
        baseL=float(np.mean([a['L_mae'] for a,b in held]));candL=float(np.mean([b['L_mae'] for a,b in held]))
        baseE=float(np.mean([a['DE76_mean'] for a,b in held]));candE=float(np.mean([b['DE76_mean'] for a,b in held]))
        result['tone_diagnostic'][mode]={'fit':fit,'heldout_scene_equal_mean_L_mae_baseline':baseL,
          'heldout_scene_equal_mean_L_mae_candidate':candL,'heldout_L_mae_relative_reduction':1-candL/baseL,
          'heldout_scene_equal_mean_DE76_baseline':baseE,'heldout_scene_equal_mean_DE76_candidate':candE,
          'heldout_L_wins':sum(b['L_mae']<a['L_mae'] for a,b in held),
          'promotion':'NOT_PROMOTED: diagnostic L* correction; source-adapter and coverage caveats remain.'}
    result['status']='PASS_NATIVE_TARGET_BOUNDARY_PHOTOGRAPHIC_AUDIT'
    result['script_sha256']=sha(__file__);result['frozen_renderer_modified']=False;result['capture_policy_modified']=False
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    lines=['# M10-R PHOTOAUDIT1A — actual same-RAW photographic audit','',result['scope'],'',
      'Six Photography Blog original same-shot DNG/JPEG pairs. Identity is checked independently by camera serial, unique image ID, time and exposure fields. Reference firmware differs from the extracted-table firmware.','',
      '## Original native core results','', '| Scene | Split | ISO | Condition | Patches | L* MAE | a*b* error | Delta E76 |','|---|---|---:|---|---:|---:|---:|---:|']
    for s in result['scenes']:
        for mode,c in s['conditions'].items():
            m=c['baseline']['all'];lines.append(f"| {s['id']} | {s['split']} | {s['ISO']} | {mode} | {m['n']} | {m['L_mae']:.3f} | {m['ab_error_mean']:.3f} | {m['DE76_mean']:.3f} |")
    lines+=['','## Held-out tone-only diagnostic','', 'Training uses only neutral patches from 01/03/05, equal total scene weights, a monotonic 5-L* knot curve and the documented identity prior. No per-scene exposure or white-balance fit. 02/04/06 are never used for fitting. The correction changes L* only before an explicit RGB gamut conversion.','']
    for mode,d in result['tone_diagnostic'].items():
        lines += [f"### {mode}",f"Held-out scene-equal L* MAE: {d['heldout_scene_equal_mean_L_mae_baseline']:.3f} -> {d['heldout_scene_equal_mean_L_mae_candidate']:.3f}; {d['heldout_L_wins']}/3 wins. Delta E76: {d['heldout_scene_equal_mean_DE76_baseline']:.3f} -> {d['heldout_scene_equal_mean_DE76_candidate']:.3f}.",d['promotion'],'']
    lines+=['## Limitations','']+['- '+s for s in result['limitations']]
    lines+=['','No APK produced, no photographic baseline promotion, no firmware-exactness claim. Results come from the CI run stated in results.json; no claim of independent local rerun. Native arithmetic is checked against an independently expressed array implementation; image formation uses the original C++ function.','',
      'Reference source: https://www.photographyblog.com/reviews/leica_m10_r_review','Frozen baseline: '+result['baseline_commit'],'Audit source commit: '+str(result['executed_commit']),'Actions run: '+str(result['run_id'])]
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n')
    files=[{'path':str(p.relative_to(out)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(out.rglob('*')) if p.is_file() and p.suffix in ['.json','.md','.jpg','.cpp','.java','.bin']]
    (out/'manifest.json').write_text(json.dumps(files,indent=2)+'\n')
    shutil.rmtree(out/'scratch',ignore_errors=True)
    print(json.dumps(result['tone_diagnostic'],indent=2))
if __name__=='__main__':main()
