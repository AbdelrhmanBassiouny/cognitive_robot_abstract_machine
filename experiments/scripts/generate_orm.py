import logging
from pathlib import Path

import experiments
import experiments.control_loop_experiments.benchmark
import experiments.control_loop_experiments.scenarios
import experiments.scenarios.report
import experiments.scenarios.runner
import experiments.scenarios.scenario
import experiments.scenarios.trial
import experiments.episodes.artifacts
import experiments.episodes.recording
import experiments.episodes.long_term_memory
import experiments.paper.figure
import experiments.paper.figure_set
import experiments.paper.measurement
import experiments.paper.outcomes
import experiments.paper.queries
import coraplex.orm.ormatic_interface
import segmind.orm.ormatic_interface

from krrood.ormatic.ormatic import ORMatic
from krrood.ormatic.utils import classes_of_module
import experiments.control_loop_experiments.control_loop_profiler

# benchmarking measures a running system instead of describing it
ignored_classes = set(classes_of_module(experiments.control_loop_experiments.scenarios))
ignored_classes |= set(
    classes_of_module(experiments.control_loop_experiments.benchmark)
)
ignored_classes |= set(
    classes_of_module(experiments.control_loop_experiments.control_loop_profiler)
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

# a table of the paper is computed from what was recorded rather than recorded itself,
# and it is regenerated whenever the database changes, so storing one would store an
# answer next to the rows it was read off
for paper_module in (
    experiments.paper.figure,
    experiments.paper.figure_set,
    experiments.paper.measurement,
    experiments.paper.outcomes,
    experiments.paper.queries,
):
    ignored_classes |= set(classes_of_module(paper_module))

# an episode's artifacts are kept as files, so what this module holds is where they are
# and how they are rendered - a path names a file rather than describing one, and the
# transcript is a reading of queries the trials' rows already carry
ignored_classes |= set(classes_of_module(experiments.episodes.artifacts))

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
