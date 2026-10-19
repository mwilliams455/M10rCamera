package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.*;
import android.media.ImageReader;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.Surface;
import com.particlesdevs.photoncamera.api.CameraEventsListener;
import com.particlesdevs.photoncamera.api.CameraMode;
import com.particlesdevs.photoncamera.api.Settings;
import com.particlesdevs.photoncamera.app.PhotonCamera;
import com.particlesdevs.photoncamera.capture.CaptureController;
import com.particlesdevs.photoncamera.control.SpotWhiteBalanceHelper;
import org.junit.*;
import org.mockito.MockedStatic;
import java.lang.reflect.Method;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/** Real controller entry/completion/admission; Camera2 and RAW workers are mocked. */
public class M10RMeasuredController3PTest {
    @BeforeClass public static void keys() throws Exception { M10RCaptureMeterReference1ITest.keys(); }
    @AfterClass public static void restoreKeys() throws Exception { M10RCaptureMeterReference1ITest.restoreKeys(); }
    @After public void clear() { CaptureController.isProcessing = false; M10RPreviewState1A.clear(null); }

    static final class Fixture implements AutoCloseable {
        final MockedStatic<Looper> loopers = mockStatic(Looper.class);
        final MockedStatic<PhotonCamera> app = mockStatic(PhotonCamera.class);
        final MockedStatic<SpotWhiteBalanceHelper> helper = mockStatic(SpotWhiteBalanceHelper.class);
        final MockedStatic<Log> log = mockStatic(Log.class);
        final CaptureController controller = mock(CaptureController.class, CALLS_REAL_METHODS);
        final Settings settings = mock(Settings.class);
        final CameraDevice device = mock(CameraDevice.class);
        final CameraCaptureSession session = mock(CameraCaptureSession.class);
        final ImageReader reader = mock(ImageReader.class);
        final CameraCharacteristics chars = mock(CameraCharacteristics.class);
        final CaptureRequest.Builder preview = mock(CaptureRequest.Builder.class), requestBuilder = mock(CaptureRequest.Builder.class);
        final Handler handler = mock(Handler.class);
        final M10RExposureCamera1C exposure = mock(M10RExposureCamera1C.class);
        final M10RMeasuredRaw3N measured = mock(M10RMeasuredRaw3N.class);
        final M10RCaptureLifecycle1G shot = new M10RCaptureLifecycle1G();
        final CameraEventsListener events = mock(CameraEventsListener.class);
        final AtomicLong generation = new AtomicLong(1), now = new AtomicLong(100);
        final AtomicBoolean exposureBusy = new AtomicBoolean(true);
        final Map<String, CameraCharacteristics> characteristics = new HashMap<>();
        final M10RMeasuredAdmission3P admission = new M10RMeasuredAdmission3P(now::get);
        final List<Runnable> timers = new ArrayList<>();
        final List<M10RMeasuredRaw3N.Input> submitted = new ArrayList<>();
        final M10RMeasuredFrame3N.View view = new M10RMeasuredFrame3N.View(50, 50, 100, 100, 0);
        final M10RMeasuredRaw3N.Normalization normalization = new M10RMeasuredRaw3N.Normalization("2", true, false, 0, 0);
        final M10RExposureCamera1C.Input background;
        Fixture(CameraMode mode) throws Exception {
            settings.selectedMode = mode; app.when(PhotonCamera::getSettings).thenReturn(settings);
            Looper looper = mock(Looper.class); loopers.when(Looper::myLooper).thenReturn(looper);
            when(handler.getLooper()).thenReturn(looper);
            when(handler.postDelayed(any(Runnable.class), anyLong())).thenAnswer(i -> {
                assertEquals(1800L, (long) i.getArgument(1)); timers.add(i.getArgument(0)); return true;
            });
            when(handler.post(any(Runnable.class))).thenAnswer(i -> { ((Runnable) i.getArgument(0)).run(); return true; });
            helper.when(() -> SpotWhiteBalanceHelper.isCurrentMeasurement3N(anyLong()))
                    .thenAnswer(i -> (long) i.getArgument(0) == generation.get());
            helper.when(() -> SpotWhiteBalanceHelper.freezeNormalization3N("2")).thenReturn(normalization);
            when(device.getId()).thenReturn("2");
            when(device.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW)).thenReturn(requestBuilder);
            when(reader.getSurface()).thenReturn(mock(Surface.class));
            CaptureRequest previewRequest = mock(CaptureRequest.class);
            when(preview.build()).thenReturn(previewRequest); when(previewRequest.getKeys()).thenReturn(Collections.emptyList());
            when(exposure.busy()).thenAnswer(i -> exposureBusy.get());
            when(measured.start(any())).thenAnswer(i -> { submitted.add(i.getArgument(0)); return true; });
            doReturn(false).when(controller).isZslMode();
            set("mCameraDevice", device); set("mCaptureSession", session); set("mImageReaderRaw", reader);
            set("mPreviewRequestBuilder", preview); set("mBackgroundHandler", handler);
            set("m10rMeasuredRaw3N", measured); set("m10rMeasuredAdmission3P", admission);
            set("m10rExposure1C", exposure); set("m10rShot1G", shot); set("cameraEventsListener", events);
            set("isCameraResumed", true); set("physicalID", "2");
            characteristics.put("2", chars); set("mCameraCharacteristicsMap", characteristics);
            background = new M10RExposureCamera1C.Input(session, reader, chars, mock(CaptureRequest.Builder.class),
                    handler, "2:100x100:0", "2", "2", device, preview, "old_exposure_controls", 10, 0, 0);
            set("m10rPendingInput1C", background); set("m10rBackgroundInput1A", background);
        }
        void set(String name, Object value) throws Exception { M10RCaptureAdmission1GTest.field(controller, name, value); }
        Object call(String name, Class<?>[] types, Object... args) throws Exception {
            Method m = CaptureController.class.getDeclaredMethod(name, types); m.setAccessible(true);
            return m.invoke(controller, args);
        }
        void request(M10RMeasuredRaw3N.Callback callback) { controller.captureSingleRawForMetering3N(generation.get(), view, callback); }
        void finish(boolean drained) throws Exception {
            exposureBusy.set(!drained);
            // A completed old exposure selection may be stale while this WB intent
            // remains current. Exercise the real controller's cleanup/handoff branch.
            call("m10rFinishProbe1C", new Class<?>[] {M10RExposureCamera1C.Input.class, M10RExposureProbe1B.Output.class, String.class},
                    background, null, "test_completed_background");
        }
        public void close() { log.close(); helper.close(); app.close(); loopers.close(); }
    }

    @Test public void photoAndMotionWaitThenSubmitExactlyOneCapturedContext() throws Exception {
        for (CameraMode mode : new CameraMode[] {CameraMode.PHOTO, CameraMode.MOTION}) try (Fixture f = new Fixture(mode)) {
            var callback = mock(M10RMeasuredRaw3N.Callback.class); f.request(callback);
            assertTrue(f.admission.pending()); assertTrue(f.submitted.isEmpty());
            verify(f.device, never()).createCaptureRequest(anyInt());
            f.finish(true); f.finish(true); f.timers.get(0).run();
            assertFalse(f.admission.pending()); assertEquals(1, f.submitted.size()); verifyNoInteractions(callback);
            var in = f.submitted.get(0);
            assertEquals(1, in.generation); assertSame(f.session, in.session); assertSame(f.reader, in.reader);
            assertSame(f.device, in.device); assertSame(f.chars, in.characteristics); assertSame(f.preview, in.previewBuilder);
            assertSame(f.normalization, in.normalization); assertSame(f.view, in.view); assertEquals("2", in.physicalId);
        }
    }

    @Test public void completionCallbackCannotReleaseUnaccountedBackgroundRaw() throws Exception {
        try (Fixture f = new Fixture(CameraMode.PHOTO)) {
            var callback = mock(M10RMeasuredRaw3N.Callback.class); f.request(callback); f.finish(false);
            assertFalse(f.admission.pending()); assertTrue(f.submitted.isEmpty()); assertTrue(f.exposure.busy());
            verify(callback).onFailure("spot_background_reader_retired");
            f.finish(true); assertTrue(f.submitted.isEmpty());
        }
    }

    @Test public void cancellationAndSupersessionReachRealControllerWithoutStaleClear() throws Exception {
        try (Fixture f = new Fixture(CameraMode.PHOTO)) {
            var a = mock(M10RMeasuredRaw3N.Callback.class); var b = mock(M10RMeasuredRaw3N.Callback.class);
            f.request(a); Runnable oldTimer = f.timers.get(0);
            f.generation.set(2); f.controller.cancelMeasuredRaw3N(1); f.request(b);
            oldTimer.run(); f.controller.cancelMeasuredRaw3N(1);
            assertTrue(f.admission.pending()); f.finish(true);
            assertEquals(1, f.submitted.size()); assertEquals(2, f.submitted.get(0).generation);
            verify(a).onFailure("spot_cancelled"); verifyNoInteractions(b);
            verify(f.measured, times(2)).cancel(1);
        }
    }

    @Test public void everyCapturedCameraIdentityAndIntentIsRecheckedBeforeSubmit() throws Exception {
        for (String changed : new String[] {"generation", "session", "device", "reader", "preview", "handler", "physical", "calibration", "mode", "epoch", "resumed", "dual", "quarantine"})
            try (Fixture f = new Fixture(CameraMode.PHOTO)) {
                var callback = mock(M10RMeasuredRaw3N.Callback.class); f.request(callback);
                switch (changed) {
                    case "generation": f.generation.incrementAndGet(); break;
                    case "session": f.set("mCaptureSession", mock(CameraCaptureSession.class)); break;
                    case "device": f.set("mCameraDevice", mock(CameraDevice.class)); break;
                    case "reader": f.set("mImageReaderRaw", mock(ImageReader.class)); break;
                    case "preview": f.set("mPreviewRequestBuilder", mock(CaptureRequest.Builder.class)); break;
                    case "handler": f.set("mBackgroundHandler", mock(Handler.class)); break;
                    case "physical": f.set("physicalID", "3"); break;
                    case "calibration": f.characteristics.put("2", mock(CameraCharacteristics.class)); break;
                    case "mode": f.settings.selectedMode = CameraMode.MOTION; break;
                    case "epoch": f.set("m10rMeasuredAdmissionEpoch3P", 1L); break;
                    case "resumed": f.set("isCameraResumed", false); break;
                    case "dual": f.set("isDualSession", true); break;
                    case "quarantine": f.set("m10rRejectedRawReader1C", f.reader); break;
                }
                f.finish(true); assertFalse(changed, f.admission.pending()); assertTrue(changed, f.submitted.isEmpty());
                verify(callback).onFailure("spot_intent_or_camera_changed");
            }
    }

    @Test public void pendingReservesBothStillOwnersAndProbeEntryUntilFiniteTimeout() throws Exception {
        for (CameraMode mode : new CameraMode[] {CameraMode.PHOTO, CameraMode.MOTION}) try (Fixture f = new Fixture(mode)) {
            var callback = mock(M10RMeasuredRaw3N.Callback.class); f.request(callback);
            f.controller.takePicture(); f.controller.takePicture();
            f.call("m10rStartProbe1A", new Class<?>[] {boolean.class}, true);
            assertFalse(f.shot.busy()); verifyNoInteractions(f.events); verify(f.exposure, never()).start(any());
            f.now.addAndGet(1_800_000_000L); f.timers.get(0).run();
            assertFalse(f.admission.pending()); verify(callback).onFailure("spot_admission_timeout");
            f.finish(true); assertTrue(f.submitted.isEmpty());
        }
    }

    @Test public void retirementCancelsWaitingAndPreservesExistingReaderRecovery() throws Exception {
        try (Fixture f = new Fixture(CameraMode.PHOTO)) {
            var callback = mock(M10RMeasuredRaw3N.Callback.class); f.request(callback);
            f.call("m10rRetireMeter1H", new Class<?>[0]);
            assertFalse(f.admission.pending()); verify(callback).onFailure("spot_session_retired");
            verify(f.measured).close(); verify(f.exposure).close();
            f.timers.get(0).run(); f.finish(true); assertTrue(f.submitted.isEmpty());
            f.controller.takePicture(); assertFalse(f.shot.busy()); verifyNoInteractions(f.events);
        }
    }

    @Test public void photoForegroundAndUncertainReaderContentionStillRejectImmediately() throws Exception {
        for (String busy : new String[] {"photo", "queued_photo", "foreground_probe", "unclassified_probe", "other_background", "spot", "quarantine"})
            try (Fixture f = new Fixture(CameraMode.PHOTO)) {
                switch (busy) {
                    case "photo": f.shot.begin(); break;
                    case "queued_photo": f.set("m10rQueuedShutter1A", true); break;
                    case "foreground_probe": f.set("m10rBackgroundInput1A", null); break;
                    case "unclassified_probe": f.set("m10rBackgroundInput1A", null); f.set("m10rPendingInput1C", null); break;
                    case "other_background": f.set("m10rPendingInput1C", mock(M10RExposureCamera1C.Input.class)); break;
                    case "spot": when(f.measured.busy()).thenReturn(true); break;
                    case "quarantine": f.set("m10rRejectedRawReader1C", f.reader); break;
                }
                var callback = mock(M10RMeasuredRaw3N.Callback.class); f.request(callback);
                assertFalse(busy, f.admission.pending()); assertTrue(busy, f.submitted.isEmpty());
                verify(callback).onFailure("spot_pipeline_busy");
            }
    }

    @Test public void cancellingWaiterRestoresActualBackgroundProbeEligibility() throws Exception {
        // Reuse the existing complete physical-preview fixture to execute the real
        // background request path after cancellation, not just inspect pending().
        try (var f = new M10RCaptureMeterReference1ITest.Fixture(0)) {
            f.gate.finish(f.gate.active());
            var admission = new M10RMeasuredAdmission3P(); f.set("m10rMeasuredAdmission3P", admission);
            var timer = new M10RMeasuredAdmission3PTest.Timer();
            admission.defer(new Object(), 1, () -> true, timer, () -> fail("cancelled"), reason -> {});
            f.start(true); assertNull(f.admitted); verify(f.exposure, never()).start(any());
            f.controller.cancelMeasuredRaw3N(1); assertFalse(admission.pending());
            f.start(true); assertNotNull(f.admitted); verify(f.exposure, times(1)).start(any());
        }
    }
}
