package com.particlesdevs.photoncamera.m10r;

import org.junit.Test;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import static org.junit.Assert.*;

public class M10RCaptureLifecycle1GTest {
    @Test public void repeatedPhotosNeedNoGalleryReset() {
        var gate = new M10RCaptureLifecycle1G();
        for (int i = 0; i < 20; i++) {
            long shot = gate.begin();
            assertTrue(shot > 0);
            assertEquals(0, gate.begin());
            assertTrue(gate.submitted(shot));
            assertTrue(gate.processing(shot));
            assertEquals(0, gate.begin());
            assertTrue(gate.finish(shot));
            assertFalse(gate.busy());
        }
    }
    @Test public void rejectedMeterOrCameraCanBeRetried() {
        var gate = new M10RCaptureLifecycle1G();
        long shot = gate.begin();
        assertTrue(gate.finish(shot));
        assertTrue(gate.begin() > shot);
    }
    @Test public void duplicateFocusOrSequenceCallbacksCannotDispatchTwoSavers() {
        var gate = new M10RCaptureLifecycle1G();
        long shot = gate.begin();
        assertFalse(gate.processing(shot));
        assertTrue(gate.submitted(shot));
        assertFalse(gate.submitted(shot));
        assertTrue(gate.processing(shot));
        assertFalse(gate.processing(shot));
        assertFalse(gate.acquiring(shot));
    }
    @Test public void lateCompletionCannotReleaseTheNextPhoto() {
        var gate = new M10RCaptureLifecycle1G();
        long old = gate.begin();gate.submitted(old);gate.processing(old);gate.finish(old);
        long next = gate.begin();
        assertFalse(gate.finish(old));
        assertFalse(gate.processing(old));
        assertTrue(gate.owns(next));
    }
    @Test public void galleryRestartCannotUnlockLiveSaver() {
        var gate = new M10RCaptureLifecycle1G();
        long shot = gate.begin();gate.submitted(shot);gate.processing(shot);
        gate.retireCamera();
        assertEquals(0, gate.begin());
        assertTrue(gate.owns(shot));
        gate.finish(shot);
        assertTrue(gate.begin() > shot);
    }
    @Test public void cameraCloseCancelsAcquisitionAndRejectsItsLateCallbacks() {
        var gate = new M10RCaptureLifecycle1G();
        long shot = gate.begin();gate.submitted(shot);gate.retireCamera();
        long next = gate.begin();
        assertFalse(gate.processing(shot));assertFalse(gate.finish(shot));
        assertTrue(gate.owns(next));
    }
    @Test public void simultaneousShutterPressesAdmitOnlyOneOwner() throws Exception {
        var gate = new M10RCaptureLifecycle1G();
        var start = new CountDownLatch(1);var pool = Executors.newFixedThreadPool(8);
        var accepted = new AtomicInteger();
        try {
            Future<?>[] tasks = new Future[8];
            for (int i = 0; i < tasks.length; i++) tasks[i] = pool.submit(() -> {
                start.await();if (gate.begin() != 0) accepted.incrementAndGet();return null;
            });
            start.countDown();for (var task : tasks) task.get(5, TimeUnit.SECONDS);
            assertEquals(1, accepted.get());
        } finally { pool.shutdownNow(); }
    }
}
