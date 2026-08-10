# manifest-currency-first (workflow-unification)

Branch `claude/plan-manifest-update-priority-ex2zst` off fork `main`, draft PR
**#151**, item `in_progress`. Implemented; awaiting your review.

## What shipped

Three operations on `.claude/hooks/plan_item_bootstrap.py` — block-styled field
writing, `update` (any field, no roadmap section), `check` (recorded fields vs
local git, exits `manifest_is_stale`) — plus
`.claude/skills/plan-dashboard/manifest-currency.md` and its constant, cited by
each bound skill.

389 tests across the three CI directories, against 367 on `main`. Every new test
mutation-checked.

## Two premises corrected during the work

- **`sync_manifest_status.py` cannot be the reuse seam** the item's notes named:
  it reaches `build_dashboard` → jinja2/markdown/nh3, so a hook cannot import it,
  and it answers a post-hoc GitHub-side question. The split is by what each can
  see — dashboard vs GitHub after the fact, `check` vs local git before a push.
- **Writing `notes` silently concatenated** onto the old note and still validated.
  Latent since #143 gave `NOTES`/`BLOCKERS` members and no writer.

## Where the real gap was

`plan-item-resolve` wrote the manifest nowhere at all — the skill that exists to
diagnose a stalled item was the one guaranteed not to record the diagnosis. It now
records what it found before proposing anything.

## Verified live

`check` across all 41 items of this plan: one true positive
(`dependency-chips-blocked-fix`, published branch with no `session`, exit 9), 40
clean. `update` wrote this item's own notes.

## Open for you

- **CI is red base-side**, not this branch's: `greenlet` 3.5.5 has no Linux wheel,
  so `uv` fails to resolve before any test runs; `main`'s own run failed 11 jobs
  three minutes earlier. Blocks every PR in the repo. Reported on #151, offered as
  its own bug-labelled item — your call whether to take it.
- **No rename of `plan_item_bootstrap.py`**, per your earlier call; the package
  migration renames it once.
- **The `add-plan-item/SKILL.md` reference line** lands here only if #135 merges
  first.

## Incidental

Scratch fixture disables commit signing — the suite was failing on a different
test each run against this environment's signing service, and it halved runtime.
