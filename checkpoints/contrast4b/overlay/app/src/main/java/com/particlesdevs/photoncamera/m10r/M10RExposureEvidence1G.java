package com.particlesdevs.photoncamera.m10r;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

public final class M10RExposureEvidence1G {
    private M10RExposureEvidence1G() {}
    static JSONObject build(M10RExposure1A.Plan plan)throws JSONException {
        var m=plan.multiField;var s=m.scene;JSONObject d=new JSONObject();
        d.put("revision",M10RMultiField1G.REVISION);
        d.put("geometryRevision",M10RMultiField1G.GEOMETRY_REVISION);
        d.put("midtoneBridge",s.midtoneBridge);d.put("midtoneBridgeMask",s.midtoneBridgeMask);
        d.put("meterRawRegions4x6",new JSONArray(plan.mfm.regions4x6));
        d.put("meterRawRegionsSource","same_request_owned_meter_RAW_as_scene_decision");
        d.put("policyProvenance","experimental_regional_foreground_proxy_not_Leica_firmware");
        d.put("qualified",s.qualified);d.put("sceneReason",s.reason);d.put("decisionReason",m.reason);
        d.put("splitBrightBackground",s.splitBackground);d.put("brightBackgroundComponents",s.backgroundComponents);
        d.put("positiveRequestLimitEv",m.positiveRequestLimitEv);
        d.put("foregroundMask",s.foregroundMask);d.put("brightBackgroundMask",s.backgroundMask);
        d.put("maskCoordinates","sensor_4x6_row_major_no_semantic_subject_detection");
        d.put("rawRegionalSeparationEv",s.separationEv);d.put("neutralForegroundMeanQ90",m.neutralForegroundQ90);
        d.put("legacyRequestedEv",m.legacyRequestedEv);d.put("regionalRequestedEv",m.requestedEv);
        d.put("positiveAssistRequiresQualifiedForeground",true);
        d.put("legacyPositiveSuppressed",m.legacyRequestedEv>0&&m.requestedEv<=0);
        d.put("legacyPositiveReduced",m.legacyRequestedEv>m.requestedEv&&m.requestedEv>=0);
        d.put("legacyNegativeConflict",s.qualified&&m.legacyRequestedEv<0);
        d.put("legacyNegativeOverrideRequested",m.legacyRequestedEv<0&&m.requestedEv>0);
        d.put("legacyNegativeOverrideApplied",m.legacyRequestedEv<0&&plan.appliedAutoEv>0);
        d.put("fixedExposureBiasEv",0);
        d.put("requestedAutoEv",plan.requestedAutoEv);
        d.put("exposureRangeRevision",M10RExposureRange1H.REVISION);
        d.put("meterRequestBeforeLegacyCapEv",plan.mfm.rawBlendEv);
        d.put("appliedAutoEv",plan.appliedAutoEv);d.put("newAssistCeilingEv",M10RMultiField1G.MAX_ASSIST_EV);
        d.put("legacyPositiveCeilingEv",M10RMfm1B.MAX_POSITIVE_EV);
        d.put("nearWhiteExceptionMaxChannelClipFraction",.03);
        d.put("nearWhiteExceptionMaxChannelClipGrowth",.025);
        JSONArray candidates=new JSONArray();var progress=m.progress();
        for(int i=0;i<progress.length;i++) {
            JSONObject c=new JSONObject();c.put("relativeEv",i*M10RHighlightGuard1A.STEP_EV);
            c.put("foregroundMeanQ90",m.foregroundQ90(i));
            c.put("nearWhiteBackgroundExceptionEligible",progress[i].nearWhiteBackgroundMask!=0);
            candidates.put(c);
        }
        d.put("candidates",candidates);d.put("positiveLimitEv",plan.highlight.maxPositiveEv);
        d.put("positiveStop",plan.highlight.stop.name());
        d.put("baselineCorrectionEv",plan.baseline.correctionEv);
        d.put("userEv",plan.userEv);
        d.put("additionalRawOrRenderPasses",Math.max(0,progress.length-M10RExposureRange1H.LEGACY_CANDIDATES));
        d.put("additionalRawFrames",0);
        d.put("additionalColourPassesVersusE1G",Math.max(0,progress.length-M10RExposureRange1H.LEGACY_CANDIDATES));
        d.put("measuredPositiveRangeEv",(progress.length-1)*M10RHighlightGuard1A.STEP_EV);
        d.put("previewWysiwygChanged",false);d.put("otherRenderersEnabled",false);
        return d;
    }
}
