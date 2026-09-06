# Owner-assumed fills for missing snowfall ratios

These values fill previously unsupported CWAs only. They are assumptions
requested by the owner on 6 September 2026, not measured CIPS means or a CFS
bias correction. All 97 measured CIPS CWA values are preserved exactly.

| CWAs | Assumed ratio | Basis |
|---|---:|---|
| PSR | 10:1 | Use adjacent TWC's recorded mean; owner identified a similar pattern |
| BMX, CAE, CHS, ILM, JAN | 8:1 | Owner's Southeast approximation |
| LCH, LIX, MOB | 7:1 | Owner's Gulf Coast approximation |
| TAE, JAX, KEY, MFL, MLB, TBW | 7:1 | Owner's Florida approximation |
| BRO, CRP, HGX | 7:1 | Owner's coastal Texas approximation |
| EWX | 8:1 | Owner's inland Texas approximation |

All 116 CWAs now have measured or assumed ratios; no hatching is drawn.
Existing measured Texas ratios are unchanged. Each CWA uses one ratio, matching the existing renderer's
method; this does not reconstruct the spatial contours in the reference image.

The original measured NPZ/JSON files remain intact. The separate assumption JSON
contains exact native/display grid spans generated from the verified April 16,
2026 NWS boundaries. Runtime checks prevent fills from overwriting measured
values. No unsupported CWAs remain. Native LWE caches remain valid:
the conversion is applied after reading cached water-equivalent grids.

Rebuild: `python scripts/build_cfsv2_slr_assumptions.py /path/to/w_16ap26.zip`.
This offline builder requires shapely/pyshp; production still requires only
NumPy for the lookup. The map caption identifies CIPS / assumed ratios, and
manifest metadata lists every assumed CWA and its value.

## White areas on accumulation images

A white bin covers 0 to less than 0.1 inch. Higher amounts retain their prior
colors, including the remaining portion of the original lowest band. Native
snowfall and numeric downloads are unchanged by this color choice.

The same value-based color rule applies across CONUS, including Florida and the
far South. There is no state-specific white mask. Positive modeled snowfall is
colored when it reaches 0.1 inch; values below that threshold are white.
