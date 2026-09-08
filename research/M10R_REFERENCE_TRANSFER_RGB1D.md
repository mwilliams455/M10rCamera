M10-R REFERENCE TRANSFER RGB1D — ENCODED LUMA DEFINITION / TARGET RECONSTRUCTION

Frozen scale: 0.94 from prior scalar/RGB1C evidence. No fitting. Live capture branch untouched.

=== Aggregate ===
oetfy_code_ratio: medians={'encoded_rgb_rmse': 62.09512772311574, 'luma_rmse': 57.591836242152056, 'delta_e76_mean': 28.34827781943396, 'hue_error_deg_mean': 16.679987707194094, 'saturation_error_abs_mean': 0.2612156419457229} highlight=91.97607442499822 falseClips=66696
component_code_ratio: medians={'encoded_rgb_rmse': 62.174403751795, 'luma_rmse': 57.68581173341245, 'delta_e76_mean': 28.397088975664357, 'hue_error_deg_mean': 16.67982281212209, 'saturation_error_abs_mean': 0.26120687950322197} highlight=91.62142878928441 falseClips=132198
ll_oetf: medians={'encoded_rgb_rmse': 90.67965756313339, 'luma_rmse': 89.46991699413559, 'delta_e76_mean': 38.79584466490506, 'hue_error_deg_mean': 16.665664343453408, 'saturation_error_abs_mean': 0.2619740518863223} highlight=67.24256023496253 falseClips=454873
component_linear_target: medians={'encoded_rgb_rmse': 106.08696375543596, 'luma_rmse': 107.0989628188673, 'delta_e76_mean': 46.3325696791546, 'hue_error_deg_mean': 16.66136947527276, 'saturation_error_abs_mean': 0.2617432642826131} highlight=50.00787546270621 falseClips=685130
oetfy_linear_target: medians={'encoded_rgb_rmse': 106.39148814969379, 'luma_rmse': 107.40028757975958, 'delta_e76_mean': 46.46785528037175, 'hue_error_deg_mean': 16.658942371359956, 'saturation_error_abs_mean': 0.26173874609268605} highlight=49.793195065431576 falseClips=762477

=== Gate versus component_code_ratio ===
oetfy_code_ratio: {'core_ratios': {'encoded_rgb_rmse': 0.9987249410706738, 'luma_rmse': 0.9983709080545717, 'delta_e76_mean': 0.998281121129274}, 'highlight_ratio': 1.0038707717222948, 'passed': False}
component_linear_target: {'core_ratios': {'encoded_rgb_rmse': 1.7062803558027397, 'luma_rmse': 1.856591068074267, 'delta_e76_mean': 1.6315957497918372}, 'highlight_ratio': 0.5458098189858712, 'passed': False}
oetfy_linear_target: {'core_ratios': {'encoded_rgb_rmse': 1.711178261948708, 'luma_rmse': 1.8618146187505547, 'delta_e76_mean': 1.636359815620313}, 'highlight_ratio': 0.5434666946741082, 'passed': False}

VERDICT RGB1D_NO_ALTERNATE_DEFINITION_CLEARS_HIGHLIGHT_GATE

Workflow run id: 34200124271
Analysis input commit: b705d5f3f9bbc8814134a619734d89cffd7ad0f5
