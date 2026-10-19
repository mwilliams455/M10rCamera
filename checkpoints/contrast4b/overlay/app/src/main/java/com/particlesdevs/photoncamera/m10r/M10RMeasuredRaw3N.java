package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.CameraCaptureSession;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CaptureFailure;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.CaptureResult;
import android.hardware.camera2.TotalCaptureResult;
import android.media.Image;
import android.media.ImageReader;
import android.os.Handler;
import android.view.Surface;

import java.util.Objects;
import java.util.function.BooleanSupplier;

/** PHOTO/MOTION spot-WB transport. A tagged start, physical result and RAW timestamp
 * must all agree. Acquisition and UI commit retain one owner; no next-frame grab. */
public final class M10RMeasuredRaw3N {
    public static final long ACQUISITION_TIMEOUT_MS = 1800;
    public static final long COMPLETION_TIMEOUT_MS = 4000;

    public interface Host {
        boolean current(Input input);
        void forward(ImageReader reader, Image image);
        /** retireReader requires quarantine before photographic admission can resume. */
        void failed(Input input, String diagnosticReason, boolean retireReader);
    }
    public interface Callback {
        /** The RAW patch is already detached from ImageReader ownership. */
        void onFrame(Frame frame);
        void onFailure(String diagnosticReason);
    }
    public static final class Normalization {
        public final String physicalId;
        public final boolean useDynamicBlackLevel, useDynamicWhiteLevel;
        public final int blackLevelOverride, whiteLevelOverride;
        public Normalization(String physicalId, boolean dynamicBlack, boolean dynamicWhite,
                int blackOverride, int whiteOverride) {
            this.physicalId = Objects.requireNonNull(physicalId);
            useDynamicBlackLevel = dynamicBlack; useDynamicWhiteLevel = dynamicWhite;
            blackLevelOverride = blackOverride; whiteLevelOverride = whiteOverride;
        }
    }
    public static final class Input {
        public final CameraCaptureSession session;
        public final ImageReader reader;
        public final CameraCharacteristics characteristics;
        public final Handler handler;
        public final Object device, previewBuilder;
        public final String physicalId, deviceId;
        public final long generation;
        public final Normalization normalization;
        public final M10RMeasuredFrame3N.View view;
        private final CaptureRequest.Builder builder;
        private final BooleanSupplier intentCurrent;
        private final Callback callback;
        public Input(CameraCaptureSession session, ImageReader reader, CameraCharacteristics c,
                CaptureRequest.Builder builder, Handler handler, Object device, Object previewBuilder,
                String physicalId, String deviceId, long generation, Normalization normalization,
                M10RMeasuredFrame3N.View view, BooleanSupplier intentCurrent, Callback callback) {
            this.session = Objects.requireNonNull(session); this.reader = Objects.requireNonNull(reader);
            characteristics = Objects.requireNonNull(c); this.builder = Objects.requireNonNull(builder);
            this.handler = Objects.requireNonNull(handler); this.device = Objects.requireNonNull(device);
            this.previewBuilder = Objects.requireNonNull(previewBuilder);
            this.physicalId = Objects.requireNonNull(physicalId); this.deviceId = Objects.requireNonNull(deviceId);
            this.generation = generation; this.normalization = Objects.requireNonNull(normalization);
            this.view = Objects.requireNonNull(view); this.intentCurrent = Objects.requireNonNull(intentCurrent);
            this.callback = Objects.requireNonNull(callback);
            if (!physicalId.equals(normalization.physicalId))
                throw new IllegalArgumentException("spot_normalization_source");
        }
    }
    public static final class Frame {
        public final Input input;
        public final M10RMeasuredFrame3N raw;
        public final CaptureResult result;
        public final CaptureRequest request;
        public final long timestamp;
        private Frame(Input input, M10RMeasuredFrame3N raw, CaptureResult result,
                CaptureRequest request, long timestamp) {
            this.input = input; this.raw = raw; this.result = result;
            this.request = request; this.timestamp = timestamp;
        }
    }
    interface Copier {
        /** Owns and closes image on success and failure. */
        M10RMeasuredFrame3N copy(Input input, Image image, long timestamp, CaptureResult result);
    }
    private final Host host;
    private final Copier copier;
    private final M10RExposureGate1C<Image, CaptureResult> gate;
    private Input active;
    private M10RExposureGate1C.Ticket ticket;
    private CaptureRequest request;
    private ImageReader quarantinedReader;
    private boolean delivered;
    private Runnable acquisitionTimeout, completionTimeout;

    public M10RMeasuredRaw3N(Host host) {
        this(host, (in, image, ts, result) -> M10RMeasuredFrame3N.copyAndClose(
                image, ts, in.characteristics, result, in.view));
    }
    M10RMeasuredRaw3N(Host host, Copier copier) {
        this.host = Objects.requireNonNull(host); this.copier = Objects.requireNonNull(copier);
        gate = new M10RExposureGate1C<>(new M10RExposureGate1C.Events<Image, CaptureResult>() {
            public void forward(Object reader, Image image) { host.forward((ImageReader) reader, image); }
            public void failure(M10RExposureGate1C.Ticket t, String reason) {
                synchronized (M10RMeasuredRaw3N.this) {
                    if (active == null || ticket != t) return;
                    terminalFailure(active, reason, gate.owns(t));
                }
            }
            public void matched(M10RExposureGate1C.Ticket t, long ts, long observed,
                    Image image, CaptureResult result) {
                synchronized (M10RMeasuredRaw3N.this) {
                    Input in = active;
                    if (in == null || ticket != t) { image.close(); return; }
                    if (!current(in)) {
                        image.close(); terminalFailure(in, "spot_intent_or_camera_changed", false); return;
                    }
                    if (acquisitionTimeout != null) in.handler.removeCallbacks(acquisitionTimeout);
                    try {
                        // Session retirement obtains this same monitor before closing
                        // its reader. The small bounded copy cannot outlive that reader.
                        M10RMeasuredFrame3N raw = copier.copy(in, image, ts, result);
                        delivered = true;
                        in.callback.onFrame(new Frame(in, raw, result, request, ts));
                    } catch (RuntimeException | LinkageError | OutOfMemoryError error) {
                        diagnose("spot_copy_or_worker_dispatch_failed", error);
                        terminalFailure(in, "spot_copy_or_worker_dispatch_failed", false);
                    }
                }
            }
        });
    }

    public synchronized boolean busy() { return active != null || gate.busy() || quarantinedReader != null; }
    public synchronized boolean readerMustRetire() { return gate.busy() || quarantinedReader != null; }
    public synchronized boolean current(Frame frame) {
        return frame != null && active == frame.input && delivered && current(frame.input);
    }
    private boolean current(Input in) {
        try { return in.intentCurrent.getAsBoolean() && host.current(in); }
        catch (RuntimeException | LinkageError | OutOfMemoryError error) {
            diagnose("spot_context_unavailable", error); return false;
        }
    }

    /** true transfers ownership, including immediate disposal of a quarantined RAW. */
    public synchronized boolean offer(ImageReader reader, Image image) {
        if (reader == quarantinedReader) { image.close(); return true; }
        return gate.image(reader, image.getTimestamp(), System.nanoTime(), image);
    }

    public synchronized boolean start(Input in) {
        if (in == null || busy() || !current(in)) return false;
        M10RExposureGate1C.Ticket t = gate.begin(in.reader);
        if (t == null) return false;
        active = in; ticket = t; delivered = false;
        try {
            in.builder.setTag(t);
            request = in.builder.build();
            in.session.capture(request, new CameraCaptureSession.CaptureCallback() {
                private boolean ours(CameraCaptureSession session, CaptureRequest r) {
                    return gate.owns(t) && session == in.session && r.getTag() == t;
                }
                @Override public void onCaptureStarted(CameraCaptureSession s, CaptureRequest r, long ts, long frame) {
                    if (ours(s, r)) gate.started(t, ts);
                }
                @Override public void onCaptureCompleted(CameraCaptureSession s, CaptureRequest r, TotalCaptureResult total) {
                    if (!ours(s, r)) return;
                    try {
                        CaptureResult exact = M10RExposureCamera1C.physical(total, in.physicalId, in.deviceId);
                        Long ts = exact.get(CaptureResult.SENSOR_TIMESTAMP);
                        if (ts == null) throw new IllegalArgumentException("missing_sensor_timestamp");
                        gate.result(t, ts, exact);
                    } catch (RuntimeException error) {
                        diagnose("spot_metadata_rejected", error);
                        gate.cancel(t, "spot_metadata_rejected", false);
                    }
                }
                @Override public void onCaptureFailed(CameraCaptureSession s, CaptureRequest r, CaptureFailure failure) {
                    if (ours(s, r)) gate.cancel(t, "spot_capture_failed", !failure.wasImageCaptured());
                }
                @Override public void onCaptureBufferLost(CameraCaptureSession s, CaptureRequest r, Surface target, long frame) {
                    if (ours(s, r) && target == in.reader.getSurface()) gate.cancel(t, "spot_raw_buffer_lost", true);
                }
                @Override public void onCaptureSequenceAborted(CameraCaptureSession s, int sequence) {
                    if (s == in.session) gate.cancel(t, "spot_sequence_aborted", false);
                }
            }, in.handler);
            if (active != in) return true;
            acquisitionTimeout = () -> {
                synchronized (M10RMeasuredRaw3N.this) {
                    if (active == in && gate.owns(t)) gate.cancel(t, "spot_acquisition_timeout", false);
                }
            };
            completionTimeout = () -> fail(in, "spot_completion_timeout");
            if (!in.handler.postDelayed(acquisitionTimeout, ACQUISITION_TIMEOUT_MS)
                    || !in.handler.postDelayed(completionTimeout, COMPLETION_TIMEOUT_MS))
                fail(in, "spot_handler_unavailable");
        } catch (Exception | LinkageError | OutOfMemoryError error) {
            diagnose("spot_request_rejected", error);
            gate.cancel(t, "spot_request_rejected", true);
        }
        return true;
    }

    public synchronized void cancel(long generation) {
        if (active != null && active.generation == generation) fail(active, "spot_cancelled");
    }
    public synchronized void fail(Frame frame, String reason) {
        if (frame != null) fail(frame.input, reason);
    }
    private synchronized void fail(Input in, String reason) {
        if (active != in) return;
        if (gate.owns(ticket)) gate.cancel(ticket, reason, false);
        else terminalFailure(in, reason, false);
    }

    /** Keep shutter admission excluded until the accepted WB/UI state is committed. */
    public synchronized boolean commit(Frame frame, Runnable apply) {
        if (!current(frame)) {
            if (frame != null) fail(frame.input, "spot_intent_or_camera_changed");
            return false;
        }
        try {
            apply.run();
            clearActive();
            return true;
        } catch (RuntimeException | LinkageError | OutOfMemoryError error) {
            diagnose("spot_commit_failed", error);
            terminalFailure(frame.input, "spot_commit_failed", false);
            return false;
        }
    }

    private void terminalFailure(Input in, String reason, boolean retireReader) {
        if (active != in) return;
        // Unknown outcome is bounded: hold no arbitrary future RAW while waiting for
        // a start callback. Quarantine the entire old reader and request retirement.
        if (retireReader) quarantinedReader = in.reader;
        clearActive();
        gate.close();
        try { host.failed(in, reason, retireReader); }
        catch (RuntimeException | LinkageError | OutOfMemoryError error) { diagnose("spot_failure_host", error); }
        reportFailure(in, reason);
    }
    private void clearActive() {
        if (active != null) {
            if (acquisitionTimeout != null) active.handler.removeCallbacks(acquisitionTimeout);
            if (completionTimeout != null) active.handler.removeCallbacks(completionTimeout);
        }
        active = null; ticket = null; request = null; delivered = false;
        acquisitionTimeout = completionTimeout = null;
    }
    /** Called before session/reader destruction. Already copied patches need no lease. */
    public synchronized void close() {
        Input retired = active;
        clearActive();
        gate.close();
        quarantinedReader = null;
        if (retired != null) reportFailure(retired, "spot_session_retired");
    }
    private static void reportFailure(Input in, String reason) {
        try { in.callback.onFailure(reason); }
        catch (RuntimeException | LinkageError | OutOfMemoryError error) { diagnose("spot_failure_callback", error); }
    }
    private static void diagnose(String stage, Throwable error) {
        try { android.util.Log.e("M10RMeasuredRaw3N", stage, error); }
        catch (RuntimeException | LinkageError | OutOfMemoryError ignored) { }
    }
}
