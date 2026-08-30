# bastler-package (#185) — `claude/plan-item-kickoff-workflow-cuare2`

Plan `workflow-unification`, track `bastler`, wave `upstream`. Draft PR #185, based on
`main`. Session https://claude.ai/code/session_014kmiZegiD2Q8w2eese2L2L.

## Why this session was here

`/plan-item-resolve workflow-unification bastler-package`, in `auto` mode. Nothing about
the pull request was broken — 22 of 23 checks green with `test_each_lib (coraplex)` still
running, no label, both dependencies merged. What was open was two review threads posted
at 21:25 and 21:26, four minutes before the previous session's own push landed, and
neither had been answered.

## The plan, as settled

1. Delete `bastler/requirements.txt`; declare the four distributions statically in
   `bastler/pyproject.toml`'s `[project] dependencies`, and drop the `rendering` extra
   that existed only because `dependencies` was empty.
2. Move the `missing_requirements` heredoc out of the shell into `bastler/dependencies.py`,
   reached through a `BASTLER_DEPENDENCIES_MODULE` shell name like every other module —
   and grep the whole tooling shell for the *pattern*, not just the line commented on.
3. Repoint every reader: the session start and its summary line, `check-setup.sh`, the two
   workflows, the skills, and the docs.
4. Tests first, then mutations; verify the install live rather than only against a stub.

## Done

- All of the above, in `7730b5177`, pushed. Both threads replied to and resolved.
- The two installers diverge on purpose: a session start installs the missing specifiers
  (installing `./bastler` would put a second copy of these modules beside the clone's own,
  which the zero-install contract forbids), and the two Actions workflows install
  `./bastler` itself, since a runner has no such contract.
- The grep for embedded Python found a second hit — `save-plan.sh`'s
  `python3 -c "import yaml"` — which now asks the same module and names everything the
  tooling is short of. No bash entry point carries Python of its own any more.
- Writing the call out exposed a defect the heredoc could not have had: `echo $(python3 …)`
  reports `echo`'s exit status, so a module that dies reads as "nothing to install". Hence
  the `|| return 1`, a `dependencies: not checked` case, and the test that fails without it.
- 632 tests pass, from 615. Six mutations, each caught by exactly the test that names it,
  each restored from a copy taken before it rather than from `HEAD`.
- `nh3` uninstalled for real and put back by one session start, which also reported
  `setup: ok` in the same run; the built wheel carries its four `Requires-Dist` lines.
- PR description rewritten; `plan.yaml` (`blockers` cleared, `notes` appended) and
  `roadmap.md` saved; dashboard republished.

## Outstanding

- CI on `7730b5177` is green on all 23 checks, `test_bastler` among them, and the
  `test_each_lib (coraplex)` job that was still running when this session started
  finished green too. Nothing is red on this branch.
- Two threads from the 2026-08-23 round stay open on purpose: the `RESTACK_STEPS` name
  `monkeypatch.setattr` takes as a string, and the surviving `status_label` assertion
  offered for deletion.
- #198 fixes a bug this branch carries verbatim at `bastler/stack.py`, and #203 adds
  `.claude/setup_steps.py`. Whichever lands first, the other merges across it — and the
  `git ls-tree` check against the merged tree is what catches a module `main` gained that
  no conflict report can name.
