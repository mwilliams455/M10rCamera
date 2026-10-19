package com.particlesdevs.photoncamera.m10r;

import java.util.Objects;
import java.util.function.BooleanSupplier;
import java.util.function.Consumer;
import java.util.function.LongSupplier;

/** One foreground WB intent may wait for one already-running background probe.
 * This owns no RAW and cannot declare a reader drained. The camera owner supplies
 * that decision after its existing transport has finished or failed. */
public final class M10RMeasuredAdmission3P {
    public static final long WAIT_TIMEOUT_MS = 1800;
    private static final long WAIT_TIMEOUT_NS = WAIT_TIMEOUT_MS * 1_000_000L;

    public interface Scheduler {
        boolean postDelayed(Runnable task, long delayMs);
        void remove(Runnable task);
    }

    private final LongSupplier clock;
    private Waiting pending;

    public M10RMeasuredAdmission3P() { this(System::nanoTime); }
    M10RMeasuredAdmission3P(LongSupplier clock) { this.clock = Objects.requireNonNull(clock); }

    private final class Waiting implements Runnable {
        final Object background;
        final long generation, startedNs;
        final BooleanSupplier current;
        final Scheduler scheduler;
        final Runnable submit;
        final Consumer<String> failure;
        Waiting(Object background, long generation, BooleanSupplier current,
                Scheduler scheduler, Runnable submit, Consumer<String> failure) {
            this.background = Objects.requireNonNull(background);
            this.generation = generation; this.startedNs = clock.getAsLong();
            this.current = Objects.requireNonNull(current);
            this.scheduler = Objects.requireNonNull(scheduler);
            this.submit = Objects.requireNonNull(submit);
            this.failure = Objects.requireNonNull(failure);
        }
        @Override public void run() {
            if (remove(this)) report(this, "spot_admission_timeout");
        }
    }

    public synchronized boolean pending() { return pending != null; }

    /** The caller has already rejected photo/foreground/uncertain-RAW contention. */
    public void defer(Object background, long generation, BooleanSupplier current,
            Scheduler scheduler, Runnable submit, Consumer<String> failure) {
        Waiting next = new Waiting(background, generation, current, scheduler, submit, failure);
        if (!current(next)) { report(next, "spot_intent_or_camera_changed"); return; }
        Waiting old = null;
        boolean stale = false, invalid, scheduled = false;
        synchronized (this) {
            // Cancel/retirement can race the first validity check. Recheck while
            // publishing so they either prevent publication or remove this slot.
            invalid = !current(next);
            if (!invalid) {
                old = pending;
                stale = old != null && generation <= old.generation;
                if (!stale) {
                    if (old != null) stopTimer(old);
                    pending = next;
                    try { scheduled = scheduler.postDelayed(next, WAIT_TIMEOUT_MS); }
                    catch (RuntimeException | LinkageError | OutOfMemoryError ignored) { }
                    if (!scheduled && pending == next) pending = null;
                }
            }
        }
        // Callbacks may start/cancel another intent. They never run under this monitor.
        if (invalid) { report(next, "spot_intent_or_camera_changed"); return; }
        if (stale) { report(next, "spot_intent_changed"); return; }
        if (old != null) report(old, "spot_intent_changed");
        if (!scheduled) report(next, "spot_handler_unavailable");
    }

    /** Only this exact background owner may release its successor; a callback
     * alone is insufficient when its RAW gate still owns an unaccounted buffer. */
    public void backgroundFinished(Object background, boolean drained) {
        Waiting waiting;
        synchronized (this) {
            waiting = pending;
            if (waiting == null || waiting.background != background) return;
            pending = null;
            stopTimer(waiting);
        }
        if (!drained) { report(waiting, "spot_background_reader_retired"); return; }
        if (!current(waiting)) { report(waiting, "spot_intent_or_camera_changed"); return; }
        long elapsed = clock.getAsLong() - waiting.startedNs;
        if (elapsed < 0 || elapsed >= WAIT_TIMEOUT_NS) {
            report(waiting, "spot_admission_timeout"); return;
        }
        try { waiting.submit.run(); }
        catch (RuntimeException | LinkageError | OutOfMemoryError error) {
            report(waiting, "spot_admission_submission_failed");
        }
    }

    public void cancel(long generation) {
        Waiting waiting;
        synchronized (this) {
            waiting = pending;
            if (waiting == null || waiting.generation != generation) return;
        }
        if (remove(waiting)) report(waiting, "spot_cancelled");
    }

    /** Camera retirement never carries a waiting intent into another session. */
    public void close() {
        Waiting waiting;
        synchronized (this) { waiting = pending; }
        if (waiting != null && remove(waiting)) report(waiting, "spot_session_retired");
    }

    private synchronized boolean remove(Waiting waiting) {
        if (pending != waiting) return false;
        pending = null;
        stopTimer(waiting);
        return true;
    }
    private static boolean current(Waiting waiting) {
        try { return waiting.current.getAsBoolean(); }
        catch (RuntimeException | LinkageError | OutOfMemoryError error) { return false; }
    }
    private static void stopTimer(Waiting waiting) {
        try { waiting.scheduler.remove(waiting); }
        catch (RuntimeException | LinkageError | OutOfMemoryError ignored) { }
    }
    private static void report(Waiting waiting, String reason) {
        try { waiting.failure.accept(reason); }
        catch (RuntimeException | LinkageError | OutOfMemoryError ignored) { }
    }
}
