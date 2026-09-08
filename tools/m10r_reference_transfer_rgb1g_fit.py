#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageOps
import rawpy
from m10r_reference_order_fit import alignment_search,metadata_status
from m10r_reference_transfer_rgb_fit import crop_to_reference,metrics

MODES=("rec709_shared_linear","fw_component_shared_linear","fw_yc_preserve_chroma")

def load(p):
    with Image.open(p) as im:return np.asarray(im.convert('RGB'),dtype=np.uint8)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--jpg',type=Path,required=True);ap.add_argument('--dng',type=Path,required=True)
    ap.add_argument('--control',type=Path,required=True);ap.add_argument('--fw-shared',type=Path,required=True);ap.add_argument('--fw-yc-preserve',type=Path,required=True)
    ap.add_argument('--sample',required=True);ap.add_argument('--metadata-json',type=Path);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    with Image.open(a.jpg) as im:jpg=np.asarray(ImageOps.exif_transpose(im).convert('RGB'),dtype=np.uint8)
    r={MODES[0]:load(a.control),MODES[1]:load(a.fw_shared),MODES[2]:load(a.fw_yc_preserve)}
    if len({v.shape for v in r.values()})!=1:raise RuntimeError('geometry')
    with rawpy.imread(str(a.dng)) as x:
        z=x.postprocess(use_camera_wb=True,no_auto_bright=True,gamma=(1,1),output_bps=16,output_color=rawpy.ColorSpace.raw);white=float(x.white_level);flip=int(x.sizes.flip)
    proxy=z[...,1].astype(np.float32)*(white/65535.0);del z
    orient,scores=alignment_search(proxy,jpg);score,k,dx,dy=scores[0];rh,rw=orient.shape;jh,jw=jpg.shape[:2]
    c={n:crop_to_reference(v,k,dx,dy,rw,rh,jw,jh) for n,v in r.items()};h,w=next(iter(c.values())).shape[:2];ref=np.asarray(Image.fromarray(jpg).resize((w,h),Image.Resampling.LANCZOS),dtype=np.uint8)
    if h>12 and w>12:ref=ref[3:-3,3:-3];c={n:v[3:-3,3:-3] for n,v in c.items()}
    out={'sample':a.sample,'metadata':metadata_status(a.metadata_json),'fit_freedom':'NONE; scale 0.94 frozen; exact MEDIUM/DG; exact recovered Q12 YC matrix; inverse is mathematical only','matrix_q12':[1224,2403,469,-691,-1357,2048,2048,-1715,-333],
         'variants':{'rec709_shared_linear':'RGB1D winner','fw_component_shared_linear':'RGB1F component-Y with old shared-linear reconstruction','fw_yc_preserve_chroma':'encoded RGB -> exact YC; map Y only; preserve signed Cb/Cr; mathematical inverse to encoded RGB'},
         'alignment':{'score':float(score),'rot90_k':int(k),'dx':int(dx),'dy':int(dy),'rawpy_flip':flip,'raw_oriented':[rw,rh],'jpeg':[jw,jh]},'metrics':{n:metrics(v,ref) for n,v in c.items()}}
    a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');return 0
if __name__=='__main__':raise SystemExit(main())
