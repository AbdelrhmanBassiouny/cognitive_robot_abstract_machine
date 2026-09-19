# PR 265 extraction and rewire

## Plan
1. Audit #265 for commits no pull request's diff contains. [done]
2. Extract the ones that stand on main as small pull requests. [done]
3. Fold the ones that only edit an unlanded PR's own files into that PR. [done]
4. Reparent the pull requests based on #265. [done: none possible, proven]
5. Verify #299/#355's needs against every open PR, extract what can be. [done]

## THE METHOD LESSON (read this first)
"Which open PR introduces each file the commit CHANGES" is necessary but NOT
sufficient, and a clean cherry-pick is NOT evidence. A commit also needs the
symbols it IMPORTS and the fields it passes as KEYWORDS, which live in files it
never touches. Three wrong outcomes came from missing this:
- #286 reparented onto #275 -> ModuleNotFoundError on krrood.patterns.belief_source,
  and no WorkspaceRegion.grown_by. REVERTED.
- #415 opened against main -> base.py imports spatial_types.numeric (absent on
  main). CLOSED, folded into #244.
- The InsertAction extraction nearly shipped on main, then on #295: both would
  have raised TypeError. InsideOf(minimum_containment_ratio=...) needs #229 and
  PlaceAction(grasp_description=...) needs #296.
Tools written for this, in the session scratchpad (reusable, need python3.13):
- verify_imports.py <ref> <files...>  ast-resolves every workspace ImportFrom
  against the ref's tree. False positives: */orm/ormatic_interface (generated).
- verify_attrs.py <ref> <files...>    checks ImportedClass.attr and
  ImportedClass(kw=...) against the class and its resolvable bases.

## Audit result (81 direct commits on #265)
8 already covered; 1 empty bootstrap; 4 extracted; 7 folded; 61 blocked.

## Done
New draft PRs off main (all `bug`): #414 #416 #417 #418 - all import-verified.
Fold-ins: #256 <- 798a172d98, 06e7af3eb8, a8c66997f3; #244 <- 31c0f3a67e,
223e532824 (ex-#415); #294 <- 13e2104bcc; #295 <- 26e73cea5f.
Closed: #419, #415.
New (this pass), both drafts:
- #422 "The place an insertion builds on" <- #296. A merge of #229 + #295 + #296.
  Settles a REAL collision: #229's PlaceAction._grasp_description vs #296's
  _how_the_object_is_held are two designs for the same thing. Resolved the way
  #355 already had: keep _grasp_description, give it #296's stated-grasp
  preference first, drop _how_the_object_is_held and its now-unused imports.
  Also unions generate_orm.py's two exclusion blocks, in #355's order.
- #423 "An insertion is an action of its own" <- #422. 8483223f69 out of #355.
  Import- AND attribute-verified.
Comments posted: #299, #355, #296, #229, #265.

## #299: no reparent target exists, and none can be built
Needs two lineages that meet nowhere but #265: detector_choice.py (69f30348a1,
on #231->#239->#266->#275 and #259) and hypotheses.py (d8b654433a, on
#232->#236->#270 and #227->#238->#255->#257). No non-265 branch holds more than
6 of its 8 files. Merging the tips leaves 23 conflict hunks / ~1100 lines
(pipeline.py 13 hunks). AND that is still not enough: 11 commits on #265 touch
its 8 files and are on NO lineage branch - 0e4d632b3f a3acc06fbe 83c3eae1b7
5f63f0f503 (all four pure convergence glue), 6c968260eb 9ab3729019 746f8ea3c6
280832645d 3d6504f7d9 4bf6694f1d 54b4ec5848. 63 of #265's perception commits
are in no open PR at all.

## #355: three quarters of it is not its own work
Measured against main, not #265, it is 11 commits. 4 already on main
(9eeb9697bd 5c058d6ae6 7599ef771c 83909bdd36); 2 already open off main
(46f09b3d1f -> #362, 88a8d99315 -> #357); 1 now #423. Remaining 8:
- insertion follow-ups d11d1ad6c0 98164d4432 20e756bbdf 634f0aa708 need
  insert_shape_action.py (#169->#170->#178/#180; leanest #178, +261) merged with
  #296's chain. That merge is 39 files / 162 hunks, incl. .github/workflows,
  AGENTS.md, .gitignore - that chain is far behind main.
- demo commits 02466da20d e2de39c323 3e9e5b0698 e1352a9992 need 5 files on no
  open PR (perceived_sorting, pickup_demo_real, pickup_demo_mujoco,
  pick_and_place_action, perception/scene_publishing) + the framework figures.
  On #265 those carry 61 commits back to 36696eb02a. Stranded with the closed
  stack; no smaller cut exists.

## Damage I could not undo (earlier pass)
- #286's description was overwritten during the reverted reparent; GitHub's REST
  API does not expose the previous body. Replaced with a reconstruction plus a
  warning banner. Ask the user if they have the original.
- #286 was ready-for-review; converted to draft and left draft. User must flip.

## Next
- Answer needed on #422's resolution: keeping _grasp_description over
  _how_the_object_is_held drops an abstraction #296 introduces.
- The real remaining work: revive the 36 closed sub-PRs (#292..#363, ~122
  commits) on #262 -> #271 -> #278/#294/#295/#296/#297, then replay the 61
  blocked commits. #299 and #355's demo half both wait on it.
- Bringing the #169->#178 montessori chain forward onto main is its own job, and
  unblocks #355's four insertion follow-ups.
- No test suite runnable here: no numpy/pytest importable, no venv. CI only.

## Collision scans (2026-09-19) - scripts in the session scratchpad
Two scans, because they catch different things. BOTH are needed.
1. collide.py - pairwise trial merge (git merge-tree) between chain tips whose own
   diffs share a .py file. 78 tips, 166 candidate pairs, 119 collide. LOW VALUE on
   its own: dominated by staleness hubs (#257 collides with 14 PRs over the same 5
   files because it is 200+ commits behind, not because 14 designs duplicate).
   BLIND SPOT: cannot see a PR colliding with MAIN. It missed #296 entirely.
2. divergence.py - per PR, which of main's symbols it REMOVES (ast, top-level plus
   Class.method), and how far behind main it is. This is the one that works.
   122 PRs scanned: 82 up to date, 40 behind >50, 35 behind >200, 33 remove a
   symbol main has. Grouping by shared (file, symbol) removals -> 31 true pairs,
   which collapse into CLUSTERS:
   - predicates.py "predicates become classes": #227 #229 #33 #35 #238 #257 all
     delete the same 7 functions (contact, is_body_in_region, is_place_occupied,
     is_supported_by, is_supporting, ...) and each adds its own class version.
     SIX PRs doing one refactor. The biggest single duplication in the repo.
   - world.py/test_world.py: #232 #238 #257 delete the same 29-33 symbols.
   - base_expressions.py: #34 #142 (#35 #192 adjacent) delete HasExpression,
     RuleTreeContext.
   - example_classes.py: #36 #257.
   - setup scripts: #107 #110 both delete SetupPrerequisiteFile, CheckResult,
     CheckStatus (the known #106/#110/#117 family).
   - placing.py: #296 vs MAIN, single-sided, only scan 2 sees it.

## CORRECTION (2026-09-19): the #229/#296 collision was misattributed
I told #229 and #296 they collided over PlaceAction._grasp_description. WRONG.
#229 does not touch placing.py at all. Facts: main HAS _grasp_description (added
in 98d847a776); #295 and #296 both forked BEFORE that; #296 built
_how_the_object_is_held for the same job. #229 is current with main, so merging it
into #295's tree is what dragged main's method in - which is why the conflict
appeared next to #229. The collision is #296 vs MAIN.
#422's resolution was always right (keep main's _grasp_description, fold #296's
stated-grasp preference in as its first branch); only the rationale was wrong.
Fixed: both commit messages amended and force-pushed (tree byte-identical,
verified with git diff), #422 and #423 bodies rewritten, correction comments on
#229 and #296. Lesson: verify WHICH branch introduced a symbol with
`git diff --stat <base>...<head> -- <file>` before naming it in a comment.

## (a) RECOMMENDATION WITHDRAWN: do NOT re-cut perception
The perception work is not four accidental lineages - it is EIGHT TRACKED PLAN
ITEMS, and knowledge-directed-grounding's chain is ALREADY correctly stacked:
  #202 -> #205 -> #221 -> #225 -> #232 -> #236 -> #270   (+ #223 off #202)
matching that plan's own depends_on exactly. Re-cutting would destroy eight items'
review work for nothing. The OTHER chain (#231 -> #239 -> #266 -> #275, + #259)
belongs to knowledge-directed-requests; #257 to knowledge-directed-expectation;
#296 to icra-foundation; #295 to icra-evidence.
So the perception fan-out is a PLAN-LEVEL fault: four plans each stack over the
same files and NO PLAN OWNS THE JOIN. The plans' own descriptions record why -
"those depends_on edges could not cross the plan boundary". #265 was the join.
#299's 9c4840bf94 IS the join PR, mis-based. The right fix is a join PR per
collision, not a re-cut.
The tracy-demo half of (a) is different and the re-cut idea stands there: only
5 of the 36 closed sub-PRs are tracked plan items (#298 #301 #303 #304 #311).
The other 31 are untracked orphan work.

## (b) DONE, and it already has a plan
design-overlap (tracking issue 102) plans exactly this automation; its
definition-catalogue and overlap-detector items are not_started. The two scripts
above are a manual run of them and should seed those items. (b) needs
design-overlap updated, not a new plan.

## Plan verdict
A new cross-plan recovery plan IS needed, because the missing work is the join and
by construction no existing plan can own it. Blocked on ONE user decision: which
of the six predicate-refactor PRs wins.
