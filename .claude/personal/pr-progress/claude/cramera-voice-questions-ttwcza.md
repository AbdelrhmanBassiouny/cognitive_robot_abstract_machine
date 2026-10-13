### Outstanding
- CI not checked on #167/#168.
- Pre-existing red in this checkout: `presets.json` in the scenes submodule
  (upstream cram2/cram-scenes, no fork to fix it from) is out of step with
  `MONTESSORI_PRESETS` ordering/scopes; `test_franka_panda_equipment`'s two
  grasp-contact tests call `apply_grasp_contact_parameters` without its new
  `friction` argument; two `test_montessori_results_recording` tests log
  nothing for an unreachable database here; one event-monitoring test raises
  `MissingReferenceFrameError`.
