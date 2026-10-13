### Next
- No docs beyond `cramera/README.md`'s new section; a dual-audience guide was not asked
  for.
- `_hand_placed()` classifies a non-type as `VALUE` with `type(value).__name__` as the
  detail -- fine for `objects`/`sum`, unhelpful for anything richer.
- The 682 KB payload could be trimmed (drop `detail` for classes, or serve names only and
  fetch details per row) if it ever feels slow.
