## #265: both outstanding items closed, and #292 folded in

**State.** `0e0bacfad` on `claude/icra-experiments-simulation-pipeline-w4ep7n`, a draft,
description rewritten to match. #292 is closed as merged. Three commits this round:
`93cdd21c9` merges main, `7a6f8f7a9` migrates one stale `Match.variable` read,
`0e0bacfad` merges #292.

**1. The merge conflict against main is resolved**, in the four files predicted, all
four keeping both sides:

- `world.py` - `memoize`'s new home `krrood.patterns.caching` beside this branch's
  `BeliefSource` import. This is the silent breakage the roadmap warned of: left as git
  merged it, the module imports a name its source no longer defines.
- `mapped_variable.py` - `CallVariable._update_type_` reads a method off its owner class
  when the child resolves to no type, and keeps this branch's `__call__`-class reading
  otherwise. main's own `test_method_call_chains.py` passes (8/8).
- `geometry.py` - main's `to_hex`/`from_hex`/`__hash__` beside this branch's `ColorName`;
  main's `RED`/`PINK` classmethods dropped, since this branch's answer with those colours.
- `test_color.py` - two files of one name, kept as one file of two sections (30 passed).

**2. The experiments job's blocker is in.** #292 merged whole, so the `RecordedLook`
rename, the 12 mm hole-placement fix and the requoted narrowing millimetres are all here.

**3. One collision main brought, which nobody predicted.** `test_relational_circuit_registry_causal.py`
reads `query.variable`, retired by #192. Since #192 that builds an attribute expression
rather than raising, so what fails is `random_events` asking `issubclass` of `None`, in
another package. Standing hazard: every future merge of main can carry another, and none
will fail where it is written - re-run the convergence's `_is_own_name_` guard trick each
time.

**Correction to the last round.** `dae41889c` said left and right separate the cube from
the cylinder from no hole on this board. That was measured off hole bodies standing 12 mm
from the holes the look found; placed correctly, the square hole does lie between them.
All four direction choices still hold and none was reverted - #292 requoted the
millimetres and replaced the reason.

**Measured in the container** (`--orm-build=never`, with `pyjpt`/`matplotlib`/`flask`/`mypy`
installed): krrood 3014 passed / 2 failed (graphviz `dot`); sdt the same 45 failures as
pre-merge, its 45 added errors also on plain main (`iai_apartment`); experiments 684
passed / 18 failed, all ROS or database, identical pre-merge. CI on `93cdd21c9` was 13/15
green with exactly krrood and experiments red - the two these commits fix.

**Environment note, now stronger.** `pytest` is not blocked in a session container at all:
`--orm-build=never` skips the conftest's ORM generation. What still needs CI is the
generation itself and anything importing ROS (`coraplex`, `giskardpy`, `segmind` suites).
