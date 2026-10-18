package com.particlesdevs.photoncamera.m10r;

import java.util.Arrays;
import org.junit.Test;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

public class M10RSceneExposure1MTest {
    private static int[] pixels() {
        int[] p=new int[12*8];Arrays.fill(p,0xffb4b4b4);
        for(int y=2;y<6;y++)for(int x=3;x<9;x++)p[y*12+x]=0xff1e1e1e;
        return p;
    }
    @Test public void globalCenterAndRegionalQuantilesUseTheActualRenderedCodes() {
        var s=M10RSceneExposure1M.measure(pixels(),12,8);
        assertEquals(180,s.median);assertEquals(30,s.q25);assertEquals(180,s.q90);
        assertEquals(30,s.centerMedian);assertEquals(30,s.centerQ25);assertEquals(30,s.centerWeightedMedian);
        assertEquals(180,s.fieldMedian(0));assertEquals(30,s.fieldMedian(9));
        int[] p=new int[96];Arrays.fill(p,0xffff0000);
        assertEquals(77,M10RSceneExposure1M.measure(p,12,8).median);
        p[0]=0;
        try{M10RSceneExposure1M.measure(p,12,8);fail("nonopaque input accepted");}catch(IllegalArgumentException expected){}
    }
    @Test public void evidenceIsBoundToTheProbeAndUsesSeparateUserAndNeutralReferences()throws Exception {
        var s=M10RSceneExposure1M.measure(pixels(),12,8);var hs=M10RExposureBaseline1FTest.SAFE;
        var probe=M10RExposureBaseline1FTest.probe(-1.1666666666666665,0,0,
                new M10RHighlightGuard1A.Stats[]{hs,hs,hs},M10RExposureBaseline1FTest.flat());
        var raw=mock(M10RExposureRaw1B.Prepared.class);
        var output=new M10RExposureProbe1B.Output(probe,new short[3],new int[4][],raw,1,1,
                new M10RHighlightGuard1A.Stats[]{hs,hs,hs,hs},new M10RHighlightGuard1A.Stats[]{hs,hs,hs},
                new M10RSceneExposure1M.Stats[]{s,s,s,s},new M10RSceneExposure1M.Stats[]{s,s,s});
        var d=M10RSceneExposure1M.describe(output);
        assertTrue(d.getBoolean("available"));assertFalse(d.getBoolean("changesExposure"));
        assertEquals(probe.rendererRevision,d.getString("rendererRevision"));
        assertEquals(probe.candidateUserEv,d.getDouble("candidateUserEv"),0);
        assertEquals(0,d.getDouble("baselineUserEv"),0);
        assertEquals(-.5,d.getJSONArray("baselineCandidates").getJSONObject(2).getDouble("relativeEv"),0);
        assertEquals(.75,d.getJSONArray("positiveCandidates").getJSONObject(3).getDouble("relativeEv"),0);
        assertEquals(24,d.getJSONArray("baselineCandidates").getJSONObject(0).getJSONArray("fieldMedianCode").length());
        assertEquals(0,d.getInt("additionalColourPasses"));
        var copy=output.positiveSceneStats();copy[0]=null;assertNotNull(output.positiveSceneStats()[0]);
    }
}
