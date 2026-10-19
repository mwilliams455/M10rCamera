package com.particlesdevs.photoncamera.processing;

import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.CaptureResult;

import com.particlesdevs.photoncamera.processing.processor.RawVideoProcessor;
import com.particlesdevs.photoncamera.util.Log;
import com.particlesdevs.photoncamera.api.ParseExif;
import com.particlesdevs.photoncamera.app.PhotonCamera;
import com.particlesdevs.photoncamera.control.GyroBurst;
import com.particlesdevs.photoncamera.processing.processor.HdrxProcessor;
import com.particlesdevs.photoncamera.processing.processor.UnlimitedProcessor;
import com.particlesdevs.photoncamera.m10r.M10RNativeRenderer;
import com.particlesdevs.photoncamera.m10r.M10RStageTiming3E;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.concurrent.locks.LockSupport;

public class DefaultSaver extends SaverImplementation {
    private static final String TAG = "DefaultSaver";
    // Bind renderer choice to this saver, not a tab selected during its save.
    private final com.particlesdevs.photoncamera.api.CameraMode captureMode;
    private final boolean m10rStillCapture;
    final UnlimitedProcessor mUnlimitedProcessor;
    final RawVideoProcessor mRawVideoProcessor;
    final HdrxProcessor hdrxProcessor;

    public DefaultSaver(ProcessingEventsListener processingEventsListener) {
        super(processingEventsListener);
        captureMode = PhotonCamera.getSettings().selectedMode;
        m10rStillCapture = com.particlesdevs.photoncamera.api.CameraMode.usesM10RStillPipeline(captureMode);
        this.hdrxProcessor = new HdrxProcessor(processingEventsListener);
        this.mUnlimitedProcessor = new UnlimitedProcessor(processingEventsListener);
        this.mRawVideoProcessor = new RawVideoProcessor(processingEventsListener);
    }

    public void runRaw(int imageFormat, CameraCharacteristics characteristics, CaptureResult captureResult, CaptureRequest captureRequest, ArrayList<GyroBurst> burstShakiness, int cameraRotation, HashMap<Long, Double> exposures) {
        super.runRaw(imageFormat, characteristics, captureResult,captureRequest, burstShakiness, cameraRotation, exposures);
        //Wait for one frame at least. Park (not spin): the producers are
        //camera threads that don't all notify, so wait/notify would risk a
        //missed wakeup; parking yields the core with identical semantics.
        Log.d(TAG, "Acquiring:" + IMAGE_BUFFER.size());
        while (bufferLock || IMAGE_BUFFER.isEmpty()) {
            LockSupport.parkNanos(100_000);
        }
        Log.d(TAG, "Acquired:" + IMAGE_BUFFER.size());
        bufferLock = true;
        Log.d(TAG,"Size:"+IMAGE_BUFFER.size());
        // M10R CAPTURE1B: one RAW frame -> untouched DNG + Cobalt-free native-source M10-R C JPEG.
        if (m10rStillCapture) {
            long saveStartNs3E = System.nanoTime();
            M10RStageTiming3E saveTiming3E = new M10RStageTiming3E("savePathSetup", saveStartNs3E);
            Path capture1Dng = ImagePath.newDNGFilePath();
            String capture1DngName = capture1Dng.getFileName().toString();
            String capture1Stem = capture1DngName.toLowerCase(java.util.Locale.US).endsWith(".dng")
                    ? capture1DngName.substring(0, capture1DngName.length() - 4)
                    : capture1DngName;
            // JPEGSAVE1: same proven-writable directory + same stem + explicit MIME suffix.
            Path capture1Jpeg = capture1Dng.resolveSibling(capture1Stem + ".jpg");
            ImageFrame capture1Frame = IMAGE_BUFFER.get(0);
            boolean dngSaved = false;
            boolean jpegSaved = false;
            M10RNativeRenderer.Result capture1b = null;
            try {
                // DEVICE1: render first to avoid overlapping DNG-creation memory with the
                // full-resolution OpenCV/Bitmap render. The RAW bytes are read-only here.
                try {
                    capture1Frame.requireM10rRaw16();
                    M10RNativeRenderer.persistBreadcrumb(capture1Dng, "before_render");
                    saveTiming3E.next("renderCall");
                    capture1b = M10RNativeRenderer.render(
                            capture1Frame, characteristics, captureResult, captureRequest, cameraRotation);
                    saveTiming3E.next("postRenderBookkeeping");
                    M10RNativeRenderer.persistBreadcrumb(capture1Dng, "after_render");
                    capture1b.diagnostics.put("stillModes3A", new org.json.JSONObject()
                            .put("revision", "M10R_STILLMODES3A_PHOTO_MOTION")
                            .put("captureMode", captureMode.name())
                            .put("photographicRawFrames", 1)
                            .put("bufferedZslBurst", false)
                            .put("sameM10rExposurePolicy", true));
                    capture1b.diagnostics.put("dngPath", capture1Dng.toString());
                    capture1b.diagnostics.put("jpegPath", capture1Jpeg.toString());
                    capture1b.diagnostics.put("device1RenderBeforeDng", true);
                    capture1b.diagnostics.put("m10rPhotonUpstream", com.particlesdevs.photoncamera.m10r.M10RUpstream1A.REVISION);
                    capture1b.diagnostics.put("photonUpstreamCommit", com.particlesdevs.photoncamera.m10r.M10RUpstream1A.PHOTON_COMMIT);
                    capture1b.diagnostics.put("rawBufferPackedBits", capture1Frame.packedBits);
                    capture1b.diagnostics.put("rawBufferCapacityBytes", capture1Frame.buffer.capacity());
                    capture1b.diagnostics.put("jpegSavePolicy", "m10r_jpegsave1_same_dng_dir_explicit_jpg_best_effort_exif");
                    capture1b.diagnostics.put("jpegParent", String.valueOf(capture1Jpeg.getParent()));
                    Log.d(TAG, "M10-R CAPTURE1B JPEGSAVE1 publishing JPEG: " + capture1Jpeg);
                    saveTiming3E.next("jpegEncodeWriteAndExif");
                    jpegSaved = ImageSaver.Util.saveBitmapAsJPGM10R(
                            capture1Jpeg, capture1b.bitmap, 95,
                            ParseExif.parse(captureResult, captureRequest));
                    saveTiming3E.next("postJpegBookkeeping");
                    capture1b.diagnostics.put("jpegSaved", jpegSaved);
                    M10RNativeRenderer.persistBreadcrumb(capture1Dng, jpegSaved ? "after_jpeg_saved" : "after_jpeg_failed");
                    processingEventsListener.notifyImageSavedStatus(jpegSaved, capture1Jpeg);
                } catch (Throwable renderError) {
                    saveTiming3E.next("renderOrJpegFailureHandling");
                    Log.e(TAG, "M10-R CAPTURE1B DEVICE1 renderer failed; DNG will still be saved", renderError);
                    if (capture1b != null) {
                        try { capture1b.diagnostics.put("rendererError", renderError.toString()); } catch (Throwable ignored) {}
                    } else {
                        M10RNativeRenderer.persistFailureDiagnostics(
                                capture1Dng, renderError, capture1Frame, characteristics);
                    }
                }

                // DNG remains unconditional and uses the same untouched single RAW frame.
                M10RNativeRenderer.persistBreadcrumb(capture1Dng, "before_dng_save");
                saveTiming3E.next("dngEncodeAndWrite");
                dngSaved = ImageSaver.Util.saveSingleRawM10RPhysicalCfa(
                        capture1Dng, capture1Frame, characteristics, captureResult, captureRequest, cameraRotation);
                saveTiming3E.next("postDngBookkeeping");
                M10RNativeRenderer.persistBreadcrumb(capture1Dng, dngSaved ? "after_dng_saved" : "after_dng_failed");
                processingEventsListener.notifyImageSavedStatus(dngSaved, capture1Dng);
                if (capture1b != null) {
                    try {
                        capture1b.diagnostics.put("dngSaved", dngSaved);
                        capture1b.diagnostics.put("dngCfaAuthority",
                                "physical_camera2_characteristics");
                        float[] manualDngNeutral = com.particlesdevs.photoncamera.m10r.M10RSourceWhite3N
                                .manualNeutral(captureRequest);
                        capture1b.diagnostics.put("dngWhiteBalance3O", new org.json.JSONObject()
                                .put("revision", "M10R_DNG_REQUEST_WHITE3O")
                                .put("saved", dngSaved)
                                .put("authority", manualDngNeutral == null
                                        ? "capture_result_SENSOR_NEUTRAL_COLOR_POINT"
                                        : "capture_request_COLOR_CORRECTION_GAINS")
                                .put("manualAsShotNeutral", manualDngNeutral == null
                                        ? org.json.JSONObject.NULL : new org.json.JSONArray(manualDngNeutral))
                                .put("phoneRawAndCalibrationRetained", true)
                                .put("syntheticM10rNeutralWrittenToPhoneRaw", false));
                        capture1b.diagnostics.put("savePathTiming3E", saveTiming3E.finish().json("RAW_acquired_save_branch_through_before_sidecar")
                                .put("rendererTiming3EIsNestedInRenderCall", true)
                                .put("excludes", "shutter_AE_RAW_queue_wait_sidecar_write_final_release"));
                    } catch (Throwable ignored) {}
                    long sidecarStartNs3E = System.nanoTime();
                    boolean diagSaved = M10RNativeRenderer.persistDiagnostics(
                                capture1Jpeg, capture1b.diagnostics);
                    Log.d(TAG, "M10R_SAVE_TIMING3E sidecarWriteMs=" + (System.nanoTime() - sidecarStartNs3E) / 1_000_000.0);
                        Log.d(TAG, "M10-R DIAG1C JSON saved=" + diagSaved
                                + " siblingOf=" + capture1Jpeg);
                        if (!diagSaved) {
                            Log.e(TAG, "M10-R DIAG1C JSON WRITE FAILED; see M10RNativeRenderer log payload");
                        }
                }
            } finally {
                try {
                    M10RNativeRenderer.persistBreadcrumb(capture1Dng, "capture_finally_release");
                    capture1Frame.close();
                } finally {
                    IMAGE_BUFFER.clear();
                    bufferLock = false;
                }
            }
            Log.d(TAG, "M10R_SAVE_TIMING3E saveBranchThroughReleaseMs=" + (System.nanoTime() - saveStartNs3E) / 1_000_000.0);
            // Completion is observable only after the RAW owner has been released.
            processingEventsListener.onProcessingFinished(
                    jpegSaved ? "M10-R JPEG saved" : (dngSaved ? "M10-R DNG saved; JPEG failed" : "M10-R save failed"));
            return;
        }
        /*if (PhotonCamera.getSettings().frameCount == 1) {
            Path dngFile = ImagePath.newDNGFilePath();
            Log.d(TAG, "Size:" + IMAGE_BUFFER.size());
            boolean imageSaved = ImageSaver.Util.saveSingleRaw(dngFile, IMAGE_BUFFER.get(0),
                    characteristics, captureResult, cameraRotation);
            processingEventsListener.notifyImageSavedStatus(imageSaved, dngFile);
            processingEventsListener.onProcessingFinished("Saved Unprocessed RAW");
            IMAGE_BUFFER.clear();
            bufferLock = false;
            return;
        }*/
        Path dngFile = ImagePath.newDNGFilePath();
        Path imageFile = ImagePath.newImageFilePath();
        //Remove broken images
            /*for(int i =0; i<IMAGE_BUFFER.size();i++){
                try{
                    IMAGE_BUFFER.get(i).getFormat();
                } catch (IllegalStateException e){
                    IMAGE_BUFFER.remove(i);
                    i--;
                    Log.d(TAG,"IMGBufferSize:"+IMAGE_BUFFER.size());
                    e.printStackTrace();
                }
            }*/
        hdrxProcessor.configure(
                PhotonCamera.getSettings().alignAlgorithm,
                PhotonCamera.getSettings().rawSaver,
                PhotonCamera.getSettings().selectedMode
        );
        ArrayList<ImageFrame> slicedBuffer = new ArrayList<>();
        ArrayList<ImageFrame> imagebuffer = new ArrayList<>();
        for(int i =0; i<frameCount;i++){
            slicedBuffer.add(IMAGE_BUFFER.get(i));
        }
        for(int i = frameCount; i<IMAGE_BUFFER.size();i++){
            imagebuffer.add(IMAGE_BUFFER.get(i));
        }
        // Frames beyond frameCount are never merged: both capture paths
        // clear() this list before refilling, so anything retained here is
        // orphaned until GC (or heads the next burst with stale metadata).
        // Close deterministically instead (~122 MB per frame at 64 MP).
        // close() is idempotent; the merged set above is untouched.
        long tailBytes = 0;
        for (ImageFrame tail : imagebuffer) {
            if (tail != null && tail.buffer != null) {
                tailBytes += tail.buffer.capacity();
                tail.close();
            }
        }
        if (tailBytes > 0) {
            Log.d(TAG, "Closed tail frames: " + (tailBytes / 1048576) + "MB freed");
        }
        IMAGE_BUFFER.clear();
        IMAGE_BUFFER = imagebuffer;
        bufferLock = false;
        for(int i =0; i<slicedBuffer.size();i++){
            if (slicedBuffer.get(i) == null || slicedBuffer.get(i).buffer == null) {
                slicedBuffer.remove(i);
                i--;
                Log.d(TAG, "IMGBufferSize:" + slicedBuffer.size());
            }
        }

        Log.d(TAG,"moving images");
        //Log.d(TAG,"moved images:"+slicedBuffer.size());
        hdrxProcessor.start(
                dngFile,
                imageFile,
                ParseExif.parse(captureResult, captureRequest),
                burstShakiness,
                slicedBuffer,
                exposures,
                imageFormat,
                cameraRotation,
                characteristics,
                captureResult,
                captureRequest,
                processingCallback
        );
        slicedBuffer.clear();
    }

    public void processStart(int imageFormat, CameraCharacteristics characteristics, CaptureResult captureResult, CaptureRequest captureRequest, int cameraRotation) {
        super.processStart(imageFormat, characteristics, captureResult, captureRequest, cameraRotation);
        Path dngFile = ImagePath.newDNGFilePath();
        Path jpgFile = ImagePath.newImageFilePath();
        switch (PhotonCamera.getSettings().selectedMode) {
            case UNLIMITED:
                mUnlimitedProcessor.configure(PhotonCamera.getSettings().rawSaver);
                mUnlimitedProcessor.unlimitedStart(
                        dngFile,
                        jpgFile,
                        ParseExif.parse(captureResult, captureRequest),
                        characteristics,
                        captureResult,
                        captureRequest,
                        cameraRotation,
                        processingCallback
                );
                break;
            case RAWVIDEO:
                mRawVideoProcessor.videoStart(
                        ImagePath.getNewVideoFolderPath(),
                        ParseExif.parse(captureResult, captureRequest),
                        characteristics,
                        captureResult,
                        captureRequest,
                        cameraRotation,
                        processingCallback
                );
                break;
        }
    }

    public void videoCaptureResult(CaptureResult result) {
        mRawVideoProcessor.videoCaptureResult(result);
    }

    public void processEnd() {
        switch (PhotonCamera.getSettings().selectedMode){
            case UNLIMITED:
                mUnlimitedProcessor.unlimitedEnd();
                break;
            case RAWVIDEO:
                mRawVideoProcessor.videoEnd();
                break;
        }
    }
}
