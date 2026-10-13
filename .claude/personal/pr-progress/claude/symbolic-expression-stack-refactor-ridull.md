## Next
- PR #142 open as a **draft**, base `main`, head df0aef5e. No `bug` label. Subscribed.
- #118 merged 2026-08-05, so GitHub retargeted #142 onto `main`; `main` merged in
  cleanly (df0aef5e). A stack-maintenance routine had reported a conflict naming no
  files - there was none, because this branch already contained #118's commits. Its
  `needs-resolution` label was cleared, since a labelled branch is skipped by later
  passes and would have stayed parked.
- Post-merge suites: 1443 passed, 6 skipped (2 `test_object_diagram` = missing
  Graphviz `dot`, reproduces on `main`). PR description rewritten for the new base.
- Second false-positive conflict report (2026-08-05, after main moved to 0626bdce):
  merged main again at 41de0a63, clean, pushed. Diagnosis recorded on the PR
  (comment 5197102942): `stack.py:1177` decides conflicts with
  `git merge-tree --write-tree <parent> <ref>`, and that command returns 0/CLEAN on
  the exact refs the pass used, while GitHub reported `mergeable_state: clean`
  throughout - so the conflict comes from the agent-driven integration step, not
  repository state. Both reports left "Conflicting files:" empty. The routine also
  broke its own SKILL.md step 4.4 (clear the label unless `dirty`) and the
  label/report pair deadlocks: leaving the label parks the branch forever, clearing
  it guarantees a repeat report. Needs a fix in the routine, not here.
- 2026-08-10: the stack routine merged main again at 77f79a99 (clean; no conflict
  report this time). Local fast-forwarded to it; diff vs main unchanged at 8 files,
  +424/-102.
- CI red on 77f79a99 across ~8 `test_each_lib` jobs - NOT this branch. `greenlet`
  3.5.5 was published 2026-08-10T13:28:09Z with wheels only for macos/win and no
  sdist, so `uv` cannot install it on Linux; jobs started 13:36 and die at dependency
  resolution before any repo code is imported. greenlet is transitive (SQLAlchemy)
