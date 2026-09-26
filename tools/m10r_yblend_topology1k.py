#!/usr/bin/env python3
"""M10-R YBLEND TOPOLOGY1K.

Offline same-shot Leica M10-R DNG/JPEG discriminator for a topology-correct
Y/Yb architecture suggested by:
- M10-R firmware: CCYC, TCYC, RGB tone enabled / Yb tone disabled,
  five selectable DGamma table banks, YBLEND=(0,32).
- Related Socionext/Fujitsu R2Y source: separate Y and Yb luminance paths.
- Fujitsu image-processing patent family: pre-gamma Yl -> Yb gamma path,
  gamma-corrected RGB -> YC -> Ya/Cb/Cr, then main-line Y blends Ya/Yb.

No ASIC parity claim is made. No renderer/APK is changed.
"""
from pathlib import Path
import hashlib,json,math,os,re,subprocess,sys
import numpy as np
import cv2
from PIL import Image

STEP=4
PATCH=16
INPUT_MAX=0x3fff
DG_MAX=0x3fff
TCYC=np.array([1024.,2661.,410.])/4096.0
CCYC=np.array([77.,150.,29.])/256.0
YCM=np.array([
 [1224.,2403.,469.],
 [-691.,-1357.,2048.],
 [2048.,-1715.,-333.]
])/4096.0
YCI=np.linalg.inv(YCM)
MODELS=[
 "CURRENT_K035",
 "TOPO_RGBDG_YBDG",
 "TOPO_RGBDG_YBRAW",
 "TOPO_LUMADG_YBDG",
 "TOPO_LUMADG_YBRAW",
]
EXPECTED_CURRENT={
 "01":(2.047,5.473),"02":(2.676,2.903),"03":(2.658,7.907),
 "04":(2.460,3.518),"05":(1.923,10.861),"06":(2.479,11.696),
}

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def nums(v):
    if isinstance(v,str):return np.array([float(x) for x in v.split()],dtype=np.float64)
    return np.asarray(v,dtype=np.float64)
def constant(s,name):
    m=re.search(r'\b'+name+r'\s*=\s*\{(.*?)\};',s,re.S)
    if not m:raise ValueError("missing "+name)
    return np.array([float(x) for x in re.findall(r'[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?',m.group(1))])
def xform(a,m):
    return np.stack([a[...,0]*m[i,0]+a[...,1]*m[i,1]+a[...,2]*m[i,2] for i in range(3)],axis=-1)
def lab(rgb):
    return cv2.cvtColor(np.ascontiguousarray(rgb,dtype=np.float32).reshape(-1,1,3),cv2.COLOR_RGB2LAB).reshape(-1,3).astype(float)
def circ_abs_deg(a,b):
    d=np.abs(a-b)%360.0;return np.minimum(d,360.0-d)
def metrics(a,b):
    d=a-b;Cref=np.linalg.norm(b[:,1:],axis=1);Cr=np.linalg.norm(a[:,1:],axis=1)
    hr=np.degrees(np.arctan2(b[:,2],b[:,1]))%360;ha=np.degrees(np.arctan2(a[:,2],a[:,1]))%360
    chrom=Cref>=20;warm=(b[:,1]>5)&(b[:,2]>5)&chrom
    return {
      "n":int(len(a)),
      "L_mae":float(np.mean(np.abs(d[:,0]))),
      "ab_error":float(np.mean(np.linalg.norm(d[:,1:],axis=1))),
      "DE76":float(np.mean(np.linalg.norm(d,axis=1))),
      "chroma_ratio_ref_ge20":float(np.mean(Cr[chrom]/Cref[chrom])) if np.any(chrom) else None,
      "hue_abs_error_deg_ref_ge20":float(np.mean(circ_abs_deg(ha[chrom],hr[chrom]))) if np.any(chrom) else None,
      "warm_n":int(warm.sum()),
      "warm_ab_error":float(np.mean(np.linalg.norm(d[warm,1:],axis=1))) if np.any(warm) else None,
      "warm_chroma_ratio":float(np.mean(Cr[warm]/Cref[warm])) if np.any(warm) else None,
      "warm_hue_abs_error_deg":float(np.mean(circ_abs_deg(ha[warm],hr[warm]))) if np.any(warm) else None,
    }
def patch_values(a,b):
    h,w=a.shape[:2];h=h//PATCH*PATCH;w=w//PATCH*PATCH
    def block(x):
        return x[:h,:w].reshape(h//PATCH,PATCH,w//PATCH,PATCH,3).transpose(0,2,1,3,4).reshape(-1,PATCH*PATCH,3)/255.
    aa,bb=block(a),block(b);ma,mb=aa.mean(1),bb.mean(1);sd=bb.std(1).max(1)
    good=(sd<.035)&(mb.mean(1)>.02)&(mb.mean(1)<.98)
    return lab(ma[good]),lab(mb[good]),int(good.sum())
def solve_alignment(a,b):
    h,w=a.shape[:2];ga=cv2.GaussianBlur(a.astype(np.float32).mean(2),(0,0),2);ga-=cv2.GaussianBlur(ga,(0,0),12)
    best=None
    for k in range(4):
        rb=np.rot90(b,k).copy()
        if rb.shape[:2]!=(h,w):continue
        gb=cv2.GaussianBlur(rb.astype(np.float32).mean(2),(0,0),2);gb-=cv2.GaussianBlur(gb,(0,0),12)
        for dy in range(-3,4):
            for dx in range(-3,4):
                aa=ga[12:-12,12:-12].ravel();bb=gb[12+dy:h-12+dy,12+dx:w-12+dx].ravel()
                den=np.sqrt(np.dot(aa,aa)*np.dot(bb,bb));score=float(np.dot(aa,bb)/den) if den else -1
                if best is None or score>best[0]:best=(score,k,dx,dy)
    if best is None:raise ValueError("alignment failed")
    score,k,dx,dy=best;return {"corr":score,"k":k,"dx":dx,"dy":dy,"margin":16}
def apply_alignment(a,b,al):
    rb=np.rot90(b,al["k"]).copy();h,w=a.shape[:2];m=al["margin"];dx=al["dx"];dy=al["dy"]
    return a[m:h-m,m:w-m],rb[m+dy:h-m+dy,m+dx:w-m+dx]
def medium_coord(x,tone):
    x=np.clip(x,0,len(tone)*2-1).astype(np.int64)
    return (x*tone[x>>1].astype(np.int64))>>15
def dg_of(v,dg):
    x=np.floor(np.clip(v,0,1)*INPUT_MAX+.5).astype(np.int64)
    return dg[np.clip(x,0,len(dg)-1)]/float(DG_MAX)
def render_current(w,dst,tone,dg):
    yc=xform(w,YCM);y,cb,cr=yc[...,0],yc[...,1],yc[...,2]
    xy=np.floor(np.clip(y,0,1)*INPUT_MAX+.5).astype(np.int64)
    my=medium_coord(xy,tone);mapped=dg[np.clip(my,0,len(dg)-1)]/float(DG_MAX)
    ratio=np.divide(mapped,y,out=np.zeros_like(y),where=y>1e-12)
    scale=np.where(y>1e-12,1.0+.35*(ratio-1.0),0.0)
    yc2=np.stack([mapped,cb*scale,cr*scale],-1);n=xform(yc2,YCI);out=xform(n,dst)
    return out,{"mean_chroma_scale":float(np.mean(scale[y>1e-12])),"post_cc1_high_R_fraction":float(np.mean(out[...,0]>1))}
def render_topology(w,dst,tone,dg,rgb_dg,yb_dg):
    # Leica TCYC selects tone-control luminance; Yb tone control is disabled.
    ytc=w@TCYC
    tx=np.floor(np.clip(ytc,0,1)*INPUT_MAX+.5).astype(np.int64)
    my=medium_coord(tx,tone);tone_y=my/float(INPUT_MAX)
    tg=np.divide(tone_y,ytc,out=np.zeros_like(ytc),where=ytc>1e-12)
    wrgb=w*tg[...,None]

    if rgb_dg:
        rgb_nl=np.stack([dg_of(wrgb[...,i],dg) for i in range(3)],-1)
        rgb_gamma_mode="componentwise_common_curve"
    else:
        # Control: preserve RGB ratios through DG, using the toned TCYC luminance.
        dgy=dg[np.clip(my,0,len(dg)-1)]/float(DG_MAX)
        gg=np.divide(dgy,tone_y,out=np.zeros_like(tone_y),where=tone_y>1e-12)
        rgb_nl=wrgb*gg[...,None]
        rgb_gamma_mode="luminance_gain_control"

    # CCYC is the separate pre-tone luminance path. Tone-Yb is disabled.
    yb=w@CCYC
    yb2=dg_of(yb,dg) if yb_dg else yb

    ya_cb_cr=xform(rgb_nl,YCM)
    # M10-R normal YYBLND=0. Related architecture gives Y=(YYBLND)*Ya+(1-YYBLND)*Yb.
    final_y=yb2
    yc=np.stack([final_y,ya_cb_cr[...,1],ya_cb_cr[...,2]],-1)
    n=xform(yc,YCI);out=xform(n,dst)
    valid=ytc>1e-12
    return out,{
      "rgb_gamma_mode":rgb_gamma_mode,
      "yb_gamma_applied":bool(yb_dg),
      "mean_tone_gain":float(np.mean(tg[valid])) if np.any(valid) else None,
      "mean_ya":float(np.mean(ya_cb_cr[...,0])),
      "mean_yb_pre_gamma":float(np.mean(yb)),
      "mean_yb_final":float(np.mean(yb2)),
      "mean_abs_finalY_minus_Ya":float(np.mean(np.abs(final_y-ya_cb_cr[...,0]))),
      "post_cc1_high_R_fraction":float(np.mean(out[...,0]>1)),
      "post_cc1_high_G_fraction":float(np.mean(out[...,1]>1)),
      "post_cc1_high_B_fraction":float(np.mean(out[...,2]>1)),
    }
def render_model(sample,src,ca9,work,dst,tone,dg,name):
    tr=xform(sample.astype(float)/65535.,src)
    tr=np.clip(tr*ca9/256.,0,1)*256./ca9
    w=xform(tr,work)
    if name=="CURRENT_K035":out,st=render_current(w,dst,tone,dg)
    elif name=="TOPO_RGBDG_YBDG":out,st=render_topology(w,dst,tone,dg,True,True)
    elif name=="TOPO_RGBDG_YBRAW":out,st=render_topology(w,dst,tone,dg,True,False)
    elif name=="TOPO_LUMADG_YBDG":out,st=render_topology(w,dst,tone,dg,False,True)
    elif name=="TOPO_LUMADG_YBRAW":out,st=render_topology(w,dst,tone,dg,False,False)
    else:raise KeyError(name)
    q=np.floor(np.clip(out,0,1)*255+.5).astype(np.uint8)
    return q,st
def load_scene(sid,inp):
    if int(sid)<=6:
        meta=json.loads((inp/"samples"/f"{sid}_metadata.json").read_text())
        raw=np.load(inp/"samples"/f"{sid}_raw.npz")["raw"];jpg=inp/"samples"/f"{sid}.jpg"
    else:
        import rawpy
        d=inp/"fresh";jpg=d/f"{sid}.jpg";dng=d/f"{sid}.dng"
        em=json.loads(subprocess.check_output(["exiftool","-j","-n",str(jpg),str(dng)]))
        with rawpy.imread(str(dng)) as r:
            raw=r.raw_image.copy();pattern=r.raw_pattern.tolist();black=list(r.black_level_per_channel);white=r.white_level
        meta={"id":sid,"metadata":em,"raw_pattern":pattern,"black_level_per_channel":black,"white_level":white,
              "jpg_sha256":sha(jpg),"dng_sha256":sha(dng)}
    return meta,raw,jpg
def prep(sid,inp,js,A,D,pcs,dst,br,d50):
    meta,raw,jpg=load_scene(sid,inp);j,d=meta["metadata"]
    keys=["Model","SerialNumber","ImageUniqueID","DateTimeOriginal","ISO","ExposureTime","FNumber","FocalLength"]
    chk={k:j.get(k)==d.get(k) and j.get(k)is not None for k in keys};assert all(chk.values()),(sid,chk)
    assert all(j.get(k)==0 for k in ["Contrast","Saturation","Sharpness"]) and j["ColorSpace"]==1
    assert meta["raw_pattern"]==[[3,2],[0,1]] and all(v==0 for v in meta["black_level_per_channel"]) and meta["white_level"]==15000
    assert np.max(abs(nums(d["ColorMatrix1"]).reshape(3,3)-A))<1e-7
    assert np.max(abs(nums(d["ColorMatrix2"]).reshape(3,3)-D))<1e-7
    asn=nums(d["AsShotNeutral"]);ca9=np.clip(np.rint(256/asn),1,2000).astype(int)
    kelvin=float(d["CorrelatedColorTemp"]);xy=nums(d["WhitePoint"]);white=np.array([xy[0]/xy[1],1,(1-xy.sum())/xy[1]])
    f=np.clip((1/kelvin-1/6504)/(1/2856-1/6504),0,1);cm=f*A+(1-f)*D
    ad=np.linalg.inv(br)@np.diag((br@d50)/(br@white))@br;work=pcs@ad@np.linalg.inv(cm)
    whiteY=float((np.linalg.inv(cm)@asn)[1])
    ref=np.asarray(Image.open(jpg).convert("RGB"));H,W=sorted(ref.shape[:2]);rh,rw=raw.shape
    top,left=(rh-H)//2,(rw-W)//2;assert min(top,left)>=0
    lut=np.floor(np.clip(np.arange(65536)/15000.,0,1)*65535+.5).astype(np.uint16);norm=lut[raw];del raw
    sample=np.empty(((H+3)//4,(W+3)//4,3),np.uint16)
    for y0 in range(0,rh,256):
        y1=min(rh,y0+256);hs=max(0,y0-4);he=min(rh,y1+4)
        tile=cv2.cvtColor(norm[hs:he],cv2.COLOR_BayerGB2BGR_EA)
        ys=np.arange(max(y0,top),min(y1,top+H));ys=ys[(ys-top)%4==0]
        if len(ys):sample[(ys-top)//4]=tile[ys-hs,left:left+W:4]
    return sample,ref[::4,::4],ca9,work,whiteY,{"checks":chk,"ISO":j["ISO"],"kelvin":kelvin,
        "jpg_sha256":meta["jpg_sha256"],"dng_sha256":meta["dng_sha256"]}

def main():
    if not __debug__:raise RuntimeError("Assertions required")
    inp,out=map(Path,sys.argv[1:]);out.mkdir(parents=True,exist_ok=True);cv2.setNumThreads(1)
    for e in json.loads((inp/"manifest.json").read_text()):
        p=inp/e["path"];assert p.stat().st_size==e["bytes"] and sha(p)==e["sha256"]
    js=(inp/"source/M10RNativeRenderer.java").read_text()
    A=constant(js,"M10_CM_A").reshape(3,3);D=constant(js,"M10_CM_D65").reshape(3,3)
    pcs=constant(js,"PCS_TO_INTERNAL").reshape(3,3);dst=constant(js,"DEFAULT_SRGB_CC1").reshape(3,3)
    br=constant(js,"BRADFORD").reshape(3,3);xy=constant(js,"D50_XY");d50=np.array([xy[0]/xy[1],1,(1-xy.sum())/xy[1]])
    tone=np.fromfile(inp/"assets/tone_medium_q15.u32le",dtype="<u4");dg=np.fromfile(inp/"assets/dg_expanded_u16le.bin",dtype="<u2")
    assert len(tone)==10240 and len(dg)==32768
    res={"schema":"M10R_YBLEND_TOPOLOGY1K_V1","status":"RUNNING","models":MODELS,
      "constants":{"TCYC_q12":[1024,2661,410],"CCYC_q8":[77,150,29],"YYBLND_normal":0,"YBBLND_normal":32},
      "evidence_boundary":{
        "M10R_firmware":"TCYC/CCYC rows, tone RGB=1/Yb=0, five DGamma selector banks, normal YBLEND=(0,32).",
        "cross_revision_source":"five gamma slots structurally correspond to RGB-common/R/G/B/Yb and Y/Yb are separate luminance paths.",
        "patent_architecture":"Yb is derived from pre-gamma RGB and gamma-corrected; Ya/Cb/Cr come from gamma-corrected RGB; main Y blends Ya and Yb.",
        "not_proven":"Exact M10-R ASIC routing, DG table assignment to Yb, blend denominator, rounding and physical signal widths."
      },
      "splits":{"reused_development":["01","03","05"],"reused_validation":["02","04","06"],"fresh_holdout":["07","08","09","10"]},
      "scenes":{}}
    for sid in [f"{i:02d}" for i in range(1,11)]:
        print("BEGIN",sid,flush=True)
        sample,ref,ca9,work,whiteY,meta=prep(sid,inp,js,A,D,pcs,dst,br,d50)
        scene={"metadata":meta,"whiteY":whiteY,"conditions":{}}
        for cond,factor in [("target_native",1.0),("white_normalized_control",1.0/whiteY)]:
            src=np.eye(3)*factor
            base,_=render_model(sample,src,ca9,work,dst,tone,dg,"CURRENT_K035")
            al=solve_alignment(base,ref)
            if cond=="target_native":scene["alignment"]=al
            rows={}
            for name in MODELS:
                im,st=render_model(sample,src,ca9,work,dst,tone,dg,name)
                aa,bb=apply_alignment(im,ref,al);la,lb,npats=patch_values(aa,bb)
                m=metrics(la,lb);m["patches"]=npats;m["stage_stats"]=st;rows[name]=m
                print(sid,cond,name,"DE",round(m["DE76"],4),"ab",round(m["ab_error"],4),"L",round(m["L_mae"],4),flush=True)
                if cond=="target_native" and sid in ("02","04","06","07","08","09","10"):
                    Image.fromarray(aa).save(out/f"{sid}_{name}.jpg",quality=92)
            scene["conditions"][cond]={"alignment":al,"models":rows}
        res["scenes"][sid]=scene;(out/"results.json").write_text(json.dumps(res,indent=2)+"\n")
    sanity={}
    for sid,(L,ab) in EXPECTED_CURRENT.items():
        got=res["scenes"][sid]["conditions"]["target_native"]["models"]["CURRENT_K035"]
        sanity[sid]={"L_delta":got["L_mae"]-L,"ab_delta":got["ab_error"]-ab}
        assert abs(sanity[sid]["L_delta"])<.13 and abs(sanity[sid]["ab_delta"])<.13,(sid,sanity[sid])
    res["baseline_sanity"]=sanity
    ag={}
    for split,ids in res["splits"].items():
        ag[split]={}
        for cond in ("target_native","white_normalized_control"):
            ag[split][cond]={}
            for name in MODELS:
                rr=[res["scenes"][sid]["conditions"][cond]["models"][name] for sid in ids]
                keys=["L_mae","ab_error","DE76","chroma_ratio_ref_ge20","hue_abs_error_deg_ref_ge20","warm_ab_error","warm_chroma_ratio","warm_hue_abs_error_deg"]
                ag[split][cond][name]={k:float(np.mean([x[k] for x in rr if x[k] is not None])) for k in keys}
    res["aggregates"]=ag
    # No model-selection assertion: this is a discriminator, not a tuning gate.
    res["status"]="PASS_TOPOLOGY1K_EXECUTION"
    res["script_sha256"]=sha(__file__)
    (out/"results.json").write_text(json.dumps(res,indent=2)+"\n")
    lines=["# M10-R YBLEND TOPOLOGY1K","",
      "Offline public-reference discriminator; no APK and no M10-R ASIC parity claim.","",
      "## Fresh holdout 07–10, target-native","",
      "| Model | L* MAE | a*b* error | DE76 | chroma ratio | hue err | warm a*b* | warm chroma | warm hue |",
      "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name in MODELS:
        m=ag["fresh_holdout"]["target_native"][name]
        lines.append(f"| {name} | {m['L_mae']:.3f} | {m['ab_error']:.3f} | {m['DE76']:.3f} | {m['chroma_ratio_ref_ge20']:.3f} | {m['hue_abs_error_deg_ref_ge20']:.2f} | {m['warm_ab_error']:.3f} | {m['warm_chroma_ratio']:.3f} | {m['warm_hue_abs_error_deg']:.2f} |")
    lines+=["","## Boundaries","",
      "- The Fujitsu patent supplies an architecture/equation family, not proof that Leica's ASIC uses the exact same internal routing.",
      "- The related R2Y source supplies slot names/order for a closely related generation; M10-R selector values 0..4 and addresses are firmware-proven but their semantic labels remain cross-revision.",
      "- No coefficients are fitted to 07–10; all topology variants are predeclared.",
      "- Reference JPEG firmware differs from recovered M10-R firmware.",""]
    (out/"REPORT.md").write_text("\n".join(lines))
    print(json.dumps(ag["fresh_holdout"]["target_native"],indent=2))
if __name__=="__main__":main()
