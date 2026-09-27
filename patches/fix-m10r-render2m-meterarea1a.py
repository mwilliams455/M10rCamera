#!/usr/bin/env python3
"""RENDER2M METERAREA1A shadow probe on exact SOURCEPROXY1C.

Only insert diagnostic statements. Do not change the sparse live input, source
coefficients, MFM rules, exposure allocator, rendering arithmetic or DNG saver.
Every changed Java file must reconstruct byte-for-byte when insertion blocks are
removed. Preserve all other existing Java/native/asset files byte-for-byte.
"""
from pathlib import Path
import hashlib,json,re,sys

CPP_SHA='3f7b696cdf33e29348d7c0532f658c11819f9b8e54772b55753e357fb6018985'
BEGIN='// METERAREA1A_INSERT_BEGIN\n'
END='// METERAREA1A_INSERT_END\n'

def insert(s,anchor,code,before=False):
    if s.count(anchor)!=1:
        raise RuntimeError('expected unique anchor: '+anchor[:160]+' count='+str(s.count(anchor)))
    block=BEGIN+code.rstrip()+'\n'+END
    return s.replace(anchor,block+anchor if before else anchor+block,1)

def strip(s):
    return re.sub(re.escape(BEGIN)+'.*?'+re.escape(END),'',s,flags=re.S)

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    root=Path(sys.argv[1]).resolve(); repo=Path(__file__).resolve().parents[1]
    java=root/'app/src/main/java/com/particlesdevs/photoncamera'
    renderer=java/'m10r/M10RNativeRenderer.java'
    mainr=java/'ui/camera/views/viewfinder/MainRenderer.java'
    capture=java/'capture/CaptureController.java'
    gradle=root/'app/build.gradle'
    cpp=root/'app/src/main/cpp/m10rRender.cpp'
    if sha(cpp)!=CPP_SHA: raise RuntimeError('native baseline changed')
    if "versionName '0.97-m10r2l-mfm1d-sourceproxy1c'" not in gradle.read_text():
        raise RuntimeError('requires exact RENDER2L version')
    allfiles=[p for directory in ['app/src/main/java','app/src/main/cpp','app/src/main/assets']
              for p in (root/directory).rglob('*') if p.is_file()]
    baseline={str(p.relative_to(root)):sha(p) for p in allfiles}
    originals={p:p.read_text() for p in [renderer,mainr,capture]}
    helper='com.particlesdevs.photoncamera.m10r.M10RMeterArea1A'

    s=originals[mainr]
    s=insert(s,'    private int[] hTex;\n',
        '    private final '+helper+'.GlSampler meterAreaSampler = new '+helper+'.GlSampler();')
    s=insert(s,'        initM10rMeterFbo();\n','        meterAreaSampler.reset();')
    s=insert(s,'                    codeWhole, codeIntegral, linearWhole, linearIntegral, linearGrid);\n',
        '            meterAreaSampler.sample(mSTexture, M10RLiveMeterState.snapshot());')
    mainr.write_text(s)

    s=originals[capture]
    s=insert(s,'            mPreviewCaptureRequest = request;\n',
        '            '+helper+'.observePreview(result, mCameraCharacteristics, physicalID, logicalID, mPreviewSize);')
    s=insert(s,'            M10RLiveMeterState.freezeCapture();\n',
        '            '+helper+'.freeze();')
    capture.write_text(s)

    s=originals[renderer]
    s=insert(s,'        d.put("schema", SCHEMA);\n',
        '        final M10RMeterArea1A.Bound meterAreaBound = M10RMeterArea1A.bind();')
    s=insert(s,'        long whiteClipCount = 0L;\n','''
        // Separate CFA-aware references; leave the legacy raw counterfactual unchanged.
        double[] meterAreaPreSum = new double[352];
        double[] meterAreaPostSum = new double[352];
        double[] meterAreaGainSum = new double[352];
        long[] meterAreaCounts = new long[352];
''')
    s=insert(s,'                out[i] = (short)Math.round(stored * 65535.0);\n','''
                // The top-left 2x2 in every 8x8 tile contains both green parities
                // for all four conventional Bayer arrangements, not just RGGB.
                int meterAreaChannel = siteToGainChannel[site];
                if ((meterAreaChannel == 1 || meterAreaChannel == 2)
                        && (x & 7) < 2 && (y & 7) < 2) {
                    int mr = Math.min(15, (int)((long)y * 16 / height));
                    int mc = Math.min(21, (int)((long)x * 22 / width));
                    int mi = mr * 22 + mc;
                    meterAreaPreSum[mi] += unit;
                    meterAreaPostSum[mi] += unit * gain;
                    meterAreaGainSum[mi] += gain;
                    meterAreaCounts[mi]++;
                }
''')
    s=insert(s,'        d.put("m10rAe1A_rawMeterProbe", ae1aProbe);\n','''
        try {
            double[] pre = new double[352], post = new double[352], gains = new double[352];
            for (int mi=0; mi<352; mi++) {
                long n=meterAreaCounts[mi];
                pre[mi]=n>0?meterAreaPreSum[mi]/n:0;
                post[mi]=n>0?meterAreaPostSum[mi]/n:0;
                gains[mi]=n>0?meterAreaGainSum[mi]/n:1;
            }
            JSONObject areaRaw=new JSONObject().put("diagnosticOnly",true).put("affectsPixels",false)
                    .put("sampling","two_CFA_resolved_green_sites_per_8x8_tile")
                    .put("coordinate","existing_renderer_full_raw_normalized_coordinates")
                    .put("mapCoordinateCorrectnessIndependentlyVerified",false)
                    .put("postShadingDomain","unit_times_render_gain_before_storageScale_no_extra_clip")
                    .put("legacyGreenSamplingCompatible",cfa==0 || cfa==3)
                    .put("greenPreShadingGrid16x22",M10RMeterArea1A.grid(pre))
                    .put("greenPostShadingGrid16x22",M10RMeterArea1A.grid(post))
                    .put("meanGreenGainGrid16x22",M10RMeterArea1A.grid(gains))
                    .put("sampleCountsRowMajor",new JSONArray(meterAreaCounts))
                    .put("preShadingDecision",M10RMeterArea1A.decision(pre))
                    .put("postShadingDecision",M10RMeterArea1A.decision(post));
            d.put("m10rMeterAreaRaw1A",areaRaw);
        } catch(Exception areaRawError) {
            d.put("m10rMeterAreaRaw1A",new JSONObject().put("diagnosticOnly",true)
                    .put("status","telemetry_failed").put("error",areaRawError.toString()));
        }
''')
    s=insert(s,'            d.put("status", "success");\n',
        '            M10RMeterArea1A.append(d, meterAreaBound, characteristics, captureResult, captureRequest);',before=True)
    renderer.write_text(s)

    for p,old in originals.items():
        if strip(p.read_text())!=old: raise RuntimeError('non-additive change in '+str(p))
    for name in ['M10RMeterAreaMath.java','M10RMeterArea1A.java']:
        text=(repo/'android/meterarea1a'/name).read_text()
        # Android JSONArray(Object) declares checked JSONException.
        text=text.replace('private static JSONArray rect(Rect r) {',
                          'private static JSONArray rect(Rect r) throws Exception {')
        # Keep the old grid clearly labelled; authoritative new probe is CFA-aware.
        text=text.replace('o.put("rawPreShadingDecision",decision(readGrid(raw.optJSONArray("leicaRawGrid16x22"))))',
                          'o.put("legacyRawPreShadingDecision",decision(readGrid(raw.optJSONArray("leicaRawGrid16x22"))))')
        text=text.replace('if(post!=null) o.put("rawPostShadingDecision",decision(readGrid(post.optJSONArray("greenPostShadingGrid16x22"))));',
                          'if(post!=null) { o.put("rawPreShadingDecision",decision(readGrid(post.optJSONArray("greenPreShadingGrid16x22")))); o.put("rawPostShadingDecision",decision(readGrid(post.optJSONArray("greenPostShadingGrid16x22")))); o.put("legacyRawGreenSamplingCompatible",post.optBoolean("legacyGreenSamplingCompatible",false)); }')
        (java/'m10r'/name).write_text(text)
    newversion='0.97-m10r2m-meterarea1a'
    gradle.write_text(gradle.read_text().replace('0.97-m10r2l-mfm1d-sourceproxy1c',newversion))
    modified={str(p.relative_to(root)) for p in originals}
    frozen={rel:digest for rel,digest in baseline.items() if rel not in modified}
    for rel,digest in frozen.items():
        if sha(root/rel)!=digest: raise RuntimeError('frozen source/asset changed: '+rel)
    iso=java/'processing/parameters/IsoExpoSelector.java'
    if 'M10RMeterArea' in iso.read_text(): raise RuntimeError('diagnostic wired into active AE')
    if sha(cpp)!=CPP_SHA: raise RuntimeError('native renderer modified')
    proof={
        'schema':'RENDER2M_METERAREA1A_SHADOW_V1','versionName':newversion,
        'baselineCommit':'50705cde49e1f0318dce716970f5929ebbe9df1a',
        'nativeRendererSha256':CPP_SHA,'frozenFilesUnchanged':True,
        'frozenFileCount':len(frozen),'frozenFiles':frozen,
        'modifiedExistingJavaInsertionsOnly':True,
        'insertionRemovalRestoresExactBaseline':True,
        'activeExposureSelectorUnchanged':True,'sharedMfmDecisionUnchanged':True,
        'sourceproxy1cUnchanged':True,'nativeSourceAndAssetsUnchanged':True,
        'dngSaverUnchanged':True,'existingRawAndJpegPixelStatementsUnchanged':True,
        'diagnosticUsesSeparate64SamplesPerCell':True,
        'areaIsStratifiedApproximationNotExactFullResolutionAverage':True,
        'rawProbeResolvesBothGreenSitesAllFourBayerPatterns':True,
        'legacyRawCounterfactualUnchangedAndCfaCompatibilityFlagged':True,
        'frameMetadataRequiresExactParentTimestampMatch':True,
        'cropParityClaimed':False,'previewRawTransferParityClaimed':False,
        'phoneGpuValidated':False,'sameRawPhotographicReplayPerformed':False,
        'diagnosticMayAddPreviewCpuGpuLatency':True,
        'newPrivateCaptureDataCommitted':False,'productionPromoted':False,
        'hdrEnabled':False,'singleRaw':True,
    }
    (root/'M10R_RENDER2M_METERAREA1A_PROVENANCE.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({k:v for k,v in proof.items() if k!='frozenFiles'},indent=2))
if __name__=='__main__':main()
