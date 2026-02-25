import numpy as np

from krrood.entity_query_language.core.variable import Literal
from krrood.entity_query_language.query.match import (
    ProbableVariable,
    AttributeMatch,
    AbstractMatchExpression,
    construct_graph_and_get_root,
)
from krrood.rustworkx_utils import RWXNode
from random_events.interval import singleton, open, closed, closed_open
from random_events.product_algebra import SimpleEvent, Event
from random_events.variable import Continuous

from krrood.entity_query_language.factories import (
    variable,
    entity,
    and_,
    or_,
    match_variable,
    match,
    Entity,
    probable_variable,
    probable,
)
from krrood.probabilistic_knowledge.probable_variable import (
    QueryToRandomEventTranslator,
    is_disjunctive_normal_form,
    MatchToDAOTranslator,
)
from ..dataset.example_classes import Pose, Position, Orientation
from ..dataset.ormatic_interface import *  # type: ignore


def test_parameterizer_with_where():
    pose_variable = variable(Pose, None)

    q = entity(pose_variable).where(
        pose_variable.position.y > 0.0,
        pose_variable.position.x == 0.0,
        pose_variable.position.y < 10.0,
        pose_variable.position.z >= -1.0,
        pose_variable.position.z <= 1.0,
        pose_variable.orientation.x != 1.0,
    )
    t = QueryToRandomEventTranslator(q)
    r = t.translate()

    result_by_hand = SimpleEvent(
        {
            Continuous("Pose.orientation.x"): ~singleton(1.0),
            Continuous("Pose.position.y"): open(0.0, 10),
            Continuous("Pose.position.z"): closed(-1.0, 1.0),
            Continuous("Pose.position.x"): singleton(0.0),
        }
    )

    assert result_by_hand.as_composite_set() == r


def test_dnf_checking():
    pose_variable = variable(Pose, None)

    q1 = entity(pose_variable).where(
        and_(
            or_(
                pose_variable.position.y > 0,
                pose_variable.position.x == 0,
            ),
            or_(
                pose_variable.position.z >= -1,
                pose_variable.position.x == 0,
            ),
        )
    )

    assert not is_disjunctive_normal_form(q1)

    q2 = entity(pose_variable).where(
        or_(
            pose_variable.position.x == 0,
            and_(
                pose_variable.position.z >= -1,
                pose_variable.position.z <= 1,
                pose_variable.position.y < 10,
            ),
            and_(pose_variable.orientation.z > 0),
        )
    )
    assert is_disjunctive_normal_form(q2)

    t = QueryToRandomEventTranslator(q2)
    translated = t.translate()

    variables = [
        Continuous("Pose.position.x"),
        Continuous("Pose.position.y"),
        Continuous("Pose.position.z"),
        Continuous("Pose.orientation.z"),
    ]
    [p_x, p_y, p_z, o_z] = variables

    e1 = SimpleEvent(
        {
            p_x: singleton(0.0),
        }
    )
    e1.fill_missing_variables(variables)
    e2 = SimpleEvent(
        {
            p_z: closed(-1.0, 1.0),
            p_y: closed_open(-np.inf, 10.0),
        }
    )
    e2.fill_missing_variables(variables)
    e3 = SimpleEvent({o_z: open(0.0, np.inf)})
    e3.fill_missing_variables(variables)

    result_by_hand = Event(e1, e2, e3)

    assert (result_by_hand - translated).is_empty()
    assert (translated - result_by_hand).is_empty()


def test_query_writing_with_match():
    var: ProbableVariable = probable_variable(Pose)(
        position=probable(Position)(x=0.1, y=..., z=...), orientation=None
    )

    # Traversal directly using available attributes of MatchVariable and its children

    print(f"parent_var = {var}")
    assert isinstance(var, ProbableVariable)
    assert var.type is Pose

    position_attribute_var = var.children[0]
    print(f"position_attribute_var = {position_attribute_var}")
    assert position_attribute_var.attribute_name == "position"
    assert position_attribute_var.type is Position
    assert isinstance(position_attribute_var, AttributeMatch)
    assert position_attribute_var.parent is var

    assert len(position_attribute_var.children) == 3

    assert position_attribute_var.children[0].type is float
    assert position_attribute_var.children[0].attribute_name == "x"
    assert position_attribute_var.children[0].assigned_value == 0.1
    assert position_attribute_var.children[0].parent is position_attribute_var

    assert position_attribute_var.children[1].type is float
    assert position_attribute_var.children[1].attribute_name == "y"
    assert position_attribute_var.children[1].assigned_value == ...
    assert position_attribute_var.children[1].parent is position_attribute_var

    assert position_attribute_var.children[2].type is float
    assert position_attribute_var.children[2].attribute_name == "z"
    assert position_attribute_var.children[2].assigned_value == ...
    assert position_attribute_var.children[2].parent is position_attribute_var

    orientation_attribute_var = var.children[1]
    assert orientation_attribute_var.attribute_name == "orientation"
    assert orientation_attribute_var.type is Orientation
    assert orientation_attribute_var.assigned_value is None
    assert orientation_attribute_var.parent is var

    # Traversal using built rustworkx graph
    graph_root = construct_graph_and_get_root(var)
    graph_root.visualize()

    assert graph_root.data is var
    assert graph_root.parent is None
    assert graph_root.children[0].data is orientation_attribute_var
    assert graph_root.children[0].children == []
    assert graph_root.children[1].data is position_attribute_var
    assert graph_root.children[1].children[0].data.attribute_name == "z"
    assert graph_root.children[1].children[1].data.attribute_name == "y"
    assert graph_root.children[1].children[2].data.attribute_name == "x"

    query = var.expression
    translator = MatchToDAOTranslator(query)
    translator.translate()
