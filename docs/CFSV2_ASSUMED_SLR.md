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

BRO, CRP, EWX and HGX remain unavailable and hatched. Existing measured Texas
ratios are unchanged. Each CWA uses one ratio, matching the existing renderer's
method; this does not reconstruct the spatial contours in the reference image.

The original measured NPZ/JSON files remain intact. The separate assumption JSON
contains exact native/display grid spans generated from the verified April 16,
2026 NWS boundaries. Runtime checks prevent fills from overwriting measured
values. Hatching is removed only for filled CWAs. Native LWE caches remain valid:
the conversion is applied after reading cached water-equivalent grids.

Rebuild: `python scripts/build_cfsv2_slr_assumptions.py /path/to/w_16ap26.zip`.
This offline builder requires shapely/pyshp; production still requires only
NumPy for the lookup. The map caption identifies CIPS / assumed ratios, and
manifest metadata lists every assumed CWA and its value.
