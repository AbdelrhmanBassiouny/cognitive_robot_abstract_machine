# World modification policy study

Research prototype for the question "can `World.modify_world()` be removed so that the
modification decorators alone decide when a modification block is committed?".

`World` reads two environment variables (see `WorldModificationPolicyEnvironmentVariable`):

| Variable | Values | Effect |
|---|---|---|
| `SEMANTIC_DIGITAL_TWIN_MODIFICATION_POLICY` | `explicit` (default), `eager`, `eager_tolerant`, `deferred` | how modifications are grouped into blocks |
| `SEMANTIC_DIGITAL_TWIN_LAZY_COMPILATION` | `1` or unset | compile forward kinematics and collision data on first read instead of at every commit |

Scripts (run from this directory with ROS and the overlay sourced):

- `benchmark_policies.py [sizes...]` - build chains, spawn into a world, interleaved build and query.
- `profile_commit.py [sizes...]` - where the time of one commit goes.
- `benchmark_urdf.py` - parse the PR2 URDF under every policy.
- `stress_threads.py [seconds]` - writer thread against guarded and unguarded readers.
- `stress_ros_synchronization.py [bodies] [policies...]` - mirror a world over ROS.
