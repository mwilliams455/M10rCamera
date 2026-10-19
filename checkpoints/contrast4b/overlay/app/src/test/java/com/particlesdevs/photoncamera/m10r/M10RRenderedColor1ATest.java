package com.particlesdevs.photoncamera.m10r;

import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;
import java.io.InputStream;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import static org.junit.Assert.*;

/** Golden values come from the frozen Python/firmware evidence, not this Java implementation. */
public class M10RRenderedColor1ATest {
    static JSONObject fixture() throws Exception {
        try (InputStream in=M10RRenderedColor1ATest.class.getResourceAsStream("/m10r_rendered_color1a.json")) {
            assertNotNull(in);return new JSONObject(new String(in.readAllBytes(),StandardCharsets.UTF_8));
        }
    }
    static double[] doubles(JSONArray a) throws Exception {
        double[] out=new double[a.length()];for(int i=0;i<out.length;i++)out[i]=a.getDouble(i);return out;
    }
    static int[] ints(JSONArray a) throws Exception {
        int[] out=new int[a.length()];for(int i=0;i<out.length;i++)out[i]=a.getInt(i);return out;
    }
    static double[] matrix(JSONArray a) throws Exception {
        double[] out=new double[9];for(int i=0;i<9;i++)out[i]=a.getJSONArray(i/3).getDouble(i%3);return out;
    }
    static int[] integerMatrix(JSONArray a) throws Exception {
        int[] out=new int[9];for(int i=0;i<9;i++)out[i]=a.getJSONArray(i/3).getInt(i%3);return out;
    }
    static M10RRenderedColor1A prep(JSONObject f) throws Exception {
        JSONArray rows=f.getJSONArray("locus");double[][] locus=new double[rows.length()][];
        for(int i=0;i<rows.length();i++)locus[i]=doubles(rows.getJSONArray(i));
        return new M10RRenderedColor1A(doubles(f.getJSONArray("profileA")),doubles(f.getJSONArray("profileD65")),locus);
    }
    static M10RRenderedColor1A.Result apply(M10RRenderedColor1A p,JSONObject c,boolean enabled) throws Exception {
        return p.select(enabled,ints(c.getJSONArray("gains")),doubles(c.getJSONArray("baselineWork")),doubles(c.getJSONArray("baselineOutput")));
    }
    @Test public void recoveredReferencesAndPhoneNeutralsMatchGoldenValues() throws Exception {
        JSONObject f=fixture();M10RRenderedColor1A p=prep(f);JSONArray cases=f.getJSONArray("cases");
        assertEquals(12,cases.length());
        for(int i=0;i<cases.length();i++) {
            JSONObject c=cases.getJSONObject(i),e=c.getJSONObject("expected");
            M10RRenderedColor1A.Result r=apply(p,c,true);assertTrue(c.getString("id"),r.applied);
            assertArrayEquals(integerMatrix(e.getJSONArray("integers")),r.cc0.integers);
            assertEquals(e.getInt("scale_code"),r.cc0.scale);
            assertArrayEquals(matrix(e.getJSONArray("effective_for_current_input")),r.targetToWorking,1e-12);
            assertArrayEquals(doubles(e.getJSONArray("white_xy")),r.whiteXy,1e-12);
            assertEquals(e.getDouble("kelvin"),r.kelvin,1e-7);
            assertEquals(e.getJSONArray("iterations").length(),r.passes);
            assertArrayEquals(new int[]{1041,-372,-157,-117,631,-1,-4,-78,595},r.cc1.integers);
        }
    }
    @Test public void disabledSelectionPreservesBothMatricesExactly() throws Exception {
        JSONObject f=fixture();M10RRenderedColor1A p=prep(f);
        JSONArray cases=f.getJSONArray("cases");
        for(int i=0;i<cases.length();i++) {
            JSONObject c=cases.getJSONObject(i);M10RRenderedColor1A.Result r=apply(p,c,false);
            assertFalse(r.applied);assertEquals("disabled",r.reason);
            assertArrayEquals(doubles(c.getJSONArray("baselineWork")),r.targetToWorking,0);
            assertArrayEquals(doubles(c.getJSONArray("baselineOutput")),r.workingToOutput,0);
        }
    }
    @Test public void rejectedStateKeepsBothBaselineMatrices() throws Exception {
        JSONObject f=fixture(),c=f.getJSONArray("cases").getJSONObject(0);M10RRenderedColor1A p=prep(f);
        for(int[] bad:new int[][]{{0,256,256},{256,256,2001},{1,2000,1},{1,2}}) {
            double[] w=doubles(c.getJSONArray("baselineWork")),o=doubles(c.getJSONArray("baselineOutput"));
            M10RRenderedColor1A.Result r=p.select(true,bad,w,o);
            assertFalse(r.reason,r.applied);assertTrue(r.reason.startsWith("capture_state_rejected:"));
            assertArrayEquals(w,r.targetToWorking,0);assertArrayEquals(o,r.workingToOutput,0);
            r.targetToWorking[0]=0;assertNotEquals(0,w[0],0);
        }
    }
    @Test public void renderedRoundingIsHalfAwayFromZeroAndSaturates() {
        double[] v={-.5/512,.5/512,-1.5/512,1.5/512,4,-4,10,-10,0};
        M10RRenderedColor1A.Quantized q=M10RRenderedColor1A.quantize(v,0);
        assertArrayEquals(new int[]{-1,1,-2,2,2047,-2048,2047,-2048,0},q.integers);
        assertEquals(3,q.clipped);
    }
    @Test public void scaleRangeDecisionUsesRoundedCoefficients() {
        double[] v=new double[9];v[0]=2047.49/512;
        assertEquals(0,M10RRenderedColor1A.quantize(v,-1).scale);
        v[0]=2047.5/512;assertEquals(1,M10RRenderedColor1A.quantize(v,-1).scale);
        v[0]=2047.5/256;assertEquals(2,M10RRenderedColor1A.quantize(v,-1).scale);
        v[0]=2047.5/128;assertEquals(3,M10RRenderedColor1A.quantize(v,-1).scale);
        v[0]=100;assertEquals(1,M10RRenderedColor1A.quantize(v,-1).clipped);
    }
    @Test public void previewConversionDoesNotMutateMeterContextOrFrameBinding() throws Exception {
        JSONObject f=fixture(),c=f.getJSONArray("cases").getJSONObject(0);M10RRenderedColor1A p=prep(f);
        double[] source={1,0,0,0,1,0,0,0,1},work=doubles(c.getJSONArray("baselineWork"));
        double[] output=doubles(c.getJSONArray("baselineOutput"));int[] gains=ints(c.getJSONArray("gains"));
        M10RExposureNative1B.Context meter=new M10RExposureNative1B.Context(source,gains,work,output,"physical-test",123);
        M10RExposureNative1B.Context preview=meter.withRenderedColor(p,true),control=meter.withRenderedColor(p,false);
        assertEquals(M10RExposureNative1B.TARGET_REVISION,meter.revision);
        assertEquals(M10RRenderedColor1A.REVISION,preview.revision);
        assertEquals(meter.revision,control.revision);assertEquals(meter.cameraKey,preview.cameraKey);
        assertEquals(meter.frameTimestampNs,preview.frameTimestampNs);
        for(String field:new String[]{"sourceToTarget","targetToWorking","workingToOutput"}) {
            Field a=M10RExposureNative1B.Context.class.getDeclaredField(field);a.setAccessible(true);
            assertArrayEquals((double[])a.get(meter),(double[])a.get(control),0);
            if(field.equals("sourceToTarget"))assertArrayEquals(source,(double[])a.get(preview),0);
        }
        Field a=M10RExposureNative1B.Context.class.getDeclaredField("targetToWorking");a.setAccessible(true);
        assertArrayEquals(work,(double[])a.get(meter),0);
        assertArrayEquals(apply(p,c,true).targetToWorking,(double[])a.get(preview),0);
    }
}
