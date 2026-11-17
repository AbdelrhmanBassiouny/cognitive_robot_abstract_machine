## Plan
- Get upstream PR cram2#1003 (changes requested by tomsch420) and the fork's CI green.

## Done
- Fork CI cause found: opencv-python 5.1.0.95 has no Linux wheel (Install dependencies failed in all 10 test jobs); merged `main`, which pins it below 5.1.
- Upstream thread `has_generic.py:30` (no abbreviations): `tp` -> `generic_argument`, `x` -> `base` (18e0b18e5).
- Upstream thread `sparse_array_json_serializer.py` ("are these needed?"): yes, SparseProbabilityTable serializes a csr_array; reply drafted in the PR description, not posted upstream.
- Local: 132 krrood tests and 37 probability_table tests pass; `krrood check` clean.

## Next
- Re-read fork checks at 18e0b18e5 (not read yet) and the upstream checks once it picks up the push.
- Someone with upstream access replies to and resolves the two threads; tomsch420 re-reviews.
- Decide with code owners whether to keep the old HasGeneric / NoGenericError import paths as re-exports.
- Not checked: plan.yaml record (item brief unreadable, upstream repo not attachable here).
