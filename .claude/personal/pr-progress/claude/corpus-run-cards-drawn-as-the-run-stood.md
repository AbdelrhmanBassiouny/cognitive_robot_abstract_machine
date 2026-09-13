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
- [ ] commit round 2, push, update #356 description (keep draft)

Open points for the user: film camera (SceneRecording._camera_watching_the_scene) frames the
constant TABLE_BOUNDS, wrong for Tracy's table -> corpus videos mis-framed (not fixed);
lab DB lacks RecordedTrialDAO.instructions_carried_out (#265) - ALTER TABLE before recording
again; existing corpus recordings still hold the stretched unused arm in their traces, only a
re-recording removes it from the cards.
