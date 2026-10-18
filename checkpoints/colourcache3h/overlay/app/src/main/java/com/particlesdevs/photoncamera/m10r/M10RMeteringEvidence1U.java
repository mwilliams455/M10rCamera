package com.particlesdevs.photoncamera.m10r;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

public final class M10RMeteringEvidence1U {
    private M10RMeteringEvidence1U() {}
    public static JSONObject build(M10RExposure1A.Plan p)throws JSONException {
        var m=p.metering;boolean multi=m.config.mode==M10RMetering1U.Mode.MULTI_FIELD;
        return new JSONObject().put("revision",M10RMetering1U.REVISION)
                .put("mode",m.config.mode.name()).put("binding",m.config.key())
                .put("physicalAnchor","phone_AE_full_field_region_when_supported_not_Leica_absolute_calibration")
                .put("rawMean",m.mean).put("rawIntegral",m.integral).put("rawSpot",m.spot)
                .put("rawRegions4x6",new JSONArray(m.regions()))
                .put("rawCells16x22",new JSONArray(m.cells()))
                .put("regionGeometry",M10RMeteringGeometry1X.REVISION)
                .put("regionColumnStarts",new JSONArray(M10RMeteringGeometry1X.columnStarts()))
                .put("regionColumnWidths",new JSONArray(M10RMeteringGeometry1X.columnWidths()))
                .put("regionMeanDomain","linear_phone_green_equal_cell_means_not_firmware_Q8")
                .put("firmwareStatisticsEngineControlsExposure",false)
                .put("spatialEv",m.spatialEv).put("requestedAutoEv",p.requestedAutoEv)
                .put("appliedAutoEv",p.appliedAutoEv).put("userEv",p.userEv)
                .put("deltaFromReferenceEv",p.deltaFromReferenceEv)
                .put("integralWeights","recovered_16x22_sum_14160")
                .put("spotMask","dynamic_cell_centre_rectangle_boundary_softening_not_ported")
                .put("spotAreaFraction",.025).put("spatialCorrectionLimitEv",M10RMetering1U.MAX_SPATIAL_EV)
                .put("multiFieldProvenance","MFM1B_phone_proxy_not_exact_13_feature_firmware")
                .put("sceneSpecificForegroundOverridesEnabled",false)
                .put("sharedGeometry","same_RAW_sample_sites_crop_and_recovered_16x22_to_4x6_field_map")
                .put("rawDomain","black_subtracted_two_green_CFA_average_before_LSC_WB")
                .put("rawGreenSampleCellExtentPixels",2)
                .put("globalHighlightGuardApplied",multi)
                .put("globalHighlightLimitEv",p.highlight.maxPositiveEv)
                .put("globalHighlightStop",p.highlight.stop.name())
                .put("baselineCorrectionApplied",multi?p.baseline.correctionEv:0)
                .put("photographicRawFrames",1).put("frameFusion",false)
                .put("previewUsesSharedExposurePlan",true)
                .put("previewSourceIsRaw",false).put("previewPixelParityEstablished",false)
                .put("absoluteFirmwareCalibrationEstablished",false);
    }
}
