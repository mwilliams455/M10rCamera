#!/usr/bin/env python3
"""Verify pristine AMaZE and generate an explicitly attributed scratch-init fix."""
from pathlib import Path
import hashlib,json,shutil
ORIGINAL_SHA='a43f01c7ffe70efdf92dec473d5a785658c11756365d78df617d7a4c28117f1e'
FIXED_SHA='45029460a01972d9c4fd88b98c7b6c4715c7b54213ef1c22776f1b407a7a45ca'
ANCHOR='                for (int left = winx - 16; left < winx + width; left += ts - 32) {\n'
INSERT='''                    // M10R SCRATCH1A: each independent tile starts from the
                    // same initialized workspace, regardless of worker history.
                    memset(buffer, 0, 14 * sizeof(float) * ts * ts + sizeof(char) * ts * tsh + 18 * cldf * 64 + 63);
'''
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def prepare(source:Path,destination:Path):
    source=source.resolve();destination=destination.resolve()
    if source==destination:raise ValueError('refusing to modify pristine dependency tree')
    provenance=json.loads((source/'PROVENANCE.json').read_text())
    for name,digest in provenance['files'].items():
        if sha(source/name)!=digest:raise ValueError('upstream hash mismatch: '+name)
    if sha(source/'amaze.cc')!=ORIGINAL_SHA:raise ValueError('wrong pinned AMaZE')
    old=(source/'amaze.cc').read_text()
    if old.count(ANCHOR)!=1:raise ValueError('scratch initialization anchor mismatch')
    fixed=old.replace(ANCHOR,ANCHOR+INSERT,1)
    if hashlib.sha256(fixed.encode()).hexdigest()!=FIXED_SHA:
        raise ValueError('unexpected generated AMaZE source')
    destination.mkdir(parents=True,exist_ok=True)
    for name in list(provenance['files'])+['PROVENANCE.json']:
        out=destination/name;out.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source/name,out)
    (destination/'amaze_m10r_fix1.cc').write_text(fixed)
    proof={'revision':'M10R_AMAZE1A_FIX1_TAIL1A_SCRATCH1A',
           'originalAmazeSha256':ORIGINAL_SHA,'compiledAmazeSha256':FIXED_SHA,
           'pristineUpstreamRetained':True,'modifiedUpstreamInitialization':True,
           'modification':'zero private per-worker workspace at every independent tile entry',
           'filterOrColourEquationAdded':False,'firmwareDerivedFix':False}
    (destination/'M10R_FIX1_PROVENANCE.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof
