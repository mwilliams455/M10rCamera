package com.particlesdevs.photoncamera.m10r;

import java.nio.ByteBuffer;
import org.junit.Test;
import static org.junit.Assert.*;

public class M10RPhotoNormalization3GTest {
    private static final int W = 176, H = 128;
    private static final double[] BLACK = {64, 64.5, 63.75, 64};
    private static ByteBuffer buffer() { return ByteBuffer.allocate(W * H * 2); }
    private static M10RExposureRaw1B.Prepared prepared(int w, int h, int cfa, double scale) {
        return new M10RExposureRaw1B.Prepared(new short[w * h], new double[352],
                new long[4], new long[4], new long[4], w, h, cfa, scale);
    }
    private static M10RPhotoNormalization3G.Result run(boolean enabled, ByteBuffer data,
            int w, int h, int cfa, double[] black, float[] map, int cols, int rows,
            M10RPhotoNormalization3G.Backend backend) {
        return M10RPhotoNormalization3G.tryPrepare(enabled, data, w, h, cfa,
                black, 1023, map, cols, rows, 1, backend);
    }
    private static final M10RPhotoNormalization3G.Backend NEVER = (b,w,h,c,bl,wh,m,nc,nr) -> {
        throw new AssertionError("unsupported/disabled input reached native backend");
    };

    @Test public void disabledControlNeverCallsNative() {
        assertEquals("disabled_3F_control", run(false, buffer(), W, H, 0, BLACK, null, 0, 0, NEVER).status);
    }
    @Test public void unsupportedLayoutsRetainFallback() {
        assertNull(run(true, buffer(), W-1, H, 0, BLACK, null, 0, 0, NEVER).prepared);
        assertNull(run(true, buffer(), W, H-1, 0, BLACK, null, 0, 0, NEVER).prepared);
        assertNull(run(true, buffer(), 8193, H, 0, BLACK, null, 0, 0, NEVER).prepared);
        assertNull(run(true, ByteBuffer.allocate(4), W, H, 0, BLACK, null, 0, 0, NEVER).prepared);
        assertNull(run(true, buffer(), W, H, 4, BLACK, null, 0, 0, NEVER).prepared);
    }
    @Test public void unsupportedMetadataRetainsFallback() {
        for (double bad : new double[]{-1, 1023, Double.NaN, Double.POSITIVE_INFINITY}) {
            double[] black=BLACK.clone();black[1]=bad;
            assertNull(run(true, buffer(), W, H, 0, black, null, 0, 0, NEVER).prepared);
        }
        for (float bad : new float[]{0, -1, 65, Float.NaN, Float.POSITIVE_INFINITY}) {
            float[] map=new float[16];java.util.Arrays.fill(map,1);map[2]=bad;
            assertNull(run(true, buffer(), W, H, 0, BLACK, map, 2, 2, NEVER).prepared);
        }
        assertNull(run(true, buffer(), W, H, 0, BLACK, new float[15], 2, 2, NEVER).prepared);
        assertNull(run(true, buffer(), W, H, 0, BLACK, null, 2, 2, NEVER).prepared);
    }
    @Test public void successfulResultUsesOwnedPlaneAndProtectsCallerCursor() {
        ByteBuffer input=buffer();input.position(17);
        M10RExposureRaw1B.Prepared expected=prepared(W,H,2,1);
        M10RPhotoNormalization3G.Result r=run(true,input,W,H,2,BLACK,null,0,0,
                (b,w,h,c,bl,wh,m,nc,nr)->{b.position(0);return expected;});
        assertSame(expected,r.prepared);assertEquals(17,input.position());
        assertEquals("native_existing_EXPOSURE1E",r.status);
    }
    @Test public void invalidNativeResultIsNotPublished() {
        assertNull(run(true,buffer(),W,H,0,BLACK,null,0,0,(b,w,h,c,bl,wh,m,nc,nr)->null).prepared);
        assertNull(run(true,buffer(),W,H,0,BLACK,null,0,0,
                (b,w,h,c,bl,wh,m,nc,nr)->prepared(w,h,c,.5)).prepared);
        assertNull(run(true,buffer(),W,H,0,BLACK,null,0,0,
                (b,w,h,c,bl,wh,m,nc,nr)->prepared(w,h,1,1)).prepared);
    }
    @Test public void recoverableNativeFailureReturnsFallback() {
        assertTrue(run(true,buffer(),W,H,0,BLACK,null,0,0,
                (b,w,h,c,bl,wh,m,nc,nr)->{throw new UnsatisfiedLinkError("test");}).status.contains("UnsatisfiedLinkError"));
        assertTrue(run(true,buffer(),W,H,0,BLACK,null,0,0,
                (b,w,h,c,bl,wh,m,nc,nr)->{throw new IllegalStateException("test");}).status.contains("IllegalStateException"));
    }
    @Test(expected=OutOfMemoryError.class) public void allocationFailureIsNotHidden() {
        run(true,buffer(),W,H,0,BLACK,null,0,0,
                (b,w,h,c,bl,wh,m,nc,nr)->{throw new OutOfMemoryError("test");});
    }
}
