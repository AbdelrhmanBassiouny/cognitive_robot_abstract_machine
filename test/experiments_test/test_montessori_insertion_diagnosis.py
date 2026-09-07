"""
Tests for working out why one insertion attempt did not put its shape in the box.

Every case is built from plain evidence — a few events and at most one exception — so
the ranking is exercised without running a simulation.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from coraplex.exceptions import MotionDidNotFinish
from coraplex.plans.failures import AllChildrenFailed, BodyUnfetchable
from giskardpy.qp.exceptions import SolverReturnedFailureError
from segmind.datastructures.events import (
    ContactEvent,
    InsertionEvent,
    LossOfContactEvent,
    PickUpEvent,
    SupportEvent,
)
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.geometry import Box, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body

from experiments.montessori.insertion_diagnosis import (
    InsertionDiagnosis,
    InsertionEvidence,
    InsertionFailureReason,
)

PICKED_UP_AT = datetime(2026, 8, 13, 12, 0, 0)
"""
When the shape leaves the table in every scenario that gets that far.
"""

INSERTION_STARTED_AT = PICKED_UP_AT + timedelta(seconds=10)
"""
When the attempt stops transporting and starts lowering the shape into its hole.
"""


@pytest.fixture()
def bodies():
    """
    A tracked shape, a gripper finger, and one unrelated body, all in one world.
    """
    world = World()
    built = {}
    with world.modify_world():
        root = Body(name=PrefixedName("root"))
        world.add_body(root)
        for name in ("shape", "finger", "table"):
            body = Body.from_shape_collection(
                PrefixedName(name),
                ShapeCollection([Box(scale=Scale(0.03, 0.03, 0.03))]),
            )
            world.add_body(body)
            world.add_connection(FixedConnection(parent=root, child=body))
            built[name] = body
    return built


def evidence_of(bodies, events, raised_exception=None) -> InsertionEvidence:
    """
    Evidence for one attempt, with the gripper and insertion phase already known.

    :param bodies: The world's bodies by name.
    :param events: The segmind events detected during the attempt.
    :param raised_exception: The exception the attempt raised, if any.
    """
    return InsertionEvidence(
        events=events,
        gripper_bodies=[bodies["finger"]],
        raised_exception=raised_exception,
        insertion_phase_started_at=INSERTION_STARTED_AT,
    )


def picked_up(bodies, at=PICKED_UP_AT) -> PickUpEvent:
    """
    A pick-up of the tracked shape.

    :param bodies: The world's bodies by name.
    :param at: When the pick-up was detected.
    """
    return PickUpEvent(tracked_object=bodies["shape"], timestamp=at)


def lost_contact_with(bodies, name, at) -> LossOfContactEvent:
    """
    The tracked shape losing contact with one other body.

    :param bodies: The world's bodies by name.
    :param name: Name of the body contact was lost with.
    :param at: When the loss of contact was detected.
    """
    return LossOfContactEvent(
        tracked_object=bodies["shape"], with_object=bodies[name], timestamp=at
    )


# %% the plan said what went wrong
class TestPlanFailureWins:
    def test_an_informative_plan_failure_is_the_reason(self, bodies):
        diagnosis = InsertionDiagnosis.of(
            evidence_of(
                bodies,
                [picked_up(bodies)],
                raised_exception=BodyUnfetchable(body=bodies["shape"], arm=None),
            )
        )

        assert diagnosis.reason is InsertionFailureReason.PLAN_FAILED
        assert "BodyUnfetchable" in diagnosis.detail

    def test_a_motion_failure_is_informative_too(self, bodies):
        diagnosis = InsertionDiagnosis.of(
            evidence_of(
                bodies,
                [picked_up(bodies)],
                raised_exception=MotionDidNotFinish(failed_motions=[]),
            )
        )

        assert diagnosis.reason is InsertionFailureReason.PLAN_FAILED

    def test_an_opaque_plan_failure_falls_through_to_the_events(self, bodies):
        """
        ``AllChildrenFailed`` swallows the reasons of the children that failed, so it
        names no cause of its own and the detected events have to supply one.
        """
        diagnosis = InsertionDiagnosis.of(
            evidence_of(
                bodies,
                [SupportEvent(tracked_object=bodies["shape"], timestamp=PICKED_UP_AT)],
                raised_exception=AllChildrenFailed(language_node=None),
            )
        )

        assert diagnosis.reason is InsertionFailureReason.NOT_PICKED_UP
        assert "AllChildrenFailed" in diagnosis.detail

    def test_an_exception_that_is_not_a_plan_failure_falls_through_too(self, bodies):
        """
        A solver error leaves no reason on any plan node, which is exactly the case the
        detected events exist to cover.
        """
        diagnosis = InsertionDiagnosis.of(
            evidence_of(
                bodies,
                [picked_up(bodies)],
                raised_exception=SolverReturnedFailureError(solver_status=None),
            )
        )

        assert diagnosis.reason is InsertionFailureReason.RELEASED_OFF_TARGET
        assert "SolverReturnedFailureError" in diagnosis.detail


# %% what segmind saw
class TestSegmindEvidence:
    def test_no_pick_up_among_the_events_is_the_reason(self, bodies):
        diagnosis = InsertionDiagnosis.of(
            evidence_of(
                bodies,
                [SupportEvent(tracked_object=bodies["shape"], timestamp=PICKED_UP_AT)],
            )
        )

        assert diagnosis.reason is InsertionFailureReason.NOT_PICKED_UP

    def test_letting_go_of_the_shape_before_the_insertion_phase_is_the_reason(
        self, bodies
    ):
        diagnosis = InsertionDiagnosis.of(
            evidence_of(
                bodies,
                [
                    picked_up(bodies),
                    lost_contact_with(
                        bodies, "finger", PICKED_UP_AT + timedelta(seconds=2)
                    ),
                ],
            )
        )

        assert diagnosis.reason is InsertionFailureReason.DROPPED_BEFORE_INSERTION
        assert "finger" in diagnosis.detail

    def test_letting_go_during_the_insertion_phase_is_the_intended_release(
        self, bodies
    ):
        """
        Releasing the shape over the hole is how an insertion ends, so the same event
        after the insertion phase began is not evidence of a drop.
        """
        diagnosis = InsertionDiagnosis.of(
            evidence_of(
                bodies,
                [
                    picked_up(bodies),
                    lost_contact_with(
                        bodies, "finger", INSERTION_STARTED_AT + timedelta(seconds=1)
                    ),
                ],
            )
        )

        assert diagnosis.reason is InsertionFailureReason.RELEASED_OFF_TARGET

    def test_losing_contact_with_something_other_than_the_gripper_is_not_a_drop(
        self, bodies
    ):
        diagnosis = InsertionDiagnosis.of(
            evidence_of(
                bodies,
                [
                    picked_up(bodies),
                    lost_contact_with(
                        bodies, "table", PICKED_UP_AT + timedelta(seconds=2)
                    ),
                ],
            )
        )

        assert diagnosis.reason is InsertionFailureReason.RELEASED_OFF_TARGET

    def test_losing_gripper_contact_before_the_pick_up_is_not_a_drop(self, bodies):
        diagnosis = InsertionDiagnosis.of(
            evidence_of(
                bodies,
                [
                    lost_contact_with(
                        bodies, "finger", PICKED_UP_AT - timedelta(seconds=2)
                    ),
                    picked_up(bodies),
                ],
            )
        )

        assert diagnosis.reason is InsertionFailureReason.RELEASED_OFF_TARGET

    def test_an_insertion_that_did_not_go_through_means_the_shape_is_wedged(
        self, bodies
    ):
        """
        Segmind saw the shape enter the hole, yet it is being asked why the shape is
        not in the box: it went in but did not go through.
        """
        diagnosis = InsertionDiagnosis.of(
            evidence_of(
                bodies,
                [
                    picked_up(bodies),
                    InsertionEvent(
                        tracked_object=bodies["shape"],
                        timestamp=INSERTION_STARTED_AT + timedelta(seconds=2),
                    ),
                ],
            )
        )

        assert diagnosis.reason is InsertionFailureReason.WEDGED_IN_HOLE

    def test_a_pick_up_with_no_insertion_means_it_was_released_off_target(self, bodies):
        diagnosis = InsertionDiagnosis.of(
            evidence_of(
                bodies,
                [
                    picked_up(bodies),
                    ContactEvent(
                        tracked_object=bodies["shape"],
                        with_object=bodies["table"],
                        timestamp=INSERTION_STARTED_AT,
                    ),
                ],
            )
        )

        assert diagnosis.reason is InsertionFailureReason.RELEASED_OFF_TARGET


# %% nothing to go on
class TestNoEvidence:
    def test_no_events_and_no_exception_is_undiagnosed(self, bodies):
        """
        An empty event list means nothing was observed, which is not the same as
        observing that the shape was never picked up.
        """
        diagnosis = InsertionDiagnosis.of(evidence_of(bodies, []))

        assert diagnosis.reason is InsertionFailureReason.UNDIAGNOSED

    def test_an_opaque_exception_with_no_events_still_names_the_exception(self, bodies):
        diagnosis = InsertionDiagnosis.of(
            evidence_of(
                bodies,
                [],
                raised_exception=SolverReturnedFailureError(solver_status=None),
            )
        )

        assert diagnosis.reason is InsertionFailureReason.UNDIAGNOSED
        assert "SolverReturnedFailureError" in diagnosis.detail

    def test_an_unknown_insertion_phase_does_not_hide_a_drop(self, bodies):
        """
        Without a recorded insertion phase every gripper release after the pick-up is
        still a drop, rather than silently becoming the intended one.
        """
        evidence = InsertionEvidence(
            events=[
                picked_up(bodies),
                lost_contact_with(
                    bodies, "finger", PICKED_UP_AT + timedelta(seconds=2)
                ),
            ],
            gripper_bodies=[bodies["finger"]],
        )

        assert (
            InsertionDiagnosis.of(evidence).reason
            is InsertionFailureReason.DROPPED_BEFORE_INSERTION
        )
