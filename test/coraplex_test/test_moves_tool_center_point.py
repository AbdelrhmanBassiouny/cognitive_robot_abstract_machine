import pytest

import coraplex.robot_plans.actions.composite.tool_based
import coraplex.robot_plans.actions.core.misc
import coraplex.robot_plans.actions.core.pick_up
import coraplex.robot_plans.actions.core.placing
import coraplex.robot_plans.actions.core.robot_body
from coraplex.plans.context_extensions import MotionToleranceConfig
from coraplex.robot_plans.mixins import MovesToolCenterPoint
from krrood.utils import recursive_subclasses

# %% the context an action moving the tool center point needs


@pytest.mark.parametrize(
    "action_type",
    recursive_subclasses(MovesToolCenterPoint),
    ids=lambda action_type: action_type.__name__,
)
def test_an_action_moving_the_tool_center_point_requires_the_motion_tolerances(
    action_type: type[MovesToolCenterPoint],
):
    assert MotionToleranceConfig in action_type.context_extensions_required_to_expand
