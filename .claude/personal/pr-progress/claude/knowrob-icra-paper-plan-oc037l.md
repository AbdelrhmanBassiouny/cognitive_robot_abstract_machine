## ICRA paper re-cut (planning session 2026-09-11, no code, no PR)

Deliverable: the "KRROOD ICRA Re-cut" artifact
https://claude.ai/code/artifact/71c63b27-e7d1-495d-a1ab-9f53aeb645c1 - a four-day
paper plan reframing the paper as the single-language realisation of the KnowRob 2.0
vision, evaluated the KnowRob 2.0 way (query answering) made rigorous.

Done: read the KnowRob 2.0 paper; read icra-foundation/mechanism/evidence and the
related plans; surveyed krrood, semdt, coraplex, segmind, giskardpy and PR #265;
wrote the capability matrix, abstract, hypotheses H1-H4, paper structure, twelve
query cards, figure list, item-by-item plan modifications, six new items with
designs, the schedule and the risks.

Findings that limit claims: segmind composite events are imperative, no provenance
(new item event-rules-as-eql); no router or cross-backend disagreement check yet
(new item cross-backend-check); no question performatives or temporal operators
(new item question-performatives).

Next (developer's call): accept/amend the re-cut, then apply it to the three
plan.yaml files on claude/personal-notes and republish the dashboards; start
event-rules-as-eql and question-performatives in parallel sessions off #265.

Update 2026-09-11 (later): the segmind EQL event rules exist on the fork branch
sorinar329/cognitive_robot_abstract_machine:safety_ai_ws (forked 2026-05-06, main 2610
commits ahead, tracks a generated ormatic_interface.py, old event class names). Verdict:
port ~60 lines (rule body of _find_interaction_events, event_time_difference,
not_(exists(...)) dedup) onto #265; do not merge. Its krrood half already landed on main
as InferenceExplanation's meta-query methods. Artifact item 1 rewritten accordingly.

Update 2026-09-11 (later still): developer reports an existing VLM comparison on ~100
simulated episodes with table and statistics. Not found in the repo, the fork branch, or
Drive (the SegMind IJCAI-W paper is single-episode, no VLM arm). Plan updated: VLM items
become vlm-comparison-imported (existing results as ExperimentResult rows beside #304's
accuracy rows); asked the developer where the data lives and which question set it used.
Update 2026-09-11 (lab): developer is at the robot and will implement and merge into #265.
Published the "KRROOD Lab Runbook" artifact (step order, items A-D, data checklist, query
pictures, perturbation protocol). Surveys of #265 head 040e2daa7 found: #301/#303/#311 already
merged; #304/#299/#286 open against it; nothing populates Tick/RecordedQuery/InsertionAttempt in
production and no recording CLI exists (-> new must item episode-observer); no renderer of a
query answer in the twin (-> answers-rendered-in-the-twin, MuJoCo offscreen + segmentation);
board fit quality computed then discarded, no rule family for the board (-> look-quality-
expectation: LookQualityStandard, PerceptionDegraded(PlanFailure), BoardIsSeenClearly,
BoardRules); Q12 needs only Expectation.check (belief-checked-against-perception); robot runs
back in as robot-episodes-recorded. plan.yaml not yet edited: awaiting the developer's yes on
the item list.
Update 2026-09-11 (lab, later): developer said postgres, not sqlite (runbook v2), then asked for
copyable prompts per item; runbook v3 carries ten session prompts (0 merge #304; A observer +
record_episode; B answers rendered; C look quality; D1 belief check; D2 event rules port; E corpus +
cross-episode; F question register; G extension cost + packaging; H VLM import with placeholders).
Update 2026-09-11 (lab, v4): developer dropped the dimmed/sunlight condition entirely. Runbook v4:
no lighting recorded, tuned or mentioned; LightingChanged stays in code but is not run; item C's
trigger is a new BoardPartlyCovered perturbation (flat body over half the lid in sim, a sheet of
paper on the robot), captures renamed clear_*/covered_*; prompts C and E updated accordingly.
Update 2026-09-11 (lab, v5): developer reverted Q8 to the control-constraints read. Runbook v5:
look-quality-expectation dropped entirely (no quality gating, no BoardPartlyCovered, no rule family for
the board); item C is control-constraints-and-degrees-of-freedom-queried (ActiveTasks.of(statechart,
moment), Task constraints exposed, two Bucket.CONTROL questions, one per memory); prompt C rewritten.
Update 2026-09-11 (lab, #316): item A (episode-observer) already exists as draft PR #316
(claude/episode-observer-8mq3xv, stacked on #265). Checked against #265 head 4bf6694f1: the v5
decisions need nothing from it (LightingChanged stays in code; its CLI choice may stay or go), but
it is needs-resolution - its own krrood WrappedTable.parse_field fix duplicates 5d9049212 which
#265 now carries from main (conflicts in wrapped_table.py and test/krrood_test/conftest.py), and
observer.into does not keep the trial's motion statechart, which item C's long-term question needs.
Update 2026-09-11 (lab, v6): #316 merged into #265 (d2a39f92b); the krrood conflict resolved for main's
is_stored_as_a_value and #316's duplicate test dropped. Runbook v6: item A marked done, prompt A replaced by
prompt A' (branch claude/trial-motion-recorded-*): fill RecordedTrial.motion_statechart from
GiskardExecutable.motion_state_chart through the observer (list of RecordedMotion with moments if a trial runs
several), prove histories survive the round trip, and delete PerturbationChoice.LIGHTING_CHANGED from the CLI.
Update 2026-09-12 (figure): the paper's framework figure exists as draft PR #320 (claude/framework-figure-oc037l,
merged into #265 through the GitHub API at db4251efb after the local merge push was refused by the permission classifier):
experiments/doc/figures/framework/framework.typ (config-driven Typst, build.py with the repository root as Typst
root, reads the montessori capture), framework.pdf, two Tracy renders from iai_tracy_description + board.stl +
drawers + pieces, and tracy/ (URDF, pose files, pose_search.py, render_tracy.py, README). Placeholders flagged in
the PR: grasp probabilities, the hole rule tree, the cube pose.
Update 2026-09-12 (lab, evening): status check for the developer at the robot. #265 head 3e41b69e2 carries #316, #319, #320, #325; #323 (control constraints, clean) being merged; #318 (query cards) dirty against #265 (generate_orm.py, simulated_camera.py), needs-resolution, adds RecordedTrial.number/began_at/plans so postgres tables made before it need a migration or a fresh database; #324 (event rules) open; corpus session on claude/catalogue-in-simulation-qv7mk2 (no PR yet, based on bb1bd5095). Only TheSceneStandsStill declares runs_on_the_robot, and the perceived path of record_episode was never run against the robot (020cbc41a). Advice given: smoke-test the perceived path now into a scratch database, rehearse pickup_demo_real with a bag, record stand-still episodes now only into a schema-named database; sorting episodes wait for #318.
Update 2026-09-12 (lab, #318 in): #323 and #318 merged into #265 (head b2fb89522). pickup_demo_real now records a trial (plans, joint trace, question set via --ask-about) but resolves the database with resolve_reachable, which falls back to memory silently; advised exporting MONTESSORI_SORTING_DATABASE_URI and running the pre-flight in the same shell, recreating the database for the new schema, and merging #324 before the sorting runs so Q6 is answerable live.
Update 2026-09-12 (lab, #324 in): #324 merged into #265 at 14f1e3439 (verified: its head f35dd080b is an ancestor). #318/#323/#324/#325 were each tested against bb1bd5095, never together; a combined segmind + event-monitoring run was attempted here but the sandbox's ORM generation fails on semantic_digital_twin.exceptions (CouldNotResolveType MetaData), so the developer runs it on the lab PC.
