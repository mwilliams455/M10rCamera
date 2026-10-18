package com.particlesdevs.photoncamera.m10r;

import android.graphics.ImageFormat;
import android.graphics.Rect;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CaptureResult;
import android.hardware.camera2.params.LensShadingMap;
import android.media.Image;
import org.json.JSONObject;

/** Worker-side adapter. Caller owns Image and must close it on success, failure or cancellation. */
public final class M10RExposureAndroid1B {
    private M10RExposureAndroid1B() {}
    public static M10RExposureProbe1B.Output build(Image image,CameraCharacteristics characteristics,
            CaptureResult result,M10RExposureProbe1B.Binding binding,M10RExposureProbe1B.Clock clock,
            M10RExposureProbe1B.Cancelled cancelled) throws Exception {
        if(image==null||characteristics==null||result==null||binding==null||image.getFormat()!=ImageFormat.RAW_SENSOR
                ||image.getTimestamp()!=binding.imageTimestampNs)
            throw new IllegalArgumentException("request-owned RAW_SENSOR frame required");
        Long ts=result.get(CaptureResult.SENSOR_TIMESTAMP);
        if(ts==null||ts!=image.getTimestamp())throw new IllegalArgumentException("RAW/result timestamp mismatch");
        Rect crop=image.getCropRect();
        if(crop==null||crop.left!=0||crop.top!=0||crop.right!=image.getWidth()||crop.bottom!=image.getHeight())
            throw new IllegalArgumentException("non-full RAW crop unsupported in first exposure probe");
        Integer cfa=characteristics.get(CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT);
        if(cfa==null||cfa<0||cfa>3)throw new IllegalArgumentException("Bayer CFA metadata missing/unsupported");
        if(image.getPlanes().length!=1)throw new IllegalArgumentException("RAW plane count");
        Image.Plane plane=image.getPlanes()[0];
        java.nio.ByteBuffer buffer=plane.getBuffer();
        // Resolve via the very same metadata helpers as the JPEG source path.
        double[] black=M10RNativeRenderer.exposureBlack1B(characteristics,result);
        int white=M10RNativeRenderer.exposureWhite1B(characteristics,result);
        LensShadingMap map=result.get(CaptureResult.STATISTICS_LENS_SHADING_CORRECTION_MAP);
        float[] gains=null;int cols=0,rows=0;
        if(map!=null&&map.getColumnCount()>=2&&map.getRowCount()>=2){
            cols=map.getColumnCount();rows=map.getRowCount();gains=new float[map.getGainFactorCount()];
            map.copyGainFactors(gains,0);
        }
        M10RExposureNative1B.Context context=M10RNativeRenderer.exposureContext1B(characteristics,result,binding.cameraKey);
        M10RExposureRaw1B.Prepared raw=M10RExposureRaw1B.prepare(buffer,buffer.position(),plane.getRowStride(),
                plane.getPixelStride(),image.getWidth(),image.getHeight(),0,0,cfa,black,white,gains,cols,rows);
        return M10RExposureProbe1B.produce(raw,result,context,binding,clock,cancelled);
    }
}
