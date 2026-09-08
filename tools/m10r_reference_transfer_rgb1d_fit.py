#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageOps
import rawpy
from m10r_reference_order_fit import alignment_search,metadata_status
from m10r_reference_transfer_rgb_fit import crop_to_reference,metrics
MODES=("ll_oetf","component_code_ratio","oetfy_code_ratio","component_linear_target","oetfy_linear_target")
def load(p):
 with Image.open(p) as im:return np.asarray(im.convert('RGB'),dtype=np.uint8)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--jpg',type=Path,required=True);ap.add_argument('--dng',type=Path,required=True)
 for n in ('ll-oetf','component-code-ratio','oetfy-code-ratio','component-linear-target','oetfy-linear-target'):ap.add_argument('--'+n,type=Path,required=True)
 ap.add_argument('--sample',required=True);ap.add_argument('--metadata-json',type=Path);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 with Image.open(a.jpg) as im:jpg=np.asarray(ImageOps.exif_transpose(im).convert('RGB'),dtype=np.uint8)
 r={MODES[0]:load(a.ll_oetf),MODES[1]:load(a.component_code_ratio),MODES[2]:load(a.oetfy_code_ratio),MODES[3]:load(a.component_linear_target),MODES[4]:load(a.oetfy_linear_target)}
 if len({v.shape for v in r.values()})!=1:raise RuntimeError('geometry')
 with rawpy.imread(str(a.dng)) as x:
  z=x.postprocess(use_camera_wb=True,no_auto_bright=True,gamma=(1,1),output_bps=16,output_color=rawpy.ColorSpace.raw);white=float(x.white_level);flip=int(x.sizes.flip)
 proxy=z[...,1].astype(np.float32)*(white/65535.0);del z;orient,scores=alignment_search(proxy,jpg);score,k,dx,dy=scores[0];rh,rw=orient.shape;jh,jw=jpg.shape[:2]
 c={n:crop_to_reference(v,k,dx,dy,rw,rh,jw,jh) for n,v in r.items()};h,w=next(iter(c.values())).shape[:2];ref=np.asarray(Image.fromarray(jpg).resize((w,h),Image.Resampling.LANCZOS),dtype=np.uint8)
 if h>12 and w>12:ref=ref[3:-3,3:-3];c={n:v[3:-3,3:-3] for n,v in c.items()}
 out={'sample':a.sample,'metadata':metadata_status(a.metadata_json),'fit_freedom':'NONE; coordinate scale frozen 0.94 before RGB1D','factorial':{'encoded_input':['component_encoded_Y','OETF_of_linear_Y'],'mapped_interpretation':['code_ratio_on_linear_RGB','EOTF_mapped_to_linear_target_Y']},'alignment':{'score':float(score),'rot90_k':int(k),'dx':int(dx),'dy':int(dy),'rawpy_flip':flip,'raw_oriented':[rw,rh],'jpeg':[jw,jh]},'metrics':{n:metrics(v,ref) for n,v in c.items()}}
 a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');return 0
if __name__=='__main__':raise SystemExit(main())
