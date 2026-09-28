#!/usr/bin/env python3
"""AMAZE1A: additive interior reconstruction on pinned RENDER2M, no AE/look changes."""
from pathlib import Path
import hashlib,json,re,shutil,sys
HERE=Path(__file__).resolve().parent
from prepare_upstream import prepare
CPP_SHA='3f7b696cdf33e29348d7c0532f658c11819f9b8e54772b55753e357fb6018985'
JAVA='app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'
CMAKE='app/src/main/cpp/CMakeLists.txt'
GRADLE='app/build.gradle'
EXPECTED={JAVA:'c1da418c2be1efbdcd289b1df62a976143f98457ab578b455dad8d8e09e7de1c',
 CMAKE:'34ea39c898484be50378a7776ef1a5713f64ade1871967b159b6c52e3dfde93e',
 GRADLE:'9562d8e1f6c6ddac5ac0fa42990bdb553b214390bfa555e5916fafa610e61193'}
BEGIN='// AMAZE1A_INSERT_BEGIN\n'
END='// AMAZE1A_INSERT_END\n'
CMAKE_EXTRA='''
# AMAZE1A isolated source-reconstruction library; existing native targets untouched.
add_library(m10ramaze SHARED
    ${CMAKE_CURRENT_SOURCE_DIR}/amaze1a/jni.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/amaze1a/upstream/amaze_m10r_fix1.cc
    ${CMAKE_CURRENT_SOURCE_DIR}/amaze1a/upstream/border.cc
)
set_target_properties(m10ramaze PROPERTIES CXX_STANDARD 17 CXX_STANDARD_REQUIRED ON)
target_include_directories(m10ramaze PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/amaze1a/upstream/include)
target_compile_options(m10ramaze PRIVATE -O2 -fopenmp -ffp-contract=off -fno-fast-math)
target_link_options(m10ramaze PRIVATE -fopenmp -static-openmp -Wl,--exclude-libs,ALL)
'''
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inventory(root):
 return {str(p.relative_to(root)):sha(p) for p in (root/'app/src/main').rglob('*') if p.is_file()}
def insert(s,anchor,code,before=False):
 if s.count(anchor)!=1:raise RuntimeError('AMAZE1A anchor mismatch '+repr(anchor))
 block=BEGIN+code.rstrip()+'\n'+END
 return s.replace(anchor,block+anchor if before else anchor+block,1)
def strip(s):return re.sub(re.escape(BEGIN)+'.*?'+re.escape(END),'',s,flags=re.S)
def main(root,upstream):
 root=root.resolve();upstream=upstream.resolve()
 proofpath=root/'M10R_AMAZE1A_SOURCE_PROOF.json'
 if proofpath.exists():
  proof=json.loads(proofpath.read_text())
  assert inventory(root)==proof['after'],'AMAZE1A post-apply source drift'
  assert sha(root/GRADLE)==proof['gradleAfter'],'AMAZE1A gradle drift'
  print(json.dumps({'status':'already_applied_verified','schema':proof['schema']}));return
 for rel,digest in EXPECTED.items():
  if sha(root/rel)!=digest:raise RuntimeError('requires exact RENDER2M parent: '+rel)
 if sha(root/'app/src/main/cpp/m10rRender.cpp')!=CPP_SHA:raise RuntimeError('target renderer drift')
 provenance=json.loads((upstream/'PROVENANCE.json').read_text())
 for rel,digest in provenance['files'].items():
  if sha(upstream/rel)!=digest:raise RuntimeError('upstream provenance mismatch '+rel)
 if sha(upstream/'amaze.cc')!='a43f01c7ffe70efdf92dec473d5a785658c11756365d78df617d7a4c28117f1e':
  raise RuntimeError('wrong AMaZE source')
 for rel in ['app/src/main/cpp/amaze1a',JAVA.replace('M10RNativeRenderer.java','M10RAmaze1A.java'),'app/src/main/assets/amaze1a']:
  if (root/rel).exists():raise RuntimeError('unexpected existing candidate path '+rel)
 before=inventory(root);old=(root/JAVA).read_text();s=old
 s=insert(s,'        Bitmap bitmap = null;\n',
 '        M10RAmaze1A amaze = null;\n        long amazeInitNs = 0L, amazeBandsNs = 0L;')
 s=insert(s,'            final int rotation = ((cameraRotation % 360) + 360) % 360;\n',
 '''            long amazeStartNs = System.nanoTime();
            amaze = M10RAmaze1A.open(normalized.data, frame.width, frame.height,
                    cfa, normalized.storageScale, captureResult, d);
            amazeInitNs = System.nanoTime() - amazeStartNs;''',before=True)
 s=insert(s,'                tileBgr.get(centralRow, 0, bgr);\n',
 '''                long amazeBandStartNs = System.nanoTime();
                amaze.readBand(y0, rows, bgr);
                amazeBandsNs += System.nanoTime() - amazeBandStartNs;''')
 s=insert(s,'            d.put("renderStabilityFix", "STABILITY3_NATIVE1_FOUR_THREAD_PIXEL_CORE");\n',
 '''            amaze.close();
            amaze = null;
            d.put("amazeInitMs", amazeInitNs / 1_000_000.0);
            d.put("amazeBandsMs", amazeBandsNs / 1_000_000.0);''',before=True)
 s=insert(s,'            if (tileRaw != null) tileRaw.release();\n',
 '            if (amaze != null) amaze.close();',before=True)
 if strip(s)!=old:raise RuntimeError('nonadditive Java change')
 # Prepare all edits before mutating the assembled tree.
 changed={JAVA,CMAKE,GRADLE}
 (root/JAVA).write_text(s)
 (root/CMAKE).write_text((root/CMAKE).read_text()+CMAKE_EXTRA)
 (root/GRADLE).write_text((root/GRADLE).read_text().replace(
  "versionName '0.97-m10r2m-meterarea1a'","versionName '0.97-m10r2n-amaze1a-fix1'"))
 dest=root/'app/src/main/cpp/amaze1a';dest.mkdir()
 for name in ['session.h','jni.cpp']:shutil.copyfile(HERE/name,dest/name)
 upstreamFix=prepare(upstream,dest/'upstream')
 shutil.copyfile(HERE/'M10RAmaze1A.java',root/JAVA.replace('M10RNativeRenderer.java','M10RAmaze1A.java'))
 notices=root/'app/src/main/assets/amaze1a';notices.mkdir(parents=True)
 for name in ['LICENSE.txt','PROVENANCE.json']:shutil.copyfile(upstream/name,notices/name)
 shutil.copyfile(dest/'upstream/M10R_FIX1_PROVENANCE.json',notices/'M10R_FIX1_PROVENANCE.json')
 after=inventory(root)
 modified={p for p in before if after.get(p)!=before[p]}
 if modified!={JAVA,CMAKE}:raise RuntimeError('unexpected changed existing source '+repr(modified))
 if sha(root/'app/src/main/cpp/m10rRender.cpp')!=CPP_SHA:raise RuntimeError('target renderer changed')
 proof={'schema':'M10R_RENDER2N_AMAZE1A_SOURCE_ONLY_FIX1_V1',
  'baselineCommit':'42d13b16b787474eb88a9c4c1bdfa035ba4ab3e7',
  'before':before,'after':after,'gradleAfter':sha(root/GRADLE),
  'changedExistingFiles':sorted(changed),'rendererInsertionRemovalExact':True,
  'nativeTargetRendererUnchanged':True,'allExistingAssetsUnchanged':True,
  'exposureCaptureDngAndPreviewSourcesUnchanged':True,
  'shortTailReflectionFixed':True,'extraScratchRows':16,
  'tileScratchInitializationFixed':True,'upstreamFix':upstreamFix,
  'noiseCorrection':False,'directionalChroma':False,'hdr':False,
  'border':'existing_OpenCV_EA_16_pixels','cropOriginAssumptionChanged':False,
  'sameRawPhotographicReplayPerformed':False,'phoneValidated':False,
  'vendorReferenceCommit':'a00e722bf25b4c609ae9addcc4b612e6d8e434d6',
  'upstream':provenance,'nativeTargetRendererSha256':CPP_SHA}
 proofpath.write_text(json.dumps(proof,indent=2)+'\n')
 print(json.dumps({k:v for k,v in proof.items() if k not in ['before','after','upstream']},indent=2))
if __name__=='__main__':main(Path(sys.argv[1]),Path(sys.argv[2]))
