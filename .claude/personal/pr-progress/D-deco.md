# PR plan: D-deco — @rdr decorator (Wave 0, S2b)

Decorator half of the @rdr path, stacked on D-store (#80). Base: `D-store`.
PR: #77 (draft, retargeted from D-ui -> D-store).

## Scope

- `rdr/decorator.py` — rdr() factory + RDRWrapper.
- `rdr/templates/rdr_empty.py.jinja` — empty rule-tree section.
- `test_rdr_decorator.py`, `rdr_decorator.md` (dev + user).

SOLID split preserved; both load invariants hold (case_type.function
rewired; rdr.save_path always set). Adaptations vs rdr-engine:
FunctionCaseGenerator().generate, camel_case_to_lower_camel_case,
load_module_from_path; imports global.

## Split history (2026-07-16)

The original single D-deco PR was too big for review. Root cause: it
bundled two unrelated commits — the real @rdr feature (1993 lines) + an
"umbrella-closure sweep" (1031 lines of orphan files bundled only to make
`git diff rdr-engine <tip>` reach zero for #38).

Resolution:
1. Feature split into #80 D-store (file store) + #77 D-deco (decorator).
2. Sweep dissolved (#38 already closed). Per-file disposition:
   - rdr_conclusion_domain.py -> REHOME #76 (D-ui guide imports it; required).
   - test_rule_tree_view.py -> REHOME #76 (only real renderer coverage; the
     copy.copy assertion was rewired to _node_for_new_position_).
   - eql_rdr_refactor_plan.md -> dangling (un-indexed) design doc; offered
     to steward for #68 or drop.
   - backward_inference_{design,user_guide}.md -> DROPPED (stray krrood/docs/
     path, not in the built doc tree, referenced by nothing).
   Both keepers verified green on D-ui (test_rule_tree_view 20 passed);
   staged for the steward to land (I don't push their branch).

## Stack

main … D-core-engine (#68) -> D-ui (#76) -> D-store (#80) -> D-deco (#77)

## Status

- DONE: D-deco rebuilt on D-store, head 7e89ec60 (single decorator commit),
  force-pushed. #77 retargeted base D-ui -> D-store, description rewritten,
  subscribed. #80 opened + subscribed.
- test_rdr_decorator.py: 20 passed. Full test_eql_rdr on D-deco tip: 518
  passed, 2 skipped (-20 vs before = test_rule_tree_view moved to #76).
- Earlier: on the pre-split tip, full CI was green (all 18 matrix jobs;
  semantic_digital_twin case_factory fixed by restack, coraplex
  test_merge_motions green).
- Steward notified via #76 comment (2026-07-17): register D-store in the
  restack chain, hand off the 2 rehome files (staged on branch
  D-deco-rehome-handoff, cut from D-ui), eql_rdr_refactor_plan.md question.
- 2026-07-19: steward acted. D-ui split further into 3 stacked branches
  (D-ui-splice-fix -> D-ui-rendering -> D-ui) and D-store was registered
  in the restack chain — D-ui/D-store/D-deco all auto-restacked
  (D-ui a7eb3703->9c7f8e6b, D-store 0c4938d3->b7655f11, D-deco
  7e89ec60->86717780). Both my commits preserved verbatim (diffed
  identical old vs new). Re-verified on the new tip: test_rdr_file_store
  21 passed, test_rdr_decorator 20 passed, full test_eql_rdr 518 passed/
  2 skipped.
- New CI flake found: semantic_digital_twin -> test_multi_sim.py::
  test_world_sim_state_sync (physics-settling assertion). Confirmed
  unrelated: same job passes on #80, whose only diff from #77 is the
  decorator commit, which never touches semantic_digital_twin/
  physics_simulators. Documented in #77's description and flagged on
  #76; no fix needed here.
- 2026-07-19 (later): steward landed the rehome — single commit
  bf5b63c3 "Add conclusion-domain doc fixture + rule-tree renderer
  test" on D-ui, content byte-identical to what I staged (diffed
  handoff branch vs new D-ui: empty). D-core-engine also advanced
  (already incorporated into the new D-ui — confirmed ancestor).
  Rebuilt D-store (cherry-pick 0c4938d3 -> f1de44d9) and D-deco
  (cherry-pick 7e89ec60 -> c675dd49) onto the new tips; both diffed
  content-identical to originals before pushing. Re-verified:
  test_rdr_file_store + test_rdr_decorator 41 passed, full
  test_eql_rdr 538 passed/2 skipped (the +20 vs before = 
  test_rule_tree_view.py now included via the landed D-ui rehome).
  ORM artifacts reverted. Force-pushed both branches.
- Attempted to delete the now-landed D-deco-rehome-handoff staging
  branch; the delete push failed with HTTP 403. CONFIRMED SYSTEMIC:
  the D-ui/steward session hit the identical rejection independently
  ("the remote end hung up") trying to delete the same branch — this
  is a session-wide git-proxy limitation on ref deletion, not specific
  to my permissions. Stopping retries; branch is harmless (content
  fully landed), theirs to remove when their side allows it.
- #77 description updated (verification numbers, known-failures
  list including both confirmed-unrelated flakes, restack history).
- 2026-07-19 (later still): full CI green on #77's current head
  (c675dd49) — all 18 matrix jobs pass, INCLUDING both previously-
  flaky jobs (coraplex, semantic_digital_twin) — confirms they are
  genuinely intermittent, not real failures. Both #80 and #77 show
  mergeable_state "clean". D-ui/steward session independently
  confirmed the rehome landing and flake diagnoses in their own #76
  comments; eql_rdr_refactor_plan.md punted to the actual steward
  (S0), still unanswered.
- 2026-07-19 (restack #3, automated): D-core-engine, D-ui, D-store,
  and D-deco all advanced again (D-core-engine bd6e42f4->d98d9566,
  D-ui bf5b63c3->c50d2109, D-store f1de44d9->07cb6831, D-deco
  c675dd49->c46c0c5b). This time the restack automation itself
  pushed merge commits ("Merge origin/X into Y (restack onto updated
  parent)", authored by the automation identity) directly onto
  D-store and D-deco — no action needed from this session, just
  verification. Diffed old tip vs new tip for every file this slice
  owns (file_store.py + its test on D-store; decorator.py, the
  jinja template, test_rdr_decorator.py, both rdr_decorator.md docs
  on D-deco): all empty, confirming zero content drift through the
  automated merge. Re-ran full test_eql_rdr on the new D-deco tip:
  538 passed / 2 skipped. mergeable_state was "unstable" right after
  the restack (CI queued/in-progress on the new tip, not a real
  conflict) — expected transient state, not investigated further.
  Reverted the regenerated ormatic_interface.py diff as usual. No
  new comments on #76/#77/#80; steward's eql_rdr_refactor_plan.md
  call still outstanding.
- 2026-07-19 (webhook): CI check `test_each_lib (krrood)` failed on
  #80 at the restack-#3 tip (07cb6831) — a THIRD, new-type flake
  (not one of the two previously known ones). Investigated via job
  logs: it's a collection-time TOCTOU race, not a real test failure
  (2370 passed, 9 skipped, only 1 collection error). Root cause:
  `test/krrood_test/conftest.py::generate_sqlalchemy_interface`
  regenerates ormatic_interface.py atomically via a NamedTemporaryFile
  written *inside the same directory* pytest-xdist workers are
  scanning, then os.replace()s it into place; a worker's directory
  listing can catch another worker's in-flight .tmp file, which is
  gone by the time pytest lazily tries to collect it ->
  `AssertionError: PosixPath(...ormatic_interface.<hash>.py.tmp) is
  not a file`. Confirmed pre-existing on main (`git diff main..D-store
  -- test/krrood_test/conftest.py` shows only docformatter whitespace
  noise, the temp-file-in-same-dir logic is unchanged) — not
  introduced by this stack, not in #80/#77's own diff. Per AGENTS.md
  (don't touch ormatic_interface.py machinery myself), reported on #76
  for the developer's awareness rather than fixed; no action taken on
  #80/#77. Will note if it recurs.

## Next

- Babysit #80 and #77 until merged/closed (#80 merges first). Both
  green/clean pre-restack; post-restack content verified identical,
  CI re-running on the new tip — check back for it to go green.
- Still waiting: steward's (S0) call on eql_rdr_refactor_plan.md (land
  on #68 with an index entry, or drop) — posted, no reply yet.
- D-deco-rehome-handoff: leave as-is, systemic delete limitation
  confirmed by two independent sessions — not worth further retries.
