package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.CaptureRequest;
import com.particlesdevs.photoncamera.settings.PreferenceKeys;
import org.json.JSONException;
import org.json.JSONObject;

/** Recovered Leica still contrast tables. Standard is the unchanged 4A Medium path.
 * Selection is frozen before capture; a renderer never consults mutable preferences.
 * Exact table bytes do not establish the live hardware signal scale or stage order.
 */
public final class M10RContrast4B {
    public static final String REVISION = "M10R_CONTRAST4B_STILL_TABLE_SELECTION";

    public enum Level {
        LOW("low", "Low", "LOW", 1, M10RContrastTables4B.LOW_SHA256),
        STANDARD("standard", "Standard", "MEDIUM", 2, M10RToneDg1A.TONE_SHA256),
        HIGH("high", "High", "HIGH", 3, M10RContrastTables4B.HIGH_SHA256);

        public final String preferenceValue, displayName, firmwareToneName, assetSha256;
        public final int firmwareEnum;
        Level(String preferenceValue, String displayName, String firmwareToneName,
                int firmwareEnum, String assetSha256) {
            this.preferenceValue = preferenceValue;
            this.displayName = displayName;
            this.firmwareToneName = firmwareToneName;
            this.firmwareEnum = firmwareEnum;
            this.assetSha256 = assetSha256;
        }
    }

    private M10RContrast4B() {}

    public static Level fromPreference(String value) {
        for (Level level : Level.values()) if (level.preferenceValue.equals(value)) return level;
        return Level.STANDARD;
    }

    public static Level current() { return fromPreference(PreferenceKeys.getM10RContrastValue()); }

    public static Level normalized(Level level) { return level == null ? Level.STANDARD : level; }

    /** Missing legacy tags retain Standard. Do not substitute the current UI setting. */
    public static Level fromRequest(CaptureRequest request) {
        Object tag = request == null ? null : request.getTag();
        return tag instanceof M10RExposureReport1C
                ? normalized(((M10RExposureReport1C) tag).contrast4B) : Level.STANDARD;
    }

    public static String controlKey(String controls, Level level) {
        return controls + ":contrast4b=" + normalized(level).preferenceValue;
    }

    /** Keep the existing Standard revision so saved golden fixtures remain comparable. */
    public static String rendererRevision(String base, Level level) {
        Level selected = normalized(level);
        return selected == Level.STANDARD ? base : base + ":M10R_CONTRAST4B_" + selected.firmwareToneName;
    }

    static int[] nativeToneTable(Level level) {
        switch (normalized(level)) {
            case LOW: return M10RContrastTables4B.low();
            case HIGH: return M10RContrastTables4B.high();
            default: return M10RToneDg1A.nativeToneTable();
        }
    }

    /** Same bounded Q15 operator as the native renderer and the original Medium helper. */
    static int tone(Level level, int x) {
        int xx = Math.max(0, Math.min(M10RToneDg1A.TONE_ENTRIES * 2 - 1, x));
        return (int) (((long) xx * nativeToneTable(level)[xx >> 1]) >> 15);
    }

    static void append(JSONObject diagnostics, CaptureRequest request) throws JSONException {
        Level selected = fromRequest(request);
        boolean bound = request != null && request.getTag() instanceof M10RExposureReport1C;
        diagnostics.put("contrast4B", new JSONObject()
                .put("revision", REVISION)
                .put("setting", selected.preferenceValue)
                .put("displayName", selected.displayName)
                .put("firmwareToneName", selected.firmwareToneName)
                .put("firmwareStillEnum", selected.firmwareEnum)
                .put("toneAssetSha256", selected.assetSha256)
                .put("requestBound", bound)
                .put("selectionSource", bound ? "immutable_capture_request" : "legacy_standard_default")
                .put("standardPreserves4APixels", true)
                .put("exactFirmwareTableBytes", true)
                .put("hardwareSignalScaleProven", false));
    }
}
