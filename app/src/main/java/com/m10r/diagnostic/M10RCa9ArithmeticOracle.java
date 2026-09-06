package com.m10r.diagnostic;

/**
 * CA9_PARITY1 firmware-arithmetic probe.
 *
 * Recovered firmware evidence establishes the following narrow ABI:
 *   - source WB gains are signed 16-bit values clamped to [1, 2000]
 *   - firmware ASN is encoded as 256.0 / integerGain
 *   - ColorManagementFinished reconstructs a gain as 256.0 / ASN and then
 *     calls ARM helper 0x421A0A44
 *   - 0x421A0A44 is a nearest-integer helper with half-way cases adjusted
 *     away from zero (the helper first obtains a nearest-even integral value,
 *     then applies the +/-0.5 / 1.0 tie correction visible in the disassembly)
 *
 * This class intentionally does NOT alter the promoted renderer. It is an
 * executable oracle for recovering the source integer gain from genuine Leica
 * AsShotNeutral and for probing arithmetic boundaries. Pixel-domain clipping,
 * multiply/shift precision, saturation threshold and exact stage ordering are
 * still open CA9_PARITY1 questions.
 */
public final class M10RCa9ArithmeticOracle {
    private M10RCa9ArithmeticOracle() {}

    public static final int GAIN_MIN = 1;
    public static final int GAIN_MAX = 2000;
    public static final double ASN_SCALE = 256.0;

    /**
     * Model of firmware helper 0x421A0A44 for finite values: round to nearest,
     * with exact half-way cases away from zero.
     */
    public static long roundHalfAwayFromZero(double value) {
        if (!Double.isFinite(value)) {
            throw new IllegalArgumentException("value must be finite");
        }
        return value >= 0.0
                ? (long) Math.floor(value + 0.5)
                : (long) Math.ceil(value - 0.5);
    }

    /**
     * Recover the clamped source integer gain represented by a Leica ASN value.
     * The clamp reflects the source gain ABI before ASN encoding.
     */
    public static int recoverSourceGainFromAsn(double asn) {
        if (!Double.isFinite(asn) || asn <= 0.0) {
            throw new IllegalArgumentException("ASN must be positive and finite");
        }
        long rounded = roundHalfAwayFromZero(ASN_SCALE / asn);
        if (rounded < GAIN_MIN) return GAIN_MIN;
        if (rounded > GAIN_MAX) return GAIN_MAX;
        return (int) rounded;
    }

    public static int[] recoverSourceGainsFromAsn(double[] asn) {
        if (asn == null || asn.length != 3) {
            throw new IllegalArgumentException("ASN must have three channels");
        }
        return new int[] {
                recoverSourceGainFromAsn(asn[0]),
                recoverSourceGainFromAsn(asn[1]),
                recoverSourceGainFromAsn(asn[2])
        };
    }

    /** Encode a source gain using the recovered firmware ASN representation. */
    public static double encodeAsnFromSourceGain(int gain) {
        int clamped = Math.min(GAIN_MAX, Math.max(GAIN_MIN, gain));
        return ASN_SCALE / clamped;
    }

    /**
     * Camera-domain boundary implied by the currently promoted C mechanism.
     * This is a diagnostic boundary only, not yet a firmware-verified pixel
     * saturation threshold.
     */
    public static double promotedCandidateCameraBoundary(int gain) {
        if (gain <= 0) throw new IllegalArgumentException("gain must be positive");
        return ASN_SCALE / gain;
    }
}
