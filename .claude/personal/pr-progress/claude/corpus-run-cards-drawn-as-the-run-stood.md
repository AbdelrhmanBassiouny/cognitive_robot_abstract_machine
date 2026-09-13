Branch claude/corpus-run-cards-drawn-as-the-run-stood, stacked on #353 (-> #352 -> ... -> #265),
with the latest #265 merged in (2026-09-13).

Plan: make the query cards of the simulated corpus right.
- [x] scene panel stood at the query's moment from the joint trace (trace.py standing_at /
      put_back_afterwards; query_card._stood_when_asked)
- [x] scene drawn in the twin's own colours (SceneRender.faded optional, default None;
      BACKGROUND_COLOR removed); pose change likewise
- [x] Collada meshes built one geom per material in the file's colours (multi_sim MeshPart,
      _parts_of_a_collada_mesh); fixture resources/collada/two_coloured_cubes.dae
- [x] spatial card's camera stood behind the two objects facing the question's way
      (PointOfView.stood_behind)
- [x] camera panels for simulated runs drawn from the twin along the trace (TwinFrames,
      RecordedFrameAt); panel wording updated
- [x] leak: every MujocoSim mirror left a _MultiSimStateCallback on the world (~200 MB per
      build); scene.py, simulated_camera.py, mujoco_video_recording.py now stop_simulation()
- [ ] full figures run against the rehearsal copy of the lab DB (port 55432) to confirm
      memory stays flat over all 81 episodes
- [ ] commit, push, draft PR

Open points for the user: ANSWER_COLOR (amber) is close to the pieces' yellow and the board's
orange now that scenes are in true colours; film camera (SceneRecording._camera_watching_the_scene)
frames the constant TABLE_BOUNDS, wrong for Tracy's table -> videos of the corpus are mis-framed
(not fixed here); lab DB lacks RecordedTrialDAO.instructions_carried_out (#265) - needs an
ALTER TABLE before recording again.
