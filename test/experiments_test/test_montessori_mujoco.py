import os
import time

import pytest

from experiments.montessori.world import MontessoriWorld

only_run_test_in_ci = os.environ.get("CI", "false").lower() == "false"

pytestmark = pytest.mark.skipif(
    only_run_test_in_ci,
    reason="Only run test in CI or multisim could not be imported.",
)


def test_montessori_world_can_be_simulated_in_mujoco(tmp_path):
    from semantic_digital_twin.adapters.multi_sim import MujocoSim

    MujocoSim.default_file_path = str(tmp_path / "montessori_scene.xml")
    montessori = MontessoriWorld()
    multi_sim = MujocoSim(world=montessori.world, headless=True)

    try:
        multi_sim.start_simulation()
        time.sleep(1.0)
        assert multi_sim.is_running()
    finally:
        multi_sim.stop_simulation()
