"""
Tests for having a running Montessori sort insert a shape the viewer picked.

The viewer's side only queues a request; the sorting thread takes them one at a time, so
these check the handover between the two rather than any insertion actually running.
"""

from __future__ import annotations

import pytest

from cramera.live.action_execution import UnknownPerformableAction
from experiments.montessori.action_execution import SortingActionExecution
from experiments.montessori.performable_insertions import PerformableInsertion

CUBE_INSERTION = PerformableInsertion(
    name="insert cube", shape="cube", shape_key="square_hole", hole="square_hole"
)
"""
The insertion the scene of these tests offers.
"""

STAR_INSERTION = PerformableInsertion(
    name="insert star", shape="star", shape_key="star_hole", hole="star_hole"
)
"""
A second insertion, so the order requests are taken in has something to show.
"""


@pytest.fixture()
def execution() -> SortingActionExecution:
    """
    An execution offering both insertions, as a built world would.
    """
    execution = SortingActionExecution()
    execution.offer([CUBE_INSERTION, STAR_INSERTION])
    return execution


class TestQueueingWhatTheViewerAsksFor:
    def test_a_requested_insertion_waits_to_be_taken(self, execution):
        execution.perform(CUBE_INSERTION.name)

        assert execution.state().requested == [CUBE_INSERTION.name]
        assert execution.state().performing is None

    def test_an_insertion_this_scene_does_not_offer_is_refused(self, execution):
        with pytest.raises(UnknownPerformableAction):
            execution.perform("insert banana")

        assert execution.state().requested == []

    def test_a_refusal_names_the_insertions_this_scene_does_offer(self, execution):
        with pytest.raises(UnknownPerformableAction) as error:
            execution.perform("insert banana")

        assert error.value.offered == [CUBE_INSERTION.name, STAR_INSERTION.name]

    def test_a_scene_that_offers_nothing_refuses_everything(self):
        with pytest.raises(UnknownPerformableAction):
            SortingActionExecution().perform(CUBE_INSERTION.name)


class TestWhatTheSortingThreadTakes:
    def test_requests_are_taken_in_the_order_they_were_asked_for(self, execution):
        execution.perform(STAR_INSERTION.name)
        execution.perform(CUBE_INSERTION.name)

        assert execution.take_requested() == STAR_INSERTION
        assert execution.take_requested() == CUBE_INSERTION

    def test_nothing_asked_for_is_nothing_to_take(self, execution):
        assert execution.take_requested() is None

    def test_the_insertion_in_hand_is_the_one_being_performed(self, execution):
        execution.perform(CUBE_INSERTION.name)

        execution.take_requested()

        assert execution.state().performing == CUBE_INSERTION.name
        assert execution.state().requested == []

    def test_a_finished_insertion_leaves_nothing_being_performed(self, execution):
        execution.perform(CUBE_INSERTION.name)
        execution.take_requested()

        execution.finish_requested()

        assert execution.state().performing is None


class TestARebuiltWorld:
    def test_a_new_world_drops_the_requests_made_against_the_old_one(self, execution):
        """
        A restarted run replaces every body in the scene, so an insertion asked for
        before it names a shape that no longer exists.
        """
        execution.perform(CUBE_INSERTION.name)

        execution.offer([CUBE_INSERTION])

        assert execution.state().requested == []

    def test_a_new_world_offers_only_what_it_makes_possible(self, execution):
        execution.offer([CUBE_INSERTION])

        with pytest.raises(UnknownPerformableAction):
            execution.perform(STAR_INSERTION.name)
