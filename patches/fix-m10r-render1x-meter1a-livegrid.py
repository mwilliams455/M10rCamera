#!/usr/bin/env python3
"""METER1A live 22x16 preview-grid diagnostic on top of AE1B FREEZE1.

No exposure/tone/native render change vs FREEZE1.
Samples the actual camera SurfaceTexture every sixth rendered frame into a 22x16
offscreen FBO, computes the exact recovered Leica Integral weighting in preview
code-space and approximate linear-light space, and freezes the latest grid when
a still capture starts for comparison with the post-capture RAW Leica mask.
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
        "import com.particlesdevs.photoncamera.capture.CaptureController;\n",
        "import com.particlesdevs.photoncamera.capture.CaptureController;\n"
        "import com.particlesdevs.photoncamera.m10r.M10RIntegralMask;\n"
        "import com.particlesdevs.photoncamera.m10r.M10RLiveMeterState;\n")

    s=once(s,
        "    private int[] hTex;\n",
        """    private int[] hTex;
    private int hProgram;
    private int[] meterFbo;
    private int[] meterTex;
    private ByteBuffer meterPixels;
    private int meterFrameCounter = 0;
    private int viewportWidth = 1;
    private int viewportHeight = 1;
    private static final int METER_COLS = 22;
    private static final int METER_ROWS = 16;
    private static final int METER_EVERY_N_FRAMES = 6;
    private static final float[] IDENTITY_MATRIX = new float[] {
            1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1
    };
""")

    s=once(s,
        """        GLES20.glDrawArrays(GLES20.GL_TRIANGLE_STRIP, 0, 4);
        // GLES20.glFlush();
""",
        """        GLES20.glDrawArrays(GLES20.GL_TRIANGLE_STRIP, 0, 4);
        if ((++meterFrameCounter % METER_EVERY_N_FRAMES) == 0) {
            sampleM10rMeterGrid();
        }
        // GLES20.glFlush();
""")

    s=once(s,
        """        int hProgram = loadShader(vss_default, fss_default);
        GLES20.glUseProgram(hProgram);
""",
        """        hProgram = loadShader(vss_default, fss_default);
        GLES20.glUseProgram(hProgram);
""")

    s=once(s,
        """        mGLInit = true;
        mView.fireOnSurfaceTextureAvailable(mSTexture, 0, 0);
""",
        """        initM10rMeterFbo();
        mGLInit = true;
        mView.fireOnSurfaceTextureAvailable(mSTexture, 0, 0);
""")

    s=once(s,
        """    public void onSurfaceChanged(GL10 unused, int width, int height) {
        GLES30.glViewport(0, 0, width, height);
    }
""",
        """    public void onSurfaceChanged(GL10 unused, int width, int height) {
        viewportWidth = Math.max(1, width);
        viewportHeight = Math.max(1, height);
        GLES30.glViewport(0, 0, width, height);
    }
""")

    anchor="    public SurfaceTexture getmSTexture() {\n"
    helper=r'''    private void initM10rMeterFbo() {
        meterFbo = new int[1];
        meterTex = new int[1];
        GLES20.glGenTextures(1, meterTex, 0);
        GLES20.glBindTexture(GLES20.GL_TEXTURE_2D, meterTex[0]);
        GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_MIN_FILTER, GLES20.GL_LINEAR);
        GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_MAG_FILTER, GLES20.GL_LINEAR);
        GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_WRAP_S, GLES20.GL_CLAMP_TO_EDGE);
        GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_WRAP_T, GLES20.GL_CLAMP_TO_EDGE);
        GLES20.glTexImage2D(GLES20.GL_TEXTURE_2D, 0, GLES20.GL_RGBA,
                METER_COLS, METER_ROWS, 0, GLES20.GL_RGBA, GLES20.GL_UNSIGNED_BYTE, null);
        GLES20.glGenFramebuffers(1, meterFbo, 0);
        GLES20.glBindFramebuffer(GLES20.GL_FRAMEBUFFER, meterFbo[0]);
        GLES20.glFramebufferTexture2D(GLES20.GL_FRAMEBUFFER, GLES20.GL_COLOR_ATTACHMENT0,
                GLES20.GL_TEXTURE_2D, meterTex[0], 0);
        int status = GLES20.glCheckFramebufferStatus(GLES20.GL_FRAMEBUFFER);
        if (status != GLES20.GL_FRAMEBUFFER_COMPLETE) {
            Log.e("M10RMeter1A", "meter FBO incomplete: " + status);
        }
        GLES20.glBindFramebuffer(GLES20.GL_FRAMEBUFFER, 0);
        meterPixels = ByteBuffer.allocateDirect(METER_COLS * METER_ROWS * 4)
                .order(ByteOrder.nativeOrder());
    }

    private static double inverseSrgb(double c) {
        if (c <= 0.04045) return c / 12.92;
        return Math.pow((c + 0.055) / 1.055, 2.4);
    }

    private void sampleM10rMeterGrid() {
        if (meterFbo == null || meterTex == null || meterPixels == null || hProgram == 0) return;
        try {
            GLES20.glBindFramebuffer(GLES20.GL_FRAMEBUFFER, meterFbo[0]);
            GLES20.glViewport(0, 0, METER_COLS, METER_ROWS);

            // Meter the unrotated/unmirrored camera texture so the 22x16 grid
            // corresponds to the same sensor-oriented geometry used by RAW diagnostics.
            GLES20.glUniformMatrix4fv(uTexRotateMatrix, 1, false, IDENTITY_MATRIX, 0);
            GLES20.glUniform1i(enablePeak, 0);
            GLES20.glUniform1i(mirror, 0);
            GLES20.glVertexAttribPointer(vPosition, 2, GLES20.GL_FLOAT, false, 4 * 2, pVertex);
            GLES20.glVertexAttribPointer(vTexCoord, 2, GLES20.GL_FLOAT, false, 4 * 2, pTexCoord);
            GLES20.glDrawArrays(GLES20.GL_TRIANGLE_STRIP, 0, 4);

            meterPixels.position(0);
            GLES20.glReadPixels(0, 0, METER_COLS, METER_ROWS,
                    GLES20.GL_RGBA, GLES20.GL_UNSIGNED_BYTE, meterPixels);
            meterPixels.position(0);

            double codeSum = 0.0, codeWeighted = 0.0, codeWeightSum = 0.0;
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
            double codeWhole = codeSum / (METER_COLS * METER_ROWS);
            double linearWhole = linearSum / (METER_COLS * METER_ROWS);
            double codeIntegral = codeWeightSum > 0.0 ? codeWeighted / codeWeightSum : 0.0;
            double linearIntegral = linearWeightSum > 0.0 ? linearWeighted / linearWeightSum : 0.0;

            CaptureController cc = PhotonCamera.getCaptureController();
            long previewExposureNs = cc != null ? cc.mPreviewExposureTime : 0L;
            int previewIso = cc != null ? cc.mPreviewIso : 0;
            M10RLiveMeterState.publish(System.nanoTime(), previewExposureNs, previewIso,
                    codeWhole, codeIntegral, linearWhole, linearIntegral, linearGrid);
        } catch (Throwable t) {
            Log.e("M10RMeter1A", "live grid sample failed: " + t);
        } finally {
            GLES20.glBindFramebuffer(GLES20.GL_FRAMEBUFFER, 0);
            GLES20.glViewport(0, 0, viewportWidth, viewportHeight);
            GLES20.glUniformMatrix4fv(uTexRotateMatrix, 1, false, mTexRotateMatrix, 0);
            GLES20.glUniform1i(enablePeak, getPeakEnabled());
            GLES20.glUniform1i(mirror, mMirrorPreview ? 1 : 0);
        }
    }

'''
    s=once(s,anchor,helper+anchor)
    return s

def patch_capture(s):
    s=once(s,
        "import com.particlesdevs.photoncamera.processing.parameters.IsoExpoSelector;\n",
        "import com.particlesdevs.photoncamera.processing.parameters.IsoExpoSelector;\n"
        "import com.particlesdevs.photoncamera.m10r.M10RLiveMeterState;\n")
    s=once(s,
        """            // AE1B FREEZE1: bind one preview-derived M10-R decision to this still sequence.
            IsoExpoSelector.prepareM10rAe1BCapture(this);
""",
        """            // METER1A freezes the latest live 22x16 Leica grid beside the still.
            M10RLiveMeterState.freezeCapture();
            // AE1B FREEZE1: bind one preview-derived M10-R decision to this still sequence.
            IsoExpoSelector.prepareM10rAe1BCapture(this);
""")
    return s

def patch_renderer(s):
    anchor="    private static void appendAe1BState(JSONObject d, CaptureRequest captureRequest) throws Exception {\n"
    helper=r'''    private static void appendMeter1A(JSONObject d) throws Exception {
        M10RLiveMeterState.Snapshot s = M10RLiveMeterState.frozenSnapshot();
        JSONObject o = new JSONObject()
                .put("enabled", true)
                .put("diagnosticOnly", true)
                .put("affectsExposure", false)
                .put("affectsPixels", false)
                .put("grid", "22x16")
                .put("sampleSource", "GL_SurfaceTexture_offscreen_RGBA8")
                .put("sampleCadence", "every_6_rendered_preview_frames")
                .put("sensorOrientationIntent", "unrotated_unmirrored_texture")
                .put("integralMask", "exact_recovered_M10R_Integral_0x4001349C")
                .put("integralMaskWeightSum", M10RIntegralMask.WEIGHT_SUM)
                .put("linearization", "inverse_sRGB_per_channel_then_Rec709_luma_approx")
                .put("previewPipelineParityClaimed", false)
                .put("valid", s.valid)
                .put("generation", s.generation)
                .put("sampleTimestampNs", s.timestampNs)
                .put("previewExposureTimeNs", s.previewExposureNs)
                .put("previewIso", s.previewIso);
        if (s.valid) {
            o.put("codeWholeMean", s.codeWholeMean)
                    .put("codeIntegralMean", s.codeIntegralMean)
                    .put("codeIntegralVsWholeEv", s.codeIntegralVsWholeEv)
                    .put("linearWholeMean", s.linearWholeMean)
                    .put("linearIntegralMean", s.linearIntegralMean)
                    .put("linearIntegralVsWholeEv", s.linearIntegralVsWholeEv);
            JSONArray rows = new JSONArray();
            if (s.linearGrid != null && s.linearGrid.length == M10RIntegralMask.ROWS * M10RIntegralMask.COLS) {
                for (int row = 0; row < M10RIntegralMask.ROWS; row++) {
                    JSONArray r = new JSONArray();
                    for (int col = 0; col < M10RIntegralMask.COLS; col++) {
                        r.put(s.linearGrid[row * M10RIntegralMask.COLS + col]);
                    }
                    rows.put(r);
                }
            }
            o.put("linearGrid16x22", rows);

            JSONObject raw = d.optJSONObject("m10rAe1A_rawMeterProbe");
            if (raw != null && raw.has("leicaIntegralVsWholeEv")) {
                double rawEv = raw.optDouble("leicaIntegralVsWholeEv", Double.NaN);
                o.put("rawLeicaIntegralVsWholeEv",
                        Double.isFinite(rawEv) ? rawEv : JSONObject.NULL);
                o.put("linearPreviewMinusRawIntegralDeltaEv",
                        Double.isFinite(rawEv) && Double.isFinite(s.linearIntegralVsWholeEv)
                                ? s.linearIntegralVsWholeEv - rawEv : JSONObject.NULL);
                o.put("codePreviewMinusRawIntegralDeltaEv",
                        Double.isFinite(rawEv) && Double.isFinite(s.codeIntegralVsWholeEv)
                                ? s.codeIntegralVsWholeEv - rawEv : JSONObject.NULL);
            }
        }
        d.put("m10rMeter1A", o);
    }

'''
    s=once(s,anchor,helper+anchor)
    s=once(s,
        """            try {
                appendAe1BState(d, captureRequest);
            } catch (Throwable ae1bError) {
                d.put("m10rAe1B", new JSONObject()
                        .put("enabled", true).put("activeCapture", true)
                        .put("status", "telemetry_failed").put("error", ae1bError.toString()));
            }
            d.put("status", "success");
""",
        """            try {
                appendAe1BState(d, captureRequest);
            } catch (Throwable ae1bError) {
                d.put("m10rAe1B", new JSONObject()
                        .put("enabled", true).put("activeCapture", true)
                        .put("status", "telemetry_failed").put("error", ae1bError.toString()));
            }
            try {
                appendMeter1A(d);
            } catch (Throwable meter1aError) {
                d.put("m10rMeter1A", new JSONObject()
                        .put("enabled", true).put("diagnosticOnly", true)
                        .put("status", "telemetry_failed").put("error", meter1aError.toString()));
            }
            d.put("status", "success");
""")
    return s

def main():
    if len(sys.argv)!=2:
        raise SystemExit("usage: fix-m10r-render1x-meter1a-livegrid.py <PhotonCamera-root>")
    root=Path(sys.argv[1]).resolve()
    repo=Path(__file__).resolve().parents[1]
    mainr=root/"app/src/main/java/com/particlesdevs/photoncamera/ui/camera/views/viewfinder/MainRenderer.java"
    cap=root/"app/src/main/java/com/particlesdevs/photoncamera/capture/CaptureController.java"
    renderer=root/"app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java"
    cpp=root/"app/src/main/cpp/m10rRender.cpp"
    gradle=root/"app/build.gradle"
    for p in [mainr,cap,renderer,cpp,gradle]:
        if not p.is_file(): raise RuntimeError("missing "+str(p))
    if hashlib.sha256(cpp.read_bytes()).hexdigest()!=CPP_SHA:
        raise RuntimeError("METER1A refuses changed native renderer")

    mainr.write_text(patch_main_renderer(mainr.read_text()))
    cap.write_text(patch_capture(cap.read_text()))
    renderer.write_text(patch_renderer(renderer.read_text()))
    (renderer.parent/"M10RLiveMeterState.java").write_bytes((repo/"android/M10RLiveMeterState.java").read_bytes())

    g=gradle.read_text()
    versions=re.findall(r"versionName\s+['\"]([^'\"]+)['\"]",g)
    if len(versions)!=1 or "render1w-ae1b-freeze1-render1t-colorrecon1a-tonecal1a-" not in versions[0]:
        raise RuntimeError("unexpected FREEZE1 versionName: %r" % versions)
    version=versions[0].replace(
        "render1w-ae1b-freeze1-render1t-colorrecon1a-tonecal1a-",
        "render1x-meter1a-livegrid-ae1b-freeze1-render1t-colorrecon1a-tonecal1a-",1)
    gradle.write_text(g.replace(versions[0],version,1))

    if hashlib.sha256(cpp.read_bytes()).hexdigest()!=CPP_SHA:
        raise RuntimeError("METER1A changed native renderer")
    proof={
        "schema":"RENDER1X_METER1A_LIVEGRID_PATCH_V1",
        "baseline":"RENDER1W_AE1B_FREEZE1_on_RENDER1T",
        "versionName":version,
        "diagnosticOnly":True,
        "realExposureChangedVsFreeze1":False,
        "rendererNativeChanged":False,
        "livePreviewGrid":"22x16_RGBA8_offscreen_every_6_frames",
        "integralMask":"exact_recovered_M10R_Integral_0x4001349C",
        "integralMaskWeightSum":14160,
        "linearization":"inverse_sRGB_then_Rec709_luma_approx",
        "fullGridFrozenAtStill":True,
        "rawParityComparisonIncluded":True,
        "previewPipelineParityClaimed":False,
        "hdrEnabled":False,
        "singleRaw":True,
        "deviceValidated":False,
        "productionPromoted":False
    }
    (root/"M10R_RENDER1X_METER1A_LIVEGRID_PROVENANCE.json").write_text(json.dumps(proof,indent=2)+"\n")
    print(json.dumps(proof,indent=2))

if __name__=="__main__":
    main()
