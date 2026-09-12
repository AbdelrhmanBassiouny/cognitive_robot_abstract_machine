"""
A callback that is paused lets a change go by, and says so.
"""

from __future__ import annotations

from dataclasses import dataclass

from semantic_digital_twin.callbacks.callback import ModelChangeCallback
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body


@dataclass(eq=False)
class CountsModelChanges(ModelChangeCallback):
    """
    Counts how often the world tells it the model changed.
    """

    changes: int = 0
    """
    How many changes it was told of.
    """

    def on_model_change(self, **kwargs) -> None:
        self.changes += 1


def test_a_paused_callback_says_so_and_lets_a_change_go_by() -> None:
    world = World()
    counts = CountsModelChanges(_world=world)
    assert not counts.paused

    counts.pause()
    with world.modify_world():
        world.add_body(Body(name="stood_while_paused"))

    assert counts.paused
    assert counts.changes == 0


def test_a_resumed_callback_is_told_of_the_next_change() -> None:
    world = World()
    counts = CountsModelChanges(_world=world)
    counts.pause()

    counts.resume()
    with world.modify_world():
        world.add_body(Body(name="stood_after_resuming"))

    assert not counts.paused
    assert counts.changes == 1
