M10-R REFERENCE TRANSFER RGB1C — ENCODED-LUMA HEADROOM / SCALE

Frozen winner entering test: EL_OETF = encoded luma -> MEDIUM/DG -> shared gain on linear RGB -> sRGB OETF.
Factorial: bounded vs extended pre-output-clamp encoded luma; coordinate scale 1.00 vs pre-declared 0.94; scale is applied before the 14-bit clamp.
Scale 0.94 is not fitted here; it is the nearest-rounding median identity scale from the earlier six-pair scalar transfer evidence.
Fit freedom: NONE. Live m10r-capture1b remains untouched.

=== Aggregate ===
ll_oetf: medians={'encoded_rgb_rmse': 90.67965756313339, 'luma_rmse': 89.46991699413559, 'delta_e76_mean': 38.79584466490506, 'hue_error_deg_mean': 16.665664343453408, 'saturation_error_abs_mean': 0.2619740518863223} highlightRGB=67.24256023496253 falseClips=454873
ll_identity: medians={'encoded_rgb_rmse': 68.1789357344904, 'luma_rmse': 65.92887459629537, 'delta_e76_mean': 33.768737507983744, 'hue_error_deg_mean': 17.755216836147802, 'saturation_error_abs_mean': 0.26420572522540686} highlightRGB=111.45635254460565 falseClips=445203
el_bounded_s100: medians={'encoded_rgb_rmse': 62.507981183412525, 'luma_rmse': 58.03151262981173, 'delta_e76_mean': 28.515371179833053, 'hue_error_deg_mean': 16.67895673588561, 'saturation_error_abs_mean': 0.2612203139956478} highlightRGB=90.93570936302268 falseClips=140991
el_bounded_s094: medians={'encoded_rgb_rmse': 62.174403751795, 'luma_rmse': 57.68581173341245, 'delta_e76_mean': 28.397088975664357, 'hue_error_deg_mean': 16.67982281212209, 'saturation_error_abs_mean': 0.26120687950322197} highlightRGB=91.62142878928441 falseClips=132198
el_extended_s100: medians={'encoded_rgb_rmse': 62.50795820377627, 'luma_rmse': 58.03139533844756, 'delta_e76_mean': 28.51546047834067, 'hue_error_deg_mean': 16.67894479731524, 'saturation_error_abs_mean': 0.2612202452514567} highlightRGB=90.93237187745439 falseClips=140481
el_extended_s094: medians={'encoded_rgb_rmse': 62.17438375433616, 'luma_rmse': 57.685699764995704, 'delta_e76_mean': 28.397171128329802, 'hue_error_deg_mean': 16.679840956085393, 'saturation_error_abs_mean': 0.26120682091442277} highlightRGB=91.61843159040262 falseClips=131666

=== Targeted gate versus EL bounded scale1.00 ===
el_bounded_s094: {'core_ratios_vs_base': {'encoded_rgb_rmse': 0.9946634425668182, 'luma_rmse': 0.9940428763488462, 'delta_e76_mean': 0.9958519844113988}, 'core_not_worse_2pct': True, 'core_improves_two': True, 'highlight_improves_10pct': False, 'hue_guard': True, 'saturation_guard': True, 'clip_guard': True, 'passed': False}
el_extended_s100: {'core_ratios_vs_base': {'encoded_rgb_rmse': 0.9999996323727655, 'luma_rmse': 0.9999979788332433, 'delta_e76_mean': 1.0000031315919773}, 'core_not_worse_2pct': True, 'core_improves_two': False, 'highlight_improves_10pct': False, 'hue_guard': True, 'saturation_guard': True, 'clip_guard': True, 'passed': False}
el_extended_s094: {'core_ratios_vs_base': {'encoded_rgb_rmse': 0.9946631226483301, 'luma_rmse': 0.9940409469072089, 'delta_e76_mean': 0.9958548654072283}, 'core_not_worse_2pct': True, 'core_improves_two': True, 'highlight_improves_10pct': False, 'hue_guard': True, 'saturation_guard': True, 'clip_guard': True, 'passed': False}

VERDICT RGB1C_NO_BRIGHT_END_VARIANT_CLEARS_GATE

Interpretation boundary: this tests only encoded-luma per-channel clamp ownership and a pre-declared coordinate scale. It does not solve the literal B2Y signal mux.
Workflow run id: 34199575050
Analysis input commit: a4e2682fbd7f0eda6c3bd61eb00fade78cf8a723
