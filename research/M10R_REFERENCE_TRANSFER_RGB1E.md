M10-R REFERENCE TRANSFER RGB1E — SHARED MEDIUM GAIN / COMPONENT-WISE DG

Firmware hypothesis under test: weighted linear RGB scalar -> MEDIUM Q15 gain -> shared tone gain on RGB component coordinates -> Differential Gamma independently per component.
Working-space boundary: current ColorSpec linear sRGB is used as the component basis; literal Leica B2Y working RGB remains OPEN.
No fitting. Exact firmware MEDIUM/DG assets. Live m10r-capture1b untouched.

Scalar weights: REC709=0.2126/0.7152/0.0722; FW_TONE=1024/2661/410 normalized by 4095.
Final transfer crossed: identity vs textbook sRGB OETF.
BASELINE is RGB1D OETF(linear Rec709 Y) code-ratio scalar topology at fixed scale 0.94.

=== Per-sample RGB ranking ===
sample 01 identity=True defaults=True align=0.94064
  FW_ID RGB=8.8172 Y=7.5785 dE=5.0960 hue=9.0371 sat=0.059084 hi=5.953375361303671
  REC_ID RGB=9.0560 Y=7.8517 dE=5.1822 hue=9.0401 sat=0.059149 hi=5.943813734907085
  BASELINE RGB=36.2644 Y=36.6121 dE=15.7937 hue=9.3065 sat=0.136385 hi=16.20829180312548
  FW_OETF RGB=68.8599 Y=68.1100 dE=29.1854 hue=10.5641 sat=0.224637 hi=30.864867302949836
  REC_OETF RGB=69.0282 Y=68.2931 dE=29.2432 hue=10.5644 sat=0.224775 hi=30.859831723281722
sample 02 identity=True defaults=True align=0.94293
  FW_ID RGB=7.6309 Y=6.4586 dE=5.5588 hue=12.3250 sat=0.049658 hi=5.822883260925894
  REC_ID RGB=7.6603 Y=6.4731 dE=5.5875 hue=12.3243 sat=0.049571 hi=5.816677665198815
  BASELINE RGB=27.8070 Y=26.9546 dE=11.2824 hue=12.7114 sat=0.072965 hi=16.693974135804776
  REC_OETF RGB=60.4536 Y=59.4496 dE=23.9954 hue=13.0982 sat=0.135039 hi=33.73238086095972
  FW_OETF RGB=60.5489 Y=59.5459 dE=24.0272 hue=13.0990 sat=0.135207 hi=33.73613964642638
sample 03 identity=True defaults=True align=0.95575
  BASELINE RGB=60.0730 Y=56.5712 dE=28.6684 hue=17.3868 sat=0.289658 hi=89.35841846278156
  REC_ID RGB=65.8691 Y=63.6079 dE=30.5725 hue=17.5272 sat=0.284027 hi=106.4559328571709
  FW_ID RGB=65.9154 Y=63.6571 dE=30.5744 hue=17.5278 sat=0.284097 hi=106.66524724031662
  FW_OETF RGB=93.3774 Y=90.4137 dE=38.3865 hue=16.8526 sat=0.343290 hi=64.1767279047235
  REC_OETF RGB=93.4324 Y=90.4875 dE=38.4242 hue=16.8527 sat=0.343314 hi=63.97898770386787
sample 04 identity=True defaults=True align=0.94629
  BASELINE RGB=64.1173 Y=58.6124 dE=28.0281 hue=47.0280 sat=0.232774 hi=96.69465902154833
  REC_ID RGB=72.5549 Y=68.0214 dE=30.6564 hue=46.8644 sat=0.249603 hi=115.59723753777496
  FW_ID RGB=72.6021 Y=68.0731 dE=30.6655 hue=46.8644 sat=0.249666 hi=115.73053810832697
  FW_OETF RGB=92.4262 Y=88.3476 dE=35.4300 hue=46.7169 sat=0.235172 hi=63.669655062934766
  REC_OETF RGB=92.4624 Y=88.3898 dE=35.4473 hue=46.7157 sat=0.235165 hi=63.54965431521137
sample 05 identity=True defaults=True align=0.93278
  BASELINE RGB=75.1616 Y=75.3798 dE=40.4463 hue=22.0853 sat=0.335273 hi=109.62500501730369
  REC_ID RGB=81.4159 Y=83.7423 dE=40.8983 hue=22.4799 sat=0.321473 hi=133.55385650386694
  FW_ID RGB=81.4575 Y=83.7924 dE=40.8840 hue=22.4821 sat=0.321501 hi=133.71810758525314
  FW_OETF RGB=99.7570 Y=98.7225 dE=48.8444 hue=22.0420 sat=0.386586 hi=92.09061077400168
  REC_OETF RGB=99.8463 Y=98.8294 dE=48.9015 hue=22.0412 sat=0.386596 hi=91.96702399180984
sample 06 identity=True defaults=True align=0.92768
  BASELINE RGB=65.8752 Y=66.0425 dE=34.5771 hue=15.9731 sat=0.290720 hi=94.59373038721488
  REC_ID RGB=70.0807 Y=71.9152 dE=35.9420 hue=16.1441 sat=0.265167 hi=110.85137757333116
  FW_ID RGB=70.0883 Y=71.9200 dE=35.9117 hue=16.1450 sat=0.265207 hi=111.06990901168884
  FW_OETF RGB=93.3107 Y=93.0447 dE=42.9297 hue=15.7558 sat=0.339036 hi=67.27074974963116
  REC_OETF RGB=93.4281 Y=93.1815 dE=42.9833 hue=15.7553 sat=0.339131 hi=67.07636498370853

=== Aggregate ranking ===
BASELINE composite=1.000000 medians={'encoded_rgb_rmse': 62.09512772311574, 'encoded_rgb_mae': 50.58638811184974, 'luma_rmse': 57.591836242152056, 'luma_mae': 46.784407122332205, 'delta_e76_mean': 28.34827781943396, 'hue_error_deg_mean': 16.679987707194094, 'saturation_error_abs_mean': 0.2612156419457229} winsVsBaseline={}
  bins={'shadow': {'rgb_rmse': 81.99630279065353, 'luma_rmse': 85.58367598519402}, 'midtone': {'rgb_rmse': 49.95376642509764, 'luma_rmse': 42.869685540668286}, 'highlight': {'rgb_rmse': 91.97607442499822, 'luma_rmse': 82.93222204778519}, 'neutral_pixels': {'rgb_rmse': 77.4012841027801, 'luma_rmse': 77.40417374039717}, 'colourful_pixels': {'rgb_rmse': 56.05510311305742, 'luma_rmse': 49.513721578314765}} falseHighlightClips=66696
REC_ID composite=1.105802 medians={'encoded_rgb_rmse': 67.97489269536436, 'encoded_rgb_mae': 53.77029572701845, 'luma_rmse': 65.81461459193333, 'luma_mae': 53.17667335918484, 'delta_e76_mean': 30.614430066859853, 'hue_error_deg_mean': 16.835665766898714, 'saturation_error_abs_mean': 0.25738522032757005} winsVsBaseline={'encoded_rgb_rmse': 2, 'luma_rmse': 2, 'delta_e76_mean': 2}
  bins={'shadow': {'rgb_rmse': 72.87535374093139, 'luma_rmse': 76.38579185470019}, 'midtone': {'rgb_rmse': 61.88156239963345, 'luma_rmse': 57.1833441780488}, 'highlight': {'rgb_rmse': 108.65365521525104, 'luma_rmse': 101.68279577519672}, 'neutral_pixels': {'rgb_rmse': 76.49577600205448, 'luma_rmse': 75.43413668918976}, 'colourful_pixels': {'rgb_rmse': 63.606158670921715, 'luma_rmse': 59.21249244042589}} falseHighlightClips=172066
FW_ID composite=1.106304 medians={'encoded_rgb_rmse': 68.00185639909546, 'encoded_rgb_mae': 53.78175016317492, 'luma_rmse': 65.8651400172707, 'luma_mae': 53.22635509678847, 'delta_e76_mean': 30.619918091401928, 'hue_error_deg_mean': 16.83638823923131, 'saturation_error_abs_mean': 0.2574365522776886} winsVsBaseline={'encoded_rgb_rmse': 2, 'luma_rmse': 2, 'delta_e76_mean': 2}
  bins={'shadow': {'rgb_rmse': 72.771595141472, 'luma_rmse': 76.25220976485511}, 'midtone': {'rgb_rmse': 61.96095881216179, 'luma_rmse': 57.27749874494886}, 'highlight': {'rgb_rmse': 108.86757812600273, 'luma_rmse': 101.97055265675952}, 'neutral_pixels': {'rgb_rmse': 76.48459742302313, 'luma_rmse': 75.40540425510974}, 'colourful_pixels': {'rgb_rmse': 63.654229858008335, 'luma_rmse': 59.26972881907037}} falseHighlightClips=172269
FW_OETF composite=1.449836 medians={'encoded_rgb_rmse': 92.8684415795568, 'encoded_rgb_mae': 78.0928808010715, 'luma_rmse': 89.38063032518852, 'luma_mae': 75.53714771296656, 'delta_e76_mean': 36.90827860080243, 'hue_error_deg_mean': 16.304210437953458, 'saturation_error_abs_mean': 0.28710387179435737} winsVsBaseline={'encoded_rgb_rmse': 0, 'luma_rmse': 0, 'delta_e76_mean': 0}
  bins={'shadow': {'rgb_rmse': 118.3526163886075, 'luma_rmse': 124.5828933571147}, 'midtone': {'rgb_rmse': 77.77627402841324, 'luma_rmse': 71.94133423970631}, 'highlight': {'rgb_rmse': 63.923191483829136, 'luma_rmse': 51.045117799181554}, 'neutral_pixels': {'rgb_rmse': 97.7857385922475, 'luma_rmse': 99.90438174516729}, 'colourful_pixels': {'rgb_rmse': 88.0058819983997, 'luma_rmse': 82.02770512090618}} falseHighlightClips=175410
REC_OETF composite=1.450908 medians={'encoded_rgb_rmse': 92.9452435730152, 'encoded_rgb_mae': 78.1767702908354, 'luma_rmse': 89.43868483497583, 'luma_mae': 75.6110994848736, 'delta_e76_mean': 36.93575303021319, 'hue_error_deg_mean': 16.304012573554978, 'saturation_error_abs_mean': 0.287148245564243} winsVsBaseline={'encoded_rgb_rmse': 0, 'luma_rmse': 0, 'delta_e76_mean': 0}
  bins={'shadow': {'rgb_rmse': 118.52479346851769, 'luma_rmse': 124.78240725739886}, 'midtone': {'rgb_rmse': 77.82136027215091, 'luma_rmse': 72.01305179409975}, 'highlight': {'rgb_rmse': 63.76432100953962, 'luma_rmse': 50.789230090276035}, 'neutral_pixels': {'rgb_rmse': 97.8548889716115, 'luma_rmse': 99.99842385457565}, 'colourful_pixels': {'rgb_rmse': 88.07387358874615, 'luma_rmse': 82.10303961342689}} falseHighlightClips=175196

=== Promotion gate versus BASELINE ===
REC_ID: {'coreRatios': {'encoded_rgb_rmse': 1.0946896348851507, 'luma_rmse': 1.1427768046013949, 'delta_e76_mean': 1.0799396796468654}, 'broadCoreWins': False, 'coreMedianImproves2pct': False, 'hueGuard': True, 'saturationGuard': True, 'highlightGuard': False, 'clipGuard': False, 'passed': False}
REC_OETF: {'coreRatios': {'encoded_rgb_rmse': 1.496820233424129, 'luma_rmse': 1.552975051167317, 'delta_e76_mean': 1.3029275804857587}, 'broadCoreWins': False, 'coreMedianImproves2pct': False, 'hueGuard': True, 'saturationGuard': False, 'highlightGuard': True, 'clipGuard': False, 'passed': False}
FW_ID: {'coreRatios': {'encoded_rgb_rmse': 1.0951238670821006, 'luma_rmse': 1.1436541064662795, 'delta_e76_mean': 1.0801332725196682}, 'broadCoreWins': False, 'coreMedianImproves2pct': False, 'hueGuard': True, 'saturationGuard': True, 'highlightGuard': False, 'clipGuard': False, 'passed': False}
FW_OETF: {'coreRatios': {'encoded_rgb_rmse': 1.4955833893064896, 'luma_rmse': 1.5519670175018645, 'delta_e76_mean': 1.3019584059353413}, 'broadCoreWins': False, 'coreMedianImproves2pct': False, 'hueGuard': True, 'saturationGuard': False, 'highlightGuard': True, 'clipGuard': False, 'passed': False}

VERDICT RGB1E_COMPONENT_DG_TOPOLOGY_NOT_PROMOTED

Interpretation boundary: photographic evidence can discriminate this reconstructed topology but cannot prove that linear sRGB is the firmware component basis or establish literal hardware routing.
Workflow run id: 34200801733
Analysis input commit: 8730e63f3c9d19ba89d0f6153dcd01b315287667
