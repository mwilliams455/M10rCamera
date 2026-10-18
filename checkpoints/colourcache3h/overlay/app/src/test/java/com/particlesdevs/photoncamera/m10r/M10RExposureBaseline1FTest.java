package com.particlesdevs.photoncamera.m10r;

import java.util.Arrays;
import org.json.JSONObject;
import org.json.JSONException;
import org.junit.Test;
import static org.junit.Assert.*;

public class M10RExposureBaseline1FTest {
    static M10RHighlightGuard1A.Stats stats(double bright,double clip,int q90,double fieldBright,double fieldClip) {
        int[] q=new int[24];double[] b=new double[24],c=new double[24];
        Arrays.fill(q,q90);Arrays.fill(b,fieldBright);Arrays.fill(c,fieldClip);
        return new M10RHighlightGuard1A.Stats(bright,clip,q,b,c);
    }
    static final M10RHighlightGuard1A.Stats SAFE=stats(.02,.005,120,.02,.005);
    static final M10RHighlightGuard1A.Stats CLIPPED=stats(.03,.10,180,.02,.005);
    static M10RExposure1A.Probe probe(double user,double refUser,double refAuto,
            M10RHighlightGuard1A.Stats[] lower,double[] grid) {
        return new M10RExposure1A.Probe("cam",1,1,"renderer",123,123,1_000_000_000,1_010_000_000,
                10_000_000,200,refUser,refAuto,M10RExposure1A.ProbeDomain.M10R_RENDERED_USER_EV_REFERENCE,
                grid,new M10RHighlightGuard1A.Stats[]{SAFE,SAFE,SAFE,SAFE},M10RHighlightGuard1A.noSubject(4),user,lower);
    }
    static M10RExposure1A.Request request(double user,boolean auto,long now) {
        return new M10RExposure1A.Request("cam",1,"renderer",now,user,1.8,35,100,50000,auto);
    }
    static double[] flat(){double[] grid=new double[352];Arrays.fill(grid,.12);return grid;}
    static M10RExposure1A.Plan plan(M10RHighlightGuard1A.Stats[] lower,double user,double refUser,double refAuto,double[] grid){
        return M10RExposure1A.prepare(probe(user,refUser,refAuto,lower,grid),request(user,true,1_020_000_000));
    }
    @Test public void selectsSmallestDemonstratedCorrectionWithinExistingHalfStopBound() {
        assertEquals(-.25,M10RExposureBaseline1F.evaluate(new M10RHighlightGuard1A.Stats[]{CLIPPED,SAFE,SAFE}).correctionEv,0);
        var intermediate=stats(.02,.06,150,.02,.005);
        assertEquals(-.5,M10RExposureBaseline1F.evaluate(new M10RHighlightGuard1A.Stats[]{CLIPPED,intermediate,SAFE}).correctionEv,0);
        assertEquals(M10RMfm1B.MAX_NEGATIVE_EV,2*M10RHighlightGuard1A.STEP_EV,0);
    }
    @Test public void allFourExistingLossPredicatesCanAuthorizeMeasuredRecovery() {
        var near=stats(.25,.005,180,.02,.005);
        var regionalNear=stats(.02,.005,180,.60,.005);
        var regionalClip=stats(.02,.005,180,.02,.10);
        var current=new M10RHighlightGuard1A.Stats[]{CLIPPED,near,regionalNear,regionalClip};
        var reasons=new M10RHighlightGuard1A.Stop[]{M10RHighlightGuard1A.Stop.GLOBAL_CHANNEL_CLIP_GROWTH,
            M10RHighlightGuard1A.Stop.GLOBAL_NEARWHITE_GROWTH,M10RHighlightGuard1A.Stop.REGIONAL_NEARWHITE_GROWTH,
            M10RHighlightGuard1A.Stop.REGIONAL_CHANNEL_CLIP_GROWTH};
        for(int i=0;i<4;i++)assertEquals(reasons[i],M10RExposureBaseline1F.evaluate(new M10RHighlightGuard1A.Stats[]{current[i],SAFE,SAFE}).recoveredLoss);
    }
    @Test public void ordinarySpecularPersistentWhiteAndAlreadyBrightFieldsStayUnchanged() {
        var tiny=stats(.025,.008,140,.025,.008);
        var white=stats(.50,.35,255,.7,.4);
        var preexisting=stats(.02,.005,230,.10,.01);
        var changed=stats(.02,.005,250,.60,.12);
        for(var evidence:new M10RHighlightGuard1A.Stats[][]{{SAFE,SAFE,SAFE},{tiny,SAFE,SAFE},{white,white,white},{changed,preexisting,preexisting}})
            assertEquals(0,M10RExposureBaseline1F.evaluate(evidence).correctionEv,0);
    }
    @Test public void explicitUserEvAndReferenceIntentRemainSeparate() {
        for(double user:new double[]{-2,-.5,0,.5,2}) {
            var p=plan(new M10RHighlightGuard1A.Stats[]{CLIPPED,SAFE,SAFE},user,.5,.25,flat());
            assertTrue(p.ready());assertEquals(-.25,p.appliedAutoEv,0);
            assertEquals(user-.25,p.totalIntentEv,1e-12);
            assertEquals(user-1,p.deltaFromReferenceEv,1e-12);
        }
    }
    @Test public void provenLossSuppressesPositiveAssistWithoutAddingNegativeCorrections() {
        double[] positive=new double[352];
        for(int y=0;y<16;y++)for(int x=0;x<22;x++)positive[y*22+x]=x<5?.5:(x>7&&x<16&&y>3&&y<12?.002:.025);
        var p=plan(new M10RHighlightGuard1A.Stats[]{M10RExposureRange1HTest.qualifiedStats(.10),SAFE,SAFE},0,0,0,positive);
        assertTrue(p.multiField.scene.qualified);
        assertTrue(p.requestedAutoEv>0);assertEquals(-.25,p.appliedAutoEv,0);
        double[] negative=new double[352];Arrays.fill(negative,.005);
        for(int y=0;y<6;y++)for(int x=3;x<5;x++)negative[y*22+x]=.8;
        p=plan(new M10RHighlightGuard1A.Stats[]{CLIPPED,SAFE,SAFE},0,0,0,negative);
        assertTrue(p.requestedAutoEv<0);assertEquals(Math.min(p.requestedAutoEv,-.25),p.appliedAutoEv,0);
        assertTrue(p.appliedAutoEv>=-.5);
    }
    @Test public void invalidStaleManualAndMissingEvidenceCannotAuthorizeBaselineCorrection() {
        var p=probe(0,0,0,new M10RHighlightGuard1A.Stats[]{CLIPPED,SAFE,SAFE},flat());
        assertEquals(M10RExposure1A.Status.BYPASS_MANUAL,M10RExposure1A.prepare(p,request(0,false,1_020_000_000)).status);
        assertEquals(M10RExposure1A.Status.STALE_OR_FUTURE,M10RExposure1A.prepare(p,request(0,true,2_300_000_000L)).status);
        assertEquals(M10RExposure1A.Status.USER_EV_MISMATCH,M10RExposure1A.prepare(p,request(1,true,1_020_000_000)).status);
        assertEquals(0,plan(null,0,0,0,flat()).appliedAutoEv,0);
        for(var bad:new M10RHighlightGuard1A.Stats[][]{new M10RHighlightGuard1A.Stats[2],{SAFE,null,SAFE}}) {
            try{M10RExposureBaseline1F.evaluate(bad);fail("invalid evidence accepted");}catch(IllegalArgumentException expected){}
        }
    }
    @Test public void physicalSelectionCarriesMeasuredCorrectionIntoFrozenPairAndFallbackClearsIt() {
        var p=probe(.5,0,0,new M10RHighlightGuard1A.Stats[]{CLIPPED,SAFE,SAFE},flat());
        var r=request(.5,true,1_020_000_000);var limits=new M10RExposureCapture1B.Limits(1,1_000_000_000,50,6400);
        var selection=M10RExposureCapture1B.select(p,r,null,limits);
        assertTrue(selection.apply);assertFalse(selection.fallback);assertEquals(-.25,selection.appliedAutoEv,0);
        var expected=M10RAe1BPolicy.solve(10_000_000,200,1.8,35,.25,100,50000).oracle;
        // Keep the oracle intact, but conserve phone nominal intent independently.
        // Nominal time*ISO is not a measured physical gain calibration.
        assertEquals(expected.iso,selection.iso);
        assertEquals(10_000_000.0*200*Math.pow(2,.25),(double)selection.exposureNs*selection.iso,selection.iso*.51);
        assertEquals(expected.shutterSeconds,selection.allocation.oracle.shutterSeconds,0);
        var fallback=new M10RExposureCapture1B.Reference("cam",1,1_000_000_000,10_000_000,200,0,0);
        var missing=M10RExposureCapture1B.select(null,r,fallback,limits);
        assertTrue(missing.fallback);assertEquals(0,missing.appliedAutoEv,0);
    }
    @Test public void evidenceReportContainsEveryMeasuredCandidateAndDoesNotAliasInput()throws Exception {
        var lower=new M10RHighlightGuard1A.Stats[]{CLIPPED,SAFE,SAFE};var raw=probe(.5,0,0,lower,flat());
        lower[0]=SAFE;var p=M10RExposure1A.prepare(raw,request(.5,true,1_020_000_000));
        assertEquals(-.25,p.appliedAutoEv,0);
        var d=M10RExposureEvidence1F.build(new M10RHighlightGuard1A.Stats[]{SAFE,SAFE,SAFE,SAFE},new M10RHighlightGuard1A.Stats[]{CLIPPED,SAFE,SAFE},p);
        assertEquals(3,d.getJSONArray("baselineCandidates").length());assertEquals(4,d.getJSONArray("positiveCandidates").length());
        assertEquals(.10,d.getJSONArray("baselineCandidates").getJSONObject(0).getDouble("channelClipFraction"),0);
        assertEquals(-.5,d.getJSONArray("baselineCandidates").getJSONObject(2).getDouble("relativeEv"),0);
        assertEquals(24,d.getJSONArray("baselineCandidates").getJSONObject(0).getJSONArray("fieldQ90").length());
        assertTrue(d.getBoolean("explicitUserEvAppliedSeparately"));assertFalse(d.getBoolean("lostSensorInformationRecovered"));
    }
    @Test public void failedDiagnosticSerializationDoesNotEscape() {
        var lower=new M10RHighlightGuard1A.Stats[]{CLIPPED,SAFE,SAFE};var p=probe(0,0,0,lower,flat());
        var plan=M10RExposure1A.prepare(p,request(0,true,1_020_000_000));
        var prepared=new M10RExposureRaw1B.Prepared(new short[1],new double[352],new long[4],new long[4],new long[4],1,1,0,1);
        var output=new M10RExposureProbe1B.Output(p,new short[0],new int[4][],prepared,0,0,
                new M10RHighlightGuard1A.Stats[]{SAFE,SAFE,SAFE,SAFE},lower);
        JSONObject broken=new JSONObject(){@Override public JSONObject put(String k,Object v)throws JSONException{throw new JSONException("injected");}};
        M10RExposureEvidence1F.appendTo(broken,output,plan);assertEquals(-.25,plan.appliedAutoEv,0);
    }
}
