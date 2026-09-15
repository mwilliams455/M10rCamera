#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix-m10r-yblend-diag1a.py <PhotonCamera-root>')
root = Path(sys.argv[1]).resolve()
if not (root / 'app').is_dir():
    raise SystemExit('YBLEND DIAG1A: not a PhotonCamera root')

def rd(rel):
    p = root / rel
    if not p.exists():
        raise SystemExit('YBLEND DIAG1A missing: ' + rel)
    return p.read_text()

def wr(rel, text):
    (root / rel).write_text(text)

def one(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit('YBLEND DIAG1A anchor %s count=%d' % (label, n))
    return text.replace(old, new, 1)

# Gate-B diagnostic only, applied after frozen RENDER1Q.
#
# IMPORTANT: the live renderer's YC1A Y row is 1224,2404,467. The newly
# recovered TRUE Y_BLEND record 0x0C Y row is 1224,2403,469. Cb/Cr rows are
# identical. DIAG1A therefore measures the true record-0x0C coordinates in the
# existing 1/64 Java diagnostic sampler but deliberately does NOT replace YC1A
# and does not touch m10rRender.cpp. This keeps photographic pixels frozen.
#
# The six record-0x0C tail fields are all 0x3FFF. We log proximity to +/-0x3FFF
# only through an explicitly labelled normalized-Q14 projection. The projection
# is an oracle aid, NOT a claim that the opaque ISP consumer uses that scaling
# or that 0x3FFF is a clipping threshold.

grad = 'app/build.gradle'
g = rd(grad)
g = one(
    g,
    "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1q-cc1map1a-yblend1b-k035-redtrace1b-edge0a-nativeout1a-diag1c-saf1'",
    "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1q-yblenddiag1a-cc1map1a-yblend1b-k035-redtrace1b-edge0a-nativeout1a-diag1c-saf1'",
    'version')
wr(grad, g)

renderer = 'app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'
r = rd(renderer)

r = one(
    r,
    '            d.put("renderLook", "RENDER1Q_CC1MAP1A_YBLEND1B_K035_REDTRACE1B_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A");\n',
    '''            d.put("renderLook", "RENDER1Q_YBLENDDIAG1A_CC1MAP1A_YBLEND1B_K035_REDTRACE1B_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A");
            d.put("yBlendDiag1AEnabled", true);
            d.put("yBlendDiag1APhotographicPixelsChanged", false);
            d.put("yBlendDiag1ATrueSelector", "0x154ECC");
            d.put("yBlendDiag1ATrueRecord", "0x0C");
            d.put("yBlendDiag1ATrueDriver", "0x0D4570");
''',
    'render-identity')

init_anchor = '''            final double[][] yBlend1ASums = new double[12][11];\n'''
init_new = init_anchor + '''            // YBLENDDIAG1A Gate-B oracle. Four diagnostic-only subsets:
            // 0=all sampled pixels; 1=warm highlight; 2=saturated red;
            // 3=saturated blue. These classifications are probes, not Leica
            // firmware claims. Statistics use the TRUE record-0x0C matrix.
            final long[] yBlendDiag1ACounts = new long[4];
            // sums: trueY,trueCb,trueCr,liveYc1AY,trueMinusLiveY,absCb,absCr
            final double[][] yBlendDiag1ASums = new double[4][7];
            final double[][] yBlendDiag1AMin = new double[4][3];
            final double[][] yBlendDiag1AMax = new double[4][3];
            // endpoint projection counts: +Y,-Y,+Cb,-Cb,+Cr,-Cr near 0x3FFF
            final long[][] yBlendDiag1AEndpoint = new long[4][6];
            // 16 bins Y + 16 bins Cb + 16 bins Cr. Y projection range
            // [-0.25,1.75], Cb/Cr range [-1,1], clamped at edges.
            final long[][] yBlendDiag1AHist = new long[4][48];
            for (int di = 0; di < 4; di++) {
                for (int dc = 0; dc < 3; dc++) {
                    yBlendDiag1AMin[di][dc] = Double.POSITIVE_INFINITY;
                    yBlendDiag1AMax[di][dc] = Double.NEGATIVE_INFINITY;
                }
            }
'''
r = one(r, init_anchor, init_new, 'diag-init')

sample_anchor = '''                    // YBLEND1A diagnostics classify warm/neutral on the PRE-MAP\n'''
sample_new = '''                    // YBLENDDIAG1A: evaluate the coefficient-exact TRUE Y_BLEND
                    // record-0x0C matrix beside the frozen live YC1A matrix.
                    // YC1A stays untouched: live Y row = 1224,2404,467; true
                    // Y_BLEND row = 1224,2403,469. Cb/Cr rows are identical.
                    final double ybdY = (1224.0*lr + 2403.0*lg + 469.0*lb) / 4096.0;
                    final double ybdCb = (-691.0*lr - 1357.0*lg + 2048.0*lb) / 4096.0;
                    final double ybdCr = (2048.0*lr - 1715.0*lg - 333.0*lb) / 4096.0;
                    final double ybdDeltaLiveY = ybdY - ycY;
                    final double ybdDen = Math.max(Math.abs(ybdY), 1.0e-9);
                    final double ybdRelCb = ybdCb / ybdDen;
                    final double ybdRelCr = ybdCr / ybdDen;
                    final boolean ybdWarmHighlight = ybdY >= 0.70 && ybdRelCr >= 0.04;
                    final boolean ybdSatRed = lr >= 0.25 && lr >= 1.35*Math.max(lg, lb) && ybdRelCr >= 0.10;
                    final boolean ybdSatBlue = lb >= 0.25 && lb >= 1.35*Math.max(lr, lg) && ybdRelCb >= 0.10;
                    final boolean[] ybdMember = new boolean[]{true, ybdWarmHighlight, ybdSatRed, ybdSatBlue};
                    final double[] ybdCoord = new double[]{ybdY, ybdCb, ybdCr};
                    for (int ybdCls = 0; ybdCls < 4; ybdCls++) {
                        if (!ybdMember[ybdCls]) continue;
                        yBlendDiag1ACounts[ybdCls]++;
                        final double[] ybdS = yBlendDiag1ASums[ybdCls];
                        ybdS[0] += ybdY; ybdS[1] += ybdCb; ybdS[2] += ybdCr;
                        ybdS[3] += ycY; ybdS[4] += ybdDeltaLiveY;
                        ybdS[5] += Math.abs(ybdCb); ybdS[6] += Math.abs(ybdCr);
                        for (int ybdC = 0; ybdC < 3; ybdC++) {
                            yBlendDiag1AMin[ybdCls][ybdC] = Math.min(yBlendDiag1AMin[ybdCls][ybdC], ybdCoord[ybdC]);
                            yBlendDiag1AMax[ybdCls][ybdC] = Math.max(yBlendDiag1AMax[ybdCls][ybdC], ybdCoord[ybdC]);
                        }
                        // Projection-only proximity to +/-0x3FFF. One projected
                        // code is 1/16383 of normalized coordinate; <=64 codes
                        // is merely a compact near-endpoint bucket.
                        for (int ybdC = 0; ybdC < 3; ybdC++) {
                            final double ybdQ14 = ybdCoord[ybdC] * 16383.0;
                            if (Math.abs(ybdQ14 - 16383.0) <= 64.0) yBlendDiag1AEndpoint[ybdCls][2*ybdC]++;
                            if (Math.abs(ybdQ14 + 16383.0) <= 64.0) yBlendDiag1AEndpoint[ybdCls][2*ybdC + 1]++;
                        }
                        int ybdYBin = (int)Math.floor((ybdY + 0.25) * 8.0);
                        int ybdCbBin = (int)Math.floor((ybdCb + 1.0) * 8.0);
                        int ybdCrBin = (int)Math.floor((ybdCr + 1.0) * 8.0);
                        ybdYBin = Math.max(0, Math.min(15, ybdYBin));
                        ybdCbBin = Math.max(0, Math.min(15, ybdCbBin));
                        ybdCrBin = Math.max(0, Math.min(15, ybdCrBin));
                        yBlendDiag1AHist[ybdCls][ybdYBin]++;
                        yBlendDiag1AHist[ybdCls][16 + ybdCbBin]++;
                        yBlendDiag1AHist[ybdCls][32 + ybdCrBin]++;
                    }

                    // YBLEND1A diagnostics classify warm/neutral on the PRE-MAP\n'''
r = one(r, sample_anchor, sample_new, 'diag-sample')

json_anchor = '''            d.put("yBlend1B", yBlend1A);\n'''
json_new = json_anchor + '''            JSONObject yBlendDiag1A = new JSONObject();
            yBlendDiag1A.put("diagnosticOnly", true);
            yBlendDiag1A.put("photographicPixelsChanged", false);
            yBlendDiag1A.put("sampleStride", 64);
            yBlendDiag1A.put("trueSelector", "0x154ECC");
            yBlendDiag1A.put("trueRecord", "0x0C");
            yBlendDiag1A.put("trueDriver", "0x0D4570");
            yBlendDiag1A.put("trueMatrixQ12", "1224,2403,469;-691,-1357,2048;2048,-1715,-333");
            yBlendDiag1A.put("liveYc1AMatrixQ12", "1224,2404,467;-691,-1357,2048;2048,-1715,-333");
            yBlendDiag1A.put("trueMinusLiveYRowQ12", "0,-1,+2");
            yBlendDiag1A.put("recordTailU16", "16383,16383,16383,16383,16383,16383");
            yBlendDiag1A.put("programmedTailWords", "0x3fff3fff,0x3fff3fff,0x3fff3fff");
            yBlendDiag1A.put("recordDefaultLowBit15", 0);
            yBlendDiag1A.put("q14ProjectionCaveat", "normalized_coordinate_times_16383_is_diagnostic_projection_only_not_proven_ISP_ABI_or_clip_semantic");
            yBlendDiag1A.put("endpointProjectionBucketCodes", 64);
            yBlendDiag1A.put("histogramYRange", "[-0.25,1.75]_16_bins_clamped");
            yBlendDiag1A.put("histogramCbCrRange", "[-1,1]_16_bins_clamped");
            yBlendDiag1A.put("warmHighlightProbe", "trueY>=0.70_and_trueCr/max(abs(trueY),1e-9)>=0.04");
            yBlendDiag1A.put("saturatedRedProbe", "R>=0.25_and_R>=1.35*max(G,B)_and_trueCr/max(abs(trueY),1e-9)>=0.10");
            yBlendDiag1A.put("saturatedBlueProbe", "B>=0.25_and_B>=1.35*max(R,G)_and_trueCb/max(abs(trueY),1e-9)>=0.10");
            String[] ybdNames = new String[]{"all", "warmHighlightProbe", "saturatedRedProbe", "saturatedBlueProbe"};
            for (int ybdCls = 0; ybdCls < 4; ybdCls++) {
                JSONObject ybd = new JSONObject();
                final long ybdN = yBlendDiag1ACounts[ybdCls];
                ybd.put("count", ybdN);
                if (ybdN > 0) {
                    final double[] ybdS = yBlendDiag1ASums[ybdCls];
                    ybd.put("meanTrueY", ybdS[0] / ybdN);
                    ybd.put("meanTrueCb", ybdS[1] / ybdN);
                    ybd.put("meanTrueCr", ybdS[2] / ybdN);
                    ybd.put("meanLiveYc1AY", ybdS[3] / ybdN);
                    ybd.put("meanTrueMinusLiveY", ybdS[4] / ybdN);
                    ybd.put("meanAbsTrueCb", ybdS[5] / ybdN);
                    ybd.put("meanAbsTrueCr", ybdS[6] / ybdN);
                    ybd.put("minTrueY", yBlendDiag1AMin[ybdCls][0]);
                    ybd.put("maxTrueY", yBlendDiag1AMax[ybdCls][0]);
                    ybd.put("minTrueCb", yBlendDiag1AMin[ybdCls][1]);
                    ybd.put("maxTrueCb", yBlendDiag1AMax[ybdCls][1]);
                    ybd.put("minTrueCr", yBlendDiag1AMin[ybdCls][2]);
                    ybd.put("maxTrueCr", yBlendDiag1AMax[ybdCls][2]);
                }
                final long[] ybdE = yBlendDiag1AEndpoint[ybdCls];
                ybd.put("projectedNearPlus3fffY", ybdE[0]);
                ybd.put("projectedNearMinus3fffY", ybdE[1]);
                ybd.put("projectedNearPlus3fffCb", ybdE[2]);
                ybd.put("projectedNearMinus3fffCb", ybdE[3]);
                ybd.put("projectedNearPlus3fffCr", ybdE[4]);
                ybd.put("projectedNearMinus3fffCr", ybdE[5]);
                StringBuilder ybdHist = new StringBuilder();
                for (int hi = 0; hi < 48; hi++) {
                    if (hi > 0) ybdHist.append(',');
                    ybdHist.append(yBlendDiag1AHist[ybdCls][hi]);
                }
                ybd.put("hist48_Y16_Cb16_Cr16", ybdHist.toString());
                yBlendDiag1A.put(ybdNames[ybdCls], ybd);
            }
            d.put("yBlendDiag1A", yBlendDiag1A);\n'''
r = one(r, json_anchor, json_new, 'diag-json')
wr(renderer, r)

# Hard gates. DIAG1A must not alter native photographic arithmetic.
G = rd(grad)
R = rd(renderer)
C = rd('app/src/main/cpp/m10rRender.cpp')

if "render1q-yblenddiag1a-cc1map1a-yblend1b-k035-redtrace1b-edge0a-nativeout1a-diag1c-saf1'" not in G:
    raise SystemExit('YBLEND DIAG1A build identity missing')

for needle in [
    'RENDER1Q_YBLENDDIAG1A_CC1MAP1A_YBLEND1B_K035_REDTRACE1B_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A',
    'yBlendDiag1APhotographicPixelsChanged", false',
    'trueMatrixQ12", "1224,2403,469;-691,-1357,2048;2048,-1715,-333',
    'liveYc1AMatrixQ12", "1224,2404,467;-691,-1357,2048;2048,-1715,-333',
    'trueMinusLiveYRowQ12", "0,-1,+2',
    'programmedTailWords", "0x3fff3fff,0x3fff3fff,0x3fff3fff',
    'q14ProjectionCaveat',
    'warmHighlightProbe',
    'saturatedRedProbe',
    'saturatedBlueProbe',
    'hist48_Y16_Cb16_Cr16'
]:
    if needle not in R:
        raise SystemExit('YBLEND DIAG1A renderer invariant missing: ' + needle)

# Frozen live RENDER1Q native path must remain present exactly.
for needle in [
    'const double y  = (1224.0*lr + 2404.0*lg + 467.0*lb) / 4096.0;',
    'const double cb = (-691.0*lr - 1357.0*lg + 2048.0*lb) / 4096.0;',
    'const double cr = (2048.0*lr - 1715.0*lg - 333.0*lb) / 4096.0;',
    'const double yBlendChromaScale = y > 1.0e-12 ? 1.0 + 0.35 * (yRatio - 1.0) : 0.0;',
    'const double mappedCb = cb * yBlendChromaScale;',
    'const double mappedCr = cr * yBlendChromaScale;',
    'const double outR = outMat[0]*nr + outMat[1]*ng + outMat[2]*nb;',
    'linear8(outR)', 'linear8(outG)', 'linear8(outB)'
]:
    if needle not in C:
        raise SystemExit('YBLEND DIAG1A frozen native invariant missing: ' + needle)

# Prove the true record matrix exists only in Java diagnostics; it must not have
# silently replaced live native YC1A.
if '(1224.0*lr + 2403.0*lg + 469.0*lb) / 4096.0' in C:
    raise SystemExit('YBLEND DIAG1A changed native Y matrix; diagnostic must be output-neutral')

print('M10-R YBLEND DIAG1A applied')
print(' - TRUE record-0x0C Q12 coordinates logged in existing 1/64 Java sampler')
print(' - live YC1A 1224/2404/467 matrix preserved; true Y_BLEND 1224/2403/469 measured separately')
print(' - all/warm-highlight/saturated-red/saturated-blue subsets + compact histograms emitted')
print(' - 0x3FFF proximity is explicitly projection-only; no ISP ABI/clip claim')
print(' - m10rRender.cpp photographic output remains frozen RENDER1Q k0.35')
