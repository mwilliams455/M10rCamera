# M10-R REFERENCE CHROMASUPPRESS1A

Constrained six-pair screen of a Fujitsu-family low-chroma suppression topology inside the exact RGB1G Leica YC path.

No continuous fitting. Candidate inner/outer thresholds come only from M10-R record-0x18 MEDIUM values 20000/30000/40000/50000.
Normalization hypothesis: CsumCode=(abs(Cb)+abs(Cr))*65536.

## Baseline

{'encoded_rgb_rmse': 112.82191211597711, 'encoded_rgb_mae': 104.0596026867768, 'luma_rmse': 109.14194924862696, 'luma_mae': 100.35873306753439, 'delta_e76_mean': 43.57921661646391, 'hue_error_deg_mean': 16.697459901158194, 'saturation_error_abs_mean': 0.3747021083378741}

## Candidates

cs_20000_30000: ratios={'rgb': 1.0669904739270961, 'de': 1.1337810664099703, 'hue': 3.9269716899212534, 'saturation': 1.4203696626787097, 'colourful': 1.096860955932146, 'neutral': 1.0245490720308719, 'highlight': 1.01613305056473} wins={'rgb': 0, 'de': 0, 'hue': 0, 'saturation': 0, 'colourful': 0, 'neutral': 1} screen={'broad_improvement': False} render={'median_suppressed_pixels': 2562328.5, 'median_mean_gain': 0.00016278499999999998, 'per_sample': [{'suppressed_pixels': 2562321, 'mean_gain': 0.0058718}, {'suppressed_pixels': 2562336, 'mean_gain': 8.565e-05}, {'suppressed_pixels': 2562336, 'mean_gain': 8.2e-07}, {'suppressed_pixels': 2562316, 'mean_gain': 8.096e-05}, {'suppressed_pixels': 2550145, 'mean_gain': 0.01317772}, {'suppressed_pixels': 2562336, 'mean_gain': 0.00023992}]}
cs_20000_40000: ratios={'rgb': 1.0674474755709566, 'de': 1.1352829665244049, 'hue': 3.9278142797172255, 'saturation': 1.4225561836761504, 'colourful': 1.0977228856987526, 'neutral': 1.024625178240593, 'highlight': 1.0166888190212282} wins={'rgb': 0, 'de': 0, 'hue': 0, 'saturation': 0, 'colourful': 0, 'neutral': 1} screen={'broad_improvement': False} render={'median_suppressed_pixels': 2562336.0, 'median_mean_gain': 8.1395e-05, 'per_sample': [{'suppressed_pixels': 2562336, 'mean_gain': 0.00293661}, {'suppressed_pixels': 2562336, 'mean_gain': 4.283e-05}, {'suppressed_pixels': 2562336, 'mean_gain': 4.1e-07}, {'suppressed_pixels': 2562336, 'mean_gain': 4.087e-05}, {'suppressed_pixels': 2562336, 'mean_gain': 0.00752582}, {'suppressed_pixels': 2562336, 'mean_gain': 0.00011996}]}
cs_20000_50000: ratios={'rgb': 1.067614967969734, 'de': 1.1358000645238626, 'hue': 3.9287283194759555, 'saturation': 1.4233713555156375, 'colourful': 1.098038677324614, 'neutral': 1.0246753276972664, 'highlight': 1.0169304918519702} wins={'rgb': 0, 'de': 0, 'hue': 0, 'saturation': 0, 'colourful': 0, 'neutral': 1} screen={'broad_improvement': False} render={'median_suppressed_pixels': 2562336.0, 'median_mean_gain': 5.426e-05, 'per_sample': [{'suppressed_pixels': 2562336, 'mean_gain': 0.00195774}, {'suppressed_pixels': 2562336, 'mean_gain': 2.855e-05}, {'suppressed_pixels': 2562336, 'mean_gain': 2.7e-07}, {'suppressed_pixels': 2562336, 'mean_gain': 2.724e-05}, {'suppressed_pixels': 2562336, 'mean_gain': 0.00501722}, {'suppressed_pixels': 2562336, 'mean_gain': 7.997e-05}]}
cs_30000_40000: ratios={'rgb': 1.067973991629695, 'de': 1.136818158187052, 'hue': 3.9677765776671743, 'saturation': 1.4251160752115615, 'colourful': 1.0987148514215406, 'neutral': 1.024740143852169, 'highlight': 1.0174382168387366} wins={'rgb': 0, 'de': 0, 'hue': 0, 'saturation': 0, 'colourful': 0, 'neutral': 1} screen={'broad_improvement': False} render={'median_suppressed_pixels': 2562336.0, 'median_mean_gain': 3.85e-07, 'per_sample': [{'suppressed_pixels': 2562336, 'mean_gain': 1.42e-06}, {'suppressed_pixels': 2562336, 'mean_gain': 0.0}, {'suppressed_pixels': 2562336, 'mean_gain': 0.0}, {'suppressed_pixels': 2562336, 'mean_gain': 7.7e-07}, {'suppressed_pixels': 2562336, 'mean_gain': 0.00187393}, {'suppressed_pixels': 2562336, 'mean_gain': 0.0}]}
cs_30000_50000: ratios={'rgb': 1.067974166254517, 'de': 1.1368187392586364, 'hue': 3.967776518662974, 'saturation': 1.4251163762056376, 'colourful': 1.0987151631707586, 'neutral': 1.0247702649591202, 'highlight': 1.0174635602297457} wins={'rgb': 0, 'de': 0, 'hue': 0, 'saturation': 0, 'colourful': 0, 'neutral': 1} screen={'broad_improvement': False} render={'median_suppressed_pixels': 2562336.0, 'median_mean_gain': 1.95e-07, 'per_sample': [{'suppressed_pixels': 2562336, 'mean_gain': 7.1e-07}, {'suppressed_pixels': 2562336, 'mean_gain': 0.0}, {'suppressed_pixels': 2562336, 'mean_gain': 0.0}, {'suppressed_pixels': 2562336, 'mean_gain': 3.9e-07}, {'suppressed_pixels': 2562336, 'mean_gain': 0.00093696}, {'suppressed_pixels': 2562336, 'mean_gain': 0.0}]}
cs_40000_50000: ratios={'rgb': 1.067974421046598, 'de': 1.136819403448249, 'hue': 3.9677822576457134, 'saturation': 1.4251167036788854, 'colourful': 1.0987156180385678, 'neutral': 1.0248045175421854, 'highlight': 1.0175005360946834} wins={'rgb': 0, 'de': 0, 'hue': 0, 'saturation': 0, 'colourful': 0, 'neutral': 1} screen={'broad_improvement': False} render={'median_suppressed_pixels': 2562336.0, 'median_mean_gain': 0.0, 'per_sample': [{'suppressed_pixels': 2562336, 'mean_gain': 0.0}, {'suppressed_pixels': 2562336, 'mean_gain': 0.0}, {'suppressed_pixels': 2562336, 'mean_gain': 0.0}, {'suppressed_pixels': 2562336, 'mean_gain': 0.0}, {'suppressed_pixels': 2562336, 'mean_gain': 0.0}, {'suppressed_pixels': 2562336, 'mean_gain': 0.0}]}

## Result

Passing candidates: []
Best RGB ratio: cs_20000_30000 = 1.0669904739270961
Best DeltaE ratio: cs_20000_30000 = 1.1337810664099703
Best colourful-pixel ratio: cs_20000_30000 = 1.096860955932146

VERDICT CHROMASUPPRESS1A_DIRECT_THRESHOLD_MAPPING_NOT_SUPPORTED

Interpretation boundary: failure falsifies this direct threshold/normalization mapping, not the firmware-proven existence of the color_dif_suppression block. Success would justify deeper mapping/offline replication, not immediate Android promotion.

Workflow run id: 36226490118
Analysis input commit: aca01e847744a976f1ac17a01108e26e421ebf1b
