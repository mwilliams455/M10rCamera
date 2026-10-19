package com.particlesdevs.photoncamera.m10r;

import org.junit.Test;
import java.util.concurrent.atomic.AtomicInteger;
import static org.junit.Assert.*;

public class M10RDetail3DTest {
    @Test public void controlNeverCallsNative() {
        M10RDetail3D.Result r = M10RDetail3D.run(false, 200, iso -> {
            throw new AssertionError("Control must not invoke sharpening");
        });
        assertFalse(r.executed);
        assertEquals(200, r.iso);
        assertEquals(0L, r.affectedPixels);
        assertEquals(0.0, r.elapsedMs, 0.0);
    }

    @Test public void trialCallsOnceWithDeliveredSensorIso() {
        AtomicInteger calls = new AtomicInteger();
        M10RDetail3D.Result r = M10RDetail3D.run(true, 200, iso -> {
            calls.incrementAndGet();
            assertEquals(200, iso);
            return 456134L;
        });
        assertEquals(1, calls.get());
        assertTrue(r.executed);
        assertEquals(200, r.iso);
        assertEquals(456134L, r.affectedPixels);
        assertTrue(r.elapsedMs >= 0.0);
    }

    @Test public void invalidOrMissingIsoRetainsExistingFallback() {
        for (Integer input : new Integer[]{null, 0, -1}) {
            M10RDetail3D.Result r = M10RDetail3D.run(true, input, iso -> {
                assertEquals(100, iso);
                return 0L;
            });
            assertEquals(100, r.iso);
        }
    }

    @Test public void zeroAffectedStillMeansPassExecuted() {
        M10RDetail3D.Result r = M10RDetail3D.run(true, 640, iso -> 0L);
        assertTrue(r.executed);
        assertEquals(0L, r.affectedPixels);
    }

    @Test public void everyNativeFailureCodeRejectsTheRender() {
        for (long code : new long[]{-1L, -2L, -3L}) {
            IllegalStateException e = assertThrows(IllegalStateException.class,
                    () -> M10RDetail3D.run(true, 100, iso -> code));
            assertTrue(e.getMessage().contains(Long.toString(code)));
        }
    }

    @Test public void nativeExceptionsReachRendererCleanup() {
        RuntimeException failure = new RuntimeException("native failure");
        assertSame(failure, assertThrows(RuntimeException.class,
                () -> M10RDetail3D.run(true, 100, iso -> { throw failure; })));
    }
}
