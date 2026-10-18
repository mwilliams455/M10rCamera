package com.particlesdevs.photoncamera.m10r;

import java.io.PrintWriter;
import java.io.Writer;
import org.json.JSONArray;
import org.json.JSONObject;

/** Request-local diagnostics only. Never used to accept, extend or allocate exposure. */
public final class M10RExposureTrace1D implements M10RExposureProbe1B.Progress {
    public static final String REVISION = "M10R_EXPOSURE1D_PROBE_DIAGNOSTICS";
    private static final int MAX_STAGES = 24, MAX_STACK = 12288, MAX_MESSAGE = 2048;
    private final long started = System.nanoTime();
    private final String[] stages = new String[MAX_STAGES];
    private final long[] entered = new long[MAX_STAGES];
    private int count;
    private long observed, ended;
    private String failureStage, exceptionClass, exceptionMessage, exceptionStack;
    private boolean stackTruncated;

    public M10RExposureTrace1D() { step("request_prepared"); }
    public synchronized void observed(long ns) { observed = ns; }
    @Override public synchronized void step(String stage) {
        if (ended != 0 || count == MAX_STAGES) return;
        stages[count] = stage;
        entered[count++] = System.nanoTime();
    }
    public synchronized String stage() { return count == 0 ? "unknown" : stages[count - 1]; }
    public synchronized void complete() { if (ended == 0) ended = System.nanoTime(); }

    /** Best effort even when reporting an allocation/linkage failure. */
    public synchronized void failure(Throwable error) {
        complete();
        try {
            failureStage = stage();
            exceptionClass = error.getClass().getName();
            String message = error.getMessage();
            exceptionMessage = message == null ? null : message.substring(0, Math.min(MAX_MESSAGE, message.length()));
            BoundedWriter out = new BoundedWriter(MAX_STACK);
            error.printStackTrace(new PrintWriter(out));
            exceptionStack = out.value.toString();
            stackTruncated = out.truncated;
        } catch (RuntimeException | LinkageError | OutOfMemoryError ignored) {
            // Failure reporting must not interrupt fallback, frame cleanup or session retirement.
        }
    }

    /** Build separately, then attach. A serializer failure cannot cancel the photograph. */
    public synchronized boolean appendTo(JSONObject report) {
        try {
            long end = ended == 0 ? System.nanoTime() : ended;
            JSONObject d = new JSONObject();
            d.put("revision", REVISION);
            d.put("lastStage", stage());
            d.put("requestElapsedMs", Math.max(0L, end - started) / 1e6);
            d.put("evidenceAgeMs", observed == 0 ? JSONObject.NULL : Math.max(0L, end - observed) / 1e6);
            d.put("evidenceDeadlineMs", M10RExposure1A.MAX_AGE_NS / 1e6);
            JSONArray timing = new JSONArray();
            for (int i = 0; i < count; i++) {
                long next = i + 1 < count ? entered[i + 1] : end;
                timing.put(new JSONObject().put("stage", stages[i])
                        .put("elapsedMs", Math.max(0L, next - entered[i]) / 1e6));
            }
            d.put("stages", timing);
            if (exceptionClass != null) {
                d.put("failure", new JSONObject().put("stage", failureStage)
                        .put("exceptionClass", exceptionClass)
                        .put("message", exceptionMessage == null ? JSONObject.NULL : exceptionMessage)
                        .put("stackTrace", exceptionStack == null ? JSONObject.NULL : exceptionStack)
                        .put("stackTruncated", stackTruncated));
            }
            report.put("probeDiagnostics", d);
            return true;
        } catch (Exception | LinkageError | OutOfMemoryError ignored) {
            return false;
        }
    }

    private static final class BoundedWriter extends Writer {
        final StringBuilder value = new StringBuilder();
        final int limit;
        boolean truncated;
        BoundedWriter(int limit) { this.limit = limit; }
        @Override public void write(char[] data, int offset, int length) {
            int take = Math.min(length, limit - value.length());
            if (take > 0) value.append(data, offset, take);
            if (take < length) truncated = true;
        }
        @Override public void flush() {}
        @Override public void close() {}
    }
}
