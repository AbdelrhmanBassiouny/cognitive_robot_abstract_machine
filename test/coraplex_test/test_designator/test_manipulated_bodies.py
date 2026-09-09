"""
What the actions that act on the scene say about the bodies they act on.

..note:: The symbol graph is shared by everything alive in the process, so a query over
    it is asserted by what it contains rather than by what it equals.
"""

from coraplex.datastructures.enums import Arms, ApproachDirection, VerticalAlignment
from coraplex.datastructures.grasp import GraspDescription
from coraplex.robot_plans.actions.core.pick_up import GraspingAction, PickUpAction
from coraplex.robot_plans.mixins import ManipulatesBodies
from krrood.entity_query_language.factories import an, entity, variable
from semantic_digital_twin.semantic_annotations.semantic_annotations import Milk


def _grasp_description(view) -> GraspDescription:
    """
    A grasp from the front with the left arm's end effector.

    :param view: The robot view the end effector is taken from.
    """
    return GraspDescription(
        ApproachDirection.FRONT,
        VerticalAlignment.NoAlignment,
        view.left_arm.end_effector,
    )


# %% what an action says it acts on


def test_an_action_on_an_annotation_names_the_body_it_is_rooted_at(
    immutable_model_world,
):
    """
    An action whose object is a semantic annotation acts on the body that annotation is
    rooted at, rather than on the annotation itself.
    """
    world, view, _ = immutable_model_world
    milk = world.get_semantic_annotations_by_type(Milk)[0]

    action = PickUpAction(milk, Arms.LEFT, _grasp_description(view))

    assert action.manipulated_bodies == [milk.root]


def test_an_action_on_a_body_names_that_body(immutable_model_world):
    """
    An action whose object is already a body acts on it as it stands.
    """
    world, view, _ = immutable_model_world
    body = world.get_semantic_annotations_by_type(Milk)[0].root

    action = GraspingAction(body, Arms.LEFT, _grasp_description(view))

    assert action.manipulated_bodies == [body]


# %% asking which actions acted on the scene


def test_both_kinds_of_action_answer_one_query(immutable_model_world):
    """
    Actions naming their object differently are still asked for as one kind, which is
    what makes the objects the robot acted on askable without naming every action that
    could have acted on them.
    """
    world, view, _ = immutable_model_world
    milk = world.get_semantic_annotations_by_type(Milk)[0]
    pick_up = PickUpAction(milk, Arms.LEFT, _grasp_description(view))
    grasp = GraspingAction(milk.root, Arms.LEFT, _grasp_description(view))

    manipulation = variable(ManipulatesBodies)
    answered = list(an(entity(manipulation)).evaluate())

    assert any(action is pick_up for action in answered)
    assert any(action is grasp for action in answered)
