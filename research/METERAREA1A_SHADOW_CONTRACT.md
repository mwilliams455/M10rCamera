# METERAREA1A shadow diagnostic contract

Baseline: RENDER2L SOURCEPROXY1C, commit 50705cde49e1f0318dce716970f5929ebbe9df1a.

No promotion of new metering input. Existing sparse preview grid still controls MFM.
The existing source coefficients, source identity, MFM thresholds, exposure allocator,
RAW/JPEG rendering statements, DNG saver and native colour/tone assets remain unchanged.
New diagnostic statements are insertion-only; removing their delimited blocks must restore
all three modified baseline Java files exactly.

A second FBO uses the same bound preview shader and texture, peaking/mirror off, on the
same GL draw iteration, with an 8x8 stratified sample lattice per logical 22x16 cell.
The 128x176 transposed FBO contributes 22528 sample positions, not a full-resolution box
filter. Inverse sRGB is applied per RGB sample before reduction. This only removes the
assumed display transfer; it does NOT undo arbitrary ISP tone processing.

Record point, area-linear, area-proxy-after-average and area-proxy-before-average decisions.
The two proxy orders are different experiments and are not silently interchanged.
Four interleaved 4x4 sublattices expose residual sampling sensitivity. None changes exposure.

Retain texture timestamps, exact-matched parent-result timestamps where available,
selected physical/logical IDs, physical-result authority, static source signature,
preview/still crop, focus, optical state, shading/tonemap/distortion modes and the producer
texture transform. The producer transform is RECORDED, not newly applied: sampling coverage
must remain the same as the existing sparse meter for this first isolation. Crop parity,
absolute photometric parity and hardware timing equivalence are not claimed from the flags.
No nearest-result match is called exact. Missing pairs and binding mismatches are explicit.

New RAW diagnostic grids resolve both green CFA sites for RGGB, GRBG, GBRG and BGGR, and
record pre-shading, post-existing-renderer-shading and mean green gain in the same cells.
The old RAW diagnostic's fixed site-1/site-2 sampling is retained for baseline continuity but
flagged incompatible on GRBG/GBRG. Neither the old nor the new RAW decision is Leica ground truth.
Map-coordinate correctness on all devices remains unproven. No new image ownership or RAW copy.

Use a static scene containing fine blinds, a smooth neutral scene and an ordinary backlit
scene on multiple physical cameras. Keep JPEG, DNG and the existing CAPTURE1B JSON.
Inspect m10rMeterArea1A and m10rMeterAreaRaw1A. Do not calibrate from unavailable/stale/mismatched
pairs or from different cropping. The extra GL readback and CPU work may affect preview latency;
its measured duration is recorded, and phone validation is mandatory before promotion.

Only code and synthetic tests are committed with this experiment; no user capture fixtures.
