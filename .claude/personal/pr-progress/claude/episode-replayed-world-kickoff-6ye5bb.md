## Outstanding — the developer's, not this session's
- **r3927219116 left open on purpose.** Two places are deliberately undocumented: the two
  new exceptions' `error_message`/`suggest_correction` overrides (no `DataclassException`
  subclass in the workspace documents theirs, and the abstract base states both contracts)
  and `DataPlayer.__post_init__`/`FilePlayer.__post_init__` (untouched by this branch).
  Offered on the thread to add either.
- CI was still running on `f9a961fc` when this session finished; `mergeable_state` was
  `unstable` for that reason rather than for a red check.
