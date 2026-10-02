# Splitting #202 into reviewable layers

## Why

#202 (*Land the Montessori perception package on main*) has grown to 65 files and +11,220
lines, with no deletions. It is the base that every item of `knowledge-directed-grounding`
stacks on, and too large to review as one piece. On 2026-10-02 the developer asked whether
it could be split cleanly. This plan is the answer, recorded as a plan of its own at the
developer's request.

## The cut lines come from the import graph

Every module #202 adds was mapped to the other modules of #202 it imports, on
`4653fe32e`. All of those imports point one way, so each layer below imports only `main`
and the layers beneath it:

| layer | item | files | lines | imports from #202 |
|---|---|---|---|---|
| 1 | `network-limits-on-main` | 2 | 424 | nothing |
| 2 | `shape-vocabulary-on-main` | 7 | ~1,340 | nothing |
| 3 | `simulated-world-on-main` | 5 | ~1,770 | 2 |
| 4 | `frame-reading-on-main` | 8 | ~1,570 | nothing |
| 5a | `piece-recognition-on-main` | ~6 | ~1,500 | 2, 4 |
| 5b | `detection-pipeline-on-main` | ~10 | ~2,060 | 2, 3, 4, 5a |
| 6 | `captures-on-main` | 22 | ~790 | 4 |
| 7 | `perception-node-on-main` (#202) | 7 | ~1,770 | everything |

Each item's `notes` list its exact files.

## Where the split is not perfectly clean

- **`pipeline.py` reads `BOARD_SCALE` from `world.py`.** That one constant puts all 1,169
  lines of the simulated world ahead of any detection code.
  `detect-per-supporting-surface` removes that use later. Until then the order has to
  accept it.
- **The ROS runtime has no tests that can run here.** All of layer 7 imports `rclpy`.
  556 of its lines are `equipment.py`, brought in for `table_top_z` alone, which
  `surfaces-from-world` removes.
- **The detection layer is cut where the tests allow.** `test_montessori_piece_matching.py`
  imports `pipeline.py` at the top and uses the shared scene fixtures. Layer 5a therefore
  gets its tests as a module split verbatim out of that file, and the colour tests that
  need only `pieces.py` move down to layer 2. If the piece-matcher tests turn out not to
  stand without the pipeline, 5a folds into 5b. No layer lands code that nothing tests.

## Decisions (developer, 2026-10-02)

- `network_limits` is its own pull request off `main`, not the bottom of the stack.
- The ~3,560-line detection layer is cut in two (5a/5b).
- #202 is kept and becomes the top layer. It is not closed and replaced.

Also decided while drafting, with the reason given so it can be revisited:
- Layers 4 and 6 need only `main` and layer 4 respectively, but are still stacked in a
  line. That gives every branch a single parent, so no base is a merge of two branches.

## How the stack is built, and why it breaks nothing above #202

1. Each layer is a new branch with new commits. Its files are checked out verbatim from
   #202's tip at a recorded SHA (`git checkout <sha> -- <paths>`), so its contents are
   exactly #202's. A layer must not edit any code. The only permitted change is moving a
   test section verbatim into its own module.
2. Once the stack is built, its top branch and `network-limits-on-main`'s branch are
   *merged* into `montessori_perception_on_main`. The contents are identical, so the
   merge changes no file. Verify that with an empty `git diff` across the merge.
3. #202's base is then retargeted to `captures-on-main`'s branch, and its description is
   rewritten to cover the ROS runtime alone.

Nothing on #202 is rebased, amended or force-pushed. So #205, #221, #223, #225, #232,
#236, #270, the ICRA integration branch #265 and #299 all still contain #202's commits and
need nothing. #202's two review rounds stay on #202. Their threads concern files that now
show up in the lower pull requests, but all of them are resolved.

**If #202 moves before the stack is finished**, for example when a downstream fix lands on
it, the layers re-sync to the new tip. That is why each layer records the SHA it was cut
from.

## Authorship

Four of #202's commits are sorinar329's (`714efc6a4` the node, `b5d0745ee` the world,
`256fe58bc` the board mesh, `ac2fb7e1b` the synthetic robot). A layer that carries files
those commits first added gets a `Co-authored-by: sorinar329 <...>` trailer, using the
address on the original commit. Rebuilding the layers as new commits would otherwise drop
that credit. This is a human co-author, which `AGENTS.md` allows.

## Verification, per layer

- The layer's own tests pass on its branch alone, using `--noconftest` and the workspace
  installed into a virtual environment (see `knowledge-directed-grounding`'s environment
  note). CI must also be green.
- Every name every file imports resolves against `main` plus the layers below.
- At the end, `git diff <captures-on-main> montessori_perception_on_main` lists exactly
  layer 7's files, plus `network_limits`' two until that pull request lands.

## Upstream

#202 carries `cram2-link-sent`. The compare link built for it covers the whole package
and no longer fits. Each layer gets its own promotion link when it is ready, and opening
it upstream stays the developer's click.

## Relationship to `knowledge-directed-grounding`

That plan's `montessori-perception-on-main` item still tracks #202's branch and remains
what its `surfaces` track stacks on. This plan changes how #202 reaches review, not what
it contains, so no `depends_on` there changes.

## `network-limits-on-main` — kickoff (2026-10-02)

Branch `claude/clever-carson-wp7c09` off `main` (`236b295a2`), draft PR #487.

- **Source:** #202's tip `4653fe32e`. Its two files are checked out verbatim with
  `git checkout 4653fe32e -- experiments/src/experiments/network_limits.py test/experiments_test/test_network_limits.py`.
  No code is edited.
- **Authorship:** both files were first added by `7d54d8002`, authored by Abdelrhman Bassiouny,
  so this layer needs no `Co-authored-by` trailer.
- **Imports:** the only import outside the standard library and `typing_extensions` is
  `krrood.exceptions.DataclassException`, which exists on `main`. Nothing else in #202 is
  imported.
- **Verification:** run `test_network_limits.py` with `--noconftest`, then check that both
  files are byte-identical to `4653fe32e`.
- **Scope check:** the two paths do not exist on `main`. They overlap #202 only, which is
  the plan's design, so there is nothing to fold.

## `shape-vocabulary-on-main` (layer 2), kicked off 2026-10-02

Branch `claude/ecstatic-knuth-curscv`, off `main` at `236b295a2`, draft #488. Cut from
#202's tip `4653fe32e`.

**What it carries, verbatim from `4653fe32e`:** `montessori/semantics.py`,
`montessori/exceptions.py`, `montessori/hole_geometry.py`, `montessori/resources/board.stl`,
`montessori/pieces.py`, `test_montessori_semantics.py`, `test_montessori_hole_geometry.py`.

**The one new file:** `test/experiments_test/test_montessori_pieces.py`. It holds the three
tests from `test_montessori_piece_matching.py`'s "reading a piece's colour" section that need
only `pieces.py`: the piece's pure-hue colour, two pieces at one hue coloured alike, and hue
measured the short way round. The other two tests in that section, and the `_painted` helper
they share, read `SurfaceColors` (`pipeline.py`), so they stay for `detection-pipeline-on-main`.
The new module is named after the module it tests, matching the `test_montessori_<module>.py`
convention #202's test split set.

**Co-author:** sorinar329 (`mrsoran2009@gmail.com`). `b5d0745ee` first added `semantics.py`,
`hole_geometry.py` and their tests, and `256fe58bc` added `board.stl`.

**Flag for `detection-pipeline-on-main` and `perception-node-on-main`:** moving tests
breaks the roadmap's claim that the final merge into `montessori_perception_on_main`
"changes no file". After this layer, the stack's `test_montessori_piece_matching.py` lacks
three tests that #202's copy still has, and the stack adds `test_montessori_pieces.py`, which
#202 lacks. `detection-pipeline-on-main` lands the trimmed `test_montessori_piece_matching.py`.
The final merge into #202 then has to take the stack's side for these test files. Only test
files are affected, so the claim still holds for every source file. The empty-diff check at
the end should exclude these files, or #202 should take the same move first. That choice
belongs to `perception-node-on-main`; this layer only records it.
