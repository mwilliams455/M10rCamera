package com.particlesdevs.photoncamera.m10r;

import org.junit.Test;
import org.json.JSONObject;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.Arrays;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CaptureResult;

public class M10RFirmwareShadow2RTest {
    @org.junit.BeforeClass public static void keys()throws Exception {
        M10RPreviewMetadata1ETest.installFrameworkKeyIdentities();
        var m=M10RPreviewMetadata1ETest.class.getDeclaredMethod("keys",Class.class,Class.class,String[].class);m.setAccessible(true);
        m.invoke(null,CaptureResult.class,CaptureResult.Key.class,new String[]{"SENSOR_TIMESTAMP","SENSOR_EXPOSURE_TIME","SENSOR_SENSITIVITY","LENS_APERTURE","LENS_FOCAL_LENGTH","LENS_FOCUS_DISTANCE","CONTROL_POST_RAW_SENSITIVITY_BOOST","SENSOR_DYNAMIC_BLACK_LEVEL","SENSOR_DYNAMIC_WHITE_LEVEL"});
        m.invoke(null,CameraCharacteristics.class,CameraCharacteristics.Key.class,new String[]{"LENS_INFO_FOCUS_DISTANCE_CALIBRATION","SENSOR_ORIENTATION","LENS_FACING","SENSOR_BLACK_LEVEL_PATTERN"});
    }
    @org.junit.AfterClass public static void restore()throws Exception {M10RPreviewMetadata1ETest.restoreFrameworkKeys();}
    private static final int W=384,H=288,STRIDE=W*2+16,OFFSET=12;
    private static final int[][] MAP={{0,1,2,3},{1,0,3,2},{2,3,0,1},{3,2,1,0}};
    private static final M10RMetering1U.Config CFG=new M10RMetering1U.Config(M10RMetering1U.Mode.MULTI_FIELD);
    private static ByteBuffer frame(int cfa,int[] channels) {
        ByteBuffer b=ByteBuffer.allocate(OFFSET+H*STRIDE).order(ByteOrder.LITTLE_ENDIAN);
        for(int y=0;y<H;y++)for(int x=0;x<W;x++)
            b.putShort(OFFSET+y*STRIDE+x*2,(short)channels[MAP[cfa][(y%2)*2+x%2]]);
        return b;
    }
    private static M10RFirmwareRaw2R.Sample sample(ByteBuffer b,int cfa,double[] black,int white,M10RMetering1U.Config cfg){
        return M10RFirmwareRaw2R.sample(b,OFFSET,STRIDE,W,H,cfa,black,white,cfg);
    }
    @Test public void fourCfasPreserveCanonicalColorsAndBufferCursor() {
        for(int cfa=0;cfa<4;cfa++) {
            var b=frame(cfa,new int[]{1010,2020,3030,4040});b.position(7);b.order(ByteOrder.BIG_ENDIAN);
            double[] black=new double[4];for(int p=0;p<4;p++)black[p]=10*(MAP[cfa][p]+1);
            var s=sample(b,cfa,black,5000,CFG);
            assertEquals(7,b.position());assertEquals(ByteOrder.BIG_ENDIAN,b.order());
            for(int i=0;i<352;i++) {
                assertEquals(2500,s.meanYCodes()[i]);int n=s.counts()[i];
                for(int c=0;c<4;c++) {
                    assertEquals((long)n*(c+1)*1010,s.codeSums()[i*4+c]);
                    assertEquals((double)n*(c+1)*1000,s.correctedSums()[i*4+c],0);
                }
            }
        }
    }
    @Test public void clippingIsRetainedWithoutWhiteClampingOrRepair() {
        var s=sample(frame(0,new int[]{999,1000,1200,65535}),0,new double[4],1000,CFG);
        for(int i=0;i<352;i++) {
            int n=s.counts()[i];assertEquals(n,s.atWhite()[i*4+1]);assertEquals(n,s.aboveWhite()[i*4+2]);
            assertEquals(n,s.aboveWhite()[i*4+3]);assertEquals(n,s.nearWhite()[i*4]);
            assertEquals(65535.0*n,s.correctedSums()[i*4+3],0);
            assertTrue(s.meanYCodes()[i]>1000);
        }
    }
    @Test public void fractionalBlackAndDarkFloorHaveExplicitArithmetic() {
        var s=sample(frame(0,new int[]{10,20,30,40}),0,new double[]{10.5,1.25,2.5,3.75},1000,CFG);
        long expected=(long)Math.floor((45*18.75+45*27.5+83*36.25+128)/256);
        for(long v:s.meanYCodes())assertEquals(expected,v);
    }
    @Test public void cropCountsMatchExistingMeterSampleMembership() {
        var cfg=new M10RMetering1U.Config(M10RMetering1U.Mode.MULTI_FIELD,.13,.17,.88,.83,.5,.5);
        var s=sample(frame(0,new int[]{100,100,100,100}),0,new double[4],1000,cfg);
        int[] expected=new int[352];
        for(int y=0;y<128;y++)for(int x=0;x<176;x++) {
            double px=M10RMetering1U.sampleCoordinate(x,176,W)+.5,py=M10RMetering1U.sampleCoordinate(y,128,H)+.5;
            if(px<cfg.left*W||px>=cfg.right*W||py<cfg.top*H||py>=cfg.bottom*H)continue;
            expected[(int)((py-cfg.top*H)/((cfg.bottom-cfg.top)*H)*16)*22+
                    (int)((px-cfg.left*W)/((cfg.right-cfg.left)*W)*22)]++;
        }
        assertArrayEquals(expected,s.counts());for(long v:s.meanYCodes())assertEquals(100,v);
    }
    @Test public void invalidLayoutsAndIncompleteCropsFailClosed() {
        var b=frame(0,new int[]{1,2,3,4});
        assertThrows(IllegalArgumentException.class,()->sample(b,4,new double[4],1000,CFG));
        assertThrows(IllegalArgumentException.class,()->sample(b,0,new double[]{0,0,0,Double.NaN},1000,CFG));
        assertThrows(IllegalArgumentException.class,()->sample(b,0,new double[4],1000,
                new M10RMetering1U.Config(M10RMetering1U.Mode.SPOT,.49,.49,.51,.51,.5,.5)));
        b.limit(30);assertThrows(IllegalArgumentException.class,()->sample(b,0,new double[4],1000,CFG));
    }
    @Test public void snapshotsAreDefensiveAndExplainTheInputDomain()throws Exception {
        var s=sample(frame(0,new int[]{100,100,100,100}),0,new double[4],1000,CFG);
        s.counts()[0]=0;s.meanYCodes()[0]=999;s.codeSums()[0]=0;s.black()[0]=99;
        JSONObject j=new JSONObject();M10RFirmwareShadow2R.appendSample(j,s);
        assertEquals(100,j.getJSONArray("trialYCells").getLong(0));assertTrue(s.counts()[0]>0);
        assertEquals(1408,j.getJSONArray("codeSumsCellMajor").length());assertFalse(j.getBoolean("upperClampApplied"));
    }
    @Test public void nativeBridgeRunsOriginalFixtureAndReturnsFourCompleteTrials()throws Exception {
        System.loadLibrary("m10rfirmwareshadow");assertTrue(M10RFirmwareShadow2R.nativeSelfTest());
        long[] y=new long[352];Arrays.fill(y,1000);
        int[] p=M10RFirmwareShadow2R.nativeEvaluate(y,1280,1792);
        var j=M10RFirmwareShadow2R.trials(p);assertEquals(4,j.length());
        for(int t=0;t<4;t++) {
            var trial=j.getJSONObject(t);assertEquals(t,trial.getInt("tilt"));
            assertEquals(24,trial.getJSONArray("regions").length());assertEquals(800,trial.getString("aggregateWorkHex").length());
            assertEquals(1000,trial.getJSONArray("regions").getJSONObject(0).getInt("normalizedY"));
        }
        Arrays.fill(y,0);p=M10RFirmwareShadow2R.nativeEvaluate(y,0,0);
        assertEquals(-12,p[1]);assertEquals(-12,p[126]);
    }
    @Test public void nativeBridgeRejectsMalformedAndUnsignedOverflowInputs() {
        System.loadLibrary("m10rfirmwareshadow");
        assertThrows(IllegalArgumentException.class,()->M10RFirmwareShadow2R.nativeEvaluate(new long[351],0,0));
        long[] y=new long[352];y[0]=1L<<32;
        assertThrows(IllegalArgumentException.class,()->M10RFirmwareShadow2R.nativeEvaluate(y,0,0));
        y[0]=-1;assertThrows(IllegalArgumentException.class,()->M10RFirmwareShadow2R.nativeEvaluate(y,0,0));
        assertThrows(IllegalArgumentException.class,()->M10RFirmwareShadow2R.nativeEvaluate(new long[352],32768,0));
    }
    @Test public void diagnosticFailureStaysDataAndCannotRequestExposure()throws Exception {
        var binding=new M10RExposureProbe1B.Binding("test",1,1,1,1,1000,100,0,0,0);
        String text=M10RFirmwareShadow2R.capture(null,0,0,0,null,0,null,null,binding);
        var j=new JSONObject(text);assertEquals("DIAGNOSTIC_UNAVAILABLE",j.getString("status"));
        assertFalse(j.getBoolean("controlsExposure"));assertFalse(j.getBoolean("recommendedExposureAvailable"));
        JSONObject parent=new JSONObject();M10RFirmwareShadow2R.appendTo(parent,text);
        assertEquals(1,parent.length());M10RFirmwareShadow2R.appendTo(parent,"invalid JSON");
        assertFalse(parent.getJSONObject("firmwareShadow2R").getBoolean("controlsExposure"));
    }
    @Test public void apexCandidatesAreExplicitlyRoundedAndBounded() {
        assertEquals(1280,M10RFirmwareShadow2R.apexQ8(Math.log(100/3.125)/Math.log(2)));
        assertEquals(2048,M10RFirmwareShadow2R.apexQ8(Math.log(256)/Math.log(2)));
        assertThrows(IllegalArgumentException.class,()->M10RFirmwareShadow2R.apexQ8(Double.NaN));
    }
    @Test public void completeFrameBindingAndJniRoundTripProduceReplayableSidecar()throws Exception {
        var c=mock(CameraCharacteristics.class);var r=mock(CaptureResult.class);
        when(r.get(CaptureResult.SENSOR_TIMESTAMP)).thenReturn(123L);
        when(r.get(CaptureResult.SENSOR_EXPOSURE_TIME)).thenReturn(10000000L);
        when(r.get(CaptureResult.SENSOR_SENSITIVITY)).thenReturn(100);
        when(r.get(CaptureResult.SENSOR_DYNAMIC_BLACK_LEVEL)).thenReturn(new float[4]);
        when(r.get(CaptureResult.SENSOR_DYNAMIC_WHITE_LEVEL)).thenReturn(4095);
        var binding=new M10RExposureProbe1B.Binding("physical-test",1,2,123,123,10000000,100,0,0,0,CFG);
        ByteBuffer b=ByteBuffer.allocate(W*H*2).order(ByteOrder.LITTLE_ENDIAN);
        for(int y=0;y<H;y++)for(int x=0;x<W;x++)b.putShort((y*W+x)*2,(short)(100+x*3+y));
        String text=M10RFirmwareShadow2R.capture(b,W,H,0,new double[4],4095,c,r,binding);
        var j=new JSONObject(text);assertEquals("UNCALIBRATED_TRIAL_COMPLETE",j.getString("status"));
        assertTrue(j.getBoolean("nativeSelfTestPassed"));assertFalse(j.getBoolean("calibrated"));
        assertEquals(123,j.getLong("imageTimestampNs"));assertEquals("physical-test",j.getString("cameraKey"));
        String destination=System.getProperty("m10r.shadow.fixture");
        if(destination!=null)java.nio.file.Files.write(java.nio.file.Paths.get(destination),
                new JSONObject().put("syntheticHostTestOnly",true).put("firmwareShadow2R",j).toString(2)
                        .getBytes(java.nio.charset.StandardCharsets.UTF_8));
        when(r.get(CaptureResult.SENSOR_TIMESTAMP)).thenReturn(124L);
        j=new JSONObject(M10RFirmwareShadow2R.capture(b,W,H,0,new double[4],4095,c,r,binding));
        assertEquals("DIAGNOSTIC_UNAVAILABLE",j.getString("status"));assertFalse(j.has("trials"));
    }
}
