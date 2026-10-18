package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.CaptureResult;
import android.hardware.camera2.params.ColorSpaceTransform;
import android.hardware.camera2.params.RggbChannelVector;
import android.util.Rational;
import org.json.JSONArray;
import org.json.JSONObject;

/** Observation only: records candidates and the actual still-frame WB controls. */
final class M10RWhiteBalanceDiagnostics1D {
    private M10RWhiteBalanceDiagnostics1D() {}
    static void append(JSONObject destination,short[] raw,int width,int height,int cfa,double storageScale,
            double sourceKelvin,CameraCharacteristics c,CaptureRequest request,CaptureResult result) {
        long start=System.nanoTime();
        try {
            Rational[] reported=result.get(CaptureResult.SENSOR_NEUTRAL_COLOR_POINT);
            double[] neutral=reported==null||reported.length<3?null:new double[]{reported[0].doubleValue(),reported[1].doubleValue(),reported[2].doubleValue()};
            M10RWhiteBalanceProbe1D.Result probe=M10RWhiteBalanceProbe1D.inspect(raw,width,height,cfa,storageScale,neutral);
            JSONObject record=describe(probe)
                    .put("sourceCctKelvin",sourceKelvin).put("sourceSensorNeutral",array(neutral))
                    .put("sourceFrameTimestampNs",nullable(result.get(CaptureResult.SENSOR_TIMESTAMP)))
                    .put("sourceFrameNumber",result.getFrameNumber())
                    .put("requested",requested(request)).put("delivered",delivered(result))
                    .put("sourceCalibration",calibration(c))
                    .put("elapsedNs",System.nanoTime()-start);
            destination.put("m10rWhiteBalanceProbe1D",record);
        } catch(Exception e) {
            // Optional diagnostics must never turn a valid photograph into a failed save.
            try {destination.put("m10rWhiteBalanceProbe1D",new JSONObject()
                    .put("revision",M10RWhiteBalanceProbe1D.REVISION).put("applied",false)
                    .put("reason","diagnostic_error").put("errorType",e.getClass().getSimpleName()));}
            catch(Exception ignored) {}
        }
    }
    static JSONObject describe(M10RWhiteBalanceProbe1D.Result p)throws Exception {
        JSONArray selected=new JSONArray();
        for(M10RWhiteBalanceProbe1D.Tile t:p.selected)selected.put(new JSONArray().put(t.x).put(t.y));
        JSONArray all=new JSONArray();
        for(M10RWhiteBalanceProbe1D.Tile t:p.valid)all.put(new JSONArray().put(t.x).put(t.y)
                .put(t.r).put(t.b).put(t.green).put(t.madR).put(t.madB));
        return new JSONObject().put("revision",M10RWhiteBalanceProbe1D.REVISION)
                .put("mode","observation_only").put("applied",false).put("automaticCorrectionEnabled",false)
                .put("hasProposal",p.hasProposal()).put("reason",p.reason).put("materialNeutralityProven",false)
                .put("proposedSensorNeutral",array(p.proposedNeutral))
                .put("validTiles",p.valid.size()).put("candidateTiles",p.candidates.size())
                .put("consensusTiles",p.selected.size()).put("competingSupport",p.competingSupport)
                .put("gridColumns",M10RWhiteBalanceProbe1D.COLS).put("gridRows",M10RWhiteBalanceProbe1D.ROWS)
                .put("gridCoordinates","unrotated_physical_raw_columns_rows")
                .put("sampleDomain","lens_shading_corrected_linear_sensor_before_demosaic")
                .put("brightnessQuantile",.65).put("brightnessThreshold",p.brightnessThreshold)
                .put("maxBlueNeutralShiftEv",.40).put("redNeutralShiftEvBounds",new JSONArray().put(-.10).put(.25))
                .put("minimumBlueNeutralShiftEv",.10).put("clusterRadiusEv",.10)
                .put("thresholdsExperimental",true).put("firmwareDerived",false)
                .put("selectedTileXY",selected).put("tileFields","x,y,log2_Rneutral_ratio,log2_Bneutral_ratio,green,madR,madB")
                .put("validTileStatistics",all);
    }
    private static JSONObject requested(CaptureRequest r)throws Exception {
        if(r==null)return new JSONObject().put("available",false);
        return new JSONObject().put("available",true)
                .put("awbMode",nullable(r.get(CaptureRequest.CONTROL_AWB_MODE)))
                .put("awbLock",nullable(r.get(CaptureRequest.CONTROL_AWB_LOCK)))
                .put("colorCorrectionMode",nullable(r.get(CaptureRequest.COLOR_CORRECTION_MODE)))
                .put("gainsRGGB",gains(r.get(CaptureRequest.COLOR_CORRECTION_GAINS)))
                .put("colorTransformRows",matrix(r.get(CaptureRequest.COLOR_CORRECTION_TRANSFORM)));
    }
    private static JSONObject delivered(CaptureResult r)throws Exception {
        return new JSONObject().put("awbMode",nullable(r.get(CaptureResult.CONTROL_AWB_MODE)))
                .put("awbState",nullable(r.get(CaptureResult.CONTROL_AWB_STATE)))
                .put("awbLock",nullable(r.get(CaptureResult.CONTROL_AWB_LOCK)))
                .put("colorCorrectionMode",nullable(r.get(CaptureResult.COLOR_CORRECTION_MODE)))
                .put("gainsRGGB",gains(r.get(CaptureResult.COLOR_CORRECTION_GAINS)))
                .put("colorTransformRows",matrix(r.get(CaptureResult.COLOR_CORRECTION_TRANSFORM)));
    }
    private static JSONObject calibration(CameraCharacteristics c)throws Exception {
        return new JSONObject().put("matrixConvention","rows_from_Camera2_getElement_column_row")
                .put("referenceIlluminant1",nullable(c.get(CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT1)))
                .put("referenceIlluminant2",nullable(c.get(CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT2)))
                .put("calibration1",matrix(c.get(CameraCharacteristics.SENSOR_CALIBRATION_TRANSFORM1)))
                .put("calibration2",matrix(c.get(CameraCharacteristics.SENSOR_CALIBRATION_TRANSFORM2)))
                .put("color1",matrix(c.get(CameraCharacteristics.SENSOR_COLOR_TRANSFORM1)))
                .put("color2",matrix(c.get(CameraCharacteristics.SENSOR_COLOR_TRANSFORM2)))
                .put("forward1",matrix(c.get(CameraCharacteristics.SENSOR_FORWARD_MATRIX1)))
                .put("forward2",matrix(c.get(CameraCharacteristics.SENSOR_FORWARD_MATRIX2)));
    }
    private static Object gains(RggbChannelVector g)throws Exception {
        return g==null?JSONObject.NULL:new JSONArray().put(g.getRed()).put(g.getGreenEven()).put(g.getGreenOdd()).put(g.getBlue());
    }
    private static Object matrix(ColorSpaceTransform m)throws Exception {
        if(m==null)return JSONObject.NULL;
        JSONArray a=new JSONArray();
        for(int row=0;row<3;row++){JSONArray r=new JSONArray();for(int col=0;col<3;col++)r.put(m.getElement(col,row).doubleValue());a.put(r);}
        return a;
    }
    private static Object array(double[] values)throws Exception {
        if(values==null)return JSONObject.NULL;
        JSONArray a=new JSONArray();for(double v:values)a.put(v);return a;
    }
    private static Object nullable(Object value){return value==null?JSONObject.NULL:value;}
}
