#ifndef M10R_METERING_H
#define M10R_METERING_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Firmware Q8.8 coordinates. These are NOT normalized phone RAW samples.
 * All signed inputs must fit int16. No exposure / distance defaults are inferred.
 * The original wrapper supplies baseline = Integral BV + AV, offset = 0,
 * sub_av = AV, sub_tv = TV, add_sv = SV, then subtracts AV from the result.
 * Fpos physical calibration and Tilt-to-phone-orientation mapping remain open.
 */
typedef struct M10RMeterInput {
    int32_t baseline_q8;
    int32_t regions_q8[24];
    int32_t offset_q8;
    int32_t sub_av_q8;
    int32_t sub_tv_q8;
    int32_t add_sv_q8;
    uint32_t fpos;
    uint32_t tilt;
} M10RMeterInput;
typedef struct M10RMeterOutput {
    int32_t result_q8;
    uint8_t work[400];
} M10RMeterOutput;
/* 0 success, -1 invalid arguments, -2 bounded-execution failure.
 * Output is committed only on success. Reentrant; no mutable meter globals.
 */
int m10r_meter(const M10RMeterInput* input, M10RMeterOutput* output);
/* Diagnostic direct entry: mask is the aliased selection at work+0x173.
 * Each input selection must be 0 or 1. For synthetic feature validation only.
 */
int m10r_features(const uint8_t input_work[400], uint8_t output_work[400]);
/* Thread-local test tracing. Disabled by default; not required by the meter. */
void m10r_trace_enable(int enabled);
size_t m10r_trace_copy(uint32_t* addresses, size_t capacity);
#ifdef __cplusplus
}
#endif
#endif
