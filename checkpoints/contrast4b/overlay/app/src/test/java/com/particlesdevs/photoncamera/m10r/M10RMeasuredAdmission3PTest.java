package com.particlesdevs.photoncamera.m10r;

import org.junit.Test;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import java.util.function.BooleanSupplier;
import java.util.function.Consumer;
import static org.junit.Assert.*;

/** Deterministic ownership/deadline tests; no camera or wall-clock sleeps. */
public class M10RMeasuredAdmission3PTest {
    static final class Timer implements M10RMeasuredAdmission3P.Scheduler {
        final List<Runnable> posted = new ArrayList<>(), removed = new ArrayList<>();
        boolean available = true;
        public boolean postDelayed(Runnable task, long delayMs) {
            assertEquals(1800, delayMs); posted.add(task); return available;
        }
        public void remove(Runnable task) { removed.add(task); }
        Runnable last() { return posted.get(posted.size() - 1); }
    }
    static final class Fixture {
        final AtomicLong now = new AtomicLong(10);
        final M10RMeasuredAdmission3P admission = new M10RMeasuredAdmission3P(now::get);
        final Timer timer = new Timer();
        final List<String> failures = new ArrayList<>();
        final AtomicInteger submissions = new AtomicInteger();
        final Object background = new Object();
        final AtomicBoolean valid = new AtomicBoolean(true);
        final Consumer<String> failure = reason -> {
            assertFalse("callback under admission monitor", Thread.holdsLock(admission));
            failures.add(reason);
        };
        void defer(long generation) {
            admission.defer(background, generation, valid::get, timer, submissions::incrementAndGet, failure);
        }
    }

    @Test public void exactDrainedBackgroundSubmitsOnceAndCancelsDeadline() {
        Fixture f = new Fixture(); f.defer(1); Runnable timeout = f.timer.last();
        f.admission.backgroundFinished(new Object(), true);
        assertTrue(f.admission.pending()); assertEquals(0, f.submissions.get());
        f.admission.backgroundFinished(f.background, true);
        f.admission.backgroundFinished(f.background, true); timeout.run();
        assertFalse(f.admission.pending()); assertEquals(1, f.submissions.get());
        assertTrue(f.timer.removed.contains(timeout)); assertTrue(f.failures.isEmpty());
    }

    @Test public void latestGenerationCannotBeClearedByOldCancelTimerOrBackground() {
        Fixture f = new Fixture(); f.defer(1); Runnable oldTimeout = f.timer.last();
        Object newerBackground = new Object();
        f.admission.defer(newerBackground, 2, f.valid::get, f.timer, f.submissions::incrementAndGet, f.failure);
        f.admission.cancel(1); oldTimeout.run(); f.admission.backgroundFinished(f.background, true);
        assertTrue(f.admission.pending()); assertEquals(List.of("spot_intent_changed"), f.failures);
        f.admission.backgroundFinished(newerBackground, true);
        assertEquals(1, f.submissions.get()); assertFalse(f.admission.pending());
    }

    @Test public void explicitCancelReleasesSlotAndLateCallbacksCannotSubmit() {
        Fixture f = new Fixture(); f.defer(1); Runnable timeout = f.timer.last();
        f.admission.cancel(1); f.admission.cancel(1); timeout.run();
        f.admission.backgroundFinished(f.background, true);
        assertFalse(f.admission.pending()); assertEquals(0, f.submissions.get());
        assertEquals(List.of("spot_cancelled"), f.failures);
        f.defer(2); assertTrue(f.admission.pending()); // Background eligibility is no longer held by 1.
    }

    @Test public void timeoutAndBlockedHandlerDeadlineBothReleaseWithoutSubmission() {
        for (boolean timerRuns : new boolean[] {true, false}) {
            Fixture f = new Fixture(); f.defer(1);
            f.now.addAndGet(1_800_000_000L);
            if (timerRuns) f.timer.last().run();
            f.admission.backgroundFinished(f.background, true);
            assertFalse(f.admission.pending()); assertEquals(0, f.submissions.get());
            assertEquals(List.of("spot_admission_timeout"), f.failures);
        }
    }

    @Test public void invalidContextAndUnaccountedRawCannotHandOff() {
        for (boolean drained : new boolean[] {true, false}) {
            Fixture f = new Fixture(); f.defer(1); f.valid.set(!drained);
            f.admission.backgroundFinished(f.background, drained);
            assertFalse(f.admission.pending()); assertEquals(0, f.submissions.get());
            assertEquals(List.of(drained ? "spot_intent_or_camera_changed" : "spot_background_reader_retired"), f.failures);
        }
    }

    @Test public void retirementReleasesPendingAndOldCallbacksCannotClearNewSessionIntent() {
        Fixture f = new Fixture(); f.defer(1); Runnable retiredTimer = f.timer.last();
        f.admission.close(); f.admission.close();
        Object newSession = new Object();
        f.admission.defer(newSession, 2, f.valid::get, f.timer, f.submissions::incrementAndGet, f.failure);
        retiredTimer.run(); f.admission.backgroundFinished(f.background, true);
        assertTrue(f.admission.pending()); assertEquals(List.of("spot_session_retired"), f.failures);
        f.admission.backgroundFinished(newSession, true); assertEquals(1, f.submissions.get());
    }

    @Test public void cancelOrRetirementDuringPrePublicationCheckCannotLeaveStalePending() {
        for (boolean retire : new boolean[] {false, true}) {
            Fixture f = new Fixture(); AtomicInteger checks = new AtomicInteger();
            BooleanSupplier racedCurrent = () -> {
                if (checks.getAndIncrement() == 0) {
                    f.valid.set(false);
                    if (retire) f.admission.close(); else f.admission.cancel(1);
                    return true; // Validity observed immediately before the concurrent invalidation.
                }
                return f.valid.get();
            };
            f.admission.defer(f.background, 1, racedCurrent, f.timer, f.submissions::incrementAndGet, f.failure);
            assertEquals(2, checks.get()); assertFalse(f.admission.pending());
            assertTrue(f.timer.posted.isEmpty()); assertEquals(0, f.submissions.get());
            assertEquals(List.of("spot_intent_or_camera_changed"), f.failures);
        }
    }

    @Test public void unavailableHandlerCannotLeaveBackgroundStarved() {
        Fixture f = new Fixture(); f.timer.available = false; f.defer(1);
        assertFalse(f.admission.pending()); f.admission.backgroundFinished(f.background, true);
        assertEquals(0, f.submissions.get()); assertEquals(List.of("spot_handler_unavailable"), f.failures);
    }

    @Test public void reentrantFailureCallbackCannotClearNewerIntent() {
        Fixture f = new Fixture();
        f.admission.defer(f.background, 1, f.valid::get, f.timer, () -> fail("superseded"), reason -> {
            f.failure.accept(reason);
            f.admission.defer(f.background, 3, f.valid::get, f.timer, f.submissions::incrementAndGet, f.failure);
        });
        f.defer(2); // Reporting 1's replacement immediately replaces 2 with 3.
        assertTrue(f.admission.pending()); f.admission.cancel(2);
        f.admission.backgroundFinished(f.background, true);
        assertFalse(f.admission.pending()); assertEquals(1, f.submissions.get());
        assertEquals(List.of("spot_intent_changed", "spot_intent_changed"), f.failures);
    }

    @Test public void olderOrDuplicateIntentCannotReplaceCurrentWaiter() {
        Fixture f = new Fixture(); f.defer(3); Runnable currentTimer = f.timer.last();
        f.defer(2); f.defer(3);
        assertEquals(1, f.timer.posted.size()); assertFalse(f.timer.removed.contains(currentTimer));
        assertTrue(f.admission.pending()); f.admission.backgroundFinished(f.background, true);
        assertEquals(1, f.submissions.get());
        assertEquals(List.of("spot_intent_changed", "spot_intent_changed"), f.failures);
    }
}
