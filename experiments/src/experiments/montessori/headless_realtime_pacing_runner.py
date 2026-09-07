"""
Runs the full multi-shape :mod:`~experiments.montessori.franka_montessori_demo`
headless, but with :class:`~semantic_digital_twin.adapters.multi_sim.MujocoSim` forced
to ``real_time_factor=1.0`` regardless of ``--viewer`` -- isolating whether real-time
pacing itself (not the viewer window) is what changed circular_hole_1's fell-through
rate from ~30-55% (headless, unpaced) to 95% (``--viewer``, real-time paced) in a
20-iteration run.

Headless mode normally runs physics as fast as the CPU allows (``real_time_factor=None``);
:data:`~experiments.montessori.franka_montessori_demo.SYNC_RATE_HZ` throttles the
physics-to-world-model joint-state readback by *wall-clock* time regardless, so if
physics outruns real time, the controller works from stale position feedback relative
to the task. See ``circular_hole_1_tuning_log.md``'s ``FORCE_REAL_TIME_PACING_OVERRIDE``
entry for the full reasoning; this script applies the same monkeypatch to the actual
full-board demo instead of the circular_hole_1-only isolated harness.

Run with (the ``experiments`` package must be importable), passing through every
argument :mod:`~experiments.montessori.franka_montessori_demo` itself accepts::

    python -m experiments.montessori.headless_realtime_pacing_runner --world2 --no-rviz --iterations 20
"""

from __future__ import annotations

from semantic_digital_twin.adapters import multi_sim as multi_sim_module


def main() -> None:
    original_mujoco_sim_init = multi_sim_module.MujocoSim.__init__

    def _forced_real_time_init(self, *args, **kwargs):
        kwargs["real_time_factor"] = 1.0
        return original_mujoco_sim_init(self, *args, **kwargs)

    multi_sim_module.MujocoSim.__init__ = _forced_real_time_init

    from experiments.montessori.franka_montessori_demo import main as demo_main

    demo_main()


if __name__ == "__main__":
    main()
