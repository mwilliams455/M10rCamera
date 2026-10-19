package com.particlesdevs.photoncamera.control;

import android.hardware.camera2.params.RggbChannelVector;
import android.view.View;
import android.view.ViewPropertyAnimator;

import com.particlesdevs.photoncamera.capture.CaptureController;
import com.particlesdevs.photoncamera.circularbarlib.api.ManualModeConsole;
import com.particlesdevs.photoncamera.circularbarlib.control.ManualParamModel;
import com.particlesdevs.photoncamera.circularbarlib.util.Motion;
import com.particlesdevs.photoncamera.manual.ParamController;
import com.particlesdevs.photoncamera.ui.camera.views.SpotWbIndicatorView;
import com.particlesdevs.photoncamera.util.Log;

import org.junit.Test;
import org.mockito.MockedStatic;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/** Actual touch entry and indicator callbacks; camera, view queue and animation are controlled doubles. */
public class TouchFocusSpotWb3PTest {
    private static final class Fixture implements AutoCloseable {
        final MockedStatic<Log> log = mockStatic(Log.class);
        final MockedStatic<Motion> motion = mockStatic(Motion.class);
        final MockedStatic<SpotWhiteBalanceHelper> helper = mockStatic(SpotWhiteBalanceHelper.class);
        final CaptureController controller = mock(CaptureController.class);
        final ParamController param = mock(ParamController.class);
        final ManualModeConsole console = mock(ManualModeConsole.class);
        final View viewfinder = mock(View.class);
        final View focus = mock(View.class);
        final SpotWbIndicatorView marker = mock(SpotWbIndicatorView.class);
        final ViewPropertyAnimator animator = mock(ViewPropertyAnimator.class, RETURNS_SELF);
        final ArrayDeque<Runnable> posted = new ArrayDeque<>();
        final Map<Runnable, Long> delayed = new LinkedHashMap<>();
        final List<Runnable> animationEnds = new ArrayList<>();
        final List<float[]> points = new ArrayList<>();
        final List<SpotWhiteBalanceHelper.SpotWbCallback> measurements = new ArrayList<>();
        final TouchFocus touch;
        int visibility = View.INVISIBLE;
        float x, y, alpha = 1f, scaleX = 1f, scaleY = 1f;
        String error;

        Fixture() {
            when(controller.getParamController()).thenReturn(param);
            when(controller.getManualModeConsole()).thenReturn(console);
            when(viewfinder.getWidth()).thenReturn(1000);
            when(viewfinder.getHeight()).thenReturn(1200);
            when(marker.getMeasuredWidth()).thenReturn(48);
            when(marker.getMeasuredHeight()).thenReturn(48);
            when(marker.getWidth()).thenReturn(48);
            when(marker.getHeight()).thenReturn(48);
            when(marker.getVisibility()).thenAnswer(i -> visibility);
            when(marker.getX()).thenAnswer(i -> x);
            when(marker.getY()).thenAnswer(i -> y);
            when(marker.getAlpha()).thenAnswer(i -> alpha);
            when(marker.animate()).thenReturn(animator);
            doAnswer(i -> { visibility = i.getArgument(0); return null; }).when(marker).setVisibility(anyInt());
            doAnswer(i -> { x = i.getArgument(0); return null; }).when(marker).setX(anyFloat());
            doAnswer(i -> { y = i.getArgument(0); return null; }).when(marker).setY(anyFloat());
            doAnswer(i -> { alpha = i.getArgument(0); return null; }).when(marker).setAlpha(anyFloat());
            doAnswer(i -> { scaleX = i.getArgument(0); return null; }).when(marker).setScaleX(anyFloat());
            doAnswer(i -> { scaleY = i.getArgument(0); return null; }).when(marker).setScaleY(anyFloat());
            doAnswer(i -> { error = null; return null; }).when(marker).setMeasuringState();
            doAnswer(i -> { error = i.getArgument(0); return null; }).when(marker).setErrorState(anyString());
            // Apply animation targets immediately, but retain end actions so a
            // test can deliver an old completion even after cancel() was called.
            doAnswer(i -> { alpha = i.getArgument(0); return animator; }).when(animator).alpha(anyFloat());
            doAnswer(i -> { scaleX = i.getArgument(0); return animator; }).when(animator).scaleX(anyFloat());
            doAnswer(i -> { scaleY = i.getArgument(0); return animator; }).when(animator).scaleY(anyFloat());
            doAnswer(i -> { animationEnds.add(i.getArgument(0)); return animator; })
                    .when(animator).withEndAction(any(Runnable.class));
            when(marker.post(any(Runnable.class))).thenAnswer(i -> {
                posted.add(i.getArgument(0)); return true;
            });
            when(marker.postDelayed(any(Runnable.class), anyLong())).thenAnswer(i -> {
                delayed.put(i.getArgument(0), i.getArgument(1)); return true;
            });
            when(marker.removeCallbacks(any(Runnable.class))).thenAnswer(i -> {
                Runnable task = i.getArgument(0);
                posted.remove(task); delayed.remove(task); return true;
            });
            helper.when(() -> SpotWhiteBalanceHelper.measureSpotWbRaw(
                    eq(viewfinder), eq(controller), anyFloat(), anyFloat(),
                    any(SpotWhiteBalanceHelper.SpotWbCallback.class))).thenAnswer(i -> {
                points.add(new float[]{i.getArgument(2), i.getArgument(3)});
                measurements.add(i.getArgument(4)); return null;
            });
            touch = new TouchFocus(controller, focus, marker, viewfinder);
            drainPosted(); // Constructor reset, with the marker initially hidden.
        }

        void hold(float px, float py) {
            touch.processSpotWb(px, py);
            drainPosted();
        }

        void drainPosted() {
            while (!posted.isEmpty()) posted.removeFirst().run();
        }

        Runnable runScheduledHide(long expectedDelay) {
            assertEquals(1, delayed.size());
            Map.Entry<Runnable, Long> entry = delayed.entrySet().iterator().next();
            assertEquals(expectedDelay, entry.getValue().longValue());
            Runnable task = entry.getKey();
            delayed.remove(task);
            task.run();
            return task;
        }

        Runnable latestAnimationEnd() {
            return animationEnds.get(animationEnds.size() - 1);
        }

        void assertVisibleAt(float px, float py) {
            assertEquals(View.VISIBLE, visibility);
            assertEquals(px - 24f, x, 0f);
            assertEquals(py - 24f, y, 0f);
            assertEquals(1f, alpha, 0f);
        }

        void assertResampledWithoutCancel() {
            assertEquals(2, measurements.size());
            assertArrayEquals(points.get(0), points.get(1), 0f);
            helper.verify(SpotWhiteBalanceHelper::cancelPendingMeasurement, never());
            verify(param, never()).setWB(anyInt());
            verify(console, never()).setManualWbValue(anyDouble());
        }

        @Override public void close() {
            helper.close(); motion.close(); log.close();
        }
    }

    @Test public void repeatedHoldInsideMeasuringMarkerResamplesFromAutoManualOrSpot() {
        for (int previousKelvin : new int[]{0, 3500, 3524}) {
            try (Fixture f = new Fixture()) {
                f.param.WB = previousKelvin;
                f.param.isSpotWb = previousKelvin == 3524;
                RggbChannelVector previousGains = mock(RggbChannelVector.class);
                f.param.spotGains = f.param.isSpotWb ? previousGains : null;
                f.hold(200f, 250f);
                f.assertVisibleAt(200f, 250f);
                f.hold(200f, 250f);
                f.assertResampledWithoutCancel();
                assertEquals(previousKelvin, f.param.WB);
                assertEquals(previousKelvin == 3524, f.param.isSpotWb);
                if (f.param.isSpotWb) assertSame(previousGains, f.param.spotGains);
                verify(f.marker, times(2)).setMeasuringState();
            }
        }
    }

    @Test public void repeatedHoldInsideSuccessMarkerResamplesAndRemovesOldHide() {
        try (Fixture f = new Fixture()) {
            f.param.WB = 3524; f.param.isSpotWb = true;
            f.hold(200f, 250f);
            f.measurements.get(0).onSpotWbMeasured(3524, "G+1.2");
            f.drainPosted();
            assertEquals(Long.valueOf(2000), f.delayed.values().iterator().next());
            Runnable oldHide = f.delayed.keySet().iterator().next();
            f.hold(200f, 250f);
            f.assertResampledWithoutCancel();
            assertTrue(f.delayed.isEmpty());
            verify(f.marker).removeCallbacks(oldHide);
            f.assertVisibleAt(200f, 250f);
        }
    }

    @Test public void repeatedHoldInsideErrorMarkerResamplesAndRestoresMeasuringState() {
        try (Fixture f = new Fixture()) {
            f.param.WB = 3500;
            f.hold(200f, 250f);
            f.measurements.get(0).onSpotWbFailed("too_dark");
            f.drainPosted();
            assertEquals("too_dark", f.error);
            assertEquals(Long.valueOf(1500), f.delayed.values().iterator().next());
            f.hold(200f, 250f);
            f.assertResampledWithoutCancel();
            assertNull(f.error);
            assertTrue(f.delayed.isEmpty());
            f.assertVisibleAt(200f, 250f);
        }
    }

    @Test public void oldHideAndPulseCompletionsCannotHideOrRecenterLatestMarker() {
        try (Fixture f = new Fixture()) {
            f.hold(200f, 250f);
            Runnable oldPulseEnd = f.latestAnimationEnd();
            f.measurements.get(0).onSpotWbMeasured(3500, "0");
            f.drainPosted();
            Runnable oldHide = f.runScheduledHide(2000);
            Runnable oldHideEnd = f.latestAnimationEnd();
            assertEquals(0f, f.alpha, 0f);

            f.hold(700f, 800f);
            f.assertVisibleAt(700f, 800f);
            verify(f.animator, times(3)).cancel(); // First show, old hide, replacement show.
            oldHideEnd.run();
            oldPulseEnd.run();
            oldHide.run();
            f.assertVisibleAt(700f, 800f);
            assertEquals(1.25f, f.scaleX, 0f);
            assertEquals(1.25f, f.scaleY, 0f);
            assertEquals(2, f.measurements.size());
        }
    }

    @Test public void oldQueuedShowAndStatusCannotAlterLatestMeasurement() {
        try (Fixture f = new Fixture()) {
            f.touch.processSpotWb(200f, 250f);
            f.measurements.get(0).onSpotWbFailed("old_failure");
            f.touch.processSpotWb(700f, 800f);
            f.drainPosted();
            f.measurements.get(0).onSpotWbMeasured(3500, "0");
            f.measurements.get(0).onSpotWbFailed("late_old_failure");
            f.drainPosted();
            f.assertVisibleAt(700f, 800f);
            verify(f.marker, times(1)).setMeasuringState();
            verify(f.marker, never()).setErrorState(anyString());
            assertTrue(f.delayed.isEmpty());
            assertEquals(2, f.measurements.size());
        }
    }

    @Test public void explicitCancelStillSelectsAutoAndInvalidatesIndicatorCallbacks() {
        try (Fixture f = new Fixture()) {
            f.param.WB = 3524; f.param.isSpotWb = true;
            f.hold(200f, 250f);
            f.touch.cancelSpotWb();
            f.drainPosted();
            f.helper.verify(SpotWhiteBalanceHelper::cancelPendingMeasurement);
            verify(f.param).setWB((int) ManualParamModel.WB_AUTO);
            verify(f.console).setManualWbValue(ManualParamModel.WB_AUTO);
            Runnable cancelEnd = f.latestAnimationEnd();
            f.measurements.get(0).onSpotWbFailed("cancelled_old_measurement");
            f.drainPosted();
            verify(f.marker, never()).setErrorState(anyString());
            assertTrue(f.delayed.isEmpty());
            cancelEnd.run();
            assertEquals(View.GONE, f.visibility);

            f.hold(700f, 800f);
            cancelEnd.run();
            f.assertVisibleAt(700f, 800f);
        }
    }

    @Test public void queuedResetCannotHideANewerHold() {
        try (Fixture f = new Fixture()) {
            f.hold(200f, 250f);
            f.touch.resetSpotWbIndicator();
            f.touch.processSpotWb(700f, 800f);
            f.drainPosted();
            f.assertVisibleAt(700f, 800f);
            verify(f.animator, never()).alpha(0f);
            assertEquals(2, f.measurements.size());
        }
    }
}
