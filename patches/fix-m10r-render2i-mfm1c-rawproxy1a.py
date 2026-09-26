#!/usr/bin/env python3
"""RENDER2I MFM1C RAWPROXY1A diagnostic on top of RENDER2H PORT1A.

Goal: test live -> RAW-domain parity without retuning MFM1B and without changing
the frozen RENDER2G photographic renderer.

A throttled preview-time RAW request is sent to the already configured RAW
surface using the current preview exposure/ISO. ImageSaver intercepts only the
exact sensor timestamp belonging to that diagnostic request, M10RRawProxyMeter1A
samples the same sparse semantic-green 16x22 grid as the post-capture RAW oracle,
and immediately closes the RAW image.

RAWPROXY1A is diagnostic-only: active capture exposure still uses the existing
MFM1B GL-grid decision. The sidecar compares RAWPROXY1A vs the post-capture RAW
counterfactual so parity can be established before switching the active meter.
"""
from pathlib import Path
import hashlib
import json
import re
import sys

VALIDATED_CPP_SHA = "3f7b696cdf33e29348d7c0532f658c11819f9b8e54772b55753e357fb6018985"

def once(s, old, new, label):
    n = s.count(old)
    if n != 1:
        raise RuntimeError(f"RAWPROXY1A {label}: expected one anchor, found {n}")
    return s.replace(old, new, 1)

def patch_capture(s):
    s = once(
        s,
        "import com.particlesdevs.photoncamera.m10r.M10RLiveMeterState;\n",
        "import com.particlesdevs.photoncamera.m10r.M10RLiveMeterState;\n"
        "import com.particlesdevs.photoncamera.m10r.M10RRawProxyMeter1A;\n",
        "CaptureController import"
    )

    s = once(
        s,
        "            cameraEventsListener.onPreviewCaptureCompleted(result);\n",
        "            cameraEventsListener.onPreviewCaptureCompleted(result);\n"
        "            maybeM10rRawProxyMeter(result);\n",
        "preview callback hook"
    )

    anchor = "    Surface surface;\n    public void createCameraPreviewSession(boolean isBurstSession) {\n"
    helper = r'''    private final CameraCaptureSession.CaptureCallback mM10rRawProxyCaptureCallback =
            new CameraCaptureSession.CaptureCallback() {
        @Override
        public void onCaptureStarted(@NonNull CameraCaptureSession session,
                                     @NonNull CaptureRequest request,
                                     long timestamp,
                                     long frameNumber) {
            M10RRawProxyMeter1A.onCaptureStarted(timestamp);
        }

        @Override
        public void onCaptureCompleted(@NonNull CameraCaptureSession session,
                                       @NonNull CaptureRequest request,
                                       @NonNull TotalCaptureResult result) {
            M10RRawProxyMeter1A.onCaptureCompleted(result);
        }

        @Override
        public void onCaptureFailed(@NonNull CameraCaptureSession session,
                                    @NonNull CaptureRequest request,
                                    @NonNull android.hardware.camera2.CaptureFailure failure) {
            M10RRawProxyMeter1A.onCaptureAborted();
        }

        @Override
        public void onCaptureSequenceAborted(@NonNull CameraCaptureSession session,
                                             int sequenceId) {
            M10RRawProxyMeter1A.onCaptureAborted();
        }
    };

    /**
     * MFM1C RAWPROXY1A diagnostic.
     * Uses the physical RAW surface already present in the session, but does not
     * add it to the repeating request. One manual-exposure RAW meter frame is
     * requested at most every 800 ms. The ordinary visible preview keeps its
     * normal repeating request and rendering.
     */
    private void maybeM10rRawProxyMeter(TotalCaptureResult previewResult) {
        if (previewResult == null
                || PhotonCamera.getSettings().selectedMode != CameraMode.PHOTO
                || mCameraDevice == null || mCaptureSession == null
                || mImageReaderRaw == null || mCameraCharacteristics == null
                || burst || mState != STATE_PREVIEW) {
            return;
        }

        Long exposureNs = previewResult.get(CaptureResult.SENSOR_EXPOSURE_TIME);
        Integer iso = previewResult.get(CaptureResult.SENSOR_SENSITIVITY);
        Integer cfa = mCameraCharacteristics.get(
                CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT);
        if (exposureNs == null || exposureNs <= 0L || iso == null || iso <= 0
                || cfa == null || cfa < 0 || cfa > 3) {
            return;
        }

        long now = System.nanoTime();
        if (!M10RRawProxyMeter1A.tryArm(now, exposureNs, iso, cfa)) return;

        try {
            CaptureRequest.Builder meter =
                    mCameraDevice.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW);
            meter.addTarget(mImageReaderRaw.getSurface());

            // Match the current preview sensor exposure instead of asking a
            // second AE loop to meter the scene independently.
            meter.set(CaptureRequest.CONTROL_AE_MODE, CaptureRequest.CONTROL_AE_MODE_OFF);
            meter.set(CaptureRequest.SENSOR_EXPOSURE_TIME, exposureNs);
            meter.set(CaptureRequest.SENSOR_SENSITIVITY, iso);

            Long frameDuration = previewResult.get(CaptureResult.SENSOR_FRAME_DURATION);
            if (frameDuration != null && frameDuration >= exposureNs) {
                meter.set(CaptureRequest.SENSOR_FRAME_DURATION, frameDuration);
            }
            Float focusDistance = previewResult.get(CaptureResult.LENS_FOCUS_DISTANCE);
            if (focusDistance != null) {
                try {
                    meter.set(CaptureRequest.LENS_FOCUS_DISTANCE, focusDistance);
                } catch (Throwable ignored) {}
            }
            try {
                meter.set(CaptureRequest.STATISTICS_LENS_SHADING_MAP_MODE,
                        CaptureRequest.STATISTICS_LENS_SHADING_MAP_MODE_OFF);
            } catch (Throwable ignored) {}

            meter.setTag("M10R_RAWPROXY1A");
            mCaptureSession.capture(meter.build(), mM10rRawProxyCaptureCallback,
                    mBackgroundHandler);
        } catch (Throwable t) {
            Log.w(TAG, "M10R RAWPROXY1A request failed: " + t);
            M10RRawProxyMeter1A.onCaptureAborted();
        }
    }

'''
    s = once(s, anchor, helper + anchor, "raw proxy capture helper")

    s = once(
        s,
        """            // METER1A freezes the latest live 22x16 Leica grid beside the still.
            M10RLiveMeterState.freezeCapture();
            // AE1B FREEZE1: bind one preview-derived M10-R decision to this still sequence.
""",
        """            // METER1A freezes the latest live 22x16 Leica grid beside the still.
            M10RLiveMeterState.freezeCapture();
            // RAWPROXY1A freezes the latest sensor-linear preview-time RAW grid for
            // diagnostic comparison only; active MFM1B still uses the GL grid.
            M10RRawProxyMeter1A.pauseAndFreezeForStill();
            // AE1B FREEZE1: bind one preview-derived M10-R decision to this still sequence.
""",
        "still freeze"
    )

    s = once(
        s,
        """            // After this, the camera will go back to the normal state of preview.
            mState = STATE_PREVIEW;
            rebuildPreviewBuilder();
""",
        """            // After this, the camera will go back to the normal state of preview.
            mState = STATE_PREVIEW;
            M10RRawProxyMeter1A.resumePreview();
            rebuildPreviewBuilder();
""",
        "preview resume"
    )
    return s

def patch_image_saver(s):
    hook = '''            if (mImage == null)
                return;
            int format = mImage.getFormat();
'''
    repl = '''            if (mImage == null)
                return;
            if (com.particlesdevs.photoncamera.m10r.M10RRawProxyMeter1A.tryConsume(
                    mImage,
                    com.particlesdevs.photoncamera.capture.CaptureController.mCameraCharacteristics)) {
                return;
            }
            int format = mImage.getFormat();
'''
    s = once(s, hook, repl, "ImageSaver active branch intercept")

    hook2 = '''            if (mImage == null)
                return;
            mImage.close();
'''
    repl2 = '''            if (mImage == null)
                return;
            if (com.particlesdevs.photoncamera.m10r.M10RRawProxyMeter1A.tryConsume(
                    mImage,
                    com.particlesdevs.photoncamera.capture.CaptureController.mCameraCharacteristics)) {
                return;
            }
            mImage.close();
'''
    s = once(s, hook2, repl2, "ImageSaver discard branch intercept")
    return s

def patch_renderer(s):
    anchor = "    private static void appendMfm1B(JSONObject d) throws Exception {\n"
    helper = r'''    private static void appendRawProxy1A(JSONObject d) throws Exception {
        M10RRawProxyMeter1A.Snapshot s = M10RRawProxyMeter1A.frozenSnapshot();
        M10RMfm1B.Decision proxy = s != null && s.valid
                ? M10RMfm1B.evaluate(s.grid) : M10RMfm1B.evaluate(null);
        M10RMfm1B.Decision raw = mfm1bRawCounterfactual(d);

        JSONObject o = new JSONObject()
                .put("enabled", true)
                .put("diagnosticOnly", true)
                .put("activeCaptureUsesRawProxy", false)
                .put("meterDomain", "preview_time_RAW_SENSOR_semantic_green_pre_lens_shading")
                .put("requestCadenceMinMs", M10RRawProxyMeter1A.MIN_INTERVAL_NS / 1000000L)
                .put("stateValid", s != null && s.valid)
                .put("stateGeneration", s != null ? s.generation : 0L)
                .put("status", s != null ? s.status : "missing")
                .put("imageTimestampNs", s != null ? s.imageTimestampNs : 0L)
                .put("requestedExposureNs", s != null ? s.requestedExposureNs : 0L)
                .put("requestedIso", s != null ? s.requestedIso : 0)
                .put("actualExposureNs", s != null ? s.actualExposureNs : 0L)
                .put("actualIso", s != null ? s.actualIso : 0)
                .put("cfa", s != null ? s.cfa : -1)
                .put("rawWidth", s != null ? s.width : 0)
                .put("rawHeight", s != null ? s.height : 0)
                .put("rowStrideBytes", s != null ? s.rowStrideBytes : 0)
                .put("pixelStrideBytes", s != null ? s.pixelStrideBytes : 0)
                .put("dynamicBlackUsed", s != null && s.dynamicBlackUsed)
                .put("dynamicWhiteUsed", s != null && s.dynamicWhiteUsed)
                .put("rawProxyDecision", mfm1bDecisionJson(proxy))
                .put("postCaptureRawCounterfactualDecision", mfm1bDecisionJson(raw));

        if (proxy != null && proxy.valid && raw != null && raw.valid) {
            o.put("proxyMinusPostRawRecommendedEv",
                        proxy.recommendedEv - raw.recommendedEv)
                    .put("proxyPostRawDecisionSignAgreement",
                        Math.signum(proxy.recommendedEv) == Math.signum(raw.recommendedEv))
                    .put("proxyPostRawWouldApplyAgreement",
                        proxy.wouldApply == raw.wouldApply)
                    .put("targetParityToleranceEv", 0.15)
                    .put("withinTargetParityTolerance",
                        Math.abs(proxy.recommendedEv - raw.recommendedEv) <= 0.15);
        }

        if (s != null && s.grid != null) {
            JSONArray rows = new JSONArray();
            for (int rr = 0; rr < M10RMfm1B.GRID_R; rr++) {
                JSONArray row = new JSONArray();
                for (int cc = 0; cc < M10RMfm1B.GRID_C; cc++) {
                    row.put(s.grid[rr * M10RMfm1B.GRID_C + cc]);
                }
                rows.put(row);
            }
            o.put("rawProxyGrid16x22", rows);
        }
        d.put("m10rRawProxy1A", o);
    }

'''
    s = once(s, anchor, helper + anchor, "renderer helper insertion")

    # Add import beside the existing MFM1B imports.
    import_anchor = "import com.particlesdevs.photoncamera.m10r.M10RMfm1BState;\n"
    if import_anchor in s:
        s = once(
            s, import_anchor,
            import_anchor + "import com.particlesdevs.photoncamera.m10r.M10RRawProxyMeter1A;\n",
            "renderer import"
        )
    elif "M10RRawProxyMeter1A" not in s:
        raise RuntimeError("RAWPROXY1A could not locate renderer import anchor")

    active_block = '''            try {
                appendMfm1B(d);
            } catch (Throwable mfm1bError) {
                d.put("m10rMfm1B", new JSONObject()
                        .put("enabled", true).put("activeCapture", true)
                        .put("status", "telemetry_failed").put("error", mfm1bError.toString()));
            }
            d.put("status", "success");
'''
    active_repl = '''            try {
                appendMfm1B(d);
            } catch (Throwable mfm1bError) {
                d.put("m10rMfm1B", new JSONObject()
                        .put("enabled", true).put("activeCapture", true)
                        .put("status", "telemetry_failed").put("error", mfm1bError.toString()));
            }
            try {
                appendRawProxy1A(d);
            } catch (Throwable rawProxy1AError) {
                d.put("m10rRawProxy1A", new JSONObject()
                        .put("enabled", true).put("diagnosticOnly", true)
                        .put("activeCaptureUsesRawProxy", false)
                        .put("status", "telemetry_failed")
                        .put("error", rawProxy1AError.toString()));
            }
            d.put("status", "success");
'''
    s = once(s, active_block, active_repl, "renderer sidecar append")
    return s

def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: fix-m10r-render2i-mfm1c-rawproxy1a.py <PhotonCamera-root>")
    root = Path(sys.argv[1]).resolve()
    repo = Path(__file__).resolve().parents[1]

    capture = root / "app/src/main/java/com/particlesdevs/photoncamera/capture/CaptureController.java"
    image_saver = root / "app/src/main/java/com/particlesdevs/photoncamera/processing/ImageSaver.java"
    renderer = root / "app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java"
    cpp = root / "app/src/main/cpp/m10rRender.cpp"
    gradle = root / "app/build.gradle"
    for p in (capture, image_saver, renderer, cpp, gradle):
        if not p.is_file():
            raise RuntimeError("RAWPROXY1A missing " + str(p))

    cpp_before = hashlib.sha256(cpp.read_bytes()).hexdigest()
    if cpp_before != VALIDATED_CPP_SHA:
        raise RuntimeError("RAWPROXY1A refuses changed RENDER2G native source: " + cpp_before)

    # Require PORT1A first so the live RAW proxy and post-capture oracle share
    # the same semantic-green CFA interpretation on every lens.
    r0 = renderer.read_text()
    for marker in [
        'cfaAwareGreenSelection", true',
        'cfaAuthority", "active_physical_Camera2_characteristics"',
        'targetRendererLensIndependent", true',
        'hsmRuntimeDependency", false',
    ]:
        if marker not in r0:
            raise RuntimeError("RAWPROXY1A requires PORT1A marker: " + marker)

    capture.write_text(patch_capture(capture.read_text()))
    image_saver.write_text(patch_image_saver(image_saver.read_text()))
    renderer.write_text(patch_renderer(renderer.read_text()))

    src = repo / "android/M10RRawProxyMeter1A.java"
    if not src.is_file():
        raise RuntimeError("RAWPROXY1A source state missing")
    (renderer.parent / "M10RRawProxyMeter1A.java").write_bytes(src.read_bytes())

    g = gradle.read_text()
    versions = re.findall(r"versionName\s+['\"]([^'\"]+)['\"]", g)
    if len(versions) != 1 or versions[0] != "0.97-m10r2h-port1a":
        raise RuntimeError("RAWPROXY1A unexpected PORT1A versionName: " + repr(versions))
    g = g.replace(versions[0], "0.97-m10r2i-mfm1c-rawproxy1a", 1)
    gradle.write_text(g)

    # Fail closed: this build gathers evidence only.
    iso = root / "app/src/main/java/com/particlesdevs/photoncamera/processing/parameters/IsoExpoSelector.java"
    iso_text = iso.read_text()
    if "M10RMfm1B.evaluate(meterSnapshot.linearGrid)" not in iso_text:
        raise RuntimeError("RAWPROXY1A active MFM1B GL-grid path unexpectedly changed")
    if "M10RRawProxyMeter1A" in iso_text:
        raise RuntimeError("RAWPROXY1A must not feed active IsoExpoSelector yet")

    cpp_after = hashlib.sha256(cpp.read_bytes()).hexdigest()
    if cpp_after != cpp_before or cpp_after != VALIDATED_CPP_SHA:
        raise RuntimeError("RAWPROXY1A changed frozen RENDER2G native pixels")

    proof = {
        "schema": "M10R_RENDER2I_MFM1C_RAWPROXY1A_PATCH_V1",
        "baseline": "RENDER2H_PORT1A_on_RENDER2G_YA_TOPOLOGY1A_MFM1B",
        "versionName": "0.97-m10r2i-mfm1c-rawproxy1a",
        "diagnosticOnly": True,
        "activeCaptureUsesRawProxy": False,
        "activeMfm1BSourceUnchanged": "GL_SurfaceTexture_linearized_grid",
        "probeSource": "preview_time_RAW_SENSOR_same_configured_physical_RAW_surface",
        "probeExposure": "manual_match_to_current_preview_exposure_and_iso",
        "probeCadenceMinMs": 800,
        "probeGrid": "16x22_semantic_green_pre_lens_shading",
        "probeCfaAuthority": "active_physical_Camera2_characteristics",
        "postCaptureOracle": "PORT1A_semantic_green_pre_lens_shading",
        "parityTargetEv": 0.15,
        "rendererNativeChanged": False,
        "render2gPhotographicCoreChanged": False,
        "mfm1bFormulaChanged": False,
        "captureExposureChangedByRawProxy": False,
        "cobaltRuntimeDependency": False,
        "hsmRuntimeDependency": False,
        "singleRawStill": True,
        "hdrEnabled": False,
        "deviceValidated": False,
        "productionPromoted": False
    }
    (root / "M10R_RENDER2I_MFM1C_RAWPROXY1A_PROVENANCE.json").write_text(
        json.dumps(proof, indent=2) + "\n"
    )
    print(json.dumps(proof, indent=2))

if __name__ == "__main__":
    main()
