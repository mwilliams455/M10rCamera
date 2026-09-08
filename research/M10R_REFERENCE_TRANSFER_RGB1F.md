M10-R REFERENCE TRANSFER RGB1F — FIRMWARE YC_CONVERSION Y-ROW AUDIT

No fitting. Frozen coordinate scale 0.94, exact MEDIUM->DG, shared code-ratio gain on linear RGB, final standard sRGB OETF.
Firmware Y row: [1224,2403,469]/4096 from recovered B2Y record 0x0C.

=== Aggregate ===
rec709_oetfy: medians={'encoded_rgb_rmse': 62.09512772311574, 'encoded_rgb_mae': 50.58638811184974, 'luma_rmse': 57.591836242152056, 'luma_mae': 46.784407122332205, 'delta_e76_mean': 28.34827781943396, 'hue_error_deg_mean': 16.679987707194094, 'saturation_error_abs_mean': 0.2612156419457229} bins={'shadow': 81.99630279065353, 'midtone': 49.95376642509764, 'highlight': 91.97607442499822, 'neutral_pixels': 77.4012841027801, 'colourful_pixels': 56.05510311305742} falseClips=66696 sampleWins=control
fw601_oetfy: medians={'encoded_rgb_rmse': 62.13892747985493, 'encoded_rgb_mae': 50.6303223876248, 'luma_rmse': 57.68401047160782, 'luma_mae': 46.85266974830277, 'delta_e76_mean': 28.405776992371536, 'hue_error_deg_mean': 16.6797273351022, 'saturation_error_abs_mean': 0.2611934031661869} bins={'shadow': 82.39437334749275, 'midtone': 49.94376284594253, 'highlight': 91.50717447446789, 'neutral_pixels': 77.53183737162192, 'colourful_pixels': 56.223189334259} falseClips=59520 sampleWins={'encoded_rgb_rmse': 1, 'luma_rmse': 1, 'delta_e76_mean': 1, 'highlight_rgb_rmse': 6}
fw601_component_y: medians={'encoded_rgb_rmse': 62.2616429024348, 'encoded_rgb_mae': 50.73760515147537, 'luma_rmse': 57.832998716420974, 'luma_mae': 46.98677741657852, 'delta_e76_mean': 28.482575814997077, 'hue_error_deg_mean': 16.679255139160258, 'saturation_error_abs_mean': 0.2611763254359225} bins={'shadow': 82.93829659759527, 'midtone': 49.998520746612044, 'highlight': 90.95665232619098, 'neutral_pixels': 77.69912854353052, 'colourful_pixels': 56.51346080698112} falseClips=100307 sampleWins={'encoded_rgb_rmse': 0, 'luma_rmse': 0, 'delta_e76_mean': 0, 'highlight_rgb_rmse': 6}

=== Promotion gate versus rec709_oetfy ===
fw601_oetfy: {'core_ratios': {'encoded_rgb_rmse': 1.0007053654343783, 'luma_rmse': 1.0016004738773774, 'delta_e76_mean': 1.0020283127357443}, 'highlight_ratio': 0.9949019356016038, 'false_clip_ratio': 0.8924073407700611, 'passed': False}
fw601_component_y: {'core_ratios': {'encoded_rgb_rmse': 1.0026816142493749, 'luma_rmse': 1.0041874420057544, 'delta_e76_mean': 1.0047374304858494}, 'highlight_ratio': 0.9889164426164053, 'false_clip_ratio': 1.5039432649634161, 'passed': False}

VERDICT RGB1F_FIRMWARE_Y_DOES_NOT_CLEAR_PROMOTION_GATE

Workflow run id: 34211327444
Analysis input commit: 9a5329dde2493bd5aed04904a753058b52365660
