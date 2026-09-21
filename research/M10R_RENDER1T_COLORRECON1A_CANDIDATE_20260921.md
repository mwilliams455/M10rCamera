# RENDER1T COLORRECON1A isolated test candidate

The phone replay showed that clipping an already reconstructed red channel to the gamut boundary flattened bright warm colour. The ordinary-colour deficit also remained. COLORRECON1A changes the colour reconstruction while retaining the original source processing, capture exposure, WB, CA9, MEDIUM/DG assets and TONECAL1A coefficients. No resolution, JPEG quality, demosaic, sharpening, spatial denoise, HDR or stacking change is bundled. Q and capture branches remain frozen.

This is empirical renderer engineering, **not recovered Leica Y BLEND arithmetic**. CC1 is applied to pre-tone working RGB to construct an explicit linear RGB colour direction. The existing S floating output supplies a lightness anchor: apply the existing S gamut operation to the legacy reconstruction, decode that code RGB with the sRGB EOTF, then take weighted linear Y. Scale the new linear colour direction to that Y. The legacy k=0.35 participates only in this lightness anchor; it no longer directly sets the photographic chroma direction.

A saturation-dependent shoulder then limits the encoded peak. Let p be the positive linear RGB peak, s=clamp((p-minRGB)/p,0,1), width=0.30*s, knee=1-width, and m the requested encoded peak. Below the knee, leave it unchanged. Above it, use knee + width*(m-knee)/(m-knee+width). Convert that peak back to linear light and limit the common RGB gain. This avoids a fixed red-channel plateau and preserves linear RGB ratios before the final gamut operation. The coefficient 0.30 is an engineering choice, not a firmware value. Exact equal-channel working inputs bypass the new reconstruction and retain S's neutral output. Negative/out-of-range output still uses GAMUT1A; first 8-bit quantization and TONECAL1A remain in their established positions. There is no claim of perceptual hue preservation.

An earlier prototype used the unchanged MEDIUM/DG curve at the linear RGB peak as its limit. It was rejected: on the seven historical holdouts its target-native L* MAE rose 0.354878 to 0.649074, exceeding the fixed +0.15 gate, despite improved colour. The gate was not relaxed. The replacement shoulder was checked on the development references 01/03/05 and private tungsten replay before reusing the regression set. The seven historical holdouts are therefore **reused regression inputs**, not fresh independent blind validation for the final design. No new independent public scenes were introduced.

Local native validation: all ten original reference pairs under both established input conditions. Original R alignment fixes the geometry for S and T; reference-only flat patch selection is unchanged. The S baseline reproduces the existing S aggregate metrics. Development IDs remain 01/03/05. Gates: mean L* MAE increase <=0.15, neutral L* MAE increase <=0.15, worst-scene DE76 increase <=0.5, and at least 20% mean reduction in ab error and DE76, separately for each input condition and for historical holdouts/all reused scenes.

| All ten, equal capture weight | S | T |
|---|---:|---:|
| Target-native L* MAE | 0.409880214 | 0.382313088 |
| Target-native ab error | 6.059949602 | 2.364417274 |
| Target-native DE76 | 6.102140989 | 2.422881299 |
| White-normalized L* MAE | 1.268649641 | 1.206672388 |
| White-normalized ab error | 5.681112539 | 2.055241203 |
| White-normalized DE76 | 5.981347675 | 2.495683257 |

Every scene's DE76 improved in both conditions. This is a specific flat-patch regression protocol, not a percentage of total Leica fidelity. References remain one publisher/camera/lens family, mostly daylight, with the existing firmware mismatch. The Leica adapter is not the phone frontend. Private phone replay evidence is retained separately and is not uploaded to this repository or CI.

Native checks include 600,000 random input pixels, an independent vector-form oracle, 40,000-pixel chunk equivalence, original first-eight counter equality, bounded output and a full 65,536-input neutral ramp. Source patches reject unknown S C++ and Java hashes. New diagnostics distinguish legacy S counterfactual distributions from actual new output, retain exact gamut counts on the new encoded RGB, and add full-resolution colour-reconstruction counts. CI build requires successful validation and matching generated C++/Java/header provenance.

Android saving, actual device latency, repeat-capture stability, smooth gradients and photographic acceptance remain phone-test requirements. No production promotion. A colour fix cannot restore detail lost to focus, motion or earlier clipping; spatial filtering and capture policy require separate attribution.

## Build outcome

Run [35570277374](https://github.com/mwilliams455/M10rCamera/actions/runs/35570277374) completed validation and APK build successfully at `e87efd7842d13b74b0b5f482abb99b453a0db17b`. All 120 local/CI scene metrics matched exactly. The evidence artifact 10625558092 contains all 46 hash-verified manifest entries. Test APK artifact 10625891564 contains `M10RCam_RENDER1T_COLORRECON1A_TONECAL1A.apk`, 113,337,636 bytes, SHA256 `56b6aa24eb10bda88378b11d3122b73f86881cd17c7fc86342de89e5693cb62f`. ZIP/APK integrity was verified locally; CI retained successful v2 signature verification. Three private full-resolution source-faithful phone replays completed locally, with source/count checks and no private image upload to this repository or CI. Device installation and acceptance remain pending. The result-index/report persistence commits are later than the exact APK-built commit; they are not new APK builds.

The initial CI fixture attempt 35570072011 failed because a workflow command supplied the S patch path as an argument to the R patch. The fixture invocation was corrected and the exact fixture was executed locally; renderer guards and photographic gates were unchanged. A later diagnostic-only correction counts the actual shoulder condition rather than floating-point EOTF/OETF roundoff. Both are included in the successful exact build above.
