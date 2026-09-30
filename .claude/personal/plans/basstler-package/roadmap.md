# basstler-package — Roadmap

Narrative companion to `plan.yaml`. Kept short on purpose: the size budget this split was made
under counts these lines.

## Where this plan came from

Split out of `workflow-unification` on 2026-08-30, under `plan-size-limits`'
`split-workflow-unification`. That plan had reached 59 items and 16,917 lines across its manifest
and roadmap, well past the 15-item / 2,000-line budget, and became seven plans seamed on subject.

This plan is the `basstler` track, carried across unchanged. Every item keeps its branch, pull
request number, status and session verbatim. **The full predecessor roadmap remains in the
personal-notes branch's history**; what is kept here is what binds future work.

## Why this work exists

Three directories under `.claude/` - `hooks/`, `stack/` and `skills/plan-dashboard/` - are separate
`sys.path` roots, so nothing in one can import another. The consequence is not stylistic: the same
code was written out repeatedly because there was no shared home to put it in, and each duplication
was recorded on the item that found it rather than fixed.

The carriers on record when the migration was moved to the front:

- A `run_git`-style subprocess seam three times, plus `stack.py`'s deliberately-opposite `_git`.
- The frozen-dataclass command-class base twice, where making them identical would have meant
  copying a fifth file in answer to a complaint about duplication.
- `ItemStatus`, and the personal-notes precedence rules' second Python copy.
- The gh-CLI-else-token GitHub backend rule three times, which keeps its own item.

## Decisions this plan inherits

Numbering is the predecessor's, kept so cross-references in item notes still resolve.

**8. A proper package, with boundaries.** All Python under `.claude/` moves into one package with
its tests under the standard `test/` directory. What stays in `.claude/`: `SKILL.md` files,
`settings.json` and the bash entry points, since Claude Code discovers them by path - they become
thin wrappers invoking `python -m`. Zero-install must survive: the package is a plain top-level
directory importable from the repository root, with a `pyproject` for *optional* installation. It
stays visibly dev-tooling - its own directory, not published, not in the default install.

**12. The bash layer retires into the package.** About 1,300 lines across nine hook scripts and the
dashboard refresh move in. The permanent bash remainder is roughly eight three-line shims at the
existing paths, a slimmed configuration file, and the environment-configuration script unchanged,
since it is pasted by reference into cloud environment setup fields this repository cannot update.
`settings.json` stays byte-identical. The Python floor is 3.11.

**13. The package is named `basstler`, and the migration goes first.** From the first letters of the
user's surname and the German word for a tinkerer; it supersedes `development_tooling`, and keeps
that name's abbreviation-free property. Decision 8 had sequenced the migration *last*, to avoid
moving files under in-flight pull requests; it moves to the front because the duplication carriers
accumulated faster than the review queue drained. The cost was measured rather than guessed - every
open tooling pull request but one touches Python this moves - and accepted: each merges main across
the move and re-applies its delta in the package.

**14. Derive rather than declare, and depend on krrood eventually.** What the package knows about
itself is computed from the directory and the modules rather than written down. And basstler is to
depend on `krrood`, to cut duplication rather than mirror its idioms - which makes decision 12's
version-1 independence a stage rather than a permanent state.

## The dependency-tier reversal, which later items should not re-derive

Three successive shapes existed to protect callers that run before anything is installed: a declared
tier table, a set of modules that may need the requirements, and an import closure derived from the
callers themselves. All three are gone. The user's answer is that **nothing should run before an
install**: the session-start hook installs whatever declared dependency is missing on every start,
gated on the notes-branch fetch the hook already exits on, reporting a failure on its own summary
line and finishing the run regardless; Actions runners install the package themselves.

The two installers diverge on purpose, and the zero-install contract is why: a session installs the
missing *specifiers*, because installing the package would leave a second copy of these modules
beside the clone's own and the clone's copy is what a caller imports; a runner has no such contract.
Dependencies are declared statically in `pyproject`, matching what main did for every other
workspace member, and the package stays out of the workspace members list, since membership would
put it in the default sync.

## Landing hazards

- **Whichever lands second rebases.** The migration moves files nearly every open tooling pull
  request touches. A pull request already through review may instead land just before the
  migration's final merge, which folds it in on the migration side - cheaper, and the user decides
  per pull request at merge time.
- **The conversion items must follow the in-flight bash-touching pull requests**, not lead them: a
  wholesale body rewrite cannot be merged by the whichever-lands-second convention.
- **Two carriers are unreachable from the migration branch** and stay with
  `basstler-github-api-unification`, whose two remaining carriers live on other plans' branches.

## Process notes worth keeping

- **A green run after a deletion says nothing about what the deletion took with it.** Deleting a
  block by slicing from one anchor to the next also deleted a test sitting between them, and the
  suite stayed green. The check is the mutation that used to fail, or the test count. Seen twice in
  two days.
- **Grep for the claim, not for its expected callers.** Three module docstrings kept a justification
  a review round had already shown false, because nothing looked for the sentence.

## What actually stalled the extraction, found 2026-09-03

The manifest called `basstler-package` in progress and still a draft. Both were wrong, and the second
one is what hid the first: **#185 has been out of draft since 2026-08-23**, which in this workflow is
the promotion approval rather than a loose end, and it has carried `needs-resolution` since
2026-08-22, which withholds a branch from promotion. So the work was finished and approved, and held
at the last step for twelve days by a conflict nothing in the plan recorded.

The conflict is one file and one kind: `.claude/hooks/tests/test_setup_steps.py` was added on `main`
inside a directory this branch renamed, so git reports `CONFLICT (file location)` and declines to
place it. Its silent half is the one this plan's own process note already warns about twice:
`.claude/hooks/setup_steps.py` merges with **no conflict at all**, because this branch moved
`.claude/hooks/*.py` file by file rather than renaming that directory - and left where it lands it
breaks the branch's own "no `.py` remains under `.claude/`" contract. Third occurrence. The check is
still `git ls-tree -r origin/main --name-only .claude/ | grep '\.py$'` against the merged tree, and
nothing runs it automatically.

Both were resolved the same day at `674f1507f`. The named conflict took the new suite at its renamed
location; the unnamed one took `setup_steps.py` into the package, where its hand-counted `.parent`
chain became `package_layout.REPOSITORY_ROOT` and its suite lost all three shapes this package exists
to end at once - a bare module import, a bare sibling import, and a `sys.path.insert` reaching the
plan-dashboard directory for `build_dashboard.PullRequestLabel`. 664 tests pass, against 632.

`basstler-first-time-setup` landing is what produced both files: upstream #577, merged into `main` at
`017be2aa2` on 2026-09-01, while the manifest carried it as `in_progress`. This is the
whichever-lands-second convention working exactly as the landing hazards section says it does.

Two tooling defects turned up alongside, and neither belongs to this plan:

- The maintenance routine's own comment promises that "later passes skip it rather than re-reporting
  the same conflict". It re-reported 20 times between 2026-08-31 and 2026-09-03, roughly every two
  hours. The label suppresses promotion but evidently not the report.
- `plan-item-resolve/SKILL.md` instructs a session to record its findings with
  `plan_item_bootstrap update` and to follow `${MANIFEST_STALENESS_DOCUMENT}`. Neither exists - the
  script has only `record` and `open`, and no `manifest-staleness.md` is on any branch. The findings
  here were written by editing `plan.yaml` directly instead.

## Open

- Whether the package is ever published, and whether agent-provider plugins ship with it. Left to
  their own item; the "never published" claim is deleted from the metadata rather than replaced.
- Two review threads on the extraction stay open on purpose, each answered differently from what it
  asked. Both are the user's to close.

## What stalled it again, found 2026-09-30

`integration-conflict` has withheld #185 since 2026-09-19. Its two comments blame `D-store`, then
`D-ui`. Both are krrood branches that share no file with this one, and neither is the cause.

**#185 is red on its own under the suite the published pipeline runs.** `integration-refresh.yml`
runs from the `integration` branch and reads `integration_test_command` from that branch's own
`.claude/stack/stack.toml`. That command still names `.claude/skills/plan-dashboard/tests`,
`.claude/hooks/tests` and `.claude/stack/tests`, and this branch moves all three to
`test/basstler_test/`. Run on #185's head, pytest exits 4 with `file or directory not found`. The
branch's own suite passes 665/665.

**Why an innocent tip was named.** The narrowing round pairs the suspect with each earlier tip, but
it never tries the suspect alone on the base. A tip that is red by itself fails every pairing, so
the most recent earlier tip gets the blame. The triage skill does say to confirm each branch passes
alone, but the automatic label and comment are written before anyone runs that check. This is a
`red-candidate-localisation` (#211) defect, not this plan's.

**It is a deadlock, not a collision.** The pipeline takes its suite from the last build it
published, and a build carrying #185 cannot publish while that suite names the pre-move paths.
#154 and #211 are stacked on #185 and already set
`python3 -m pytest test/basstler_test --confcutdir=test/basstler_test`, but they can only reach
`integration` behind #185. Removing the label on its own gets it re-applied by the next build. The
label also kept the branch out of the maintenance pass, including its `main` merges, so the branch
had fallen 113 commits behind. That merge was clean and 665 tests still pass.

Two ways out, and both belong to the pipeline: have `build` read the suite from the tree under test
rather than from the tooling running it, or dispatch one refresh on a reference that already carries
the new command. The second is what the workflow's own comment gives a dispatch for.

**A tooling defect met while recording this.** `plan_item_bootstrap update --append-notes` rewrote
this item's literal-block (`|-`) note as a folded scalar, with a blank line after every hard-wrapped
line, so one appended paragraph turned the note into 57. The manifest was repaired by hand and saved
with `save-plan.sh`.

**Resolution, same day.** `main` was merged at `0c7ff268f`. The user chose the personal override:
`.claude/personal/stack.toml` on the notes branch now sets `integration_test_command` to the
command #154 and #211 commit. Loaded through the published `.claude/stack/stack.py`, it resolves
to that value. `integration-conflict` was removed from #185. The override is temporary, so delete
it once a build carrying #154 or #211 has published. The localisation defect is not recorded on
`stack-maintenance`'s manifest yet.

**What the resolution missed at first: the upstream review.** `/upstream-reviews` was skipped
because #185 carries `cram2-link-sent`, not `in-review`. When it did run, it showed the real
stall behind the integration one: #185 is cram2#659, where LucaKro requested changes on
2026-09-21 and nine threads are still unresolved. They cover global constants in `dependencies.py`,
`plan_item_mode.py` and `package_layout.py`, moving helpers onto `Dependency`, a StrEnum in
`sync_version.py` and why basstler is not a proper package, a version check, and an `__init__`
comment. This is the case `always-read-upstream-reviews` records: the label does not tell you
whether an upstream pull request exists.

## The src-layout follow-up, decided 2026-09-30

cram2#659 asked why basstler is not a proper package like the others. The honest answer has
changed since decision 8. The session-start hook now installs on every start, and an editable
install leaves no second copy, so both premises that ruled out a `src` layout are gone. The user
chose to keep #185 flat and do the move as `basstler-src-layout` straight after it. Doing it inside
#185 would re-move about 40 files in a PR whose readability depends on its rename diff, would shift
the lines nine open upstream threads point at, and would make every stacked branch merge across a
second move. #154, #211 and #430 are deliberately *not* made to depend on it: the move is cheap to
redo, while crossing it is not. The one hazard worth a test is the silent case: a module added
directly under `basstler/` merges cleanly into the old location.
