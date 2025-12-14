from krrood.entity_query_language.core_entity import contains_all
from krrood.entity_query_language.entity import entity, set_of, let, contains, match_all
from krrood.entity_query_language.entity_result_processors import the, a, an
from semantic_digital_twin.spatial_types import Expression

from semantic_digital_twin.testing import world_setup
from semantic_digital_twin.world_description.degree_of_freedom import PositionVariable


def test_querying_equations(world_setup):
    results = list(an(entity(PositionVariable)).evaluate())
    expr = results[0] + results[1]
    expression = entity(Expression)
    found_expr = the(
        expression.where(
            expression.is_scalar(),
            contains(expression.free_variables(), results[0]),
            contains(expression.free_variables(), results[1]),
        ).evaluate()
    )

    found_expr = the(
        entity(Expression)(
            is_scalar=True, free_variables=contains_all([results[0], results[1]])
        )
    ).evaluate()

    assert found_expr is expr
