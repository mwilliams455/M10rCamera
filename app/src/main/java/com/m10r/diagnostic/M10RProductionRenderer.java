package com.m10r.diagnostic;

/**
 * Promoted default render policy after RENDER_PARITY1A scene validation.
 *
 * This selects canonical candidate C:
 *   RAW headroom OFF, CA9 neutral-domain clipping ON.
 *
 * Mechanism selection is promoted; exact Leica firmware arithmetic/stage parity
 * is not claimed here. The canonical A/B/C/D diagnostic renderer remains separate.
 */
public final class M10RProductionRenderer {
    private M10RProductionRenderer() {}

    public static final M10RHighlightFactorialRenderer.Mode PROMOTED_MODE =
            M10RHighlightFactorialRenderer.Mode.C_CA9_CLIP;

    public static M10RHighlightFactorialRenderer.Result render(
            DngRawDecoder.RawImage raw, DngMetadataReader.DngInfo info) {
        return M10RHighlightFactorialRenderer.render(raw, info, PROMOTED_MODE);
    }

    static M10RHighlightFactorialRenderer.Result render(
            DngRawDecoder.RawImage raw, DngMetadataReader.DngInfo info, int maxDimension) {
        return M10RHighlightFactorialRenderer.render(raw, info, PROMOTED_MODE, maxDimension);
    }
}
