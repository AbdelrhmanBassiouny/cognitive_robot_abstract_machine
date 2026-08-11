# integration-branch (#154) — regenerated personal integration branch

`workflow-unification` plan, `stack-tooling` track. Branch
`claude/plan-item-kickoff-workflow-ixbvxl`, currently on **#139's head**, moving
to **#151's** (which now contains #139). Draft PR #154, head `97cdde313`.
Sessions: https://claude.ai/code/session_01Ue4PvfV5LDxHGRRS5BZB4g (built it, then
settled this review round).

## Status: review round settled, implementation handed over

28 review threads arrived. All are **answered**; **none is actioned** and none is
resolved. This session settled the five that needed a decision and stopped there,
at the user's instruction, so the next session implements from the plan below.

Nothing is pushed. `97cdde313` is still the head, the PR is a draft, and the tree
is clean — a conflicted #139 merge was started and aborted, because the base
changed (see step A1).

**Read the "Handover" sections before touching anything.** The threads are worded
as small local asks; most of them are one consequence of a stale base.

## Handover — decisions already settled (do not re-litigate)

| Question | Decision |
|---|---|
| Escalating a semantic break | The skill **pushes** a mimic test to the breaking branch, comments on the PR, applies a blocking label, writes the manifest and republishes the dashboard. Reuse the scripted pipeline; do not write prose steps. |
| Which label | A **separate** one (`integration-conflict`), not `needs-resolution`. Reason below. |
| `suspect-replay` | Discard the bad `rr-cache` entry, then triage normally. Never auto-write a replacement in the same pass. |
| A PR based on both conflicting branches | **No** — one base per PR, so it is a diamond: the diff swells to contain the whole second branch, it cannot promote alone, and `restack_plan` derives exactly one parent per branch. |
| The verdict source | GitHub CI, not a local suite. `build` pushes and exits; a separate subcommand reads the run's conclusion. |
| Base | **#151**, not #139. |

**Why a separate label.** `WithholdBranchStillConflicting`
(`maintenance_restack_steps.py:225`) clears `needs-resolution` whenever
`mergeable_state` is not `dirty` — and a semantic break never makes a PR dirty.
Reusing that label means the very next maintenance pass strips it. The new label
must still *block*: generalise `Configuration.needs_resolution_label` into a
collection of blocking labels read by both the withholding step and
`maintenance_promotion.py`'s exclusion, so both labels travel one code path. The
auto-clear stays keyed to `needs-resolution` alone.

## Handover — A: rebase onto the parent chain

Most of the "you duplicated #139" threads dissolve here. #139 split
`maintenance.py` into eleven modules and added `class_property.py` *after* this
branch was cut, so `integration.py` independently grew its own error base,
command classes and git helpers.

1. **Merge #151, not #139.** #151 rebased onto #139 (`6fd229ff3` contains
   `ebf67734`), so the chain is linear and one merge brings the module split,
   `class_property.py` *and* the manifest subcommands. Retarget the PR base.
2. Re-apply this branch's two additions onto the split: the `GitCommandRunner`
   per-command config overrides and the two named git methods belong in
   `maintenance_git_commands.py`.
3. Rewire `integration.py` to import rather than carry its own: errors →
   `maintenance_errors.ExternalCallFailed`; git → `maintenance_git_commands`;
   report/exit codes → `maintenance_report`.
4. Delete `integration.py`'s command base; reuse #139's `MaintenanceCommand` with
   `classproperty`. Same directory, same `sys.path` entry, so it imports directly.
   If it cycles, extract the ABC into a module both import — do not copy it.

The tree will then hold two command-base patterns: #139's `MaintenanceCommand`
(`classproperty`, parser from classes) and #151's `Subcommand` (abstract instance
properties, parser from instances). They differ because of where each builds its
parser; `dev-tooling-python-package` unifies them. Follow #139's here.

## Handover — B: the escalation pipeline

The mimic test goes on the **breaking** branch — the relying branch cannot express
a test against an import that does not exist on it yet. Worked case: #111 gives
`stack.py` a module-scope `import development_tooling`; #110's fixture builds a
minimal project without it, so the test asserts `stack.py` imports in a mimic
minimal checkout and fails on #111 today with no merge at all.

Reuse, do not rebuild: `LabelWrite.replacing` for the label (never compute the set
from the addition alone), `ForkPullRequests.add_comment` addressed via
`get_session_link_in`, `plan_item_bootstrap.py block --branch` / `unblock --branch`
for the manifest, `/plan-dashboard` for the republish.

`SKILL.md:12` says a conflict "is fixed in the feature branch it belongs to, never
here", which reads as ruling out the `rr-cache` writes a *defer* verdict actually
makes. Reword to separate the two artifacts: feature branches are never edited by
the build; the throwaway cache is.

## Handover — C: mechanical threads

`TipOutcome` → `PullRequestStackTipOutcome`; `bisect` → a descriptive name
everywhere it appears; `maintenance.py:184`'s inner two-string tuple → a named
frozen dataclass; `stack.py:361`'s repeated key → one imported constant. In the
tests: `a_*` factories → `create_*`; repeated literals defined once; the suite
runner into its own file; git through `GitCommandRunner` rather than raw
`subprocess`; report keys and values as `StrEnum`s imported from their definition;
env-var names from `maintenance_constants`. `test_integration_skill.py:127` →
structured checks instead of full-sentence assertions.

## Handover — D: CI as the verdict

`build` pushes the branch, prints the run URL and exits. A separate subcommand
reads the conclusion. Localisation pushes every prefix at once so CI runs them
concurrently — one round trip instead of N, at the cost of N probe branches
needing out-of-harness deletion. `integration_test_command`, `--test` and
`--no-test` all go; the `tests-failed` status stays, only its source changes.

This reverses "the tool pushes nothing" **narrowly**: to a branch it owns and
regenerates, never to a feature branch. Reachability was measured on #146 —
`actions/runs`, `jobs` and job-logs all answer 200 from a session, and this fork's
queue time is a median of 0s.

## What shipped (the state being revised)

- **`.claude/stack/integration.py`** — builds the upstream base plus every
  in-flight stack tip. Tips only, ascending PR number. Conflicts skip and
  continue; the report names the **pair**. `--restack` off by default (it pushes
  to other people's branches), `--test` on by default.
- **`bisect`** — when the branch builds and the suite fails, adds tips back one
  at a time until it turns and names the pair. A semantic break leaves no
  conflict to attribute, so there is nothing else to go on. Probes run detached,
  so no ref is left behind.
- **`.claude/skills/integration-conflict-triage/SKILL.md`** — the judgement.
  Merge collisions: defer resolves into `rr-cache`, reconcile proposes without
  applying, stack reports. Semantic breaks: adapt / reconcile / sequence, all
  proposed. Ask by whose decision it is, not by confidence.
- `integration_test_command` in `stack.toml` + `Configuration`;
  `INTEGRATION_SCRIPT` constant; README sections.
- On #139's files: `GitCommandRunner` gains per-command config overrides (rerere
  on for the build without touching the developer's config) + two git methods;
  `print_configuration` omits empty settings as well as unset ones.

## The two findings worth remembering

**A replayed rerere resolution fails exactly like a merge that never began** —
non-zero exit, no unmerged paths, because `autoupdate` already staged them. Only
git's stderr (`using previous resolution`) separates them, so the replay marker
must be read *before* the unmerged-paths rule.

**Nothing can be recorded for a semantic break.** rerere keys on a conflict
preimage and a semantic break has none, so the collision recurs on every build
until a branch changes. Reasoning by analogy from the merge case is the trap; a
contract test pins the sentence that rules it out.

## Verified

- 479 tests across the three directories CI runs, was 428 before the item. 51
  new, TDD, each mutation-checked to fail only for its own reason.
- Live on the real fork: 22 tips, 10 merged, 12 skipped, then `tests-failed` —
  and it was real. **#110 alone passes 32, #111 alone green, merged 18 fail**
  (#111 adds a module-scope package import; #110's scratch fixture has no such
  package). Clean merge, invisible to both PRs' CI. Reported on both. `bisect`
  reproduced it independently, excluding the innocent tip.
- After every run: invoking checkout on its own branch, clean tree, pointer at
  the build, no worktree or probe branch left, nothing pushed by the tool.

## If this is picked up again

- Re-draft #154 after any push.
- **The `greenlet` claim recorded here earlier is retracted.** 3.5.5 does publish
  cp312 manylinux wheels and an sdist; it read as a publish-propagation window.
  Judge any `test_each_lib` red on its own evidence, not on that note.
- #139 and #151 are both moving; a base merge may land underneath again.
- This clone has a `cram2` remote, a local `integration` branch, and `integration`
  was pushed to the fork on request (the tool itself never pushes — until part D,
  which changes that for the integration branch only).
- All 28 threads are answered and unresolved. Resolve each only after doing what
  it asked, with an inline reply naming the commit; two are answered-not-actioned
  by design (the `--quiet` question and the doc-formatting sweep) and stay open.

