# knowledge-directed-expectation — standing rules

- A belief decays only when something acts on it: released over a hole, an object is believed at that hole; still grasped, its pose is the gripper's; acted on by nothing, it is where it was last seen. Preserve this rule in any extension of belief tracking.
- Of the 2026-08-28 rosbags only tracy_pickup_demo carries /tf, /tf_static and /joint_states; the other five are camera-only, so they get expectations from the board and the action model, not from a replayed event history. Record /tf and /joint_states alongside the camera in future captures.
- If every ORM-building CI job fails identically, check first for a generic that is also a context manager (krrood's Variable); that shape broke make_specialized_dataclass's memoization workspace-wide once (fixed in 1e93c138).
