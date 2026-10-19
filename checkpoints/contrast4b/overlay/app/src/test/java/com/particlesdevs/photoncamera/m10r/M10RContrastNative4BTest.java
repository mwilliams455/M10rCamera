package com.particlesdevs.photoncamera.m10r;

import android.util.Base64;
import java.io.ByteArrayInputStream;
import java.io.InputStream;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;
import java.util.zip.GZIPInputStream;
import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.AfterClass;
import org.junit.BeforeClass;
import org.junit.Test;
import org.mockito.MockedStatic;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/**
 * Real inherited JNI pixel arithmetic with frozen pre-4B MEDIUM/DG inputs.
 * The verified host exposure JNI shim forwards to the same nativeProcessTile
 * operator as production m10rExposure1B.cpp. This does not exercise Android
 * bitmap detail, the 3I optimization, or full-frame AMaZE demosaicing.
 */
public class M10RContrastNative4BTest {
    private static final String PROBE_SHA =
            "cc872ebe46765fa4b0337a4418b425f34df63a64e6afece33bb7bb2ec365ce33";
    private static final String MEDIUM_SHA =
            "2fd6ca209f290c75aa96976b3d7692e55c41a55c0017a063aba9808da3b41a00";
    private static final String DG_SHA =
            "9e65de24d52271be0783f4e2728f20f482c0ba43b63159b75033b4a4fc75457d";
    private static final String[] VARIANTS = {
            "legacy", "renderedBeforeOrder", "renderedCurrentOrder"
    };

    private static MockedStatic<Base64> base64;
    private static JSONObject probe, goldenCorpus;
    private static int[] frozenMedium, frozenDg;
    private static Method nativeRender;
    private static M10RRenderedColor1A renderedColor;

    @BeforeClass public static void nativeFixture() throws Exception {
        M10RSourceCalibration3CTest.keys();
        // Replace only the nonfunctional Android host decoder, retaining the
        // production gzip inflater, int decoding and real native arithmetic.
        base64 = mockStatic(Base64.class);
        base64.when(() -> Base64.decode(anyString(), anyInt()))
                .thenAnswer(i -> java.util.Base64.getDecoder().decode((String) i.getArgument(0)));

        byte[] resource = resource("/contrast4b/native_probe4a.json");
        assertEquals(PROBE_SHA, sha256(resource));
        probe = new JSONObject(new String(resource, StandardCharsets.UTF_8));
        byte[] mediumBytes = inflate(probe.getString("mediumU32leGzipBase64"));
        byte[] dgBytes = inflate(probe.getString("dgU16leGzipBase64"));
        assertEquals(MEDIUM_SHA, sha256(mediumBytes));
        assertEquals(DG_SHA, sha256(dgBytes));
        frozenMedium = unpack(mediumBytes, 4);
        frozenDg = unpack(dgBytes, 2);
        assertEquals(10240, frozenMedium.length);
        assertEquals(32768, frozenDg.length);

        assertArrayEquals(frozenMedium,
                M10RContrast4B.nativeToneTable(M10RContrast4B.Level.STANDARD));
        assertArrayEquals(frozenMedium, M10RContrast4B.nativeToneTable(null));
        assertArrayEquals(frozenDg, M10RToneDg1A.nativeDgTable());
        assertEquals("136b69127e73cc43c28c0aa7b511f1f3e9b29be139f4d491422f2eb574a49fb0",
                sha256(pack(M10RContrast4B.nativeToneTable(M10RContrast4B.Level.LOW), 4)));
        assertEquals("0a764cf29d35cd4a4eb7f816e5d128bccaef81b4d5eca991d9b80ab207bd0101",
                sha256(pack(M10RContrast4B.nativeToneTable(M10RContrast4B.Level.HIGH), 4)));

        byte[] golden = resource(probe.getString("existingGoldenResource"));
        assertEquals(probe.getString("existingGoldenSha256"), sha256(golden));
        goldenCorpus = new JSONObject(new String(golden, StandardCharsets.UTF_8));
        nativeRender = M10RExposureNative1B.class.getDeclaredMethod("nativeRender",
                short[].class, int.class, double.class, double[].class, int[].class,
                double[].class, double[].class, int[].class, int[].class,
                int[].class, long[].class, boolean.class);
        nativeRender.setAccessible(true);
        Field field = M10RNativeRenderer.class.getDeclaredField("RENDERED_COLOR");
        field.setAccessible(true);
        renderedColor = (M10RRenderedColor1A) field.get(null);
    }

    @AfterClass public static void restore() throws Exception {
        try { if (base64 != null) base64.close(); }
        finally { M10RSourceCalibration3CTest.restore(); }
    }

    @Test public void standardAndMissingSelectionKeepEveryFrozenNativeGoldenPixel() throws Exception {
        JSONArray cases = goldenCorpus.getJSONArray("cases");
        for (int i = 0; i < cases.length(); i++) {
            JSONObject golden = cases.getJSONObject(i);
            M10RExposureNative1B.Context[] contexts = variants(golden, null);
            short[] rgb = shorts(golden.getJSONArray("sensorRgbU16"));
            double inverseScale = golden.getDouble("inverseScale");
            for (int v = 0; v < contexts.length; v++) {
                String label = "fixture " + i + " " + VARIANTS[v];
                JSONObject state = golden.getJSONObject(VARIANTS[v]);
                M10RExposureNative1B.Context context = contexts[v];
                assertState(label, state, context);
                assertSame(M10RContrast4B.Level.STANDARD, context.contrast4B);
                int[] expected = ints(state.getJSONArray("argb"));
                // Frozen output oracle plus independent old table invocation:
                // neither expected path consults the new profile selector.
                assertArrayEquals(label + " frozen 4A-compatible output", expected,
                        context.render(rgb, inverseScale));
                assertArrayEquals(label + " explicit old MEDIUM/DG arguments", expected,
                        reference(rgb, inverseScale, state, frozenMedium));
                assertArrayEquals(label + " missing selection", expected,
                        context.withContrast(null).render(rgb, inverseScale));
                assertEquals(label, state.getString("revision"),
                        context.withContrast(null).revision);
            }
        }
    }

    @Test public void selectedProfilesReachNativePixelsForColorAndSparseDngSamples() throws Exception {
        short[][] inputs = {syntheticRgb(), sparseDngRgb()};
        assertEquals(64 * 3, inputs[1].length);
        long lowChanges = 0, highChanges = 0, pairChanges = 0;
        long dngLowChanges = 0, dngHighChanges = 0;
        JSONArray cases = goldenCorpus.getJSONArray("cases");
        for (int i = 0; i < cases.length(); i++) {
            JSONObject golden = cases.getJSONObject(i);
            M10RExposureNative1B.Context[] contexts = variants(golden, null);
            for (int v = 0; v < contexts.length; v++) {
                JSONObject state = golden.getJSONObject(VARIANTS[v]);
                for (int input = 0; input < inputs.length; input++) {
                    short[] rgb = inputs[input];
                    int[] standard = contexts[v].render(rgb, 1.0);
                    int[] low = contexts[v].withContrast(M10RContrast4B.Level.LOW).render(rgb, 1.0);
                    int[] high = contexts[v].withContrast(M10RContrast4B.Level.HIGH).render(rgb, 1.0);
                    assertArrayEquals("Standard uses the frozen pre-4B table",
                            reference(rgb, 1.0, state, frozenMedium), standard);
                    assertArrayEquals("Low uses LOW in the real JNI call",
                            reference(rgb, 1.0, state, M10RContrastTables4B.low()), low);
                    assertArrayEquals("High uses HIGH in the real JNI call",
                            reference(rgb, 1.0, state, M10RContrastTables4B.high()), high);
                    lowChanges += differences(standard, low);
                    highChanges += differences(standard, high);
                    pairChanges += differences(low, high);
                    if (input == 1) {
                        dngLowChanges += differences(standard, low);
                        dngHighChanges += differences(standard, high);
                    }
                    assertOpaque(standard);
                    assertOpaque(low);
                    assertOpaque(high);
                }
            }
        }
        assertTrue("Low must change actual rendered RGB pixels", lowChanges > 0);
        assertTrue("High must change actual rendered RGB pixels", highChanges > 0);
        assertTrue("Low and High cannot share the same native output", pairChanges > 0);
        assertTrue("Low changes representative supplied-DNG inputs", dngLowChanges > 0);
        assertTrue("High changes representative supplied-DNG inputs", dngHighChanges > 0);
    }

    @Test public void copiedContextsFreezeContrastWithoutReplacingSourceColourOrFrameBinding() throws Exception {
        JSONObject golden = goldenCorpus.getJSONArray("cases").getJSONObject(0);
        JSONObject state = golden.getJSONObject("legacy");
        M10RSourceCalibration3CTest.Fixture fixture =
                new M10RSourceCalibration3CTest.Fixture(golden.getInt("fixtureIndex"), true);
        when(fixture.r.get(android.hardware.camera2.CaptureResult.SENSOR_TIMESTAMP))
                .thenReturn(state.getLong("frameTimestampNs"));
        M10RSourceWhite3N white = M10RSourceWhite3N.fromCaptureResult(fixture.r);
        M10RExposureNative1B.Context base = context(state, white);
        M10RExposureNative1B.Context low = base.withContrast(M10RContrast4B.Level.LOW);
        M10RExposureNative1B.Context high = low.withContrast(M10RContrast4B.Level.HIGH);
        short[] rgb = sparseDngRgb();
        int[] lowBefore = low.render(rgb, 1.0);
        int[] baseBefore = base.render(rgb, 1.0);
        assertSame(M10RContrast4B.Level.STANDARD, base.contrast4B);
        assertSame(M10RContrast4B.Level.LOW, low.contrast4B);
        assertSame(M10RContrast4B.Level.HIGH, high.contrast4B);
        assertNotSame(base, low);
        assertNotSame(low, high);
        for (M10RExposureNative1B.Context copy : new M10RExposureNative1B.Context[]{low, high}) {
            assertColourAndBindingEqual(base, copy);
            assertSame(white, copy.sourceWhite);
        }

        for (boolean enabled : new boolean[]{false, true}) {
            for (boolean order : new boolean[]{false, true}) {
                M10RExposureNative1B.Context selectedThenPrepared =
                        low.withRenderedColor(renderedColor, enabled, order);
                M10RExposureNative1B.Context preparedThenSelected =
                        base.withRenderedColor(renderedColor, enabled, order)
                                .withContrast(M10RContrast4B.Level.LOW);
                assertSame(M10RContrast4B.Level.LOW, selectedThenPrepared.contrast4B);
                assertSame(white, selectedThenPrepared.sourceWhite);
                assertSame(white, preparedThenSelected.sourceWhite);
                assertColourAndBindingEqual(selectedThenPrepared, preparedThenSelected);
                assertEquals(selectedThenPrepared.revision, preparedThenSelected.revision);
                assertArrayEquals(selectedThenPrepared.render(rgb, 1.0),
                        preparedThenSelected.render(rgb, 1.0));
            }
        }

        // Simulate a later global choice while retaining real selector methods.
        // No Android preference store is needed: any context read of current()
        // would be observed, and would return the conflicting HIGH selection.
        try (MockedStatic<M10RContrast4B> selection = mockStatic(M10RContrast4B.class, invocation -> {
            if (invocation.getMethod().getName().equals("current"))
                return M10RContrast4B.Level.HIGH;
            return invocation.callRealMethod();
        })) {
            assertSame(M10RContrast4B.Level.HIGH, M10RContrast4B.current());
            selection.clearInvocations();
            assertArrayEquals(lowBefore, low.render(rgb, 1.0));
            assertArrayEquals(baseBefore, base.render(rgb, 1.0));
            selection.verify(M10RContrast4B::current, never());
        }

        float[] neutral = white.copySourceNeutral();
        white.copySourceNeutral()[0] = 42;
        assertArrayEquals(neutral, low.sourceWhite.copySourceNeutral(), 0);
        M10RExposureNative1B.Context restored = high.withContrast(M10RContrast4B.Level.STANDARD);
        assertEquals(base.revision, restored.revision);
        assertSame(white, restored.sourceWhite);
        assertColourAndBindingEqual(base, restored);
        assertArrayEquals(baseBefore, restored.render(rgb, 1.0));
        assertArrayEquals(lowBefore, low.render(rgb, 1.0));
    }

    @Test public void neutralRampShowsRecoveredShadowResponseAndSharedEndpoints() throws Exception {
        double[] identity = {1,0,0, 0,1,0, 0,0,1};
        M10RExposureNative1B.Context base = new M10RExposureNative1B.Context(
                identity, new int[]{256,256,256}, identity, identity, "contrast_identity", 1234567890L);
        int[] levels = {0, 655, 3277, 11796, 32768, 64879, 65535};
        short[] rgb = new short[levels.length * 3];
        for (int i = 0; i < levels.length; i++)
            for (int c = 0; c < 3; c++) rgb[i * 3 + c] = (short) levels[i];
        int[] standard = base.render(rgb, 1.0);
        int[] low = base.withContrast(M10RContrast4B.Level.LOW).render(rgb, 1.0);
        int[] high = base.withContrast(M10RContrast4B.Level.HIGH).render(rgb, 1.0);
        for (int endpoint : new int[]{0, levels.length - 1}) {
            assertEquals(standard[endpoint], low[endpoint]);
            assertEquals(standard[endpoint], high[endpoint]);
        }
        assertEquals(0xff000000, standard[0]);
        for (int shadow : new int[]{1, 2}) {
            assertTrue("Low opens deep shadows", red(low[shadow]) > red(standard[shadow]));
            assertTrue("High deepens deep shadows", red(high[shadow]) < red(standard[shadow]));
        }
        assertTrue("High raises the model's 18% middle-tone response",
                red(high[3]) > red(standard[3]));
        assertTrue("Low lowers the model's 18% middle-tone response",
                red(low[3]) < red(standard[3]));
        assertArrayEquals(standard,
                base.withContrast(M10RContrast4B.Level.HIGH).withContrast(null).render(rgb, 1.0));
    }

    private static M10RExposureNative1B.Context context(JSONObject state, M10RSourceWhite3N white)
            throws Exception {
        return new M10RExposureNative1B.Context(
                doubles(state.getJSONArray("sourceToTarget")), ints(state.getJSONArray("ca9")),
                doubles(state.getJSONArray("targetToWorking")), doubles(state.getJSONArray("workingToOutput")),
                state.getString("cameraKey"), state.getLong("frameTimestampNs"), white);
    }

    private static M10RExposureNative1B.Context[] variants(JSONObject golden, M10RSourceWhite3N white)
            throws Exception {
        M10RExposureNative1B.Context base = context(golden.getJSONObject("legacy"), white);
        return new M10RExposureNative1B.Context[]{base,
                base.withRenderedColor(renderedColor, true, false),
                base.withRenderedColor(renderedColor, true, true)};
    }

    private static int[] reference(short[] rgb, double inverseScale, JSONObject state, int[] tone)
            throws Exception {
        int[] argb = new int[rgb.length / 3];
        long[] counts = new long[24];
        nativeRender.invoke(null, rgb, argb.length, inverseScale,
                doubles(state.getJSONArray("sourceToTarget")), ints(state.getJSONArray("ca9")),
                doubles(state.getJSONArray("targetToWorking")), doubles(state.getJSONArray("workingToOutput")),
                tone, frozenDg, argb, counts, state.getBoolean("cc1BeforeDg"));
        assertEquals("Native oracle must process every requested pixel", argb.length, counts[8]);
        assertOpaque(argb);
        return argb;
    }

    private static void assertState(String label, JSONObject state, M10RExposureNative1B.Context context)
            throws Exception {
        for (String name : new String[]{"sourceToTarget", "targetToWorking", "workingToOutput"})
            assertArrayEquals(label + " " + name, doubles(state.getJSONArray(name)),
                    (double[]) field(context, name), 0);
        assertArrayEquals(label, ints(state.getJSONArray("ca9")), (int[]) field(context, "ca9"));
        assertEquals(label, state.getBoolean("cc1BeforeDg"), field(context, "cc1BeforeDg"));
        assertEquals(label, state.getString("revision"), context.revision);
        assertEquals(label, state.getString("cameraKey"), context.cameraKey);
        assertEquals(label, state.getLong("frameTimestampNs"), context.frameTimestampNs);
    }

    private static void assertColourAndBindingEqual(M10RExposureNative1B.Context expected,
            M10RExposureNative1B.Context actual) throws Exception {
        for (String name : new String[]{"sourceToTarget", "targetToWorking", "workingToOutput"})
            assertArrayEquals(name, (double[]) field(expected, name), (double[]) field(actual, name), 0);
        assertArrayEquals((int[]) field(expected, "ca9"), (int[]) field(actual, "ca9"));
        assertEquals(field(expected, "cc1BeforeDg"), field(actual, "cc1BeforeDg"));
        assertEquals(expected.cameraKey, actual.cameraKey);
        assertEquals(expected.frameTimestampNs, actual.frameTimestampNs);
        assertSame(expected.sourceWhite, actual.sourceWhite);
    }

    private static short[] syntheticRgb() {
        int[] levels = {0, 328, 655, 3277, 11796, 32768, 65535};
        List<Short> values = new ArrayList<>();
        for (int r : levels) for (int g : levels) for (int b : levels) {
            values.add((short) r); values.add((short) g); values.add((short) b);
        }
        short[] result = new short[values.size()];
        for (int i = 0; i < result.length; i++) result[i] = values.get(i);
        return result;
    }

    private static short[] sparseDngRgb() throws Exception {
        JSONObject dng = probe.getJSONObject("sparseDng");
        assertFalse(dng.getBoolean("demosaicParityClaimed"));
        assertEquals("7c845978bef32c94f908e09893ade83412f961064e1a4c18fb209b4701c80838",
                dng.getString("sha256"));
        JSONArray samples = dng.getJSONArray("samples");
        assertEquals(64, samples.length());
        short[] result = new short[samples.length() * 3];
        for (int i = 0; i < samples.length(); i++) {
            JSONObject sample = samples.getJSONObject(i);
            assertEquals(0, sample.getInt("x") & 1);
            assertEquals(0, sample.getInt("y") & 1);
            JSONArray rgb = sample.getJSONArray("rgbU16");
            for (int c = 0; c < 3; c++) {
                int value = rgb.getInt(c);
                assertTrue(value >= 0 && value <= 65535);
                result[i * 3 + c] = (short) value;
            }
        }
        return result;
    }

    private static Object field(Object value, String name) throws Exception {
        Field field = value.getClass().getDeclaredField(name);
        field.setAccessible(true);
        return field.get(value);
    }

    private static byte[] resource(String name) throws Exception {
        try (InputStream input = M10RContrastNative4BTest.class.getResourceAsStream(name)) {
            assertNotNull(name, input);
            return input.readAllBytes();
        }
    }

    private static byte[] inflate(String value) throws Exception {
        byte[] gzip = java.util.Base64.getDecoder().decode(value);
        try (GZIPInputStream input = new GZIPInputStream(new ByteArrayInputStream(gzip))) {
            return input.readAllBytes();
        }
    }

    private static int[] unpack(byte[] bytes, int width) {
        assertEquals(0, bytes.length % width);
        ByteBuffer buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN);
        int[] result = new int[bytes.length / width];
        for (int i = 0; i < result.length; i++)
            result[i] = width == 4 ? buffer.getInt() : buffer.getShort() & 0xffff;
        return result;
    }

    private static byte[] pack(int[] values, int width) {
        ByteBuffer buffer = ByteBuffer.allocate(values.length * width).order(ByteOrder.LITTLE_ENDIAN);
        for (int value : values) {
            if (width == 4) buffer.putInt(value); else buffer.putShort((short) value);
        }
        return buffer.array();
    }

    private static String sha256(byte[] bytes) throws Exception {
        StringBuilder text = new StringBuilder();
        for (byte value : MessageDigest.getInstance("SHA-256").digest(bytes))
            text.append(String.format("%02x", value & 0xff));
        return text.toString();
    }

    private static int[] ints(JSONArray array) throws Exception {
        int[] result = new int[array.length()];
        for (int i = 0; i < result.length; i++) result[i] = array.getInt(i);
        return result;
    }

    private static double[] doubles(JSONArray array) throws Exception {
        double[] result = new double[array.length()];
        for (int i = 0; i < result.length; i++) result[i] = array.getDouble(i);
        return result;
    }

    private static short[] shorts(JSONArray array) throws Exception {
        int[] values = ints(array);
        short[] result = new short[values.length];
        for (int i = 0; i < values.length; i++) result[i] = (short) values[i];
        return result;
    }

    private static long differences(int[] a, int[] b) {
        assertEquals(a.length, b.length);
        long result = 0;
        for (int i = 0; i < a.length; i++) if (a[i] != b[i]) result++;
        return result;
    }

    private static void assertOpaque(int[] argb) {
        for (int value : argb) assertEquals(255, value >>> 24);
    }

    private static int red(int argb) { return (argb >>> 16) & 255; }
}
