import operator

from .object_access_variable import ObjectAccessVariable
from ..entity_query_language.core.base_expressions import Selectable
from ..entity_query_language.core.variable import Variable, Literal
from ..entity_query_language.operators.comparator import Comparator
from ..entity_query_language.query_graph import QueryGraph
from ..ormatic.dao import get_dao_class


def build_object_from_built_query(query: Selectable):
    query.build()
    dao_class = get_dao_class(query.selected_variable._type_)
    assert dao_class
    dao_instance = dao_class()

    # Get the Where expression
    where_expr = query._where_expression_

    if not where_expr:
        return dao_class()

    # Get all descendants of the Where expression that are Comparators
    operations = [
        expr for expr in where_expr._descendants_ if isinstance(expr, Comparator)
    ]

    # check that it is always a comparison between a variable and a literal
    for operation in operations:
        assert isinstance(operation.left, Literal) or isinstance(
            operation.right, Literal
        )

    assignment_operations = [
        operation for operation in operations if operation.operation == operator.eq
    ]

    for assignment_operation in assignment_operations:
        object_assignment_variable = (
            ObjectAccessVariable.from_attribute_access_and_type(
                assignment_operation.left, assignment_operation.left._type_
            )
        )
