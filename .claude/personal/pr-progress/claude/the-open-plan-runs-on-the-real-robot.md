Branch claude/the-open-plan-runs-on-the-real-robot, stacked on #369 (the-open-plan-runs), with
#265's tip 9b3c7f5dc9 merged in (2026-09-14). Draft PR #376 (base claude/the-open-plan-runs),
commit e95bdd23a2 pushed. Plan file:
~/.claude/plans/silly-gliding-thimble.md. PR 256 not relevant (old monitor split-out).

Plan: run the framework figure's plan on the physical Tracy, record the episode, fill the figure.
- [x] ActuatorDrivenAction binds the lab too: Generic[ActionT, LabT], lab_it_drives(),
      performing(plan, lab); SimulatedActuators(simulation, actuators) for the MuJoCo members
- [x] pick_and_place_action_real.py: TracyActuators, PickUpActionReal, InsertionActionReal
      (arm through Giskard, fingers through Robotiq action server, slip watch on the carry)
- [x] open_slots/grounding.py GroundedPlan (shared by both labs, .report() prints slots)
- [x] framework_demo.py --execution {simulated,real}; framework_demo_real.py (FrameworkTrial,
      FrameworkDemoOnTracy: person places cube on lid far from square hole, look, rviz check,
      ground, park, perform, question set, keep episode; --record/--database-uri/--no-episode)
- [x] tests: test_pick_and_place_action_real.py 10 passed; plan/framework tests 18 passed;
      shared fixtures test/experiments_test/dataset/figure_plan_fixtures.py
- [x] sim dry run: Perception->DetectedMontessoriShape, Probabilistic->GraspDescription,
      HoleRules->ShapeSortingHole, 100% through hole (scratchpad/slots_in_simulation.txt)
- [x] regression: rehearsal 9 errors on ROS_DOMAIN_ID=2 (hears the live robot) -> 15 passed on
      domain 77 localhost; prism test fails at the base worktree too (pre-existing, not mine);
      #369 CI red on greenlet==3.5.6 having no wheel (install step, every lib)
- [x] bag_frames.py + test_tracy_bag_frames.py (4 passed)
- [ ] env: venv imports ~/workspace checkout (lab's, 7 uncommitted files, left alone); run
