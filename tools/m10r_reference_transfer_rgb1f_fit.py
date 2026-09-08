#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps
import rawpy
from m10r_reference_order_fit import alignment_search, metadata_status
from m10r_reference_transfer_rgb_fit import crop_to_reference, metrics

MODES=("rec709_oetfy","fw601_oetfy","fw601_component_y")

def load(p: Path):
    with Image.open(p) as im:
        return np.asarray(im.convert("RGB"), dtype=np.uint8)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--jpg", type=Path, required=True)
    ap.add_argument("--dng", type=Path, required=True)
    ap.add_argument("--rec709-oetfy", type=Path, required=True)
    ap.add_argument("--fw601-oetfy", type=Path, required=True)
    ap.add_argument("--fw601-component-y", type=Path, required=True)
    ap.add_argument("--sample", required=True)
    ap.add_argument("--metadata-json", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    a=ap.parse_args()

    with Image.open(a.jpg) as im:
        jpg=np.asarray(ImageOps.exif_transpose(im).convert("RGB"), dtype=np.uint8)
    rendered={
        "rec709_oetfy": load(a.rec709_oetfy),
        "fw601_oetfy": load(a.fw601_oetfy),
        "fw601_component_y": load(a.fw601_component_y),
    }
    if len({v.shape for v in rendered.values()}) != 1:
        raise RuntimeError("RGB1F rendered geometry differs across variants")

    with rawpy.imread(str(a.dng)) as x:
        z=x.postprocess(use_camera_wb=True, no_auto_bright=True, gamma=(1,1), output_bps=16, output_color=rawpy.ColorSpace.raw)
        white=float(x.white_level)
        flip=int(x.sizes.flip)
    proxy=z[...,1].astype(np.float32)*(white/65535.0)
    del z
    orient,scores=alignment_search(proxy,jpg)
    score,k,dx,dy=scores[0]
    rh,rw=orient.shape
    jh,jw=jpg.shape[:2]
    crops={n:crop_to_reference(v,k,dx,dy,rw,rh,jw,jh) for n,v in rendered.items()}
    h,w=next(iter(crops.values())).shape[:2]
    ref=np.asarray(Image.fromarray(jpg).resize((w,h),Image.Resampling.LANCZOS),dtype=np.uint8)
    if h>12 and w>12:
        ref=ref[3:-3,3:-3]
        crops={n:v[3:-3,3:-3] for n,v in crops.items()}

    out={
        "sample":a.sample,
        "metadata":metadata_status(a.metadata_json),
        "fit_freedom":"NONE; coordinate scale frozen 0.94 from prior evidence; exact MEDIUM/DG; only Y definition varies",
        "firmware_y_row_q12":{"r":1224,"g":2403,"b":469,"den":4096},
        "variants":{
            "rec709_oetfy":"OETF(0.2126 Rlin + 0.7152 Glin + 0.0722 Blin)",
            "fw601_oetfy":"OETF((1224 Rlin + 2403 Glin + 469 Blin)/4096)",
            "fw601_component_y":"(1224 OETF(Rlin) + 2403 OETF(Glin) + 469 OETF(Blin))/4096",
        },
        "alignment":{"score":float(score),"rot90_k":int(k),"dx":int(dx),"dy":int(dy),"rawpy_flip":flip,"raw_oriented":[rw,rh],"jpeg":[jw,jh]},
        "metrics":{n:metrics(v,ref) for n,v in crops.items()},
    }
    a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
