# M10-R CAPTURE1 baseline

## Purpose

CAPTURE1 is the first real camera fork. It deliberately separates capture bring-up from exact CA9/B2Y parity work.

## Frozen provenance

- PhotonCamera upstream: `eszdman/PhotonCamera`
- PhotonCamera commit: `f0e6425d2509fb8ab834d5d3af593183038b778c`
- Reason: this is the exact Photon baseline pinned by the current M9 multilens/source-calibration build chain.
- M10-R renderer branch used as the starting repository state: `m10r-render-parity1a`
- Promoted M10-R render policy remains candidate C: RAW headroom OFF / CA9 neutral-domain clipping ON.

## CAPTURE1 milestone A

Normal PHOTO mode must:

1. use Photon preview/camera selection;
2. request exactly one physical RAW exposure;
3. save one untouched DNG;
4. return before HdrxProcessor/PostPipeline;
5. use a separate M10-R application id so it can coexist with Photon/M9 builds.

Milestone A does **not** yet claim an M10-R-rendered JPEG. Its purpose is to prove the reused Photon capture foundation on-device without touching the validated M10-R renderer.

## Rear physical cameras already observed on Xiaomi 15 Ultra

| camera id | physical focal length | aperture | RAW geometry | CFA |
|---|---:|---:|---|---|
| 2 | 8.72 mm | f/1.63 | 4096x3072 | RGGB |
| 3 | 2.13 mm | f/2.2 | 4096x3072 | GRBG |
| 4 | 11.5 mm | f/1.8 | 4096x3072 | RGGB |
| 5 | 25.1 mm | f/2.6 | 4080x3072 | RGGB |

The renderer integration must therefore never hard-code RGGB or one sensor geometry.

## Next seam after Milestone A

Introduce a source-sensor adapter between Photon RAW and the M10-R renderer. The adapter owns Xiaomi camera-specific CFA, black/white level, lens shading and source colour characterization. The M10-R render engine must remain camera-agnostic and receive a common scene-referred representation.

No HDR, burst merge or Photon tone/post pipeline is to be introduced into the M10-R photographic path.
