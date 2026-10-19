package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.*;
import android.media.Image;
import android.media.ImageReader;
import android.os.Handler;
import android.view.Surface;
import org.junit.Test;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

public class M10RMeasuredRaw3NTest {
    static class E implements M10RMeasuredRaw3N.Host, M10RMeasuredRaw3N.Callback {
        final CameraCaptureSession session = mock(CameraCaptureSession.class);
        final ImageReader reader = mock(ImageReader.class);
        final CameraCharacteristics characteristics = mock(CameraCharacteristics.class);
        final Handler handler = mock(Handler.class);
        final CaptureRequest.Builder builder = mock(CaptureRequest.Builder.class);
        final TotalCaptureResult result = mock(TotalCaptureResult.class);
        final AtomicLong generation = new AtomicLong(1);
        final AtomicReference<Object> tag = new AtomicReference<>();
        final Map<Long, Runnable> timers = new HashMap<>();
        final ArrayList<Image> forwarded = new ArrayList<>();
        final M10RMeasuredRaw3N camera;
        final M10RMeasuredRaw3N.Input input;
        CaptureRequest request;
        CameraCaptureSession.CaptureCallback callback;
        M10RMeasuredRaw3N.Frame frame;
        boolean valid = true, rejectedDispatch;
        int copied, failures, retirements, commits;
        String reason;
        E() throws Exception { this(null); }
        E(M10RMeasuredRaw3N.Copier copy) throws Exception {
            when(reader.getSurface()).thenReturn(mock(Surface.class));
            doAnswer(i -> { tag.set(i.getArgument(0)); return null; }).when(builder).setTag(any());
            when(builder.build()).thenAnswer(i -> {
                CaptureRequest built = mock(CaptureRequest.class);
                when(built.getTag()).thenReturn(tag.get());
                return built;
            });
            when(handler.postDelayed(any(), anyLong())).thenAnswer(i -> {
                timers.put(i.getArgument(1), i.getArgument(0)); return true;
            });
            doAnswer(i -> { timers.values().remove(i.getArgument(0)); return null; }).when(handler).removeCallbacks(any());
            when(session.capture(any(), any(), any())).thenAnswer(i -> {
                request = i.getArgument(0); callback = i.getArgument(1); return 9;
            });
            when(result.get(CaptureResult.SENSOR_TIMESTAMP)).thenReturn(100L);
            camera = new M10RMeasuredRaw3N(this, copy != null ? copy : (in, image, ts, exact) -> {
                assertSame(inputCharacteristics(in), in.characteristics);
                assertEquals(100, ts); assertSame(result, exact);
                copied++; image.close(); return null; // ROI copying has its own suite.
            });
            input = newInput(1);
        }
        CameraCharacteristics inputCharacteristics(M10RMeasuredRaw3N.Input in) { return characteristics; }
        M10RMeasuredRaw3N.Input newInput(long id) {
            return new M10RMeasuredRaw3N.Input(session, reader, characteristics, builder, handler,
                    new Object(), new Object(), "2", "2", id,
                    new M10RMeasuredRaw3N.Normalization("2", true, false, 17, 1023),
                    new M10RMeasuredFrame3N.View(50, 50, 100, 100, 90),
                    () -> generation.get() == id, this);
        }
        Image image(long ts) { Image image = mock(Image.class); when(image.getTimestamp()).thenReturn(ts); return image; }
        void start() { assertTrue(camera.start(input)); }
        void bind(Image image) {
            callback.onCaptureStarted(session, request, 100, 1);
            callback.onCaptureCompleted(session, request, result);
            assertTrue(camera.offer(reader, image));
        }
        public boolean current(M10RMeasuredRaw3N.Input in) { return valid; }
        public void forward(ImageReader r, Image image) { assertSame(reader, r); forwarded.add(image); image.close(); }
        public void failed(M10RMeasuredRaw3N.Input in, String why, boolean retire) { if (retire) retirements++; }
        public void onFrame(M10RMeasuredRaw3N.Frame f) {
            if (rejectedDispatch) throw new RejectedExecutionException("test worker occupied");
            frame = f;
        }
        public void onFailure(String why) { failures++; reason = why; }
    }

    @Test public void allSixOrdersBindExactFrameAndHoldAdmissionUntilCommit() throws Exception {
        int[][] orders = {{0,1,2},{0,2,1},{1,0,2},{1,2,0},{2,0,1},{2,1,0}};
        for (int[] order : orders) {
            E e = new E(); Image image = e.image(100); e.start();
            assertFalse(e.camera.start(e.input));
            for (int event : order) {
                if (event == 0) e.callback.onCaptureStarted(e.session, e.request, 100, 1);
                if (event == 1) e.callback.onCaptureCompleted(e.session, e.request, e.result);
                if (event == 2) assertTrue(e.camera.offer(e.reader, image));
            }
            assertEquals(1, e.copied); assertEquals(0, e.failures); assertNotNull(e.frame);
            assertSame(e.input, e.frame.input); assertSame(e.result, e.frame.result);
            assertSame(e.request, e.frame.request); assertEquals(100, e.frame.timestamp);
            assertTrue(e.camera.busy()); assertFalse(e.camera.readerMustRetire());
            verify(image, times(1)).close();
            assertTrue(e.camera.commit(e.frame, () -> { assertTrue(e.camera.busy()); e.commits++; }));
            assertFalse(e.camera.busy()); assertEquals(1, e.commits);
            assertFalse(e.camera.commit(e.frame, () -> e.commits++)); assertEquals(1, e.commits);
            e.camera.close(); assertEquals(0, e.failures);
        }
    }

    @Test public void cancelBeforeStartQuarantinesInsteadOfHoldingFuturePhotoRaw() throws Exception {
        E e = new E(); e.start(); e.camera.cancel(1);
        assertEquals(1, e.failures); assertEquals(1, e.retirements); assertTrue(e.camera.busy());
        assertTrue(e.camera.readerMustRetire()); assertFalse(e.camera.start(e.input));
        Image photoLike = e.image(200), lateSpot = e.image(100);
        assertTrue(e.camera.offer(e.reader, photoLike)); verify(photoLike, times(1)).close();
        e.callback.onCaptureStarted(e.session, e.request, 100, 1);
        e.callback.onCaptureCompleted(e.session, e.request, e.result);
        assertTrue(e.camera.offer(e.reader, lateSpot)); verify(lateSpot, times(1)).close();
        assertEquals(0, e.copied); assertTrue(e.forwarded.isEmpty());
        // Retirement, not an arbitrary timeout release, ends the old reader gate.
        e.camera.close(); assertFalse(e.camera.busy());
        Image newPhoto = e.image(300);
        assertFalse(e.camera.offer(mock(ImageReader.class), newPhoto));
        verify(newPhoto, never()).close(); newPhoto.close();
        assertEquals(1, e.failures);
    }

    @Test public void acquisitionTimeoutClosesHeldRawAndRequestsOneRetirement() throws Exception {
        E e = new E(); e.start(); Image held = e.image(100);
        assertTrue(e.camera.offer(e.reader, held));
        Runnable timeout = e.timers.get(M10RMeasuredRaw3N.ACQUISITION_TIMEOUT_MS);
        timeout.run(); timeout.run();
        assertEquals(1, e.failures); assertEquals("spot_acquisition_timeout", e.reason);
        assertEquals(1, e.retirements); verify(held, times(1)).close();
        e.callback.onCaptureStarted(e.session, e.request, 100, 1);
        e.callback.onCaptureCompleted(e.session, e.request, e.result);
        assertNull(e.frame); assertTrue(e.camera.busy()); e.camera.close();
    }

    @Test public void completionTimeoutReleasesAdmissionAndRejectsLateUiWithoutRestart() throws Exception {
        E e = new E(); e.start(); e.bind(e.image(100));
        assertFalse(e.timers.containsKey(M10RMeasuredRaw3N.ACQUISITION_TIMEOUT_MS));
        e.timers.get(M10RMeasuredRaw3N.COMPLETION_TIMEOUT_MS).run();
        assertEquals("spot_completion_timeout", e.reason); assertEquals(1, e.failures);
        assertEquals(0, e.retirements); assertFalse(e.camera.busy());
        assertFalse(e.camera.commit(e.frame, () -> e.commits++)); assertEquals(0, e.commits);
    }

    @Test public void changedGenerationCannotApplyDuringWorkerOrQueuedUi() throws Exception {
        for (boolean beforeCopy : new boolean[] {true, false}) {
            E e = new E(); e.start(); Image image = e.image(100);
            if (beforeCopy) e.generation.incrementAndGet();
            e.bind(image);
            if (!beforeCopy) { e.generation.incrementAndGet(); assertFalse(e.camera.commit(e.frame, () -> e.commits++)); }
            assertEquals(0, e.commits); assertEquals(1, e.failures); assertFalse(e.camera.busy());
            verify(image, times(1)).close(); assertEquals(0, e.retirements);
        }
    }

    @Test public void changedCameraCannotApplyDetachedPatch() throws Exception {
        E e = new E(); e.start(); e.bind(e.image(100)); e.valid = false;
        assertFalse(e.camera.current(e.frame)); assertFalse(e.camera.commit(e.frame, () -> e.commits++));
        assertEquals(0, e.commits); assertEquals(1, e.failures); assertFalse(e.camera.busy());
    }

    @Test public void cancelAfterCopyKeepsNoCameraLeaseAndCannotCancelNextGeneration() throws Exception {
        E e = new E(); e.start(); Image oldImage = e.image(100); e.bind(oldImage);
        M10RMeasuredRaw3N.Frame oldFrame = e.frame;
        e.camera.cancel(1); assertEquals(0, e.retirements); assertFalse(e.camera.busy());
        e.generation.set(2); assertTrue(e.camera.start(e.newInput(2)));
        e.camera.cancel(1); assertTrue(e.camera.busy());
        assertFalse(e.camera.commit(oldFrame, () -> e.commits++)); assertEquals(0, e.commits);
        e.camera.close(); verify(oldImage, times(1)).close();
    }

    @Test public void retiredSessionClosesLeaseAndIgnoresDelayedStartResultAndCommit() throws Exception {
        for (boolean copied : new boolean[] {false, true}) {
            E e = new E(); e.start(); Image image = e.image(100);
            if (copied) e.bind(image); else assertTrue(e.camera.offer(e.reader, image));
            Surface oldSurface = e.reader.getSurface();
            e.camera.close(); e.camera.close();
            when(e.reader.getSurface()).thenThrow(new IllegalStateException("retired reader"));
            e.callback.onCaptureStarted(e.session, e.request, 100, 1);
            e.callback.onCaptureCompleted(e.session, e.request, e.result);
            e.callback.onCaptureBufferLost(e.session, e.request, oldSurface, 1);
            assertFalse(e.camera.commit(e.frame, () -> e.commits++));
            assertEquals(0, e.commits); assertFalse(e.camera.busy()); assertEquals(1, e.failures);
            verify(image, times(1)).close();
        }
    }

    @Test public void wrongSessionRequestAndTimestampCannotAssociate() throws Exception {
        E e = new E(); e.start(); Image image = e.image(100);
        assertTrue(e.camera.offer(e.reader, image));
        e.callback.onCaptureStarted(mock(CameraCaptureSession.class), e.request, 100, 1);
        e.callback.onCaptureCompleted(e.session, mock(CaptureRequest.class), e.result);
        assertNull(e.frame); assertEquals(0, e.copied);
        e.callback.onCaptureStarted(e.session, e.request, 100, 1);
        when(e.result.get(CaptureResult.SENSOR_TIMESTAMP)).thenReturn(101L);
        e.callback.onCaptureCompleted(e.session, e.request, e.result);
        assertNull(e.frame); assertEquals(1, e.failures); verify(image, times(1)).close();
    }

    @Test public void unrelatedEarlyRawIsNeverSampled() throws Exception {
        E e = new E(); e.start(); Image other = e.image(90);
        assertTrue(e.camera.offer(e.reader, other)); e.callback.onCaptureStarted(e.session, e.request, 100, 1);
        assertEquals(1, e.forwarded.size()); verify(other, times(1)).close();
        e.callback.onCaptureCompleted(e.session, e.request, e.result);
        assertTrue(e.camera.offer(e.reader, e.image(100))); assertEquals(1, e.copied);
        e.camera.close();
    }

    @Test public void knownNoImageFailureAndSubmissionRejectionReleaseImmediately() throws Exception {
        E e = new E(); e.start(); CaptureFailure failure = mock(CaptureFailure.class);
        when(failure.wasImageCaptured()).thenReturn(false);
        e.callback.onCaptureFailed(e.session, e.request, failure);
        assertEquals(1, e.failures); assertEquals(0, e.retirements); assertFalse(e.camera.busy());
        E rejected = new E(); when(rejected.session.capture(any(), any(), any())).thenThrow(new IllegalStateException("closed"));
        rejected.start(); assertEquals(1, rejected.failures); assertEquals(0, rejected.retirements); assertFalse(rejected.camera.busy());
    }

    @Test public void abortedUnknownSequenceRetiresButLostKnownBufferDoesNot() throws Exception {
        E aborted = new E(); aborted.start(); aborted.callback.onCaptureSequenceAborted(aborted.session, 9);
        assertEquals(1, aborted.retirements); assertTrue(aborted.camera.busy()); aborted.camera.close();
        E lost = new E(); lost.start();
        lost.callback.onCaptureBufferLost(lost.session, lost.request, lost.reader.getSurface(), 1);
        assertEquals(1, lost.failures); assertEquals(0, lost.retirements); assertFalse(lost.camera.busy());
    }

    @Test public void allocationFailureAndRejectedWorkerDispatchCloseRawAndFailOnce() throws Exception {
        E oom = new E((in, image, ts, result) -> { image.close(); throw new OutOfMemoryError("injected"); });
        oom.start(); Image image = oom.image(100); oom.bind(image);
        verify(image, times(1)).close(); assertEquals(1, oom.failures); assertFalse(oom.camera.busy());
        E rejected = new E(); rejected.rejectedDispatch = true; rejected.start();
        Image raw = rejected.image(100); rejected.bind(raw);
        verify(raw, times(1)).close(); assertEquals(1, rejected.failures); assertFalse(rejected.camera.busy());
    }

    @Test public void handlerShutdownCannotLeaveAnUnboundedAcquisition() throws Exception {
        E e = new E(); when(e.handler.postDelayed(any(), anyLong())).thenReturn(false); e.start();
        assertEquals("spot_handler_unavailable", e.reason); assertEquals(1, e.retirements);
        Image late = e.image(100); assertTrue(e.camera.offer(e.reader, late)); verify(late, times(1)).close();
        e.camera.close(); assertFalse(e.camera.busy());
    }

    @Test public void boundNormalizationCannotNameAnotherSensor() throws Exception {
        E e = new E();
        assertEquals("2", e.input.normalization.physicalId);
        assertTrue(e.input.normalization.useDynamicBlackLevel); assertFalse(e.input.normalization.useDynamicWhiteLevel);
        assertEquals(17, e.input.normalization.blackLevelOverride); assertEquals(1023, e.input.normalization.whiteLevelOverride);
        assertThrows(IllegalArgumentException.class, () -> new M10RMeasuredRaw3N.Input(e.session, e.reader,
                e.characteristics, e.builder, e.handler, new Object(), new Object(), "2", "2", 1,
                new M10RMeasuredRaw3N.Normalization("3", false, true, -1, -1), e.input.view, () -> true, e));
    }
}
