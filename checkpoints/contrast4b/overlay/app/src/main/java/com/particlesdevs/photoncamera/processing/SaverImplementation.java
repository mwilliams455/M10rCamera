package com.particlesdevs.photoncamera.processing;

import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.CaptureResult;
import android.media.Image;
import android.media.ImageReader;

import android.graphics.Rect;
import com.particlesdevs.photoncamera.app.PhotonCamera;
import com.particlesdevs.photoncamera.capture.CaptureController;
import com.particlesdevs.photoncamera.capture.ZoomController;
import com.particlesdevs.photoncamera.control.GyroBurst;
import com.particlesdevs.photoncamera.processing.processor.ProcessorBase;
import com.particlesdevs.photoncamera.util.Allocator;

import java.util.ArrayList;
import java.util.HashMap;

public class SaverImplementation {
    private static final String TAG = "SaverImplementation";
    public volatile boolean bufferLock = true;
    public volatile boolean newBurst = false;
    public static ArrayList<ImageFrame> IMAGE_BUFFER = new ArrayList<>();
    public int frameCount = 0;
    private int imageFormat;
    public final ProcessingEventsListener processingEventsListener;

    public ImageFrame getFrame(Image image){
        try {
            image.getFormat();
        } catch (Exception e) {
            // This image is not valid, skip it
            return null;
        }
        com.particlesdevs.photoncamera.m10r.M10RRawBinding4A.ImageEvidence original4A = null;
        try { original4A = com.particlesdevs.photoncamera.m10r.M10RRawBinding4A.ImageEvidence.captureOriginal(image); }
        catch (RuntimeException | LinkageError | OutOfMemoryError ignored) { /* diagnostic only */ }
        int width;
        int height;
        int offset = 0;
        int capacity = image.getPlanes()[0].getBuffer().capacity();
        int rowStride = image.getPlanes()[0].getRowStride();
        int pixelStride = image.getPlanes()[0].getPixelStride();
        if(image.getFormat() == 0x25){
            width = image.getWidth();
            height = image.getHeight();
        } else {
            width = rowStride / pixelStride;
            height = image.getHeight();
        }

        // Digital zoom: crop a rectangular region of the RAW buffer that the
        // preview already reflects. This crops both the stored JPEG and RAW/DNG
        // because both derive from this single ImageFrame.
        CaptureController captureController = PhotonCamera.getCaptureController();
        if (captureController != null && captureController.zoomController.isZoomed()) {
            int logicalW = image.getWidth();
            int logicalH = image.getHeight();
            ZoomController.CropRegion cropRegion =
                    captureController.zoomController.computeCropRegion(logicalW, logicalH);
            boolean useZoomCrop = cropRegion.width < logicalW || cropRegion.height < logicalH;
            if (useZoomCrop) {
                boolean cropBinning4A = PhotonCamera.getSettings().binning;
                ImageFrame frame = ImageFrame.fromCrop(
                        image.getPlanes()[0].getBuffer(), image.getFormat(),
                        logicalW, logicalH, rowStride, pixelStride, cropRegion,
                        cropBinning4A);
                if (frame == null) return null;
                frame.timestamp = image.getTimestamp();
                try {
                    int factor4A = cropBinning4A ? 2 : 1;
                    appendRawEvidence4A(frame, original4A, cropBinning4A, "digital_zoom_crop",
                            new Rect(frame.cropOriginX, frame.cropOriginY,
                                    frame.cropOriginX + frame.width * factor4A,
                                    frame.cropOriginY + frame.height * factor4A));
                } catch (RuntimeException | LinkageError | OutOfMemoryError ignored) { /* diagnostic only */ }
                return frame;
            }
        }

        if(PhotonCamera.getSettings().aspect169){
            if(width > height){
                height = width * 9 / 16;
                int offsetH;
                if (ImageSaver.SETTINGS.cropType) {
                    // Do nothing
                } else {
                    offsetH = (image.getHeight() - height) / 2;
                    offsetH -= offsetH % 2;
                    offset = rowStride * offsetH;
                }
                capacity = rowStride * height;
            }
        }
        boolean doBinning = PhotonCamera.getSettings().binning;
        ImageFrame frame;
        synchronized (Allocator.class) {
            Allocator.binning = doBinning;
            frame = new ImageFrame(image.getPlanes()[0].getBuffer(), image.getFormat(), width, rowStride, offset, capacity);
        }
        frame.timestamp = image.getTimestamp();
        if (doBinning) {
            frame.width = width / 2;
            frame.height = height / 2;
        } else {
            frame.width = width;
            frame.height = height;
        }
        try {
            int top4A = rowStride > 0 ? offset / rowStride : 0;
            appendRawEvidence4A(frame, original4A, doBinning,
                    offset != 0 || height != image.getHeight() ? "aspect_crop_copy" : "full_buffer_copy",
                    new Rect(0, top4A, Math.min(width, image.getWidth()), top4A + height));
        } catch (RuntimeException | LinkageError | OutOfMemoryError ignored) { /* diagnostic only */ }
        return frame;
    }

    private static void appendRawEvidence4A(ImageFrame frame,
            com.particlesdevs.photoncamera.m10r.M10RRawBinding4A.ImageEvidence original,
            boolean appBinning, String conversion, Rect sourceCrop) {
        try {
            if (original != null) frame.rawBinding4A = original.withConversion(
                    frame, appBinning, conversion, sourceCrop);
        } catch (RuntimeException | LinkageError | OutOfMemoryError ignored) { /* diagnostic only */ }
    }

    final ProcessorBase.ProcessingCallback processingCallback = new ProcessorBase.ProcessingCallback() {
        @Override
        public void onStarted() {
            CaptureController.isProcessing = true;
        }

        @Override
        public void onFailed() {
            onFinished();
        }

        @Override
        public void onFinished() {
            //clearImageReader(imageReader);
            CaptureController.isProcessing = false;
        }
    };
    public SaverImplementation(ProcessingEventsListener processingEventsListener){
        this.processingEventsListener = processingEventsListener;
    }

    public void addImage(Image image) {
        //image.close();
    }

    void addRAW10(Image image){
        //image.close();
    }
    protected void clearImageReader(ImageReader reader) {
        while (true) {
            try {
                reader.acquireNextImage().close();
            } catch (Exception ignored){
                break;
            }
        }
        //reader.close();
    }

    public void runRaw(int imageFormat, CameraCharacteristics characteristics, CaptureResult captureResult, CaptureRequest captureRequest, ArrayList<GyroBurst> burstShakiness, int cameraRotation, HashMap<Long, Double> exposures) {
        this.imageFormat = imageFormat;
    }
    public void processStart(int imageFormat, CameraCharacteristics characteristics, CaptureResult captureResult, CaptureRequest captureRequest, int cameraRotation) {
        this.imageFormat = imageFormat;
    }
    public void processEnd(){
    }
}
