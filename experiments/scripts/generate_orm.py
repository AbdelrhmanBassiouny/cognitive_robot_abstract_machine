import logging
from pathlib import Path

import experiments
import experiments.control_loop_experiments.benchmark
import experiments.control_loop_experiments.scenarios
import experiments.montessori.scenarios
import experiments.scenarios.report
import experiments.scenarios.runner
import experiments.scenarios.scenario
import experiments.scenarios.trial
import experiments.episodes.artifacts
import experiments.episodes.recording
import experiments.episodes.long_term_memory
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

# recording an episode and asking after one are machinery rather than records: each
# holds the database a run is written to or read from, which is nothing to store in it
for episode_database_module in (
    experiments.episodes.recording,
    experiments.episodes.long_term_memory,
):
    ignored_classes |= set(classes_of_module(episode_database_module))

# an episode's artifacts are kept as files, so what this module holds is where they are
# and how they are rendered - a path names a file rather than describing one, and the
# transcript is a reading of queries the trials' rows already carry
ignored_classes |= set(classes_of_module(experiments.episodes.artifacts))

# the Montessori scenes and scripts are the same kind of description one level down:
# they say how a sorting run is set up and what is done to it, and what a run then
# recorded is the episode model's, not theirs
ignored_classes |= set(classes_of_module(experiments.montessori.scenarios))

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
