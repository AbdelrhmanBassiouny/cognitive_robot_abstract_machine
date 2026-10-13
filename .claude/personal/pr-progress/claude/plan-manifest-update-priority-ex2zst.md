### Outstanding
- CI on `3b355bb89` had not reported when this session ended.
- `update` now writes statuses with spaces (#185's `ItemStatus`); live manifests still
  use underscores and #185 reads both, but the dashboard tooling on `main` only knows
  the underscore form until #185 lands.

---


### Outstanding
- CI run 33340371549 was still in progress when this session ended. The previous head
  (`fb1a5a4a`) was green and this diff is `.claude/`-only.
- #160 is left open and untouched; it is superseded by this merge and is the user's to
  close.
- The three review threads #151 already had open are unchanged — none of them touch this
  work.

### Plan
1. Record the real blockers in the manifest and republish the dashboard (done).
2. Merge #185's head across the `bastler` → `basstler` rename: apply the substitution,
   record `213ad791c` as merged (`-s ours`), then merge the head (done: `2628b9959`,
   `4e83230aa`, `be1bd2f62`).
3. Reproduce the `integration-conflict` against `D-deco` (#77) and clear it if it no
   longer reproduces (done: it doesn't, so the label was removed).
4. Fix the `--append-notes` literal-note defect this round hit, failing test first (done:
   `e17bf4d5d`), and restore the manifest the defect damaged (done).
5. Update the PR description, roadmap, notes and dashboard (done).
