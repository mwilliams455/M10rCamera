#ifndef M10R_STATISTICS_H
#define M10R_STATISTICS_H
#include "m10r_metering.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Firmware statistics coordinates ONLY. A normalized phone green plane is not
 * this input. No reference brightness, exposure metadata, focus or tilt is
 * inferred here. The producer's phone calibration remains a separate task. */
typedef struct M10RGridInput {
    uint32_t y_sums[352];
    uint32_t step_a, step_b;
    int32_t sv_q8, tv_q8, av_q8;
    uint32_t fpos, tilt;
} M10RGridInput;
typedef struct M10RYResult {
    int32_t status, ev_q8, bv_q8;
    uint32_t normalized_y, normalized_reference;
} M10RYResult;
typedef struct M10RGridOutput {
    M10RYResult integral;
    M10RYResult regions[24];
    int32_t mfm_status, mfm_bv_q8, mfm_ev_q8;
    M10RMeterOutput aggregate;
} M10RGridOutput;
/* 0 success (including firmware dark-region status -12 in the output),
 * -1 invalid input, -2 core failure. Output committed only on success.
 * Nonempty 16x22 grid; pitches 1..65535 with product >=4; Q8 fields int16;
 * Fpos uint16; Tilt 0..3. */
int m10r_meter_grid(const M10RGridInput*, M10RGridOutput*);
/* Narrow firmware log port for positive normal binary64 inputs. Diagnostic;
 * returns NaN outside that domain. Original exceptional paths not ported. */
double m10r_statistics_log(double);
/* 0x420a3146..0x420a3170 conversion of workflow+0x7c. Units are deliberately
 * unnamed until the caller is traced. NOT a phone diopter conversion. */
uint32_t m10r_workflow_fpos(int32_t);
/* 0x420a3172..0x420a31ba conversion of workflow+0x27c angle. Mapping to
 * Android sensor/display rotation remains the caller's responsibility. */
uint32_t m10r_workflow_tilt(int32_t);
#ifdef __cplusplus
}
#endif
#endif
