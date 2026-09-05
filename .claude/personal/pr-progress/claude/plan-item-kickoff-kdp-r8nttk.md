# competing-explanations (#270)

Plan item `competing-explanations` of `knowledge-directed-perception` (tracking issue
#201). Branch `claude/plan-item-kickoff-kdp-r8nttk`, stacked on #236 (`ee4b242da`), which
carries #232. Kicked off 2026-09-05 in `auto` mode. Full reasoning is in the plan's
`roadmap.md` section of the same name.

## The plan

Replace `PieceMatcher.minimum_agreement` (one number, 0.62) with a comparison of accounts
of the same edges. Three parts:

1. **The board's own account** -- #236 settles the board's layout over the picture, so the
   edges the board itself produces are predictable (its six hole boundaries at the fitted
   placement, and the lid outline).
2. **A two-sided score** -- how much of an account's outline the picture bears out *and*
   how much of the edge it stands over it actually accounts for. One-sided agreement
   cannot tell a triangle laid across a round rim from a circle sitting in it.
3. **A lead, not a level** -- a report is made where *board + this piece here* leads the
   alternatives (board alone; another piece claiming the place) by a stated margin, which
   is a statement about the cost of a wrong report. The lead required rises with the number
   of candidates the fit was the best of, which is the plan's central claim as a number.

`Occupancy.keep_one_detection_per_place` reads that comparison rather than raw agreement,
so the threshold and the place rule share one resolution instead of filtering in sequence.

## Files

- `perception/explanations.py` (new) -- the account, its two-sided score, the comparison.
- `perception/piece_matcher.py` -- `minimum_agreement` goes; fits and scores without
  refusing.
- `perception/occupancy.py` -- a place goes to the leading account.
- `perception/pipeline.py` -- build the board's account once per frame, resolve once.
- Tests: `test_montessori_explanations.py` (new), plus
  `test_montessori_piece_matching.py`, `test_montessori_perception.py` and
  `test_montessori_detection_on_captures.py`.

## Done

- Setup check fixed (dashboard dependencies installed; branch re-cut off `main`, then onto
  #236).
- Context gathered: plan manifest, roadmap (read in full through the sections naming this
  item and its two parents), both parents' pull request descriptions and the code at
  #236's tip. Dependency readiness: both `open_ready`.
- Duplicate/purpose check run against the repository's open pull requests -- nothing else
  is building this. (Run because of the #268/#251 correction of 2026-09-05.)
- Branch cut, draft #270 opened, manifest and roadmap section saved.

## Next

1. Environment: `pip install -U uv`, then `/usr/local/bin/uv sync --extra dev --python 3.12`.
2. Measure first, before designing the score: on `tracy_pickup_demo`, what the prism at
   0.682 and the cylinder at 0.673 each leave unexplained, and what the board's own account
   covers of both. The design above predicts the two-sided score separates them; if it does
   not, that is the finding and the lead rule has to carry it alone.
3. Tests for the scoring and the comparison, then the implementation, then the captures.
4. Report the false-report count across all six captures and the cost as a same-run ratio.

## Open

- Whether the two-sided score alone takes the `tracy_pickup_demo` mark off, or whether the
  stated lead does. Measurement decides; recorded either way.
