M10-R REFERENCE TRANSFER RGB1G — YC PRESERVATION TOPOLOGY AUDIT

No fitting. Scale 0.94, exact MEDIUM->DG, exact B2Y record 0x0C RGB->YC matrix. YC inverse is mathematical only.

=== Aggregate ===
rec709_shared_linear: medians={'encoded_rgb_rmse': 62.09512772311574, 'encoded_rgb_mae': 50.58638811184974, 'luma_rmse': 57.591836242152056, 'luma_mae': 46.784407122332205, 'delta_e76_mean': 28.34827781943396, 'hue_error_deg_mean': 16.679987707194094, 'saturation_error_abs_mean': 0.2612156419457229} bins={'shadow': 81.99630279065353, 'midtone': 49.95376642509764, 'highlight': 91.97607442499822, 'neutral_pixels': 77.4012841027801, 'colourful_pixels': 56.05510311305742} falseClips=66696 wins=control
fw_component_shared_linear: medians={'encoded_rgb_rmse': 62.2616429024348, 'encoded_rgb_mae': 50.73760515147537, 'luma_rmse': 57.832998716420974, 'luma_mae': 46.98677741657852, 'delta_e76_mean': 28.482575814997077, 'hue_error_deg_mean': 16.679255139160258, 'saturation_error_abs_mean': 0.2611763254359225} bins={'shadow': 82.93829659759527, 'midtone': 49.998520746612044, 'highlight': 90.95665232619098, 'neutral_pixels': 77.69912854353052, 'colourful_pixels': 56.51346080698112} falseClips=100307 wins={'rgb': 0, 'luma': 0, 'de': 0, 'highlight': 6}
fw_yc_preserve_chroma: medians={'encoded_rgb_rmse': 112.82191211597711, 'encoded_rgb_mae': 104.0596026867768, 'luma_rmse': 109.14194924862696, 'luma_mae': 100.35873306753439, 'delta_e76_mean': 43.57921661646391, 'hue_error_deg_mean': 16.697459901158194, 'saturation_error_abs_mean': 0.3747021083378741} bins={'shadow': 152.0818576737608, 'midtone': 98.0930538592468, 'highlight': 33.96439033283662, 'neutral_pixels': 121.84852395789568, 'colourful_pixels': 109.3221416986613} falseClips=449708 wins={'rgb': 0, 'luma': 0, 'de': 0, 'highlight': 4}

=== YC preserve gate versus RGB1D control ===
{'core_ratios': {'encoded_rgb_rmse': 1.8169205258591916, 'luma_rmse': 1.895094103089994, 'delta_e76_mean': 1.537279156569733}, 'highlight_ratio': 0.3692741894581818, 'false_clip_ratio': 6.742653232577666, 'passed': False}

=== Reconstruction-only delta versus firmware-component shared-linear ===
{'rgb_ratio': 1.812061276519337, 'luma_ratio': 1.8871915977207911, 'de_ratio': 1.5300307422869361, 'highlight_ratio': 0.373412933130308, 'false_clip_ratio': 4.483316219207034}

VERDICT RGB1G_YC_PRESERVE_DOES_NOT_CLEAR_PROMOTION_GATE

Workflow run id: 34212091234
Analysis input commit: 67cece4b32bda11c798a9bb54864cd4075babe19
