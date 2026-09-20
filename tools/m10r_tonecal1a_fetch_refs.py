#!/usr/bin/env python3
"""Fetch only published 07..10 test references with the existing audit curl recipe.
No fitting, scoring or renderer changes. Do not substitute different scenes on failure.
"""
from pathlib import Path
import hashlib,json,subprocess,sys
import numpy as np
import rawpy

def main():
    root=Path(sys.argv[1])/'fresh';root.mkdir(parents=True,exist_ok=True)
    rows=[]
    for sid in ['07','08','09','10']:
        paths=[];sources=[]
        for ext in ['jpg','dng']:
            url=f'https://img.photographyblog.com/reviews/leica_m10_r/sample_images/leica_m10_r_{sid}.{ext}'
            p=root/f'{sid}.{ext}';tmp=p.with_suffix('.partial')
            print('Published reference:',url,flush=True)
            subprocess.run(['curl','-L','--fail','--retry','2','--retry-delay','2','--max-time','120',url,'-o',str(tmp)],check=True)
            assert tmp.stat().st_size>100000,'Unexpectedly small original reference'
            tmp.replace(p);paths.append(p)
            sources.append({'url':url,'path':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
        meta=json.loads(subprocess.check_output(['exiftool','-j','-n',*map(str,paths)]))
        with rawpy.imread(str(paths[1])) as r:
            # The six retained input arrays use raw_image_visible. Require exact equivalence
            # before the new validator uses raw_image, rather than assuming missing margins.
            assert r.sizes.top_margin==0 and r.sizes.left_margin==0
            assert r.raw_image.shape==r.raw_image_visible.shape
            assert np.array_equal(r.raw_image,r.raw_image_visible)
            row={'id':sid,'sources':sources,'metadata':meta,'raw_sizes':str(r.sizes),'raw_image_equals_visible':True,'rawpy_version':rawpy.__version__}
        rows.append(row)
        (root/'provenance.json').write_text(json.dumps(rows,indent=2)+'\n')
    print('All four predeclared new reference pairs fetched; no test scores inspected or parameters fitted.',flush=True)
if __name__=='__main__':main()
