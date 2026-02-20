from krrood.entity_query_language.factories import (
    match_variable,
    variable,
    entity,
    match,
    variable_from,
)
from krrood.entity_query_language.query_graph import QueryGraph
from krrood.ormatic.dao import to_dao
from krrood.probabilistic_knowledge.parameterizer import Parameterizer
from krrood.probabilistic_knowledge.probable_variable import (
    build_object_from_built_query,
)
from ..dataset.example_classes import Position, Pose, Orientation
from ..dataset.ormatic_interface import *


def test_parameterizer_with_where():
    pose = Pose(
        position=Position(..., ..., ...),
        orientation=Orientation(..., ..., ..., None),
    )

    pose_dao_variable = variable_from([to_dao(pose)])

    entity(pose_dao_variable).where(pose_dao_variable.position.y > 0)
