# claude/answers-rendered-7aa6z6 -> PR #318 (draft)

Base: claude/icra-experiments-simulation-pipeline-w4ep7n (#265). NOT main - this
stacks on #265, which owns the recording pipeline the cards read.

## Plan (all done)

Original six steps (query cards beside the paper's tables) - done, commits
532264f..b1e9947. See the PR description for what each one built.

Follow-up asked for in the same session: a four-level card showing WHY an
answer is yes or no. Done in three commits:

1. [x] 255a636 - chart.py (TrialChart, shared by both charts), run_plan.py
       (TrialClock, PlanItem, RunPlan.accounts_for), plan_timeline.py.
       Also folded ANSWER_COLOR into panel.py (scene+timeline had it twice).
2. [x] 6ead61a - pose_change.py (PoseChange, PoseChangeRender): the object
       drawn where it was and where it ended up, one camera, ghost laid over.
3. [x] ecb7c6a - EventAgainstThePlanCard with the four panels, BagFramesAround
       (camera either side of the event), panel dispatch refactored to one
       named method per PanelKind.
4. [x] f1017a0 - layered.py (LayeredFigure, Layer): the four levels stacked
       into ONE picture, which is what "four levelled visualization" actually
       meant. The card sets layered = True and its markup names the one
       stacked figure; each level is still written beside it.
       PanelKind members now carry a PanelWording (level name / caption /
       what is written where the level is missing).
       Stacking caught a real defect: both charts were drawn only as wide as
       what they happened to hold, so a second sat in a different place on
       each. TrialChart.drawn now takes the trial's span and both span it.

The two runs it exists for both verified by rendering: the robot's own pick-up
gets its plan item picked out in amber; the shoved piece gets a plan that was
handling something else, nothing picked out.

## Outstanding / for the next session

- CI has not reported. Nothing subscribed, no check-in armed, per my own rules.
- GitHub showed mergeable_state "dirty" right after the push; verified stale -
  the base sha IS an ancestor of HEAD locally, so there is no real conflict.
- Two numbers are my choice, not measured: JUST_FINISHED = 1.0 s (how long
  after a plan item finishes it still accounts for an event) and
  EITHER_SIDE = 1.0 s (how far either side of an event the camera frames are
  taken). Both flagged in the PR description for the user to tune.
- The camera before/after level is the one of the four never drawn for real
  here: its geometry is asserted, but the tests that open an actual rosbag are
  skipped without the recordings, same as test_montessori_bag_replay. In the
  rendered example figures it shows as its "only a run on the robot records a
  camera" band.
- OPEN JUDGEMENT CALL flagged in the PR: a level with nothing to draw is
  stacked as a band saying why, rather than dropped. Good for showing the
  structure; the user may prefer it omitted for the paper's simulated runs.
- Still cannot run (no ROS in sandbox, so ORM interfaces cannot be generated):
  test_paper_figures.py, test_paper_figures_from_the_database.py, end-to-end
  runs of the two scripts, and generate_orm.py itself. The new paper modules
  (chart, plan_timeline, pose_change, run_plan) were added to its ignore list
  unverified - first place to look if CI's ORM build goes red.
- Drive-by fix still carried: MujocoEntityNotFoundError was not a @dataclass.
- Example card PNGs still not committed (experiments/doc tracks only
  references.bib); they go to the session instead.

## Sandbox notes (not committed, would need redoing in a fresh session)

Workspace installed with `pip install --no-deps -e <each package>` under
python3.12, plus hand-stubbed rosbag2_py / rclpy / sensor_msgs / tf2_msgs in
site-packages, urdf_parser_py copied from an sdist, casadi pinned to ~=3.7.0,
and libosmesa6 via apt. This session additionally needed `pip install
transforms3d` and an rclpy/node.py stub exposing a no-op `Node` class.
Tests run with
`MUJOCO_GL=osmesa python3.12 -m pytest <paths> --orm-build=never`.
Note ~30 experiments_test modules fail to COLLECT in this sandbox (tracy,
sage10k, scalability - all ROS imports); that is pre-existing, so name the
paper test files explicitly rather than using -k.
  BEGIN-PR-PROGRESS/END-PR-PROGRESS markers, written automatically by
  session-start.sh). Initialize it with a short plan as soon as you start
  real work on the PR.
- Keep it current: update it whenever the plan changes, whenever you update
  your task list, and before ending any turn that changed either. Run
  `save-pr-progress.sh` whenever you update it.
- Never write this plan into any file tracked on the PR branch itself. It
  must live only in the PR-progress section, which is stored on the
  `claude/personal-notes` branch and is never merged.

## Plan-mode approval → persistent plans

- The moment a normal Claude Code plan-mode plan is approved, before implementing, judge whether
  the work spans multiple PRs/branches/sessions to complete. If it's contained in one PR from this
  session, just implement it - do not invoke anything below for it.
- If it spans multiple PRs/sessions:
  - **No existing plan covers it**: invoke `/plan-create <plan-id>`, handing it the just-approved
    plan-mode markdown directly as source material - it's valid input under that skill's "existing
    freeform doc to migrate" case even though it only lives in this conversation, not a file.
  - **An existing plan covers/extends it** (check auto-discovery on the current branch, or ask):
    if this session is that plan's designated planning/steward session, edit `plan.yaml` directly
    and run `save-plan.sh` + `/plan-dashboard <plan-id>`; otherwise comment-propose it on the
    plan's `tracking_issue` instead of editing directly - see
    `.claude/personal/plans/README.md`'s "Proposing structural changes" section.
- This is the moment that decides whether the plan gets captured durably or evaporates once the
  session ends - do not let it pass by default.

## New PR/item, or a change to one already in flight?

- **Ask this before opening any branch or adding any plan item, and prefer the change.** Something
  is genuinely new only if it still stands alone once the work before it lands. If it *modifies*
  what an unlanded PR/item introduces, it is that PR's work - stacking it reflects the order I
  wrote things in, not a real dependency.
- The test is mechanical, so run it rather than judging by feel:
  `git ls-tree <base-branch> -- <paths the work touches>`. Empty output means those files do not
  exist on the base yet, so whichever PR introduces them is a candidate owner.
- **That flags it for inspection; it does not settle it.** Ask what the PR would be if those edits
  were removed. Substantial and standing on its own → it is real work on top of an unlanded parent,
  which is just stacking. Nothing left → it exists only to change the parent, so it is not a
  separate PR. Weighing the two halves usually decides it at a glance (#110: 2,645 lines of new
  setup infrastructure vs 187 lines editing #106's files — real; #117: nothing but edits to #106's
  files — folded).
- A duplicate will not show up as an overlapping path if the two PRs named the file differently,
  so compare by *purpose* too, not only by path.
- Costs of splitting anyway, all of which we have now paid: the earlier PR ships a state nobody
  should run; the later one spends its review re-explaining the first; if the earlier one is live
  infrastructure, landing it alone regresses that infrastructure until the later one follows; and
  two PRs both touching unlanded files can independently build the same file without noticing.
- When it has already happened, fold rather than sequence - and decide *before* either lands,
  because afterwards a duplicate is a merge conflict instead of a choice.
- Split on what the work *is*, never on when I thought of it. One PR with a coherent story beats
  two that only make sense read in order.
- Precedent: #133 folded into #117, #117 folded into #106, and #110 turned out to be building
  `.claude/stack/routine-prompt.md` while #106 was building `POINTER.md` - the same artifact,
  twice, because nobody ran the check above.

## Keeping plan state current

- **Whenever anything happens that changes a tracked plan's state, update that plan's
  `plan.yaml` and its data - immediately, in the same turn.** Starting an item, finishing
  it, opening or merging its PR, blocking on something, abandoning an approach, or reaching
  a conclusion that changes what an item means: all of it goes into the manifest, not only
  into the chat.
- What to write: the item's `status`, `branch`, `pull_request_number` and `session` as soon
  as each is known, plus `notes` when a conclusion changes the item's substance. Record the
  narrative and the reasoning in the sibling `roadmap.md` - especially a premise that turned
  out to be wrong, a decision I overrode, or a dependency rule that no longer applies.
- Then run `save-plan.sh <plan-id>` so it lands on the personal-notes branch, and immediately
  run `/plan-dashboard <plan-id>` yourself to republish the dashboard. A script cannot call
  the Artifact tool, so only a live session can - do not stop at telling me it needs doing.
- **Always republish the dashboard whenever a plan's data changes, whatever changed it and
  whichever session did it**: `save-plan.sh`, `/plan-create`, a refresh's manifest
  auto-correction, or a hand edit on the personal-notes branch. Republish in the same turn
  as the change, so a published dashboard is never older than the manifest behind it.
- Do this even when the session is not the plan's steward. Prefer editing `plan.yaml`
  directly and saying so over leaving the manifest stale; a comment on the `tracking_issue`
  is a useful record of *why*, but it is not a substitute for the state itself being right.
  This overrides the propose-don't-edit guidance above for state that is already fact.
- A plan whose manifest lags behind reality is worse than no plan: every dashboard, kickoff
  and resolve run downstream reads it as truth.

<!--
Add new personal-only rules below this line. Keep each rule short and
imperative, same style as above.
-->

## Plan updates: recheck deltas, don't reread

- Note the personal-notes commit SHA whenever you read plan state (the fetch you read it
  from); it is your staleness stamp.
- Recheck for plan/tracking-issue updates at these moments: (a) when I prompt you after
  you have been idle or stale for a while, (b) when starting a new task or plan item, and
  (c) **always immediately before any `save-plan.sh` write** - fetch first and re-apply
  your edits onto the latest manifest, never write back a copy loaded earlier (two silent
  stale-save reverts are already on record in workflow-unification's roadmap).
- Recheck means reading the *delta only*: fetch the notes branch, then
  `git diff <last-seen-sha>..FETCH_HEAD -- .claude/personal/plans/<plan-id>/`; for the
  plan's tracking issue, read only comments newer than your stamp. Do not reread whole
  files that a diff can summarize.
- Keep tracking-issue subscriptions where they exist: events are the push channel for
  structural changes; this recheck is the pull channel for everything else (most manifest
  edits produce no event at all). Neither replaces the other.

## Comment routing for plan changes

- The plan's tracking issue always gets the structural record.
- Comment on a PR only when that PR's owner must act or its review context materially
  changes (scope change, landing hazard). Pure FYIs go in the manifest/roadmap only - nobody
  is watching that PR, so an FYI there is just noise its owner has to triage.

## When your PR's job ends

- A PR your session owns is finished the moment any of three things happens: it merges, it
  closes, or **I convert it from draft to ready-for-review myself**. All three mean the same
  thing for you - there is nothing left for this session to do on it.
- The moment one of them happens: delete any armed triggers or check-ins that reference it
  (`list_triggers` → `delete_trigger`), and stop any polling or monitoring tied to it.
  Nothing may stay armed for a finished branch. You never subscribed to the PR itself, so
  there is nothing to unsubscribe there - but do drop anything you subscribed to on its
  behalf, such as the plan's tracking issue when that PR was this session's only reason to
  hold it.
- Why draft→ready counts: a PR of yours stays a draft until I have reviewed it, so taking it
  out of draft is my record that I read the changes and accepted them. Push no further
  commits, do not re-draft it, and start no new work on it.
- Only a flip I made counts. A session marking its own PR ready - because I told it to, or to
  unblock a dependent item - is not the signal: keep working, and keep re-drafting after each
  push as usual.
- Report anything still outstanding when the signal arrives - red CI, a merge conflict, an
  unresolved review thread - in the session chat, and on the PR only if it is genuinely
  blocking. Then stop anyway; do not stay to fix it.
- If I want more work on that PR afterwards, I will start a new session for it.

<!-- END-PERSONAL-NOTES -->

<!--
PR progress for branch 'claude/answers-rendered-7aa6z6', synced from
'claude/personal-notes' (.claude/personal/pr-progress/claude/answers-rendered-7aa6z6.md) on remote 'https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine' by
session-start.sh. Maintain the current plan, what's done, and what's next
here throughout work on this PR. It is never merged: it lives only on
'claude/personal-notes', never on this branch. A stale file left behind after the
PR merges is harmless (just unread from then on) - delete it directly on
'claude/personal-notes' if you want to tidy it up.
To edit: change the notes between the markers below, then run
  "$CLAUDE_PROJECT_DIR/.claude/hooks/save-pr-progress.sh"
to push the change back. This header and the markers are regenerated every
session - editing them has no effect; only content between the markers is
ever saved.
-->
# claude/answers-rendered-7aa6z6 -> PR #318 (draft)

Base: claude/icra-experiments-simulation-pipeline-w4ep7n (#265). NOT main - this
stacks on #265, which owns the recording pipeline the cards read.

## Plan (all six steps done)

1. [x] MujocoSim.geoms_of / recolor / make_visible, promoted out of
       test_region_appearance.py (commit 532264f, b1e9947)
2. [x] experiments/paper/scene.py - SceneRender, RenderedScene, PointOfView (adb67f0)
3. [x] experiments/paper/timeline.py - EventTimeline (7befcc8)
4. [x] experiments/paper/camera_frame.py - BagFrameAt (8611ca0)
5. [x] experiments/paper/query_card.py + panel.py, FigureFile.IMAGE,
       TypstRenderer.render_image_figure (bd817d3)
6. [x] experiments/scripts/render_query_cards.py, cards wired into
       generate_paper_figures.py (e0c4225)

All four "done when" cards exist and are tested: ObjectsSeen,
SideOfAnotherObject, PickedUpRecently, NumberOfOwnDegreesOfFreedom.

## Outstanding / for the next session

- CI has not reported yet. Nothing has been subscribed and no check-in is armed,
  per my own rules - I will prompt if I want CI handled.
- Could not run locally (no ROS in the sandbox, so the ORM interfaces cannot be
  generated): test_paper_figures.py, test_paper_figures_from_the_database.py, and
  any end-to-end run of the two scripts. The scripts are smoke-tested via --help
  only; their logic lives in QueryCardSet.write_every_episode, which is tested.
- generate_orm.py was edited to ignore the five new paper modules. That edit was
  NOT verified by running the generator (same ROS reason). If CI's ORM build
  fails, that is the first place to look.
- Drive-by fix carried in this PR: MujocoEntityNotFoundError was not a @dataclass,
  so all fifteen raises of it in multi_sim.py died with a TypeError. Fixed because
  geoms_of depends on it. It does NOT fix test_world_multi_sim_with_change, which
  was already red and now shows its real cause.
- The example card PNG is not committed (experiments/doc tracks only
  references.bib); the PR description carries the .typ and a description instead,
  and the images went to the session. Say the word if you want them committed so
  the description can show them inline.

## Sandbox notes (not committed, would need redoing in a fresh session)

Workspace installed with `pip install --no-deps -e <each package>` under
python3.12, plus hand-stubbed rosbag2_py / rclpy / sensor_msgs / tf2_msgs in
site-packages, urdf_parser_py copied from an sdist, casadi pinned to ~=3.7.0, and
libosmesa6 via apt. Tests then run with
`MUJOCO_GL=osmesa python3.12 -m pytest <paths> --orm-build=never`.
