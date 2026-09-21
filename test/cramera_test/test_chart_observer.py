"""
Tests for watching an executing motion statechart.
"""

from .test_live_bridge import make_chart

from cramera.live.chart_observer import ChartObserver
from cramera.live.chart_structure import ObservationName

# %% what one tick of a statechart looks like


class TestSnapshotOfAnExecutingChart:
    """
    A statechart exists only while it is being ticked, so what a viewer shows of it --
    or what a recording keeps of it -- is a snapshot taken per tick.
    """

    def test_nothing_is_executing_before_a_chart_is_seen(self):
        assert ChartObserver().snapshot(None) is None

    def test_a_chart_is_snapshotted_with_its_nodes(self):
        snapshot = ChartObserver().snapshot(make_chart())

        assert [node.name for node in snapshot.nodes] == [
            "Goal",
            "MoveJoints",
            "JointGoalReached",
        ]

    def test_the_transitions_are_snapshotted_too(self):
        snapshot = ChartObserver().snapshot(make_chart())

        assert [edge.kind for edge in snapshot.edges] == ["START", "END"]

    def test_every_node_says_where_it_stands(self):
        snapshot = ChartObserver().snapshot(make_chart())

        assert [node.observation for node in snapshot.nodes] == [
            ObservationName.UNKNOWN,
            ObservationName.UNKNOWN,
            ObservationName.FALSE,
        ]

    def test_a_chart_that_has_not_moved_is_still_snapshotted(self):
        observer = ChartObserver()
        chart = make_chart()
        observer.snapshot(chart)

        assert observer.snapshot(chart) is not None

    def test_a_chart_whose_nodes_moved_is_snapshotted_again(self):
        observer = ChartObserver()
        observer.snapshot(make_chart())

        assert observer.snapshot(make_chart(life_cycle=(1, 2, 0))) is not None

    def test_the_title_travels_into_the_snapshot(self):
        snapshot = ChartObserver(title="PickUpAction").snapshot(make_chart())

        assert snapshot.title == "PickUpAction"


# %% what the live wire sends


class TestOnlyChangesGoOnTheWire:
    """
    A live viewer already holds the last chart it was sent, so re-sending an unchanged
    one is wasted traffic.

    A recording cannot dedupe that way: a tick with nothing to say
    there means the chart stopped, not that it stood still.
    """

    def test_the_first_look_is_a_change(self):
        assert ChartObserver().change(make_chart()) is not None

    def test_a_chart_that_has_not_moved_is_not_sent_twice(self):
        observer = ChartObserver()
        chart = make_chart()
        observer.change(chart)

        assert observer.change(chart) is None

    def test_a_chart_whose_nodes_moved_is_sent_again(self):
        observer = ChartObserver()
        observer.change(make_chart())

        assert observer.change(make_chart(life_cycle=(1, 2, 0))) is not None

    def test_nothing_executing_is_not_a_change(self):
        assert ChartObserver().change(None) is None
