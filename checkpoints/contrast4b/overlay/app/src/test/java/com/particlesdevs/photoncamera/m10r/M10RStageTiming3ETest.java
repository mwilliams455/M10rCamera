package com.particlesdevs.photoncamera.m10r;

import org.json.JSONObject;
import org.junit.Test;
import java.util.concurrent.atomic.AtomicLong;
import static org.junit.Assert.*;

public class M10RStageTiming3ETest {
    @Test public void repeatedStagesPartitionWallTimeWithoutDoubleCounting() throws Exception {
        AtomicLong clock = new AtomicLong(100L);
        M10RStageTiming3E t = new M10RStageTiming3E("colour", 100L, clock::get);
        clock.set(110L); t.next("diagnostics");
        clock.set(125L); t.next("colour");
        clock.set(155L); M10RStageTiming3E.Snapshot s = t.finish();
        JSONObject j = s.json("test");
        assertEquals(55L, s.elapsedNs);
        assertEquals(55L, s.stageSumNs);
        assertTrue(j.getBoolean("partitionValid"));
        assertEquals(0L, j.getLong("unattributedNs"));
        assertEquals(40L, j.getJSONObject("stages").getJSONObject("colour").getLong("elapsedNs"));
        assertEquals(2L, j.getJSONObject("stages").getJSONObject("colour").getLong("intervals"));
        assertEquals(15L, j.getJSONObject("stages").getJSONObject("diagnostics").getLong("elapsedNs"));
    }

    @Test public void zeroDurationIntervalsAreValid() throws Exception {
        M10RStageTiming3E t = new M10RStageTiming3E("a", 0L, () -> 0L);
        t.next("b");
        JSONObject j = t.finish().json("zero");
        assertEquals(0L, j.getLong("elapsedNs"));
        assertTrue(j.getBoolean("partitionValid"));
        assertEquals(2, j.getJSONObject("stages").length());
    }

    @Test public void longCapturesRetainNanosecondPrecision() throws Exception {
        long duration = 7_890_538_539L;
        M10RStageTiming3E t = new M10RStageTiming3E("render", 100L, () -> 100L + duration);
        JSONObject j = t.finish().json("long");
        assertEquals(duration, j.getLong("elapsedNs"));
        assertEquals(7890.538539, j.getDouble("elapsedMs"), 1e-9);
    }

    @Test public void finishedSnapshotsCannotAccumulateMoreTime() {
        M10RStageTiming3E t = new M10RStageTiming3E("render", 0L, () -> 10L);
        M10RStageTiming3E.Snapshot s = t.finish();
        assertThrows(IllegalStateException.class, () -> t.next("save"));
        assertThrows(IllegalStateException.class, t::finish);
        assertEquals(10L, s.stageSumNs);
    }

    @Test public void invalidInputsDoNotCreateNegativeOrUnnamedTimings() {
        assertThrows(IllegalArgumentException.class,
                () -> new M10RStageTiming3E("", 0L, () -> 0L));
        M10RStageTiming3E t = new M10RStageTiming3E("a", 10L, () -> 9L);
        assertThrows(IllegalStateException.class, t::finish);
        assertThrows(IllegalArgumentException.class, () -> t.next(null));
    }

    @Test public void nestedScopesStaySeparateAndDeclareMeasurementLimits() throws Exception {
        AtomicLong clock = new AtomicLong(10L);
        M10RStageTiming3E saver = new M10RStageTiming3E("renderCall", 0L, clock::get);
        M10RStageTiming3E renderer = new M10RStageTiming3E("colour", 10L, clock::get);
        clock.set(30L); JSONObject render = renderer.finish().json("renderer");
        clock.set(40L); saver.next("jpeg");
        clock.set(60L); JSONObject save = saver.finish().json("saver");
        assertEquals(20L, render.getLong("elapsedNs"));
        assertEquals(60L, save.getLong("elapsedNs"));
        assertEquals(40L, save.getJSONObject("stages").getJSONObject("renderCall").getLong("elapsedNs"));
        assertTrue(save.getBoolean("exclusiveStagesWithinScope"));
        assertFalse(save.getBoolean("timingJsonPublicationIncluded"));
        assertTrue(save.getBoolean("includesSchedulingGcAndInstrumentationOverhead"));
    }
}
