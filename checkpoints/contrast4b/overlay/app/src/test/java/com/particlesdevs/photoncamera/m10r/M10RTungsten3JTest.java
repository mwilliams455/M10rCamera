package com.particlesdevs.photoncamera.m10r;
import org.junit.Test;
import java.util.concurrent.atomic.AtomicInteger;
import static org.junit.Assert.*;

public class M10RTungsten3JTest {
    @Test public void disabledDoesNotLoadOrInvokeNative() throws Exception {
        M10RTungsten3J.Result r=M10RTungsten3J.run(false, () -> { throw new AssertionError(); });
        assertFalse(r.requested); assertFalse(r.executed); assertEquals(0,r.changedPixels);
        assertEquals("disabled",r.diagnostics().getString("status"));
        assertEquals(0,r.elapsedMs,0);
    }
    @Test public void enabledInvokesOnlyOnceAndPublishesActualCount() throws Exception {
        AtomicInteger calls=new AtomicInteger();
        M10RTungsten3J.Result r=M10RTungsten3J.run(true, () -> { calls.incrementAndGet(); return 234L; });
        assertEquals(1,calls.get()); assertTrue(r.executed); assertEquals(234,r.changedPixels);
        assertTrue(r.diagnostics().getBoolean("applied"));
        assertFalse(r.diagnostics().getBoolean("automaticIlluminantDetection"));
        assertFalse(r.diagnostics().getBoolean("rawDngChanged"));
    }
    @Test public void noMatchingColoursIsSuccessfulWithoutClaimingAChange() throws Exception {
        M10RTungsten3J.Result r=M10RTungsten3J.run(true, () -> 0);
        assertTrue(r.executed); assertFalse(r.diagnostics().getBoolean("applied"));
        assertEquals("completed_no_matching_colours",r.status);
    }
    @Test public void missingNativeLibraryPreservesBaselineAndIsReported() {
        M10RTungsten3J.Result r=M10RTungsten3J.run(true, () -> { throw new UnsatisfiedLinkError("test"); });
        assertTrue(r.requested); assertFalse(r.executed);
        assertEquals("native_unavailable_baseline_retained",r.status);
    }
    @Test public void preflightFailuresCannotClaimApplied() {
        for(long code:new long[]{-1,-2,-3}) {
            M10RTungsten3J.Result r=M10RTungsten3J.run(true, () -> code);
            assertFalse(r.executed); assertEquals(0,r.changedPixels);
            assertEquals("preflight_rejected_baseline_retained",r.status);
        }
    }
    @Test public void failureAfterMutationRejectsTheRender() {
        assertThrows(IllegalStateException.class, () -> M10RTungsten3J.run(true, () -> -4));
    }
    @Test public void unexpectedFailuresReachExistingRendererCleanup() {
        RuntimeException failure=new RuntimeException("test");
        assertSame(failure, assertThrows(RuntimeException.class,
                () -> M10RTungsten3J.run(true, () -> { throw failure; })));
    }
}
