package com.particlesdevs.photoncamera.m10r;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

/** Bounded per-capture evidence; diagnostic failure cannot cancel an exposure selection. */
public final class M10RExposureEvidence1F {
    private M10RExposureEvidence1F() {}
    public static void appendTo(JSONObject parent,M10RExposureProbe1B.Output output,M10RExposure1A.Plan plan) {
        try {
            if(parent==null||output==null||plan==null||!plan.ready())return;
            M10RFirmwareShadow2R.appendTo(parent,output.firmwareShadow2R);
            if(plan.metering!=null) {
                parent.put("liveViewMetering1U",M10RMeteringEvidence1U.build(plan));
                parent.put("alignedRenderedCandidates1U",stats(output.positiveStats(),M10RHighlightGuard1A.STEP_EV));
                return;
            }
            parent.put("highlightEvidence1F",build(output.positiveStats(),output.baselineStats(),plan));
            parent.put("multiFieldEvidence1G",M10RExposureEvidence1G.build(plan));
            parent.put("sceneExposure1M",M10RSceneExposure1M.describe(output));
        }catch(JSONException|RuntimeException|LinkageError|OutOfMemoryError ignored) {
            // Evidence reporting is best effort, as in the existing E1D trace.
        }
    }
    static JSONObject build(M10RHighlightGuard1A.Stats[] positive,M10RHighlightGuard1A.Stats[] baseline,
            M10RExposure1A.Plan plan)throws JSONException {
        JSONObject d=new JSONObject();
        d.put("revision",M10RExposureBaseline1F.REVISION);
        d.put("policyProvenance","new_inverse_use_of_existing_incremental_loss_predicates_not_firmware_constants");
        d.put("candidateProjection","one_RAW_reconstruction_scaled_before_unchanged_native_M10R_colour");
        d.put("baselineCandidateUserEv",0);d.put("positiveCandidateUserEv",plan.userEv);
        d.put("explicitUserEvAppliedSeparately",true);
        d.put("requestedMfmEv",plan.requestedAutoEv);d.put("mfmReason",plan.multiField.reason);
        d.put("legacyMfmReason",plan.mfm.reason);d.put("legacyMfmRequestedEv",plan.multiField.legacyRequestedEv);
        d.put("exposureRangeRevision",M10RExposureRange1H.REVISION);
        d.put("meterRequestBeforeLegacyCapEv",plan.mfm.rawBlendEv);
        d.put("extendedRangeEvidenceComplete",positive.length==M10RExposureRange1H.POSITIVE_CANDIDATES);
        d.put("measuredPositiveRangeEv",(positive.length-1)*M10RHighlightGuard1A.STEP_EV);
        d.put("extendedMeterRequestUsed",plan.requestedAutoEv>plan.multiField.requestedEv);
        d.put("baselineCorrectionEv",plan.baseline.correctionEv);
        d.put("baselineReason",plan.baseline.reason);d.put("recoveredLossPredicate",plan.baseline.recoveredLoss.name());
        d.put("baselineSelectedStep",plan.baseline.selectedStep);
        d.put("appliedAutoEv",plan.appliedAutoEv);d.put("totalIntentEv",plan.totalIntentEv);
        d.put("deltaFromReferenceEv",plan.deltaFromReferenceEv);
        d.put("positiveLimitEv",plan.highlight.maxPositiveEv);
        d.put("positiveFirstRejectedStep",plan.highlight.firstRejectedStep);
        d.put("positiveStop",plan.highlight.stop.name());
        d.put("positiveGuardRevision",M10RHighlightGuard1A.POSITIVE_REVISION);
        d.put("existingClipGrowthBudgetFraction",M10RHighlightGuard1A.POSITIVE_CLIP_GROWTH_BUDGET);
        d.put("existingClipGrowthAppliesToPositiveAssistOnly",true);
        d.put("baselineCandidates",stats(baseline,-M10RHighlightGuard1A.STEP_EV));
        d.put("positiveCandidates",stats(positive,M10RHighlightGuard1A.STEP_EV));
        d.put("sampleWidth",M10RExposureProbe1B.WIDTH);d.put("sampleHeight",M10RExposureProbe1B.HEIGHT);
        d.put("excludedRawBorderPixels",M10RExposureProbe1B.BORDER);
        d.put("fieldRows",M10RHighlightGuard1A.ROWS);d.put("fieldColumns",M10RHighlightGuard1A.COLS);
        d.put("fractionsAreRenderedOutputNotSensorSaturation",true);
        d.put("lostSensorInformationRecovered",false);
        return d;
    }
    private static JSONArray stats(M10RHighlightGuard1A.Stats[] values,double step)throws JSONException {
        JSONArray array=new JSONArray();
        for(int i=0;i<values.length;i++) {
            var s=values[i];JSONObject d=new JSONObject();JSONArray q=new JSONArray(),bright=new JSONArray(),clip=new JSONArray();
            for(int f=0;f<M10RHighlightGuard1A.FIELDS;f++) {
                q.put(s.q90(f));bright.put(s.bright(f));clip.put(s.clipped(f));
            }
            d.put("relativeEv",i*step);d.put("nearWhiteFraction",s.bright);d.put("channelClipFraction",s.clipped);
            d.put("fieldQ90",q);d.put("fieldNearWhiteFraction",bright);d.put("fieldChannelClipFraction",clip);array.put(d);
        }
        return array;
    }
}
