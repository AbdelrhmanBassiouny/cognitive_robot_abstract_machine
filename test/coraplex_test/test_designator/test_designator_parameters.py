"""
What a designator reports as the parameters it was described by.
"""

from inspect import signature

from coraplex.robot_plans.actions.core.pick_up import PickUpAction

# %% fields a base contributes for its own purposes


def test_the_parameters_are_the_ones_the_constructor_takes():
    """
    A field contributed by a base mixed in for something other than description is not
    one the designator was asked for, so it is not reported as a parameter.

    ..note:: :class:`~coraplex.robot_plans.mixins.ManipulatesBodies` inherits
        :class:`~krrood.symbol_graph.symbol_graph.Symbol`, which carries such a field.
    """
    constructor_parameters = list(signature(PickUpAction.__init__).parameters)[1:]

    reported = [action_field.name for action_field in PickUpAction.fields]

    assert sorted(reported) == sorted(constructor_parameters)
