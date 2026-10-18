package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.*;
import android.hardware.camera2.params.BlackLevelPattern;
import com.particlesdevs.photoncamera.processing.ImageFrame;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import org.json.JSONObject;
import org.junit.Test;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

public class M10RRawResponse2STest {
    @org.junit.BeforeClass public static void keys() throws Exception {
        M10RPreviewMetadata1ETest.installFrameworkKeyIdentities();
        var m=M10RPreviewMetadata1ETest.class.getDeclaredMethod("keys",Class.class,Class.class,String[].class);
        m.setAccessible(true);
        // Distinct identities prevent unrelated null Android stub keys from aliasing.
        for(Class<?> owner:new Class<?>[]{CaptureResult.class,CaptureRequest.class,CameraCharacteristics.class}) {
            Class<?> type=owner==CaptureResult.class?CaptureResult.Key.class:
                    owner==CaptureRequest.class?CaptureRequest.Key.class:CameraCharacteristics.Key.class;
            var names=new java.util.ArrayList<String>();
            for(var f:owner.getFields())if(f.getType()==type&&f.get(null)==null)names.add(f.getName());
            m.invoke(null,owner,type,names.toArray(new String[0]));
        }
    }
    @org.junit.AfterClass public static void restore() throws Exception {M10RPreviewMetadata1ETest.restoreFrameworkKeys();}
    static final int W=384,H=288;
    final CameraCharacteristics c=mock(CameraCharacteristics.class);
    final CaptureResult r=mock(CaptureResult.class);
    final CaptureRequest q=mock(CaptureRequest.class);
    ImageFrame frame(int[] colors) throws Exception {
        var constructor=ImageFrame.class.getDeclaredConstructor();constructor.setAccessible(true);
        ImageFrame f=constructor.newInstance();f.width=W;f.height=H;f.timestamp=100;
        ByteBuffer b=ByteBuffer.allocate(W*H*2).order(ByteOrder.LITTLE_ENDIAN);
        for(int y=0;y<H;y++)for(int x=0;x<W;x++)b.putShort((y*W+x)*2,(short)colors[(y&1)*2+(x&1)]);
        f.buffer=b.asReadOnlyBuffer().order(ByteOrder.BIG_ENDIAN);f.buffer.position(7);
        when(c.get(CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT)).thenReturn(0);
        when(r.get(CaptureResult.SENSOR_TIMESTAMP)).thenReturn(100L);
        when(r.get(CaptureResult.SENSOR_EXPOSURE_TIME)).thenReturn(4000000L);
        when(r.get(CaptureResult.SENSOR_SENSITIVITY)).thenReturn(100);
        when(r.get(CaptureResult.SENSOR_DYNAMIC_BLACK_LEVEL)).thenReturn(new float[]{64,64,64,64});
        when(r.get(CaptureResult.SENSOR_DYNAMIC_WHITE_LEVEL)).thenReturn(1023);
        when(r.get(CaptureResult.CONTROL_AE_MODE)).thenReturn(0);
        when(q.get(CaptureRequest.SENSOR_EXPOSURE_TIME)).thenReturn(4001000L);
        when(q.get(CaptureRequest.SENSOR_SENSITIVITY)).thenReturn(100);
        when(q.get(CaptureRequest.CONTROL_AE_MODE)).thenReturn(0);
        return f;
    }
    JSONObject capture(ImageFrame f) throws Exception {
        JSONObject parent=new JSONObject();M10RRawResponse2S.append(parent,f,c,r,q);
        return parent.getJSONObject("photographicRawResponse2S");
    }
    @Test public void manualPhotographUsesDeliveredFrameAndPreservesBuffer() throws Exception {
        var f=frame(new int[]{164,264,364,464});var j=capture(f);
        assertEquals("PHOTOGRAPHIC_RAW_MEASURED",j.getString("status"));
        assertEquals(4000000L,j.getLong("exposureNs"));assertEquals(4001000L,j.getLong("requestedExposureNs"));
        assertEquals(0,j.getInt("aeMode"));assertTrue(j.getBoolean("frameTimestampMatched"));
        assertFalse(j.getBoolean("controlsExposure"));assertFalse(j.getBoolean("leicaScaleAssigned"));
        assertEquals(352,j.getJSONArray("sampleCounts").length());
        for(int i=0;i<352;i++)assertEquals(250,j.getJSONArray("trialYCells").getInt(i));
        assertEquals(7,f.buffer.position());assertEquals(ByteOrder.BIG_ENDIAN,f.buffer.order());
        assertTrue(f.buffer.isReadOnly());
        String destination=System.getProperty("m10r.response.fixture");
        if(destination!=null)java.nio.file.Files.write(java.nio.file.Paths.get(destination),
                new JSONObject().put("syntheticHostTestOnly",true).put("photographicRawResponse2S",j)
                        .toString(2).getBytes(java.nio.charset.StandardCharsets.UTF_8));
    }
    @Test public void actualPhotographSeparatesAtWhiteFromAboveWhite() throws Exception {
        var j=capture(frame(new int[]{1022,1023,1024,65535}));
        assertEquals("PHOTOGRAPHIC_RAW_MEASURED",j.getString("status"));
        for(int i=0;i<352;i++) {
            int n=j.getJSONArray("sampleCounts").getInt(i);
            assertEquals(n,j.getJSONArray("atWhiteCellMajor").getInt(4*i+1));
            assertEquals(n,j.getJSONArray("aboveWhiteCellMajor").getInt(4*i+2));
            assertEquals(n,j.getJSONArray("aboveWhiteCellMajor").getInt(4*i+3));
        }
    }
    @Test public void wrongTimestampCannotProduceMeasuredGrid() throws Exception {
        var f=frame(new int[]{100,100,100,100});f.timestamp=101;var j=capture(f);
        assertEquals("DIAGNOSTIC_UNAVAILABLE",j.getString("status"));
        assertFalse(j.has("sampleCounts"));
    }
    @Test public void missingBlackIsNotReplacedByRendererFallback() throws Exception {
        var f=frame(new int[]{100,100,100,100});
        when(r.get(CaptureResult.SENSOR_DYNAMIC_BLACK_LEVEL)).thenReturn(null);
        assertEquals("black_metadata_missing",capture(f).getString("reason"));
    }
    @Test public void staticMetadataIsExplicitlyIdentified() throws Exception {
        var f=frame(new int[]{100,100,100,100});var black=mock(BlackLevelPattern.class);
        when(r.get(CaptureResult.SENSOR_DYNAMIC_BLACK_LEVEL)).thenReturn(null);
        when(r.get(CaptureResult.SENSOR_DYNAMIC_WHITE_LEVEL)).thenReturn(null);
        when(c.get(CameraCharacteristics.SENSOR_BLACK_LEVEL_PATTERN)).thenReturn(black);
        when(c.get(CameraCharacteristics.SENSOR_INFO_WHITE_LEVEL)).thenReturn(1023);
        doAnswer(call->{java.util.Arrays.fill((int[])call.getArgument(0),64);return null;}).when(black).copyTo(any(int[].class),eq(0));
        var j=capture(f);assertEquals("PHOTOGRAPHIC_RAW_MEASURED",j.getString("status"));
        assertEquals("characteristics",j.getString("blackSource"));assertEquals("characteristics",j.getString("whiteSource"));
    }
    @Test public void transformedAndCroppedFramesFailWithoutThrowingToCapture() throws Exception {
        var f=frame(new int[]{100,100,100,100});f.fp16=true;
        assertEquals("DIAGNOSTIC_UNAVAILABLE",capture(f).getString("status"));f.fp16=false;f.cropOriginX=2;
        assertEquals("DIAGNOSTIC_UNAVAILABLE",capture(f).getString("status"));f.cropOriginX=0;f.packedBits=10;
        assertEquals("DIAGNOSTIC_UNAVAILABLE",capture(f).getString("status"));
    }
}
