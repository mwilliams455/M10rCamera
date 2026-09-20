#!/usr/bin/env python3
"""PHOTOAUDIT1B validation supervisor for the retained native PHOTOAUDIT1A.
The native C++ is unchanged. Explicit harness overrides: OpenCV version guard,
CFA fixture, expanded/fixed registration, and scoring the actual corrected RGB
pixels rather than correcting a patch mean. No photographic app changes.
"""
from pathlib import Path
import json, sys, hashlib, shutil
import numpy as np
import cv2
from PIL import Image, ImageDraw
import m10r_photoaudit_measure1a as audit

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    if not __debug__: raise RuntimeError('Assertions must be enabled')
    inputs,out=map(Path,sys.argv[1:]);out.mkdir(parents=True,exist_ok=True)
    assert cv2.__version__=='4.13.0',cv2.__version__
    bayer=np.empty((32,32),np.uint16)
    bayer[0::2,0::2]=20000;bayer[0::2,1::2]=30000
    bayer[1::2,0::2]=10000;bayer[1::2,1::2]=20000
    fixture=cv2.cvtColor(bayer,cv2.COLOR_BayerGB2BGR_EA)
    assert np.all(fixture[4:-4,4:-4]==np.array([10000,20000,30000]))
    original_patch_values=audit.patch_values
    entries=[];entry_by_a={};alignment_state={'calls':0,'fixed':None}

    def aligned(a,b):
        h,w=a.shape[:2]
        if alignment_state['calls']%2==0:
            ga=cv2.GaussianBlur(a.astype(np.float32).mean(2),(0,0),2)
            ga-=cv2.GaussianBlur(ga,(0,0),12)
            template=np.ascontiguousarray(ga[16:-16,16:-16])
            best=None
            for k in range(4):
                rb=np.rot90(b,k).copy()
                if rb.shape[:2]!=(h,w):continue
                gb=cv2.GaussianBlur(rb.astype(np.float32).mean(2),(0,0),2)
                gb-=cv2.GaussianBlur(gb,(0,0),12)
                search=np.ascontiguousarray(gb[10:h-10,10:w-10])
                match=cv2.matchTemplate(search,template,cv2.TM_CCORR_NORMED)
                assert match.shape==(13,13),match.shape
                _,score,_,location=cv2.minMaxLoc(match)
                dx,dy=location[0]-6,location[1]-6
                if best is None or score>best[0]:best=(score,k,dx,dy)
            if best is None:raise ValueError('orientation match failed')
            alignment_state['fixed']=best
        else:
            best=alignment_state['fixed']
        alignment_state['calls']+=1
        score,k,dx,dy=best;rb=np.rot90(b,k).copy();margin=16
        assert score>.75
        info={'gradient_correlation':score,'reference_rot90_k':k,'dx_sample_pixels':dx,'dy_sample_pixels':dy,
          'margin_sample_pixels':margin,'search_radius_sample_pixels':6,
          'fixed_across_normalization_conditions':True,'best_on_search_boundary':abs(dx)==6 or abs(dy)==6}
        return a[margin:h-margin,margin:w-margin],rb[margin+dy:h-margin+dy,margin+dx:w-margin+dx],info

    def patches(aa,bb):
        a,b,ps=original_patch_values(aa,bb)
        e={'a':a,'b':b,'aa':aa,'bb':bb}
        entry_by_a[id(a)]=e;entries.append(e)
        return a,b,ps

    def score_actual_pixels(a,xp,yp):
        e=entry_by_a[id(a)];aa,bb=e['aa'],e['bb']
        L=audit.lab(aa.reshape(-1,3)/255.)
        L[:,0]=np.interp(L[:,0],xp,yp)
        rgb=np.floor(np.clip(audit.invlab(L),0,1)*255+.5).astype(np.uint8).reshape(aa.shape)
        ca,rb,ps=original_patch_values(rgb,bb)
        assert np.array_equal(rb,e['b']) and ps['selected']==len(a)
        e['candidate']=rgb;e['candidate_patches']=ca
        return ca

    audit.align=aligned;audit.patch_values=patches;audit.corrected_lab=score_actual_pixels
    audit.main()
    result=json.loads((out/'results.json').read_text())
    assert len(entries)==12 and alignment_state['calls']==12
    result['status']='PASS_PHOTOAUDIT1B_ACTUAL_RGB_PIXELS'
    result['validation_supervisor_sha256']=sha(__file__)
    result['validation']={'cfa_fixture':'GBRG CFA -> RGB channels [10000,20000,30000] exact interior',
      'candidate_scoring':'Pixelwise L* correction -> bounded RGB -> round to uint8 -> patch RGB means -> Lab -> errors',
      'registration':'Reference registration solved on target_native then reused unchanged by normalization control and tone candidate; 6-sample-pixel search radius',
      'center_region':'Central half-width by half-height of aligned common raster; same global fitted curve, no refit',
      'old_measurement_superseded':'PHOTOAUDIT1A initial correction-of-patch-mean scores are superseded by actual-RGB-pixel scores',
      'baseline_original_cpp_sha256':result['native']['full_cpp_sha256']}
    assert result['native']['full_cpp_sha256']=='27d42e3090435732bba6331380d2110227d3b713f59d3917b659d19cbea0f934'

    def colour(a,b):
        ca=np.linalg.norm(a[:,1:],axis=1);cb=np.linalg.norm(b[:,1:],axis=1)
        mask=(cb>=20)&(ca>=5)
        if not mask.any():return {'n':0}
        delta=(np.degrees(np.arctan2(a[:,2],a[:,1])-np.arctan2(b[:,2],b[:,1]))+180)%360-180
        return {'n':int(mask.sum()),'median_absolute_hue_error_degrees':float(np.median(abs(delta[mask]))),
          'median_signed_hue_error_degrees':float(np.median(delta[mask])),
          'median_chroma_ratio_renderer_to_reference':float(np.median(ca[mask]/cb[mask]))}

    lookup={};i=0
    for scene in result['scenes']:
        for mode,rec in scene['conditions'].items():
            e=entries[i];i+=1;sid=scene['id'];lookup[(sid,mode)]=e
            aa,bb,cc=e['aa'],e['bb'],e['candidate'];h,w=aa.shape[:2]
            ys=slice(h//4,3*h//4);xs=slice(w//4,3*w//4)
            a,b,ps=original_patch_values(aa[ys,xs],bb[ys,xs]);c,b2,ps2=original_patch_values(cc[ys,xs],bb[ys,xs])
            assert np.array_equal(b,b2) and ps==ps2
            rec['central_region']={'patches':ps,'baseline':audit.groups(a,b),'tone_only_diagnostic':audit.groups(c,b)}
            rec['colour_residual']=colour(e['a'],e['b'])
            rec['central_colour_residual']=colour(a,b)
            rec['published_code_clip_fraction']={'baseline':{'low_rgb':(aa==0).mean((0,1)).tolist(),'high_rgb':(aa==255).mean((0,1)).tolist()},
               'reference':{'low_rgb':(bb==0).mean((0,1)).tolist(),'high_rgb':(bb==255).mean((0,1)).tolist()},
               'tone_diagnostic':{'low_rgb':(cc==0).mean((0,1)).tolist(),'high_rgb':(cc==255).mean((0,1)).tolist()}}
            Image.fromarray(aa).save(out/f'{sid}_{mode}_baseline.png')
            Image.fromarray(cc).save(out/f'{sid}_{mode}_tone_diagnostic.png')
            if mode=='target_native':Image.fromarray(bb).save(out/f'{sid}_reference.png')
    for mode,summary in result['tone_diagnostic'].items():
        test=[s['conditions'][mode]['central_region'] for s in result['scenes'] if s['id'] in audit.TEST]
        summary['central_heldout']={
          'baseline_L_mae':float(np.mean([r['baseline']['all']['L_mae'] for r in test])),
          'candidate_L_mae':float(np.mean([r['tone_only_diagnostic']['all']['L_mae'] for r in test])),
          'L_wins':sum(r['tone_only_diagnostic']['all']['L_mae']<r['baseline']['all']['L_mae'] for r in test),
          'baseline_ab_error':float(np.mean([r['baseline']['all']['ab_error_mean'] for r in test])),
          'candidate_ab_error':float(np.mean([r['tone_only_diagnostic']['all']['ab_error_mean'] for r in test]))}
    result['limitations']=[s.replace('Centre-region sensitivity must be checked before target attribution.','Central-half-area sensitivity is separately reported, not proof of complete lens-correction equivalence.') for s in result['limitations']]
    result['limitations']+=['OpenCV 4.13.0 is pinned to the Android baseline major/minor version, but host and Android binaries are not identical.',
      'Pixel RGB comparisons use the same declared sRGB interpretation. No calibrated scene-colour ground truth or complete ICC-profile validation is claimed.',
      'No independent local execution was possible in this chat runtime; these are CI execution results.']

    # Compact comparison board is only a viewing aid; metrics use uncompressed uint8 rasters.
    board=Image.new('RGB',(1200,1010),'white');draw=ImageDraw.Draw(board)
    draw.text((10,8),'Held-out references: camera JPEG | frozen native core | tone-only diagnostic',fill='black')
    for row,sid in enumerate(sorted(audit.TEST)):
        e=lookup[(sid,'target_native')]
        for col,(name,data) in enumerate([('Leica reference',e['bb']),('Baseline',e['aa']),('Tone diagnostic',e['candidate'])]):
            im=Image.fromarray(data);im.thumbnail((390,280))
            x=col*400+5;y=row*325+35
            draw.text((x,y),sid+' / '+name,fill='black');board.paste(im,(x,y+20))
    draw.text((10,1000),'Reference images: Photography Blog. Diagnostic only, not promoted.',fill='black')
    board.save(out/'PHOTOAUDIT1B_HELDOUT_COMPARISON.jpg',quality=95)
    report=(out/'REPORT.md').read_text().replace('PHOTOAUDIT1A','PHOTOAUDIT1B')
    report=report.replace('The correction changes L* only before an explicit RGB gamut conversion.',
      'The correction is applied to every original output pixel, converted to bounded RGB and rounded to uint8; those actual corrected pixels are then measured with the unchanged reference patch mask.')
    report=report.replace('Centre-region sensitivity must be checked before target attribution.','Central-region sensitivity is reported below.')
    report+='\n\n## Actual-pixel validation and central-crop sensitivity\n\n'
    report+='The original native function is unchanged. OpenCV 4.13.0 is pinned; a distinct-RGB constant-CFA fixture passes. Registration is shared across all conditions and candidates. Initial correction-of-patch-mean scores from PHOTOAUDIT1A are superseded. No firmware clipping candidate was inserted.\n\n'
    report+='| Held-out scene | Baseline L* MAE | Tone diagnostic L* MAE | Central baseline L* MAE | Central diagnostic L* MAE | Chromatic hue error (degrees) | Chroma ratio |\n|---|---:|---:|---:|---:|---:|---:|\n'
    for s in result['scenes']:
        if s['id'] not in audit.TEST:continue
        r=s['conditions']['target_native'];cc=r['central_region'];c=r['colour_residual']
        report+=f"| {s['id']} | {r['baseline']['all']['L_mae']:.3f} | {r['tone_only_diagnostic']['all']['L_mae']:.3f} | {cc['baseline']['all']['L_mae']:.3f} | {cc['tone_only_diagnostic']['all']['L_mae']:.3f} | {c.get('median_absolute_hue_error_degrees',float('nan')):.2f} | {c.get('median_chroma_ratio_renderer_to_reference',float('nan')):.3f} |\n"
    report+='\nThe colour columns describe baseline chromatic patches (reference C* >=20, rendered C* >=5). Ratio <1 means lower chroma, not necessarily a correctable global saturation deficit.\n'
    report+='\n## Validation metadata\n\n```json\n'+json.dumps({'validation':result['validation'],'tone_diagnostic':result['tone_diagnostic']},indent=2)+'\n```\n'
    (out/'REPORT.md').write_text(report)
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    # Repair the initial manifest ordering: scratch must be removed BEFORE manifest enumeration.
    shutil.rmtree(out/'scratch',ignore_errors=True)
    for f in out.rglob('*.class'):f.unlink()
    (out/'libaudit.so').unlink(missing_ok=True)
    (out/'manifest.json').unlink(missing_ok=True)
    manifest=[{'path':str(p.relative_to(out)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(out.rglob('*')) if p.is_file() and p.name!='stdout.txt']
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    for item in manifest:
        f=out/item['path'];assert f.is_file() and f.stat().st_size==item['bytes'] and sha(f)==item['sha256']
    print('PHOTOAUDIT1B ACTUAL RGB SCORING AND MANIFEST VERIFIED',flush=True)
    print(json.dumps(result['tone_diagnostic'],indent=2))
if __name__=='__main__':main()
