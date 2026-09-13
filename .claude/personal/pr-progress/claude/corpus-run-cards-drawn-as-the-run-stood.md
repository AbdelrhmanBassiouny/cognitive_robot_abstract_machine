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
- [x] #353 CI red (user asked 2026-09-13 ~22:00; same red as #349/#352: coraplex 6 h hang,
      experiments killed 137 in the pickup demo): fast-forwarded its branch to 96e861a679, the
      merge of #265@1bcef7d49f that #356 already sits on (green), so #356 needed no downward
      merge; #353 description got a CI section; left ready-for-review as the user set it.
      #265 has moved on past 1bcef7d49f (real pickup demo, film written as taken, camera
      optical-frame offset, grasp widths) -- not merged into the stack; would conflict in
      camera_frame.py/query_card.py and change the pickup physics #356's CI fix was tuned to.
- [x] same for #349/#352 (user asked): #349 fast-forwarded to 1bcef7d49f (its commits were
      already in #265); #352 merge 3287e8f054; cascaded #353 0010d7dc63 and #356 996e0a5af7
      (both empty-diff merges, trees unchanged). Descriptions of 349/352/353 got CI notes.
- [x] asking finished 22:39 (record exit 0, 75 episodes, 3750 scored rows); first figures run
      exit 1 at 22:39:57: recall_every_trial died on REAL episode 2f370626 (recorded 22:00 by
      #265's latest real demo in another process; its world's 65 robot link meshes sit in a
      vanished /tmp/semantic_digital_twin_meshes_<pid> root -- writer bug outside this stack).
      Fix ea28d13aca: LongTermMemory.recall_every_readable_trial passes such episodes over with
      KeptWorldCannotBeReadError; generate_paper_figures.py uses it; 2 tests; pushed, #356
      description updated. Figures relaunched ~23:05 (scratchpad/figures_again.sh ->
      figures_rerecorded_2026-09-13_run2.log; status file gets "figures exit N"/"figures done").
      A second such REAL episode 6ffe9ec2 (pid 1175127) appeared meanwhile -- someone is
      recording on the robot right now.
- [x] figures run 2 exit 0 (23:20): 8 tables, 288 cards / 60 episodes; card checked (both arms
      parked, film frames Tracy's table); 56 stale card dirs of removed episodes moved to
      ~/episode-artifacts/stale_cards_of_removed_episodes_2026-09-13; final dump
      montessori_sorting_results_final_scored_2026-09-13.dump; user given tar commands
      (~/corpus-backup-2026-09-13/essential.tgz + real-episodes.tar).
- [x] real episodes checked (user asked): 3 new REAL episodes 2f370626/d37b712d/6ffe9ec2 have
      rows, 11 scored queries per trial, bags with all trials inside, transcripts; kept worlds
      unreadable (Mesh._from_json of the fetched world exports into the process temp root --
      bug on #265's real path, not this stack); joint traces empty/sparse (samples only on
      world state change). Tables count Real=5 not 14 because the pass-over drops their trials.
- [x] shadows off + held piece drawn (user asked 23:30): commit 67efe2bfa8 -- MujocoSim.
      cast_no_shadows, SceneRender.shadows=False; MujocoBuilder.hangs_below_a_body builds a
      6DoF below a body as no joint at the connection's pose; WorldCannotBeSimulatedError and
      free_joints_below_a_body removed, tests replaced. Pushed, #356 description updated.
- [x] figures run 3 died 23:57: my pytest runs write /tmp/scene.xml which the figures process
      reads back (the race #265 fixed in 362b2b6c7d for CI workers, not in this stack);
      scratchpad/figures_from_lab.py now sets MujocoSim.default_file_path to its own file.
- [x] user (from phone, 2026-09-13 ~23:45): camera panel = Tracy's description camera; move
      panel perpendicular to the dotted line, top-down for on-table moves; sharper pictures.
      Commit 0cbb28d8ac (tracy_experiments/camera.py, TwinFrames.camera, looking_at_the_move,
      1600x1200). No pyrender anywhere in the cards -- told the user; framework figure is the
      only pyrender (render_tracy.py one-off). Pushed, #356 description updated.
- [x] figures run 4 exit 0 at 2026-09-14 00:27: 348 cards / 75 episodes (held-piece episodes
      included), 100 MB; checked a held-piece scene, a top-down push panel and a camera panel
      through Tracy's camera -- all as intended. User told to redo the figures backup.
- [ ] open for the user: tables count Real=5 (the 3 unreadable real episodes' trials are dropped
      by the pass-over); mesh-file repair or a world-free recall would bring them back.
