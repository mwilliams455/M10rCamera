#!/usr/bin/env python3
"""Score RGB1E shared-MEDIUM / component-wise-DG topology candidates.

No image-dependent fit is performed. The firmware-like scalar weights are the exact
pre-declared 1024/2661/410 triplet normalized by 4095. The baseline is the best
RGB1D OETF(linear-Y) code-ratio candidate at the already pre-declared 0.94 scale.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageOps
import rawpy
from m10r_reference_order_fit import alignment_search,metadata_status
from m10r_reference_transfer_rgb_fit import crop_to_reference,metrics

MODES=("baseline_oetfy_code_ratio","rec709_component_dg_identity","rec709_component_dg_oetf","fw_tone_component_dg_identity","fw_tone_component_dg_oetf")

def load(p:Path)->np.ndarray:
    with Image.open(p) as im:return np.asarray(im.convert("RGB"),dtype=np.uint8)

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("--jpg",type=Path,required=True);ap.add_argument("--dng",type=Path,required=True)
    ap.add_argument("--baseline",type=Path,required=True);ap.add_argument("--rec-id",type=Path,required=True);ap.add_argument("--rec-oetf",type=Path,required=True);ap.add_argument("--fw-id",type=Path,required=True);ap.add_argument("--fw-oetf",type=Path,required=True)
    ap.add_argument("--sample",required=True);ap.add_argument("--metadata-json",type=Path);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    with Image.open(a.jpg) as im:jpg=np.asarray(ImageOps.exif_transpose(im).convert("RGB"),dtype=np.uint8)
    renders={MODES[0]:load(a.baseline),MODES[1]:load(a.rec_id),MODES[2]:load(a.rec_oetf),MODES[3]:load(a.fw_id),MODES[4]:load(a.fw_oetf)}
    if len({v.shape for v in renders.values()})!=1:raise RuntimeError("RGB1E renderer geometries differ")
    with rawpy.imread(str(a.dng)) as r:
        z=r.postprocess(use_camera_wb=True,no_auto_bright=True,gamma=(1,1),output_bps=16,output_color=rawpy.ColorSpace.raw);white=float(r.white_level);flip=int(r.sizes.flip)
    proxy=z[...,1].astype(np.float32)*(white/65535.0);del z
    oriented,scores=alignment_search(proxy,jpg);score,k,dx,dy=scores[0];rh,rw=oriented.shape;jh,jw=jpg.shape[:2]
    cropped={n:crop_to_reference(v,k,dx,dy,rw,rh,jw,jh) for n,v in renders.items()}
    if len({v.shape for v in cropped.values()})!=1:raise RuntimeError("RGB1E crop geometries differ")
    h,w=next(iter(cropped.values())).shape[:2];ref=np.asarray(Image.fromarray(jpg).resize((w,h),Image.Resampling.LANCZOS),dtype=np.uint8)
    if h>12 and w>12:ref=ref[3:-3,3:-3];cropped={n:v[3:-3,3:-3] for n,v in cropped.items()}
    out={"sample":a.sample,"metadata":metadata_status(a.metadata_json),
         "fit_freedom":"NONE; all topology, weights and transfers declared before RGB1E",
         "working_space_boundary":"current reference ColorSpec -> linear sRGB; literal firmware B2Y RGB basis remains OPEN",
         "baseline":"OETF(linear Rec709 Y), scale 0.94 -> MEDIUM mapped coordinate -> scalar DG -> code-ratio shared gain on linear RGB -> sRGB OETF",
         "component_topology":"linear component 14-bit code * scalar-selected MEDIUM Q15 gain >>15 -> independent DG lookup per component",
         "weights":{"rec709":[0.2126,0.7152,0.0722],"firmware_tone_raw":[1024,2661,410],"firmware_tone_normalization":4095},
         "alignment":{"score":float(score),"rot90_k":int(k),"dx":int(dx),"dy":int(dy),"rawpy_flip":flip,"raw_oriented":[rw,rh],"jpeg":[jw,jh],"comparison":[int(ref.shape[1]),int(ref.shape[0])]},
         "metrics":{n:metrics(v,ref) for n,v in cropped.items()}}
    a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n");print(json.dumps(out,indent=2,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
