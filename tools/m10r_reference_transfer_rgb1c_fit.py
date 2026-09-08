#!/usr/bin/env python3
"""Score RGB1C encoded-luma clamp/headroom and fixed-scale candidates.

No image-dependent parameter fitting is performed. Scale 0.94 is pre-declared from
REFERENCE_TRANSFER1A's nearest-rounding median identity input scale.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageOps
import rawpy
from m10r_reference_order_fit import alignment_search,metadata_status
from m10r_reference_transfer_rgb_fit import crop_to_reference,metrics

MODES=("ll_oetf","ll_identity","el_bounded_s100","el_bounded_s094","el_extended_s100","el_extended_s094")

def load(p):
    with Image.open(p) as im:return np.asarray(im.convert("RGB"),dtype=np.uint8)

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--jpg",type=Path,required=True);ap.add_argument("--dng",type=Path,required=True)
    for x in ("ll-oetf","ll-identity","el-bounded-s100","el-bounded-s094","el-extended-s100","el-extended-s094"):
        ap.add_argument("--"+x,type=Path,required=True)
    ap.add_argument("--sample",required=True);ap.add_argument("--metadata-json",type=Path);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    with Image.open(a.jpg) as im:jpg=np.asarray(ImageOps.exif_transpose(im).convert("RGB"),dtype=np.uint8)
    renders={
        MODES[0]:load(a.ll_oetf),MODES[1]:load(a.ll_identity),MODES[2]:load(a.el_bounded_s100),
        MODES[3]:load(a.el_bounded_s094),MODES[4]:load(a.el_extended_s100),MODES[5]:load(a.el_extended_s094)}
    if len({v.shape for v in renders.values()})!=1:raise RuntimeError("RGB1C renderer geometries differ")
    with rawpy.imread(str(a.dng)) as r:
        rgb=r.postprocess(use_camera_wb=True,no_auto_bright=True,gamma=(1,1),output_bps=16,output_color=rawpy.ColorSpace.raw)
        white=float(r.white_level);flip=int(r.sizes.flip)
    proxy=rgb[...,1].astype(np.float32)*(white/65535.0);del rgb
    oriented,scores=alignment_search(proxy,jpg);score,k,dx,dy=scores[0];rh,rw=oriented.shape;jh,jw=jpg.shape[:2]
    c={name:crop_to_reference(v,k,dx,dy,rw,rh,jw,jh) for name,v in renders.items()}
    if len({v.shape for v in c.values()})!=1:raise RuntimeError("RGB1C crop geometries differ")
    h,w=next(iter(c.values())).shape[:2];ref=np.asarray(Image.fromarray(jpg).resize((w,h),Image.Resampling.LANCZOS),dtype=np.uint8)
    if h>12 and w>12:ref=ref[3:-3,3:-3];c={n:v[3:-3,3:-3] for n,v in c.items()}
    out={"sample":a.sample,"metadata":metadata_status(a.metadata_json),
         "fit_freedom":"NONE; fixed scale 0.94 declared before RGB1C from prior scalar evidence",
         "upstream":"RENDER_PARITY1A C + Leica ColorSpec; exact MEDIUM->DG; shared gain on linear RGB; final sRGB OETF for EL candidates",
         "factorial":{"encoded_luma_source":["bounded_per_channel_sRGB","extended_pre_output_clamp_sRGB"],"coordinate_scale":[1.0,0.94],"scale_placement":"before_14bit_clamp"},
         "alignment":{"score":float(score),"rot90_k":int(k),"dx":int(dx),"dy":int(dy),"rawpy_flip":flip,"raw_oriented":[rw,rh],"jpeg":[jw,jh],"comparison":[int(ref.shape[1]),int(ref.shape[0])]},
         "metrics":{n:metrics(v,ref) for n,v in c.items()}}
    a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n");print(json.dumps(out,indent=2,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
