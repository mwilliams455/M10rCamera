package com.particlesdevs.photoncamera.processing;

import android.graphics.Bitmap;
import android.graphics.ImageFormat;
import android.graphics.Point;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.CaptureResult;
import android.media.Image;
import android.media.ImageReader;
import com.particlesdevs.photoncamera.util.Log;

import androidx.exifinterface.media.ExifInterface;

import com.particlesdevs.photoncamera.api.ParseExif;
import com.particlesdevs.photoncamera.control.GyroBurst;
import com.particlesdevs.photoncamera.processing.render.Parameters;

import java.io.IOException;
import java.io.OutputStream;
import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;

import com.particlesdevs.photoncamera.settings.TunableInjector;

import static com.particlesdevs.photoncamera.processing.ImageSaverSelector.getImageSaver;
import static com.particlesdevs.photoncamera.processing.ImageSaverSelector.init;

public class ImageSaver {
    /**
     * Image frame buffer
     */
    public static final int JPG_QUALITY = 98;
    private static final String TAG = "ImageSaver";

    public static final ImageSaverSettings SETTINGS = new ImageSaverSettings();

    public SaverImplementation implementation;
    private int imageFormat;
    private int frameCounter = 0;
    private int desiredFrameCount = 0;
    public boolean newBurst = false;

    public void setFrameCount(int desiredFrameCount){
        this.desiredFrameCount = desiredFrameCount;
    }

    public void setImageFormat(int imageFormat) {
        this.imageFormat = imageFormat;
    }

    public void updateFrameCount(int desiredFrameCount){
        this.desiredFrameCount = desiredFrameCount;
        this.implementation.frameCount = desiredFrameCount;
    }

    public synchronized int bufferSize(){
        return SaverImplementation.IMAGE_BUFFER.size();
    }

    public ImageSaver(ProcessingEventsListener processingEventsListener) {
        implementation = new DefaultSaver(processingEventsListener);
        init(implementation);
        TunableInjector.inject(SETTINGS);
    }

    public void initProcess(ImageReader mReader) {
        Log.v(TAG, "initProcess()");
        if((frameCounter < desiredFrameCount) || desiredFrameCount == -1) {
            Log.v(TAG, "initProcess() : called from \"" + Thread.currentThread().getName() + "\" Thread");
            Image mImage;
            try {
                mImage = mReader.acquireNextImage();
            } catch (Exception ignored) {
                return;
            }
            if (mImage == null)
                return;
            int format = mImage.getFormat();
            imageFormat = mReader.getImageFormat();
            implementation = getImageSaver(format, implementation);
            Log.d(TAG,"Implementation:" + implementation);
            implementation.frameCount = desiredFrameCount;
            implementation.newBurst = newBurst;
            implementation.addImage(mImage);
        } else {
            Image mImage;
            try {
                mImage = mReader.acquireNextImage();
            } catch (Exception ignored) {
                return;
            }
            if (mImage == null)
                return;
            mImage.close();
        }
        frameCounter++;
    }

    /** The E1C router has already acquired this frame; ownership transfers to the original saver. */
    public synchronized void initOwnedRaw1C(ImageReader reader,Image image) {
        if(image==null)return;
        try {
            if((frameCounter<desiredFrameCount)||desiredFrameCount==-1){
                int format=image.getFormat();imageFormat=reader.getImageFormat();
                implementation=getImageSaver(format,implementation);
                implementation.frameCount=desiredFrameCount;implementation.newBurst=newBurst;
                implementation.addImage(image);
            }else image.close();
            frameCounter++;
        } catch (RuntimeException | Error e) {
            image.close();
            throw e;
        }
    }

    /** PHOTO owns the shared buffer until this cleanup completes. */
    public synchronized void discardRaw1H() {
        try {
            for (ImageFrame frame : SaverImplementation.IMAGE_BUFFER) {
                if (frame != null) {
                    try { frame.close(); }
                    catch (RuntimeException e) { Log.e(TAG, "RAW cleanup failed", e); }
                }
            }
        } finally {
            SaverImplementation.IMAGE_BUFFER.clear();
            if (implementation != null) implementation.bufferLock = false;
        }
    }

    public void runRaw(CameraCharacteristics characteristics, CaptureResult captureResult, CaptureRequest captureRequest, ArrayList<GyroBurst> burstShakiness, int cameraRotation, HashMap<Long, Double> exposures) {
        TunableInjector.inject(SETTINGS);
        implementation.runRaw(imageFormat,characteristics,captureResult, captureRequest,burstShakiness,cameraRotation, exposures);
    }

    public void processStart(CameraCharacteristics characteristics, CaptureResult captureResult, CaptureRequest captureRequest, int cameraRotation) {
        TunableInjector.inject(SETTINGS);
        implementation = ImageSaverSelector.getImageSaver(ImageFormat.RAW_SENSOR, implementation);
        implementation.processStart(imageFormat,characteristics,captureResult, captureRequest,cameraRotation);
    }

    public void processEnd() {
        implementation.processEnd();
    }

    /** Feeds per-frame capture results to the RAW video processor (metadata). */
    public void videoCaptureResult(CaptureResult captureResult) {
        if (implementation instanceof DefaultSaver) {
            ((DefaultSaver) implementation).videoCaptureResult(captureResult);
        }
    }

    public static class Util {
        public static boolean saveBitmapAsJPG(Path fileToSave, Bitmap img, int jpgQuality, ParseExif.ExifData exifData) {
            exifData.COMPRESSION = String.valueOf(jpgQuality);
            if (img != null && !img.isRecycled()) {
                exifData.IMAGE_WIDTH = String.valueOf(img.getWidth());
                exifData.IMAGE_LENGTH = String.valueOf(img.getHeight());
            }
            try {
                OutputStream outputStream = Files.newOutputStream(fileToSave);
                img.compress(Bitmap.CompressFormat.JPEG, jpgQuality, outputStream);
                outputStream.flush();
                outputStream.close();
                img.recycle();
                ExifInterface inter = ParseExif.setAllAttributes(fileToSave.toFile(), exifData);
                inter.saveAttributes();
                return true;
            } catch (IOException e) {
                e.printStackTrace();
                return false;
            }
        }

        /**
         * CAPTURE1B JPEGSAVE1 publication primitive. JPEG byte persistence is the
         * success criterion; EXIF finalisation is best effort and cannot turn a
         * valid JPEG into a user-visible save failure.
         */
        public static boolean saveBitmapAsJPGM10R(Path fileToSave, Bitmap img, int jpgQuality, ParseExif.ExifData exifData) {
            if (fileToSave == null || img == null) {
                Log.e(TAG, "M10-R JPEGSAVE1 invalid JPEG arguments");
                return false;
            }
            boolean bytesSaved = false;
            try {
                Path parent = fileToSave.getParent();
                if (parent != null) Files.createDirectories(parent);
                try (OutputStream outputStream = Files.newOutputStream(fileToSave)) {
                    bytesSaved = img.compress(Bitmap.CompressFormat.JPEG, jpgQuality, outputStream);
                    outputStream.flush();
                }
                if (!bytesSaved || !Files.exists(fileToSave) || Files.size(fileToSave) <= 0L) {
                    Log.e(TAG, "M10-R JPEGSAVE1 JPEG encoder/write produced no bytes: " + fileToSave);
                    return false;
                }
                if (exifData != null) {
                    try {
                        exifData.COMPRESSION = String.valueOf(jpgQuality);
                        ExifInterface inter = ParseExif.setAllAttributes(fileToSave.toFile(), exifData);
                        inter.saveAttributes();
                    } catch (Exception exifError) {
                        Log.e(TAG, "M10-R JPEGSAVE1 EXIF finalisation failed but JPEG bytes are preserved: "
                                + Log.getStackTraceString(exifError));
                    }
                }
                Log.d(TAG, "M10-R JPEGSAVE1 JPEG saved bytes=" + Files.size(fileToSave)
                        + " path=" + fileToSave);
                return true;
            } catch (Exception saveError) {
                Log.e(TAG, "M10-R JPEGSAVE1 JPEG byte save failed path=" + fileToSave + " "
                        + Log.getStackTraceString(saveError));
                return false;
            } finally {
                try {
                    if (!img.isRecycled()) img.recycle();
                } catch (Throwable ignored) {}
            }
        }

        /*public static boolean saveBitmapAsAVIF(Path fileToSave, Bitmap img, int jpgQuality, ParseExif.ExifData exifData) {
            exifData.COMPRESSION = String.valueOf(jpgQuality);
            try {
                OutputStream outputStream = Files.newOutputStream(fileToSave);
                //img.compress(Bitmap.CompressFormat.JPEG, jpgQuality, outputStream);
                HeifCoder coder = new HeifCoder();
                var buffer = coder.encodeAvif(img, jpgQuality, PreciseMode.LOSSY, AvifSpeed.EIGHT);
                outputStream.write(buffer);
                outputStream.flush();
                outputStream.close();
                img.recycle();
                //ExifInterface inter = ParseExif.setAllAttributes(fileToSave.toFile(), exifData);
                //inter.saveAttributes();
                return true;
            } catch (IOException e) {
                //e.printStackTrace();
                Log.d(TAG,"AVIF save error:"+Log.getStackTraceString(e));
                return false;
            }
        }*/

        public static boolean saveBitmapAsPNG(Path fileToSave, Bitmap img, int pngQuality, ParseExif.ExifData exifData) {
            try {
                OutputStream outputStream = Files.newOutputStream(fileToSave);
                img.compress(Bitmap.CompressFormat.PNG, pngQuality, outputStream);
                outputStream.flush();
                outputStream.close();
                img.recycle();
                ExifInterface inter = ParseExif.setAllAttributes(fileToSave.toFile(), exifData);
                inter.saveAttributes();
                return true;
            } catch (IOException e) {
                e.printStackTrace();
                return false;
            }
        }

        public static boolean saveStackedRaw(Path dngFilePath,
                                             ByteBuffer buffer, Parameters parameters) {
            return saveSingleRaw(dngFilePath, buffer, parameters);
        }
        public static boolean saveSingleRaw(Path dngFilePath,
                                            ImageFrame image,
                                            CameraCharacteristics characteristics,
                                            CaptureResult captureResult,
                                            int cameraRotation) {
            return saveSingleRawInternal(dngFilePath, image, characteristics, captureResult,
                    cameraRotation, false);
        }

        /**
         * M10R PORT1A DNG path. The active physical Camera2 CFA is authoritative
         * for the DNG mosaic tag, matching the source lattice consumed by the
         * M10-R renderer. Ordinary Photon saveSingleRaw behavior stays unchanged.
         */
        public static boolean saveSingleRawM10RPhysicalCfa(Path dngFilePath,
                                                           ImageFrame image,
                                                           CameraCharacteristics characteristics,
                                                           CaptureResult captureResult,
                                                           int cameraRotation) {
            return saveSingleRawInternal(dngFilePath, image, characteristics, captureResult,
                    cameraRotation, true);
        }

        private static boolean saveSingleRawInternal(Path dngFilePath,
                                                     ImageFrame image,
                                                     CameraCharacteristics characteristics,
                                                     CaptureResult captureResult,
                                                     int cameraRotation,
                                                     boolean physicalCfaAuthority) {
            if (physicalCfaAuthority) {
                try { image.requireM10rRaw16(); }
                catch (IllegalArgumentException invalidRaw) {
                    Log.e(TAG, "M10-R DNG rejected invalid RAW16 layout", invalidRaw);
                    return false;
                }
            }
            Parameters parameters = new Parameters();

            parameters.FillConstParameters(characteristics, new Point(image.width, image.height));
            if (physicalCfaAuthority && characteristics != null) {
                Integer physicalCfa = characteristics.get(
                        CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT);
                if (physicalCfa != null && physicalCfa >= 0 && physicalCfa <= 3) {
                    parameters.cfaPattern = (byte) (int) physicalCfa;
                }
            }
            parameters.setCropDetails(image.cropOriginX, image.cropOriginY);
            if (image.fullWidth > 0 && image.fullHeight > 0) {
                parameters.setFullRawSize(image.fullWidth, image.fullHeight);
            }
            int iso = captureResult.get(CaptureResult.SENSOR_SENSITIVITY);
            parameters.FillDynamicParameters(captureResult, null, iso);
            parameters.cameraRotation = cameraRotation;
            Log.d(TAG, "Camera rotation: " + parameters.cameraRotation);
            Log.d(TAG, "activearr:" + characteristics.get(CameraCharacteristics.SENSOR_INFO_ACTIVE_ARRAY_SIZE));
            Log.d(TAG, "precorr:" + characteristics.get(CameraCharacteristics.SENSOR_INFO_PRE_CORRECTION_ACTIVE_ARRAY_SIZE));
            return saveSingleRaw(dngFilePath, image.buffer, parameters);
        }

        public static boolean saveSingleRaw(Path dngFilePath,
                                            ByteBuffer buffer, Parameters parameters) {
            DngCreator dngCreator = new DngCreator();
            dngCreator.setParameters(parameters);
            dngCreator.setCompression(false);
            //dngCreator.setBinning(true);
            try {
                OutputStream outputStream = Files.newOutputStream(dngFilePath);
                dngCreator.writeBuffer(outputStream, buffer, parameters.rawSize.x, parameters.rawSize.y);
                outputStream.close();
            } catch (IOException e) {
                e.printStackTrace();
                return false;
            } finally {
                dngCreator.close();
            }
            return true;
        }
    }
}
