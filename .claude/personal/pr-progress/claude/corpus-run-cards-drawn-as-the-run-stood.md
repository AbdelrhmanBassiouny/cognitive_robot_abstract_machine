Branch claude/corpus-run-cards-drawn-as-the-run-stood, stacked on #353 (-> #352 -> ... -> #265),
with the latest #265 merged in (2026-09-13). Draft PR #356.

Plan: make the query cards of the simulated corpus right.
- [x] scene panel stood at the query's moment from the joint trace
- [x] scene drawn in the twin's own colours; Collada meshes one geom per material
- [x] spatial card's camera stood behind the two objects facing the question's way
- [x] camera panels for simulated runs drawn from the twin along the trace
- [x] leak: _MultiSimStateCallback left on the world per MujocoSim build; stop_simulation()
- [x] full figures run on the rehearsal copy (port 55432): 366 cards / 61 episodes, 30:36,
      peak RSS 17.6 GB, exit 0 (was OOM at 54 GB after 57 episodes)
- [x] round 2 (user feedback 2026-09-13): labels blue with white halo, anchored above the
      thing, pushed apart, leader line (paper/labels.py); ANSWER_COLOR magenta; spatial
      camera 80 deg down, 0.8 m back, 40 deg view; both arms parked at build
      (TracyOnItsOwnTable.build) and held there: apply_gravity_compensation now covers every
      link below the robot root (the 1 kg massless frames were uncompensated) and
      exclude_self_collision applied too -- without both, the unused arm sagged out of park
- [x] commit round 2 (7c4caf7d0b), pushed, #356 description updated (draft)
- [x] film camera frames the world's own table top (WorkspaceSurface.corners; TABLE_BOUNDS
      removed), commit 481c4f190e, pushed, #356 description updated
- [x] lab DB: backup montessori_sorting_results_before_instructions_column_2026-09-13.dump,
      then ALTER TABLE "RecordedTrialDAO" ADD COLUMN instructions_carried_out JSON NOT NULL
      DEFAULT '[]'::json (user asked for it 2026-09-13)
- [x] CI red on #356 (test_tracy_pickup_demo_mujoco): commit 130e6e5a3b -- apply_gravity_compensation
      back to arm+gripper scope (the widening made the cube/cylinder slip on the carry, 5/5),
      corpus scene uses compensate_gravity_on_every_link; MujocoBuilder._register_mesh names
      one asset per file+scale (collision meshes named like visual ones were never registered,
      every link collided with its visual hull); prism strict xfail dropped (8/8 through).
      test_the_camera_stands_where_the_captures_camera_stood fails locally at the base too
      (local tracy description), passes on CI. Pushed, #356 description updated, draft.
- [ ] re-recording the corpus on the lab DB, launched 2026-09-13 17:12 detached:
      scratchpad/rerecord_then_figures.sh -> ~/episode-artifacts/corpus_rerecord_2026-09-13.log,
      manifest corpus_episodes_rerecorded_2026-09-13.txt, status rerecord_status_2026-09-13.txt,
      then figures_from_lab.py -> figures_rerecorded_2026-09-13.log (writes experiments/doc/figures)
- [ ] once done: check a scene card of a re-recorded episode shows the idle arm parked, report
- rehearsal cluster on port 55432 stopped 2026-09-13

- [x] old recording removed from the lab DB (user asked 2026-09-13 19:20): backup
      montessori_sorting_results_before_old_corpus_removal_2026-09-13.dump, then
      scratchpad/delete_old_corpus_episodes.py --apply deleted the 75 episodes of
      corpus_episodes.txt plus the 02:08 smoke episode 29c9ca09 (76 episodes, 76 trials,
      4868 scored queries, association rows); lab DB now 75 re-recorded + 5 robot episodes.
      Their plans/worlds/ticks/motions stay as unreferenced rows (same as the smoke cleanup).
