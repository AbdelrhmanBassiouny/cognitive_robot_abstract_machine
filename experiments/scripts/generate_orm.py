import logging
from pathlib import Path

import experiments
import experiments.control_loop_experiments.benchmark
import experiments.control_loop_experiments.scenarios
import experiments.scenarios.report
import experiments.scenarios.runner
import experiments.scenarios.scenario
import experiments.scenarios.trial
import experiments.episodes.recording
import coraplex.orm.ormatic_interface
import segmind.orm.ormatic_interface

from krrood.ormatic.ormatic import ORMatic
from krrood.ormatic.utils import classes_of_module
import experiments.control_loop_experiments.control_loop_profiler
import experiments.montessori.perception.simulated_camera
import experiments.montessori.perception.simulated_setup

# benchmarking measures a running system instead of describing it
ignored_classes = set(classes_of_module(experiments.control_loop_experiments.scenarios))
ignored_classes |= set(
    classes_of_module(experiments.control_loop_experiments.benchmark)
)
ignored_classes |= set(
    classes_of_module(experiments.control_loop_experiments.control_loop_profiler)
)

# a camera renders a look, it is not a record of one; it also holds a live mirror of the
# world, which is a running system rather than anything a row could hold
ignored_classes |= set(
    classes_of_module(experiments.montessori.perception.simulated_camera)
)
ignored_classes |= set(
    classes_of_module(experiments.montessori.perception.simulated_setup)
)

# the scenario domain model describes how an experiment is run rather than what it
# recorded; what of a trial becomes a mapped record is decided where episodes are
# recorded, not here
for scenario_model_module in (
    experiments.scenarios.scenario,
    experiments.scenarios.trial,
    experiments.scenarios.report,
    experiments.scenarios.runner,
):
    ignored_classes |= set(classes_of_module(scenario_model_module))

# a recorder is machinery rather than a record: it holds an open session and the
# conversion state of a run, neither of which is anything to store
ignored_classes |= set(classes_of_module(experiments.episodes.recording))

# Create an ORMatic object with the classes to be mapped
ormatic = ORMatic.from_package(
    [experiments],
    [coraplex.orm.ormatic_interface, segmind.orm.ormatic_interface],
    ignored_classes,
    type_mappings={},
)
logging.getLogger("krrood").setLevel(logging.DEBUG)

# Generate the ORM classes
ormatic.make_all_tables()

ormatic_interface_path = (
    Path(__file__).parent.parent
    / "src"
    / "experiments"
    / "orm"
    / "ormatic_interface.py"
)
with open(ormatic_interface_path, "w") as f:
    ormatic.to_sqlalchemy_file(f)
