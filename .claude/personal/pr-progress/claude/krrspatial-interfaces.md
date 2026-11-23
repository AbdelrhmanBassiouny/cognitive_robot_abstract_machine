## Plan
- Answer every ichumuh comment on cram2#1019 in #527, decided with the owner first.
- Speed: casadi points/vectors hand changes their homogeneous column; within ~15% of main.
- Cross product onto Vector3Dimensional; MotionVectorPair folded into the 3D VectorPair.
- Open: 2D model and dot/norm placement (options under discussion); perf guard via the experiments control-loop benchmark.

## Done
- Benchmark at cc75214c vs main e7eaded0: T@point/vector 5x, norm 5.3x, dot 2.4x, T@pose 2.8x slower; compiled graphs identical.
- Plane check: 210 us per T2 with frames (FK each time); state-dependent: an IMU pitch of 1e-5 makes map->base raise.
- Kept ...Dimensional naming (owner).

## Next
- Owner decides 2D model and dot/norm; then TDD implementation on claude/krrspatial-interfaces.
