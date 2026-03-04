from copy import deepcopy
from typing import Callable

import numpy as np
from random_events.interval import singleton, open, closed, closed_open
from random_events.product_algebra import SimpleEvent, Event
from random_events.variable import Continuous

from krrood.entity_query_language.factories import (
    variable,
    entity,
    and_,
    or_,
    underspecified,
)
from krrood.entity_query_language.query.match import (
    UnderspecifiedVariable,
)
from krrood.probabilistic_knowledge.parameterizer import (
    copy_partial_object,
    MatchParameterizer,
    UnderspecifiedToParametersTranslator,
)
from krrood.probabilistic_knowledge.probable_variable import (
    QueryToRandomEventTranslator,
    is_disjunctive_normal_form,
    MatchToInstanceTranslator,
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
    q.build()
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
    q1.build()

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
    q2.build()
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


def test_query_writing_with_match_and_copy():
    var: UnderspecifiedVariable = underspecified(Pose)(
        position=underspecified(Position)(x=0.1, y=..., z=...), orientation=None
    )

    translator = MatchToInstanceTranslator(var)
    obj = translator.translate()
    assert obj.position.x == 0.1
    assert obj.position.y == ...
    assert obj.position.z == ...
    assert obj.orientation is None

    copied = copy_partial_object(obj)
    assert obj is not copied
    assert obj == copied


def test_probable_variable_with_concrete_kwarg():
    probable_pose = underspecified(Pose)

    prob_q = probable_pose(
        position=underspecified(Position)(x=..., y=..., z=...),
        orientation=Orientation(x=0.0, y=0.0, z=0.0, w=1.0),
    ).where(probable_pose.variable.position.x > 0.5)

    instance = MatchToInstanceTranslator(prob_q).translate()
    assert instance.orientation == Orientation(x=0.0, y=0.0, z=0.0, w=1.0)

    parameters = MatchParameterizer(instance).parameterize()
    assert len(parameters.variables) == 7
    assert len(parameters.assignments) == 4


def test_new_underspecified_translator():
    probable_pose = underspecified(Pose)
    prob_q = probable_pose(
        position=underspecified(Position)(x=..., y=..., z=...),
        orientation=Orientation(x=0.0, y=0.0, z=0.0, w=1.0),
    ).where(probable_pose.variable.position.x > 0.5)

    a = UnderspecifiedToParametersTranslator(prob_q).parameterize()
    assignments = a.flat_assignments
    for v, k in assignments.items():
        if isinstance(k, type(...)):
            assignments[v] = 0.0

    a.apply_assignments(assignments)
    r = a.construct_instance()
    assert r == Pose(Position(0.0, 0.0, 0.0), Orientation(0.0, 0.0, 0.0, 1.0))
