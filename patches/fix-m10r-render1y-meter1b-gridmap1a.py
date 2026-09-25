#!/usr/bin/env python3
"""METER1B GRIDMAP1A on top of RENDER1X/METER1A.

No exposure or photographic pixel changes vs METER1A.

Fixes the live 22x16 meter geometry after code review of Photon's preview shader:
- main_vs.glsl maps output through texCoord.yx = vTexCoord.xy and x = 1-x.
- Therefore an unrotated meter FBO must be 16 wide x 22 high.
- glReadPixels row (bottom->top) maps to Leica sensor X / grid column.
- glReadPixels column (left->right) maps to Leica sensor Y / grid row.

Also emits a post-capture RAW 16x22 green grid using the same sampled RAW domain
as the Leica Integral diagnostic. This makes orientation/spatial parity directly
testable rather than inferring it from the symmetric Integral mask.
"""
from pathlib import Path
import hashlib,json,re,sys

CPP_SHA="880ce125413bdf1e0f56fbbdcc56591ba91e794f9b5281488f63353dca724637"

def once(s,a,b):
    n=s.count(a)
    if n!=1:
        raise RuntimeError("Unique anchor required (%d): %s" % (n,a[:180]))
    return s.replace(a,b,1)

def patch_main_renderer(s):
    s=once(s,
        """    private static final int METER_COLS = 22;
    private static final int METER_ROWS = 16;
    private static final int METER_EVERY_N_FRAMES = 6;
""",
        """    private static final int METER_COLS = 22;
    private static final int METER_ROWS = 16;
    // The existing preview vertex shader swaps texture axes. For sensor-oriented
    // 22x16 output, the offscreen raster therefore needs the transposed shape.
    private static final int METER_FBO_WIDTH = 16;
    private static final int METER_FBO_HEIGHT = 22;
    private static final int METER_EVERY_N_FRAMES = 6;
""")

    s=once(s,
        """        GLES20.glTexImage2D(GLES20.GL_TEXTURE_2D, 0, GLES20.GL_RGBA,
                METER_COLS, METER_ROWS, 0, GLES20.GL_RGBA, GLES20.GL_UNSIGNED_BYTE, null);
""",
        """        GLES20.glTexImage2D(GLES20.GL_TEXTURE_2D, 0, GLES20.GL_RGBA,
                METER_FBO_WIDTH, METER_FBO_HEIGHT, 0,
                GLES20.GL_RGBA, GLES20.GL_UNSIGNED_BYTE, null);
""")

    s=once(s,
        """        meterPixels = ByteBuffer.allocateDirect(METER_COLS * METER_ROWS * 4)
                .order(ByteOrder.nativeOrder());
""",
        """        meterPixels = ByteBuffer.allocateDirect(METER_FBO_WIDTH * METER_FBO_HEIGHT * 4)
                .order(ByteOrder.nativeOrder());
""")

    s=once(s,
        """            GLES20.glViewport(0, 0, METER_COLS, METER_ROWS);
""",
        """            GLES20.glViewport(0, 0, METER_FBO_WIDTH, METER_FBO_HEIGHT);
""")

    s=once(s,
        """            GLES20.glReadPixels(0, 0, METER_COLS, METER_ROWS,
                    GLES20.GL_RGBA, GLES20.GL_UNSIGNED_BYTE, meterPixels);
""",
        """            GLES20.glReadPixels(0, 0, METER_FBO_WIDTH, METER_FBO_HEIGHT,
                    GLES20.GL_RGBA, GLES20.GL_UNSIGNED_BYTE, meterPixels);
""")

    old_loop=r'''            double codeSum = 0.0, codeWeighted = 0.0, codeWeightSum = 0.0;
            double linearSum = 0.0, linearWeighted = 0.0, linearWeightSum = 0.0;
            double[] linearGrid = new double[METER_COLS * METER_ROWS];
            for (int rawRow = 0; rawRow < METER_ROWS; rawRow++) {
                // glReadPixels is bottom-up; flip to the top-down Leica mask row.
                int row = METER_ROWS - 1 - rawRow;
                for (int col = 0; col < METER_COLS; col++) {
                    int r = meterPixels.get() & 0xff;
                    int g = meterPixels.get() & 0xff;
                    int b = meterPixels.get() & 0xff;
                    meterPixels.get();
                    double rc = r / 255.0, gc = g / 255.0, bc = b / 255.0;
                    double codeY = 0.2126 * rc + 0.7152 * gc + 0.0722 * bc;
                    double linearY = 0.2126 * inverseSrgb(rc)
                            + 0.7152 * inverseSrgb(gc) + 0.0722 * inverseSrgb(bc);
                    int idx = row * METER_COLS + col;
                    linearGrid[idx] = linearY;
                    int w = M10RIntegralMask.weight(row, col);
                    codeSum += codeY;
                    linearSum += linearY;
                    if (w > 0) {
                        codeWeighted += codeY * w;
                        linearWeighted += linearY * w;
                        codeWeightSum += w;
                        linearWeightSum += w;
                    }
                }
            }
'''
    new_loop=r'''            double codeSum = 0.0, codeWeighted = 0.0, codeWeightSum = 0.0;
            double linearSum = 0.0, linearWeighted = 0.0, linearWeightSum = 0.0;
            double[] linearGrid = new double[METER_COLS * METER_ROWS];

            // main_vs.glsl:
            //   texCoord.yx = vTexCoord.xy;
            //   texCoord.x = 1.0 - texCoord.x;
            // With the current pTexCoord geometry, FBO bottom->top therefore walks
            // sensor texture X and FBO left->right walks sensor texture Y.
            // glReadPixels already returns bottom row first, so:
            //   rawRow -> sensor/grid column (0..21)
            //   rawCol -> sensor/grid row    (0..15)
            for (int rawRow = 0; rawRow < METER_FBO_HEIGHT; rawRow++) {
                int col = rawRow;
                for (int rawCol = 0; rawCol < METER_FBO_WIDTH; rawCol++) {
                    int row = rawCol;
                    int r = meterPixels.get() & 0xff;
                    int g = meterPixels.get() & 0xff;
                    int b = meterPixels.get() & 0xff;
                    meterPixels.get();
                    double rc = r / 255.0, gc = g / 255.0, bc = b / 255.0;
                    double codeY = 0.2126 * rc + 0.7152 * gc + 0.0722 * bc;
                    double linearY = 0.2126 * inverseSrgb(rc)
                            + 0.7152 * inverseSrgb(gc) + 0.0722 * inverseSrgb(bc);
                    int idx = row * METER_COLS + col;
                    linearGrid[idx] = linearY;
                    int w = M10RIntegralMask.weight(row, col);
                    codeSum += codeY;
                    linearSum += linearY;
                    if (w > 0) {
                        codeWeighted += codeY * w;
                        linearWeighted += linearY * w;
                        codeWeightSum += w;
                        linearWeightSum += w;
                    }
                }
            }
'''
    s=once(s,old_loop,new_loop)
    return s

def patch_renderer(s):
    s=once(s,
        """        double ae1aFullSum = 0.0, ae1a70Sum = 0.0, ae1a45Sum = 0.0, ae1a20Sum = 0.0;
        long ae1aFullCount = 0L, ae1a70Count = 0L, ae1a45Count = 0L, ae1a20Count = 0L;
        double ae1aIntegralWeightedSum = 0.0, ae1aIntegralWeightSum = 0.0;
""",
        """        double ae1aFullSum = 0.0, ae1a70Sum = 0.0, ae1a45Sum = 0.0, ae1a20Sum = 0.0;
        long ae1aFullCount = 0L, ae1a70Count = 0L, ae1a45Count = 0L, ae1a20Count = 0L;
        double ae1aIntegralWeightedSum = 0.0, ae1aIntegralWeightSum = 0.0;
        double[] ae1aRawGridSum = new double[M10RIntegralMask.ROWS * M10RIntegralMask.COLS];
        long[] ae1aRawGridCount = new long[M10RIntegralMask.ROWS * M10RIntegralMask.COLS];
""")

    s=once(s,
        """                if (ae1aSample) {
                    ae1aFullSum += unit;
                    ae1aFullCount++;
                    int integralWeight = M10RIntegralMask.weightForPixel(x, y, width, height);
""",
        """                if (ae1aSample) {
                    ae1aFullSum += unit;
                    ae1aFullCount++;
                    int meterRow = Math.min(M10RIntegralMask.ROWS - 1,
                            Math.max(0, (int)((long)y * M10RIntegralMask.ROWS / height)));
                    int meterCol = Math.min(M10RIntegralMask.COLS - 1,
                            Math.max(0, (int)((long)x * M10RIntegralMask.COLS / width)));
                    int meterIndex = meterRow * M10RIntegralMask.COLS + meterCol;
                    ae1aRawGridSum[meterIndex] += unit;
                    ae1aRawGridCount[meterIndex]++;
                    int integralWeight = M10RIntegralMask.weight(meterRow, meterCol);
""")

    s=once(s,
        """        d.put("m10rAe1A_rawMeterProbe", ae1aProbe);
        return new BayerFrame(out, storageScale, whiteClipCount);
""",
        """        JSONArray ae1aRawRows = new JSONArray();
        for (int meterRow = 0; meterRow < M10RIntegralMask.ROWS; meterRow++) {
            JSONArray meterJsonRow = new JSONArray();
            for (int meterCol = 0; meterCol < M10RIntegralMask.COLS; meterCol++) {
                int meterIndex = meterRow * M10RIntegralMask.COLS + meterCol;
                long n = ae1aRawGridCount[meterIndex];
                meterJsonRow.put(n > 0L ? ae1aRawGridSum[meterIndex] / n : 0.0);
            }
            ae1aRawRows.put(meterJsonRow);
        }
        ae1aProbe.put("leicaRawGrid16x22", ae1aRawRows);
        ae1aProbe.put("leicaRawGridCoordinate", "source_sensor_top_down_left_right");
        d.put("m10rAe1A_rawMeterProbe", ae1aProbe);
        return new BayerFrame(out, storageScale, whiteClipCount);
""")

    s=once(s,
        '''                .put("sampleSource", "GL_SurfaceTexture_offscreen_RGBA8")
                .put("sampleCadence", "every_6_rendered_preview_frames")
                .put("sensorOrientationIntent", "unrotated_unmirrored_texture")
''',
        '''                .put("sampleSource", "GL_SurfaceTexture_offscreen_RGBA8")
                .put("sampleCadence", "every_6_rendered_preview_frames")
                .put("sensorOrientationIntent", "source_sensor_top_down_left_right")
                .put("gridMapFix", "GRIDMAP1A_shader_axis_swap_transposed_fbo_16x22")
                .put("meterFboRaster", "16wide_x22high_then_rawRow_to_sensorCol_rawCol_to_sensorRow")
''')
    return s

def main():
    if len(sys.argv)!=2:
        raise SystemExit("usage: fix-m10r-render1y-meter1b-gridmap1a.py <PhotonCamera-root>")
    root=Path(sys.argv[1]).resolve()
    mainr=root/"app/src/main/java/com/particlesdevs/photoncamera/ui/camera/views/viewfinder/MainRenderer.java"
    renderer=root/"app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java"
    cpp=root/"app/src/main/cpp/m10rRender.cpp"
    gradle=root/"app/build.gradle"
    for p in [mainr,renderer,cpp,gradle]:
        if not p.is_file(): raise RuntimeError("missing "+str(p))
    if hashlib.sha256(cpp.read_bytes()).hexdigest()!=CPP_SHA:
        raise RuntimeError("GRIDMAP1A refuses changed native renderer")

    mainr.write_text(patch_main_renderer(mainr.read_text()))
    renderer.write_text(patch_renderer(renderer.read_text()))

    g=gradle.read_text()
    versions=re.findall(r"versionName\s+['\"]([^'\"]+)['\"]",g)
    if len(versions)!=1 or "render1x-meter1a-livegrid-ae1b-freeze1-render1t-colorrecon1a-tonecal1a-" not in versions[0]:
        raise RuntimeError("unexpected METER1A versionName: %r" % versions)
    version=versions[0].replace(
        "render1x-meter1a-livegrid-ae1b-freeze1-render1t-colorrecon1a-tonecal1a-",
        "render1y-meter1b-gridmap1a-ae1b-freeze1-render1t-colorrecon1a-tonecal1a-",1)
    gradle.write_text(g.replace(versions[0],version,1))

    if hashlib.sha256(cpp.read_bytes()).hexdigest()!=CPP_SHA:
        raise RuntimeError("GRIDMAP1A changed native renderer")
    proof={
        "schema":"RENDER1Y_METER1B_GRIDMAP1A_PATCH_V1",
        "baseline":"RENDER1X_METER1A_on_AE1B_FREEZE1_on_RENDER1T",
        "versionName":version,
        "diagnosticOnly":True,
        "realExposureChangedVsMeter1A":False,
        "rendererNativeChanged":False,
        "gridMapFix":"shader_axis_swap_transposed_fbo_16x22",
        "outputMeterGrid":"16rows_x22cols_sensor_top_down_left_right",
        "rawGrid16x22Added":True,
        "rawGridDomain":"sampled_green_pre_lens_shading_same_as_integral_probe",
        "integralMaskUnchanged":True,
        "mfmEnabled":False,
        "reasonMfmStillOff":"must_validate_nonsymmetric_spatial_grid_mapping_first",
        "hdrEnabled":False,
        "singleRaw":True,
        "deviceValidated":False,
        "productionPromoted":False
    }
    (root/"M10R_RENDER1Y_METER1B_GRIDMAP1A_PROVENANCE.json").write_text(json.dumps(proof,indent=2)+"\n")
    print(json.dumps(proof,indent=2))

if __name__=="__main__":
    main()
