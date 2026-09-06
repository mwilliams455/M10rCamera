# M10-R CAPTURE1B

Goal: first PhotonCamera-based APK that captures one physical Xiaomi 15 Ultra RAW frame and renders a JPEG through the promoted M10-R C highlight policy.

Frozen capture baseline
- PhotonCamera upstream: f0e6425d2509fb8ab834d5d3af593183038b778c
- Normal PHOTO mode: one RAW_SENSOR frame only.
- No HDR, no stacking, no HdrxProcessor/PostPipeline.
- Untouched DNG is published for every PHOTO capture.

Source colour direction
- No Cobalt profile/runtime dependency.
- Use Camera2 dual-illuminant CalibrationTransform1/2, ColorMatrix1/2, ForwardMatrix1/2 and live SENSOR_NEUTRAL_COLOR_POINT.
- ColorMatrix remains in DNG XYZ->reference-camera convention; do not ForwardMatrix-row-normalize ColorMatrix.
- ForwardMatrix normalization follows Photon Converter semantics already exercised by M9 SOURCECAL2A.
- Resulting source scene boundary is XYZ_D50.

M10-R target bridge
- Target ColorMatrix A/D65 fixtures are the validated M10-R matrices already used by RENDER_PARITY1A.
- Interpolate target matrix in reciprocal-temperature space using the source scene white.
- Map XYZ_D50 back to scene-white XYZ, then into synthetic M10-R camera RGB.
- Derive synthetic M10-R AsShotNeutral from the same target matrix and scene white.
- Apply promoted C: RAW headroom OFF / CA9 neutral-domain clipping ON.
- Transform guarded target-camera RGB through the existing M10-R ColorSpec-equivalent camera->sRGB linear path and sRGB encode.

Multilens requirements
- CFA 0 RGGB, 1 GRBG, 2 GBRG and 3 BGGR are all accepted.
- Camera2 LensShadingMap channel order R, Geven, Godd, B is mapped to CFA positions explicitly rather than assuming RGGB.
- Black level remains row-major Bayer-position data.

Parity boundary
This is an integration candidate, not a claim of exact M10-R firmware arithmetic, exact Leica tone, or final production sensor calibration. CA9 exact integer work remains separate. The objective is to prove the complete single-frame Xiaomi RAW -> native scene -> M10-R C -> JPEG path on device without Cobalt.