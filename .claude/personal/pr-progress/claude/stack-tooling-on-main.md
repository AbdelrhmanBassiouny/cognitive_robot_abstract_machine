# PR #106 - stack tooling on main (`claude/stack-tooling-on-main`)

Plan item: `workflow-unification` / `stack-tooling-on-main`. Draft, based on `main`.

## Plan

Turn the maintenance doctrine into a skill and the recipes into `stack.py` subcommands,
**inside #106** rather than as a child PR - every path involved is absent from `main`, so
by the scope rule nothing standalone would remain, and landing a `ROUTINE.md` its own
successor deletes would change the live doctrine twice (the pointer resolves
`origin/main` first).

## Done (commit e20b0bb4, pushed)

- `.claude/skills/stacked-pr-maintenance/SKILL.md` replaces `.claude/stack/ROUTINE.md`,
  invocable as `/stacked-pr-maintenance`; context resolution is arguments -> `stack.py
  configuration` -> ask, with `--non-interactive` turning the question into a stop.
- Four new subcommands - `labels`, `preflight`, `promotion-link`, `reparents`/`landed` -
  plus `configuration --fork/--upstream`. `argparse` subparsers; `PREFLIGHT_REFUSED = 5`.
- `POINTER.md` now resolves the skill and passes both repositories; `prompt_model.py`
  gains `<UPSTREAM_REPOSITORY>` and resolves the skill from the repository root;
  `README.md` repointed.
- 331 tests pass (was 294). Each new contract test verified to fail on its own edit only.
- Description rewritten, PR returned to draft, plan manifest + roadmap saved, dashboard
  republished.
- Replied on `stack.toml:23` (left open on purpose) and told #110 what its rebase now
  inherits.

## Next

- Nothing blocking. Waiting on review of #106.
- Due when this lands: re-paste `POINTER.md`'s block into claude.ai/code/routines (it now
  resolves the skill, passes both repositories and `--non-interactive`), then drop the
  tooling-branch fallback and switch the block to `/stacked-pr-maintenance` by name.
- Still #110's, not this branch's: deleting the ~120-line remote inference alongside the
  setup that writes `fork_repository`.
- Open question already flagged to the user and answered "keep": decision 11's cut of
  `print_next` / `print_restack_plan`. If that reverses, sequence it before #110's rebase.
