package com.particlesdevs.photoncamera.m10r;

import org.json.JSONObject;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.function.LongSupplier;

/** Single-thread, disjoint wall-time intervals; never accepts image or exposure state. */
public final class M10RStageTiming3E {
    private static final class Entry {
        long ns;
        int intervals;
    }

    private final LongSupplier clock;
    private final long startNs;
    private long lastNs;
    private final LinkedHashMap<String, Entry> stages = new LinkedHashMap<>();
    private Entry active;
    private boolean finished;

    public M10RStageTiming3E(String firstStage, long startNs) {
        this(firstStage, startNs, System::nanoTime);
    }

    M10RStageTiming3E(String firstStage, long startNs, LongSupplier clock) {
        this.clock = clock;
        this.startNs = this.lastNs = startNs;
        enter(firstStage);
    }

    private void enter(String name) {
        if (name == null || name.isEmpty()) throw new IllegalArgumentException("Timing stage missing");
        active = stages.computeIfAbsent(name, unused -> new Entry());
        active.intervals++;
    }

    private long closeInterval() {
        if (finished) throw new IllegalStateException("Timing scope already finished");
        long now = clock.getAsLong();
        long elapsed = now - lastNs;
        if (elapsed < 0) throw new IllegalStateException("Timing clock moved backwards");
        active.ns += elapsed;
        lastNs = now;
        return now;
    }

    public void next(String stage) {
        if (stage == null || stage.isEmpty()) throw new IllegalArgumentException("Timing stage missing");
        closeInterval();
        enter(stage);
    }

    public Snapshot finish() {
        long now = closeInterval();
        finished = true;
        return new Snapshot(now - startNs, stages);
    }

    public static final class Snapshot {
        public final long elapsedNs;
        public final long stageSumNs;
        private final LinkedHashMap<String, long[]> stages = new LinkedHashMap<>();

        private Snapshot(long elapsedNs, Map<String, Entry> source) {
            this.elapsedNs = elapsedNs;
            long sum = 0L;
            for (Map.Entry<String, Entry> item : source.entrySet()) {
                Entry e = item.getValue();
                stages.put(item.getKey(), new long[]{e.ns, e.intervals});
                sum += e.ns;
            }
            stageSumNs = sum;
        }

        public JSONObject json(String scope) throws Exception {
            JSONObject values = new JSONObject();
            for (Map.Entry<String, long[]> item : stages.entrySet()) {
                long[] value = item.getValue();
                values.put(item.getKey(), new JSONObject().put("elapsedNs", value[0])
                        .put("elapsedMs", value[0] / 1_000_000.0).put("intervals", value[1]));
            }
            return new JSONObject().put("revision", "M10R_RENDERPROFILE3E")
                    .put("scope", scope).put("clock", "System.nanoTime_monotonic_wall_time")
                    .put("exclusiveStagesWithinScope", true)
                    .put("includesSchedulingGcAndInstrumentationOverhead", true)
                    .put("timingJsonPublicationIncluded", false)
                    .put("elapsedNs", elapsedNs).put("elapsedMs", elapsedNs / 1_000_000.0)
                    .put("stageSumNs", stageSumNs).put("unattributedNs", elapsedNs - stageSumNs)
                    .put("partitionValid", elapsedNs == stageSumNs).put("stages", values);
        }
    }
}
