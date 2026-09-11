import logging
from pathlib import Path

import experiments
import experiments.control_loop_experiments
import experiments.montessori.scenarios
import experiments.scenarios.report
import experiments.scenarios.runner
import experiments.scenarios.scenario
import experiments.scenarios.trial
import experiments.episodes.artifacts
import experiments.episodes.observer
import experiments.episodes.recording
import experiments.episodes.long_term_memory
import experiments.montessori.ask_episode
import experiments.montessori.record_episode
import experiments.montessori.watched_run
import experiments.tracy_experiments.montessori.scene_builder
import experiments.questions.long_term_memory
import experiments.questions.question
import experiments.questions.question_set
import experiments.questions.working_memory
import experiments.paper.camera_frame
import experiments.paper.chart
import experiments.paper.figure
import experiments.paper.figure_set
import experiments.paper.measurement
import experiments.paper.outcomes
import experiments.paper.panel
import experiments.paper.plan_timeline
import experiments.paper.pose_change
import experiments.paper.queries
import experiments.paper.query_card
import experiments.paper.questions
import experiments.paper.run_plan
import experiments.paper.scene
import experiments.paper.timeline
import coraplex.orm.ormatic_interface
import segmind.orm.ormatic_interface

from krrood.ormatic.ormatic import ORMatic
from krrood.ormatic.utils import classes_of_module, classes_of_package
import experiments.montessori.perception.simulated_camera
import experiments.montessori.perception.simulated_setup

# benchmarking measures a running system instead of describing it, and its modules need
# ROS message packages a checkout mapping this package may not have
ignored_classes = set(classes_of_package(experiments.control_loop_experiments))

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

# what observes a trial, the run that is observed, the command lines that start one
# and ask one back, and the scene builder they run on are machinery of the same kind:
# what they observe is written onto the episode model's own rows
for episode_machinery_module in (
    experiments.episodes.observer,
    experiments.montessori.watched_run,
    experiments.montessori.record_episode,
    experiments.montessori.ask_episode,
    experiments.tracy_experiments.montessori.scene_builder,
):
    ignored_classes |= set(classes_of_module(episode_machinery_module))

# an episode's artifacts are kept as files, so what this module holds is where they are
# and how they are rendered - a path names a file rather than describing one, and the
# transcript is a reading of queries the trials' rows already carry
ignored_classes |= set(classes_of_module(experiments.episodes.artifacts))

# the Montessori scenes and scripts are the same kind of description one level down:
# they say how a sorting run is set up and what is done to it, and what a run then
# recorded is the episode model's, not theirs
ignored_classes |= set(classes_of_module(experiments.montessori.scenarios))

# a question is asked rather than recorded: it holds the query that answers it and the
# memory it is put to, neither of which is anything to store
for question_module in (
    experiments.questions.question,
    experiments.questions.question_set,
    experiments.questions.working_memory,
    experiments.questions.long_term_memory,
):
    ignored_classes |= set(classes_of_module(question_module))

# a figure of the paper is computed from what was recorded rather than recorded itself,
# and it is regenerated whenever the database changes, so storing one would store an
# answer next to the rows it was read off. The same holds of a query card and of
# everything it is drawn from: a render holds a live mirror of the world and a drawn
# panel holds pixels, neither of which is anything a row could keep
for paper_module in (
    experiments.paper.camera_frame,
    experiments.paper.chart,
    experiments.paper.figure,
    experiments.paper.figure_set,
    experiments.paper.measurement,
    experiments.paper.outcomes,
    experiments.paper.panel,
    experiments.paper.plan_timeline,
    experiments.paper.pose_change,
    experiments.paper.queries,
    experiments.paper.query_card,
    experiments.paper.questions,
    experiments.paper.run_plan,
    experiments.paper.scene,
    experiments.paper.timeline,
):
    ignored_classes |= set(classes_of_module(paper_module))

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
