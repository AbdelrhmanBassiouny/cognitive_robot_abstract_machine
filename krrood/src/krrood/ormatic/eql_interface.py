from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing_extensions import Callable, Dict, Iterator, List, Any, Optional, Type
import operator

import sqlalchemy.inspection
from sqlalchemy import (
    and_,
    or_,
    select,
    Select,
    func,
    literal,
    case,
    not_ as sa_not,
    exists as sqlalchemy_exists,
    true,
)
from sqlalchemy.orm import Session, aliased
from sqlalchemy.types import Boolean, Numeric, Integer, String

from krrood.entity_query_language.query.query import (
    Query,
    Entity,
    SetOf,
    UnificationDict,
)
from krrood.entity_query_language.query.operations import Where
from krrood.entity_query_language.query.quantifiers import ResultQuantifier, An, The
from krrood.entity_query_language.operators.core_logical_operators import AND, OR, Not
from krrood.entity_query_language.operators.logical_quantifiers import (
    Exists as EQLExists,
)
from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.core.variable import (
    Variable,
    Literal,
    InstantiatedVariable,
)
from krrood.entity_query_language.core.mapped_variable import Attribute, FlatVariable
from krrood.entity_query_language.operators.comparator import Comparator
from krrood.entity_query_language.operators.aggregators import (
    Aggregator,
    CountAll,
    Count,
    Max,
    Min,
    Sum,
    Average,
)

from krrood.entity_query_language.operators.conditionals import CaseWhen
from krrood.exceptions import DataclassException
from krrood.ormatic.data_access_objects.helper import get_dao_class
from krrood.ormatic.data_access_objects.dao import AssociationDataAccessObject
from krrood.ormatic.exceptions import (
    NoDAOFoundForTypeError,
    NoDAOFoundForSelectionError,
)


@dataclass
class EQLTranslationError(DataclassException):
    """
    Base class for errors raised when an EQL expression cannot be translated into
    SQLAlchemy.
    """

    def suggest_correction(self) -> str:
        return ""


@dataclass
class UnsupportedQueryTypeError(EQLTranslationError, TypeError):
    """
    Raised when an EQL expression node has no SQLAlchemy translation.
    """

    query: SymbolicExpression
    """The EQL expression node whose type is not supported."""

    def error_message(self) -> str:
        return f"Unsupported query type: {type(self.query)}"

    def suggest_correction(self) -> str:
        return (
            "Express the query using supported constructs: entity() or set_of() combined "
            "with where(), and(), or(), not(), exists(), comparators or aggregators."
        )


@dataclass
class UnsupportedTranslationError(EQLTranslationError, TypeError):
    """
    Raised when an EQL construct cannot be translated into SQL that returns the same answers
    as its evaluation in memory.
    """

    expression: Any
    """The EQL expression that cannot be translated."""

    reason: str
    """Why the expression has no faithful SQL translation."""

    def error_message(self) -> str:
        name = getattr(self.expression, "_name_", type(self.expression).__name__)
        return f"Cannot translate {name} to SQL: {self.reason}"

    def suggest_correction(self) -> str:
        return "Evaluate this query in memory with EQL instead."


@dataclass
class UnsupportedOperatorError(EQLTranslationError, TypeError):
    """
    Raised when an EQL operator has no SQLAlchemy translation.
    """

    operation: Callable[[Any, Any], bool]
    """The operator callable that could not be mapped to a SQLAlchemy expression."""

    def error_message(self) -> str:
        return f"Unsupported operator: {self.operation}"

    def suggest_correction(self) -> str:
        return (
            "Use one of the supported operators: ==, !=, >, <, >=, <=, contains or in_."
        )


@dataclass
class UnsupportedQuantifierError(EQLTranslationError, TypeError):
    """
    Raised when an EQL result quantifier cannot be evaluated.
    """

    quantifier_type: Type[ResultQuantifier]
    """
    The result-quantifier kind that has no evaluation strategy.
    """

    def error_message(self) -> str:
        return f"Unsupported quantifier: {self.quantifier_type}"

    def suggest_correction(self) -> str:
        return "Wrap the query in a supported quantifier: an() or the()."


@dataclass
class AttributeResolutionError(EQLTranslationError, ValueError):
    """
    Base class for errors raised when an EQL attribute chain cannot be resolved to a
    column.
    """


@dataclass
class AttributeChainRootHasNoTypeError(AttributeResolutionError):
    """
    Raised when the root of an attribute chain carries no python type to resolve a DAO
    from.
    """

    attribute: Attribute
    """The attribute chain whose root variable has no associated class."""

    def error_message(self) -> str:
        return (
            f"Attribute chain {self.attribute} has a root that does not carry a class."
        )

    def suggest_correction(self) -> str:
        return "Create the root variable with an explicit type, e.g. variable(type_=YourClass)."


@dataclass
class DAOAttributeResolutionError(AttributeResolutionError):
    """
    Base class for attribute resolution errors that reference a specific DAO attribute.
    """

    dao_class: type
    """The DAO class involved in the failed resolution."""

    attribute_name: str
    """
    The attribute name that could not be resolved on the DAO class.
    """

    def mapped_column_names(self) -> List[str]:
        """
        :return: The names of all columns mapped on the DAO class.
        """
        return sorted(sqlalchemy.inspection.inspect(self.dao_class).columns.keys())

    def mapped_relationship_names(self) -> List[str]:
        """
        :return: The names of all relationships mapped on the DAO class.
        """
        return sorted(
            sqlalchemy.inspection.inspect(self.dao_class).relationships.keys()
        )


@dataclass
class MissingRelationshipError(DAOAttributeResolutionError):
    """
    Raised when an attribute chain hop expects a relationship the DAO does not define.
    """

    def error_message(self) -> str:
        return f"No relationship '{self.attribute_name}' found on {self.dao_class.__name__}."

    def suggest_correction(self) -> str:
        relationships = self.mapped_relationship_names()
        if not relationships:
            return f"{self.dao_class.__name__} maps no relationships to traverse."
        return f"Traverse one of the relationships on {self.dao_class.__name__}: {', '.join(relationships)}."


@dataclass
class NonRelationshipInChainError(DAOAttributeResolutionError):
    """
    Raised when a non-final attribute in a chain is a plain column rather than a
    relationship.
    """

    def error_message(self) -> str:
        return (
            f"Attribute '{self.attribute_name}' on {self.dao_class.__name__} is not a "
            f"relationship but the attribute chain continues."
        )

    def suggest_correction(self) -> str:
        relationships = self.mapped_relationship_names()
        if not relationships:
            return (
                f"End the chain at '{self.attribute_name}'; {self.dao_class.__name__} "
                f"maps no relationships to traverse further."
            )
        return (
            f"End the chain at '{self.attribute_name}', or continue through one of the "
            f"relationships on {self.dao_class.__name__}: {', '.join(relationships)}."
        )


@dataclass
class MissingColumnError(DAOAttributeResolutionError):
    """
    Raised when the leaf of an attribute chain is not a column on the DAO.
    """

    def error_message(self) -> str:
        return f"Column '{self.attribute_name}' not found on {self.dao_class.__name__}."

    def suggest_correction(self) -> str:
        return f"Use one of the columns on {self.dao_class.__name__}: {', '.join(self.mapped_column_names())}."


@dataclass
class EmptyAttributeChainError(AttributeResolutionError):
    """
    Raised when an attribute chain yields no attribute names to walk.
    """

    dao_class: type
    """
    The DAO class the empty chain started from.
    """

    attribute_names: List[str]
    """
    The (empty) list of attribute names collected from the chain.
    """

    def error_message(self) -> str:
        return (
            f"Attribute chain on {self.dao_class.__name__} produced no resolvable "
            f"attributes (names: {self.attribute_names})."
        )


@dataclass
class VariableTypeExtractor:
    """
    Extracts underlying Variable and its python type from a leaf-like node.
    """

    def extract(self, node: Any) -> tuple[Optional[Variable], Optional[type]]:
        """
        Extract variable and type from a node.

        :param node: The node to extract from
        :return: Tuple of (variable, type)
        """
        if isinstance(node, Variable):
            return node, node._type_

        if hasattr(node, "_var_"):
            var = node._var_
            if isinstance(var, Variable):
                return var, var._type_

        node_type = node._type_
        return None, node_type


@dataclass
class AttributeChainResolver:
    """
    Resolves attribute chains for EQL Attribute expressions.
    """

    def extract_leaf_variable(self, attribute: Attribute) -> Any:
        """
        Extract the leaf variable from an attribute chain.

        :param attribute: The attribute to extract from
        :return: The leaf variable or node
        """
        extractor = VariableTypeExtractor()
        node = attribute
        while isinstance(node, Attribute):
            node = node._child_
        var, _ = extractor.extract(node)
        return var or node

    def extract_base_dao(self, attribute: Attribute) -> Optional[type]:
        """
        Extract the base DAO class from an attribute chain.

        :param attribute: The attribute to extract from
        :return: The DAO class or None
        """
        extractor = VariableTypeExtractor()
        node = attribute
        while isinstance(node, Attribute):
            node = node._child_
        _, node_type = extractor.extract(node)
        return get_dao_class(node_type) if node_type is not None else None


@dataclass
class RelationshipResolver:
    """
    Resolves relationships and foreign keys for DAO classes.
    """

    def resolve_relationship_and_foreign_key(
        self, dao_class: type, attribute_name: str
    ) -> tuple[Any, Any]:
        """
        Resolve the relationship and foreign key column for a DAO attribute.

        :param dao_class: The DAO class
        :param attribute_name: The attribute name
        :return: Tuple of (relationship, foreign_key_column)
        """
        mapper = sqlalchemy.inspection.inspect(dao_class)
        relationship = self._find_relationship(mapper, attribute_name)

        if relationship is None:
            return None, None

        local_column = next(iter(relationship.local_columns))
        foreign_key_column = getattr(dao_class, local_column.key)
        return relationship, foreign_key_column

    def _find_relationship(self, mapper: Any, attribute_name: str) -> Any:
        """
        Find a relationship by name in a mapper or aliased mapper.

        :param mapper: The SQLAlchemy mapper or alias inspection
        :param attribute_name: The attribute name to find
        :return: The relationship or None
        """
        # Support both Mapper and AliasedInsp from sqlalchemy.inspection.inspect()
        relationships = None
        if hasattr(mapper, "relationships"):
            relationships = mapper.relationships
        elif hasattr(mapper, "mapper") and hasattr(mapper.mapper, "relationships"):
            relationships = mapper.mapper.relationships
        else:
            return None

        relationship = relationships.get(attribute_name)
        if relationship is not None:
            return relationship

        for rel in relationships:
            if rel.key == attribute_name:
                return rel

        return None


@dataclass
class OperatorMapper:
    """
    Maps EQL operators to SQLAlchemy expressions.
    """

    def map_comparison_operator(self, operation: Any, left: Any, right: Any) -> Any:
        """
        Map a comparison operator to a SQLAlchemy expression.

        :param operation: The operator
        :param left: Left operand
        :param right: Right operand
        :return: SQLAlchemy expression
        """
        operator_name = operation.__name__

        if operation is operator.eq or operator_name == "eq":
            return left == right
        if operation is operator.gt or operator_name == "gt":
            return left > right
        if operation is operator.lt or operator_name == "lt":
            return left < right
        if operation is operator.ge or operator_name == "ge":
            return left >= right
        if operation is operator.le or operator_name == "le":
            return left <= right
        if operation is operator.ne or operator_name == "ne":
            return self._not_equal(left, right)

        raise UnsupportedOperatorError(operation)

    @staticmethod
    def _not_equal(left: Any, right: Any) -> Any:
        """
        :return: ``left != right`` with Python's semantics for missing values, under which
            a missing value differs from every value except another missing one.
        """
        if hasattr(left, "is_distinct_from"):
            return left.is_distinct_from(right)
        if hasattr(right, "is_distinct_from"):
            return right.is_distinct_from(left)
        return left != right

    def map_contains_operator(self, operation: Any, left: Any, right: Any) -> Any:
        """
        Map a contains operator to a SQLAlchemy expression.

        :param operation: The operator
        :param left: Left operand
        :param right: Right operand
        :return: SQLAlchemy expression
        """
        operator_name = operation.__name__
        is_negated = operator_name == "not_contains"

        if isinstance(left, (list, tuple, set)):
            expression = right.in_(left)
        elif isinstance(right, (list, tuple, set)):
            expression = left.in_(right)
        elif isinstance(left, str) and not isinstance(right, str):
            expression = func.instr(literal(left), right) > 0
        elif not isinstance(left, str) and isinstance(right, str):
            if hasattr(left, "contains"):
                expression = left.contains(right)
            else:
                expression = left.like("%" + right + "%")
        elif isinstance(left, str) and isinstance(right, str):
            expression = literal(right in left)
        else:
            expression = func.instr(left, right) > 0

        return sa_not(expression) if is_negated else expression


@dataclass
class DomainValueExtractor:
    """
    Extracts values from EQL Variable/Literal domains.
    """

    session: Session

    def extract_from_literal(self, literal_node: Literal) -> Any:
        """
        Extract values from a Literal node.

        :param literal_node: The Literal node
        :return: The extracted value(s)
        """
        if not hasattr(literal_node, "_domain_"):
            return (
                literal_node.value if hasattr(literal_node, "value") else literal_node
            )

        values = [value for value in literal_node._re_enterable_domain_generator_]

        if len(values) > 1:
            return values
        if len(values) == 1:
            single_value = values[0]
            if isinstance(single_value, (list, tuple, set)):
                return single_value
            return single_value

        return literal_node.value if hasattr(literal_node, "value") else literal_node

    def extract_from_variable(self, variable: Variable) -> Any:
        """
        Extract a value from a Variable domain.

        :param variable: The Variable
        :return: The extracted value
        """
        if not hasattr(variable, "_domain_"):
            return variable.value if hasattr(variable, "value") else variable

        try:
            sample = next(iter(variable._re_enterable_domain_generator_)).value
        except (StopIteration, AttributeError):
            return variable.value if hasattr(variable, "value") else variable

        if isinstance(variable, Literal):
            return sample

        dao_class = get_dao_class(type(sample))
        if dao_class is None:
            return sample

        if isinstance(sample, dao_class):
            return sample.id if hasattr(sample, "id") else sample

        return self._resolve_dao_instance(sample, dao_class)

    def _resolve_dao_instance(self, sample: Any, dao_class: type) -> Any:
        """
        Resolve a DAO instance from a sample entity.

        :param sample: The sample entity
        :param dao_class: The DAO class
        :return: The DAO id or the sample itself
        """
        filters = {}
        if hasattr(sample, "id_"):
            filters["id_"] = sample.id_
        elif hasattr(sample, "name"):
            filters["name"] = sample.name

        if filters:
            dao_instance = self.session.query(dao_class).filter_by(**filters).first()
            if dao_instance is not None:
                return dao_instance.id if hasattr(dao_instance, "id") else dao_instance

        return sample


@dataclass
class JoinManager:
    """
    Manages JOIN operations for the EQL translator.

    Tracks both which relationship paths have been joined and the SQLAlchemy alias used
    for each path so that downstream column references can bind to the correct FROM
    element without triggering implicit joins.
    """

    aliases_by_path: dict[tuple[type, str], Any] = field(default_factory=dict)
    joined_tables: set[type] = field(default_factory=set)

    def add_path_join(self, dao_class: type, attribute_name: str, alias: Any) -> None:
        """
        Register a path-based JOIN and its alias.

        :param dao_class: The DAO class
        :param attribute_name: The attribute name
        :param alias: The SQLAlchemy aliased entity used for the join
        """
        self.aliases_by_path[(dao_class, attribute_name)] = alias

    def is_path_joined(self, dao_class: type, attribute_name: str) -> bool:
        """
        Check if a path has already been joined.

        :param dao_class: The DAO class
        :param attribute_name: The attribute name
        :return: True if already joined
        """
        return (dao_class, attribute_name) in self.aliases_by_path

    def get_alias_for_path(self, dao_class: type, attribute_name: str) -> Any:
        """
        Get the alias associated with a previously joined path.
        """
        return self.aliases_by_path.get((dao_class, attribute_name))

    def add_table_join(self, dao_class: type) -> None:
        """
        Register a table-level JOIN.

        :param dao_class: The DAO class
        """
        self.joined_tables.add(dao_class)

    def is_table_joined(self, dao_class: type) -> bool:
        """
        Check if a table has already been joined.

        :param dao_class: The DAO class
        :return: True if already joined
        """
        return dao_class in self.joined_tables


@dataclass
class EQLTranslator:
    """
    Translate an EQL query into an SQLAlchemy query.
    """

    eql_query: Query
    session: Session

    sql_query: Optional[Select] = None
    join_manager: JoinManager = field(default_factory=JoinManager)

    elements_by_node: Dict[int, Any] = field(default_factory=dict)
    """
    The FROM element (a DAO class or an alias of one) that each variable and each flattened
    collection of the query ranges over, keyed by the id of its EQL node.
    """

    collection_mode: bool = False
    """
    True if the query uses a collection-valued attribute. Every variable is then bound to
    one FROM element, so that all its uses refer to the same rows.
    """

    joins_forbidden: bool = False
    """
    True while a condition inside an EXISTS subquery is translated, where a new JOIN would
    change the outer query instead of the subquery.
    """

    @property
    def quantifier_type(self) -> Type[ResultQuantifier]:
        """
        :return: The result-quantifier kind (``An`` / ``The``) requested by the query.
        """
        return self.eql_query._quantifier_builder_.type

    @property
    def select_like(self) -> Query:
        """
        Get the select-like expression from the query.
        """
        return self.eql_query

    @property
    def root_condition(self) -> SymbolicExpression:
        """
        Get the root condition from the query.
        """
        return self.eql_query._conditions_root_

    @staticmethod
    def _require_dao_class(domain_type: type) -> type:
        """
        Resolve the DAO class for a domain type, raising when none exists.

        :param domain_type: The domain type whose DAO is required.
        :raises NoDAOFoundForTypeError: When the type has no associated DAO.
        """
        dao_class = get_dao_class(domain_type)
        if dao_class is None:
            raise NoDAOFoundForTypeError(domain_type)
        return dao_class

    def translate(self) -> None:
        self._reject_inference()
        self._bind_selected_variables()
        self.collection_mode = self._uses_collections()
        if isinstance(self.eql_query, Entity):
            self._translate_entity()
        elif isinstance(self.eql_query, SetOf):
            self._translate_set_of()
        else:
            raise UnsupportedQueryTypeError(self.eql_query)

    def _reject_inference(self) -> None:
        """
        :raises UnsupportedTranslationError: When the query selects an object that a rule
            derives, which a database query cannot create.
        """
        for selected in self.select_like._selected_variables_:
            if isinstance(selected, InstantiatedVariable):
                raise UnsupportedTranslationError(
                    selected, "an inference rule derives new objects"
                )

    def _uses_collections(self) -> bool:
        """
        :return: True if the query has a flattened collection or tests membership in a
            collection-valued attribute.
        """
        roots = [
            self.eql_query._where_expression_,
            getattr(self.eql_query._having_builder_, "conditions_expression", None),
            *self.select_like._selected_variables_,
        ]
        return any(
            self._has_collection_node(root) for root in roots if root is not None
        )

    def _has_collection_node(self, expression: Any) -> bool:
        """
        :return: True if the expression tree contains a flattened collection or a
            membership test on a collection-valued attribute.
        """
        visited = set()
        pending = [expression]
        while pending:
            node = pending.pop()
            if id(node) in visited:
                continue
            visited.add(id(node))
            if isinstance(node, FlatVariable):
                return True
            if isinstance(node, Comparator) and self._is_membership_in_collection(node):
                return True
            pending.extend(self._children_of(node))
        return False

    @staticmethod
    def _children_of(expression: Any) -> List[Any]:
        """
        :return: The child expressions of an EQL expression. The fields are read from the
            instance dictionary, because reading a missing attribute of a symbolic variable
            builds a new symbolic attribute instead of failing.
        """
        fields = vars(expression) if hasattr(expression, "__dict__") else {}
        children = [
            fields.get(name) for name in ("_child_", "left", "right", "condition")
        ]
        children.extend(fields.get("_children_", ()) or ())
        if isinstance(expression, EQLExists):
            children.extend((expression.variable, expression.condition))
        return [child for child in children if isinstance(child, SymbolicExpression)]

    def _bind_selected_variables(self) -> None:
        """
        Bind every selected variable to the DAO class that the SELECT clause ranges over.
        """
        for selected in self.select_like._selected_variables_:
            if isinstance(selected, Variable) and not isinstance(selected, Literal):
                dao_class = get_dao_class(selected._type_)
                if dao_class is not None:
                    self.elements_by_node[id(selected)] = dao_class

    def _translate_entity(self) -> None:
        """
        Translate the EQL query to SQL.
        """
        selected = self.select_like.selected_variable
        if self.collection_mode:
            self._translate_selection_of_elements([selected])
        elif isinstance(selected, Attribute):
            self._translate_entity_from_attribute(selected)
        else:
            self.sql_query = select(self._require_dao_class(selected._type_))
        self._apply_clauses()

    def _translate_entity_from_attribute(self, attribute: Attribute) -> None:
        """
        Translate ``entity(n.attr1.attr2...)`` when the selected variable is an
        attribute chain.

        Walks every hop in the chain from the root DAO outward, building JOIN clauses
        via :meth:`_apply_relationship_join` so that path tracking is consistent with
        subsequent WHERE clause translations that traverse the same chain.

        :param attribute: The outermost :class:`Attribute` node used as selected
            variable.
        :raises NoDAOFoundForTypeError: When the root variable type has no DAO.
        :raises MissingRelationshipError: When any hop in the chain is not a
            relationship.
        """
        attribute_names = self._collect_attribute_chain(attribute)
        base_class = self._extract_base_class(attribute)
        current_dao = self._require_dao_class(base_class)

        rel_resolver = RelationshipResolver()
        self.sql_query = select(current_dao)

        for attr_name in attribute_names:
            mapper = sqlalchemy.inspection.inspect(current_dao)
            relationship = rel_resolver._find_relationship(mapper, attr_name)
            if relationship is None:
                raise MissingRelationshipError(current_dao, attr_name)
            alias = self._apply_relationship_join(current_dao, attr_name, relationship)
            current_dao = alias or relationship.entity.class_

        self.sql_query = self.sql_query.with_only_columns(current_dao)

    def _translate_set_of(self) -> None:
        """
        Translate logic for set_of() queries.

        Supports two cases:

        Case 1 — Attribute variables:

        .. code-block:: python

            b = variable(type_=Body, domain=[])
            query = an(set_of(b.size, b.name))
            # → SELECT size, name FROM BodyDAO

        Case 2 — Entity variables:

        .. code-block:: python

            C = variable(Container, domain=world.bodies)
            H = variable(Handle, domain=world.bodies)
            query = an(set_of(C, H).where(C == FC.parent))
            # → SELECT ContainerDAO.*, HandleDAO.* FROM ... JOIN ...
        """
        selected = self.select_like._selected_variables_

        all_variables = all(
            isinstance(v, Variable) and not isinstance(v, Attribute) for v in selected
        )

        if self.collection_mode:
            self._translate_selection_of_elements(selected)
            self._apply_clauses()
            return
        if all_variables:
            dao_classes = [self._require_dao_class(var._type_) for var in selected]
            self.sql_query = select(*dao_classes)
        else:
            base_dao = None
            for var in selected:
                base_dao = self._extract_dao_from_expression(var)
                if base_dao is not None:
                    break

            if base_dao is None:
                base_dao = self._extract_dao_from_where_clause()
            if base_dao is None:
                raise NoDAOFoundForSelectionError(selected)

            self.sql_query = select(base_dao)
            columns = [self._translate_comparator_operand(var) for var in selected]
            self.sql_query = self.sql_query.with_only_columns(*columns)

        self._apply_clauses()

    # %% Elements of collection-valued attributes

    def _translate_selection_of_elements(self, selected: List[Any]) -> None:
        """
        Select variables, flattened collections and attributes, joining every flattened
        collection through its relationship, as ``set_of(m, flat_variable(m.is_member_of))``
        becomes ``SELECT MemberDAO, OrganizationDAO_1 FROM MemberDAO JOIN ... ON ...``.

        :param selected: The selected expressions.
        """
        first_root = self._chain_root(selected[0])
        while isinstance(first_root, FlatVariable):
            first_root = self._chain_root(first_root._child_)
        self.sql_query = select(self._element_of(first_root))
        for expression in selected:
            if expression is not first_root and self._is_plain_variable(expression):
                self.elements_by_node[id(expression)] = self._aliased_into_from(
                    expression
                )
        columns = [self._selected_column(expression) for expression in selected]
        self.sql_query = self.sql_query.with_only_columns(*columns)

    def _selected_column(self, expression: Any) -> Any:
        """
        :return: The FROM element of a selected variable or flattened collection, or the
            column of a selected attribute.
        """
        if isinstance(expression, Attribute):
            return self.translate_attribute(expression)
        return self._element_of(expression)

    @staticmethod
    def _chain_root(expression: Any) -> Any:
        """
        :return: The node an attribute chain starts from, or the expression itself.
        """
        while isinstance(expression, Attribute):
            expression = expression._child_
        return expression

    def _element_of(self, node: Any) -> Any:
        """
        :param node: A variable or a flattened collection.
        :return: The FROM element the node ranges over: the DAO class of a variable, or an
            alias of the element DAO, joined to its owner, for a flattened collection.
        """
        element = self.elements_by_node.get(id(node))
        if element is not None:
            return element
        if isinstance(node, FlatVariable):
            element = self._join_element(node)
        elif self._is_plain_variable(node):
            element = (
                self._aliased_into_from(node)
                if self.sql_query is not None and self.elements_by_node
                else self._require_dao_class(node._type_)
            )
        else:
            raise UnsupportedTranslationError(
                node, "only variables and flattened collections range over tables"
            )
        self.elements_by_node[id(node)] = element
        return element

    @staticmethod
    def _is_plain_variable(node: Any) -> bool:
        """
        :return: True if the node is a variable that ranges over the instances of a class.
        """
        return isinstance(node, Variable) and not isinstance(node, Literal)

    def _aliased_into_from(self, variable: Variable) -> Any:
        """
        Add an alias of the DAO class of a variable to the FROM clause, as a join that is
        always true, since the variable ranges over all instances independently. Every DAO
        shares the tables of its base classes, so a second variable needs its own alias of
        all of them; a plain ``select_from`` would also split the inheritance join of the
        selected DAO into unjoined tables.

        :return: The alias.
        """
        self._require_joins_allowed(variable)
        alias = aliased(self._require_dao_class(variable._type_), flat=True)
        self.sql_query = self.sql_query.join(alias, true())
        return alias

    def _join_element(self, flat: FlatVariable) -> Any:
        """
        Join aliases along the relationship of a flattened collection, from the element
        of its owner to the elements of the collection.

        :return: The alias of the element DAO.
        """
        collection = flat._child_
        if not isinstance(collection, Attribute):
            raise UnsupportedTranslationError(
                flat, "only collections reached by attribute access are stored"
            )
        names = self._collect_attribute_chain(collection)
        owner = self._walk_references(
            self._element_of(self._chain_root(collection)), names[:-1], collection
        )
        owner, steps = self._collection_steps(owner, names[-1], collection)
        for name, relationship in steps:
            alias = aliased(relationship.entity.class_, flat=True)
            self._require_joins_allowed(flat)
            self.sql_query = self.sql_query.join(
                alias, getattr(owner, name).of_type(alias)
            )
            owner = alias
        return owner

    def _collection_steps(
        self, owner: Any, name: str, expression: Any
    ) -> tuple[Any, List[tuple[str, Any]]]:
        """
        Resolve the relationships from an owner to the elements of its collection
        ``name``. ORMatic stores a collection as association objects, each of which refers
        to one element through its ``target``, so the elements are usually two steps away.

        :return: The FROM element that owns the collection, and the steps as pairs of an
            attribute name and its relationship.
        :raises UnsupportedTranslationError: When ``name`` is not a stored collection.
        """
        owner, relationship = self._resolve_relationship(owner, name)
        if relationship is None or not relationship.uselist:
            raise UnsupportedTranslationError(
                expression, f"{name} is not a stored collection"
            )
        steps = [(name, relationship)]
        association = relationship.entity.class_
        if issubclass(association, AssociationDataAccessObject):
            mapper = sqlalchemy.inspection.inspect(association)
            steps.append(("target", mapper.relationships["target"]))
        return owner, steps

    def _exists_along(
        self, links: List[tuple[Any, str, Any, Any]], criterion: Optional[Any]
    ) -> Any:
        """
        Nest correlated EXISTS subqueries along relationship steps, innermost last.

        :param links: Tuples of a source FROM element, an attribute name, its relationship
            and the alias of its target.
        :param criterion: The condition on the innermost alias, or None for none.
        :return: The outermost EXISTS expression.
        """
        for source, name, relationship, alias in reversed(links):
            attribute = getattr(source, name).of_type(alias)
            quantify = attribute.any if relationship.uselist else attribute.has
            criterion = quantify() if criterion is None else quantify(criterion)
        return criterion

    @staticmethod
    def _aliased_links(
        owner: Any, steps: List[tuple[str, Any]]
    ) -> List[tuple[Any, str, Any, Any]]:
        """
        :return: The steps from ``owner``, each with a new alias of its target.
        """
        links = []
        for name, relationship in steps:
            alias = aliased(relationship.entity.class_, flat=True)
            links.append((owner, name, relationship, alias))
            owner = alias
        return links

    def _start_of_chain(self, attribute: Attribute) -> Any:
        """
        :return: The FROM element an attribute chain starts from.
        """
        root = self._chain_root(attribute)
        if (
            isinstance(root, FlatVariable)
            or id(root) in self.elements_by_node
            or (self.collection_mode and self._is_plain_variable(root))
        ):
            return self._element_of(root)
        base_class = self._extract_base_class(attribute)
        if base_class is None:
            raise AttributeChainRootHasNoTypeError(attribute)
        return self._require_dao_class(base_class)

    def _walk_references(self, current: Any, names: List[str], chain: Any) -> Any:
        """
        Join the single-valued references named by ``names``, starting at ``current``.

        :return: The FROM element reached.
        :raises UnsupportedTranslationError: When a name is a collection or not a
            relationship.
        """
        for name in names:
            current, relationship = self._resolve_relationship(current, name)
            if relationship is None:
                raise NonRelationshipInChainError(current, name)
            if relationship.uselist:
                raise UnsupportedTranslationError(
                    chain,
                    f"{name} is a collection; range over its elements with flat_variable",
                )
            alias = self._apply_relationship_join(current, name, relationship)
            current = alias or relationship.entity.class_
        return current

    def _resolve_relationship(
        self, current: Any, name: str, join: bool = True
    ) -> tuple[Any, Any]:
        """
        Find the relationship ``name`` of ``current``. A role declares only its own
        attributes and delegates the others to its role taker, so when ``current`` has no
        attribute ``name`` but has a role taker, the role taker is searched, and joined if
        ``join`` is True. Otherwise, when only a subclass declares ``name``, as in Python,
        only the instances of that subclass have the attribute, so the subclass is
        searched, and joined if ``join`` is True.

        :return: The FROM element that has the attribute and its relationship, or None if
            the attribute is a column.
        """
        resolver = RelationshipResolver()
        while True:
            mapper = sqlalchemy.inspection.inspect(current)
            relationship = resolver._find_relationship(mapper, name)
            if relationship is not None or hasattr(current, name):
                return current, relationship
            role_taker = resolver._find_relationship(mapper, "role_taker")
            if role_taker is None:
                subclass = self._subclass_declaring(current, name)
                if subclass is None:
                    return current, None
                current = self._join_subclass(current, subclass) if join else subclass
                continue
            if not join:
                current = role_taker.entity.class_
                continue
            alias = self._apply_relationship_join(current, "role_taker", role_taker)
            current = alias or role_taker.entity.class_

    @staticmethod
    def _subclass_declaring(current: Any, name: str) -> Optional[type]:
        """
        :return: The DAO class of the first subclass of ``current`` that declares the
            attribute ``name``, or None.
        """
        mapper = sqlalchemy.inspection.inspect(current)
        mapper = getattr(mapper, "mapper", mapper)
        for descendant in mapper.self_and_descendants:
            if descendant is not mapper and name in descendant.attrs:
                return descendant.class_
        return None

    def _join_subclass(self, current: Any, subclass: type) -> Any:
        """
        Narrow ``current`` to the instances of one of its subclasses by joining an alias of
        the subclass on the same database id.

        :return: The alias.
        """
        self._require_joins_allowed(subclass)
        alias = aliased(subclass, flat=True)
        self.sql_query = self.sql_query.join(
            alias, alias.database_id == current.database_id
        )
        return alias

    def _narrow_last_link(
        self, links: List[tuple[Any, str, Any, Any]], name: str
    ) -> Any:
        """
        When the target of the last link lacks the attribute ``name`` that a subclass
        declares, replace its alias by an alias of the subclass, so that the next
        quantifier ranges only over the instances that have the attribute.

        :return: The alias of the last link.
        """
        source, link_name, relationship, alias = links[-1]
        if hasattr(alias, name):
            return alias
        subclass = self._subclass_declaring(alias, name)
        if subclass is None:
            return alias
        narrowed = aliased(subclass, flat=True)
        links[-1] = (source, link_name, relationship, narrowed)
        for node_id, element in list(self.elements_by_node.items()):
            if element is alias:
                self.elements_by_node[node_id] = narrowed
        return narrowed

    def _require_joins_allowed(self, expression: Any) -> None:
        """
        :raises UnsupportedTranslationError: While translating inside an EXISTS subquery.
        """
        if self.joins_forbidden:
            raise UnsupportedTranslationError(
                expression,
                "inside an existential quantifier over a collection, conditions may "
                "only read the columns of the quantified elements and of the outer "
                "elements",
            )

    @contextmanager
    def _subquery_scope(self) -> Iterator[None]:
        """
        Forbid joins while a condition of an EXISTS subquery is translated.
        """
        previous = self.joins_forbidden
        self.joins_forbidden = True
        try:
            yield
        finally:
            self.joins_forbidden = previous

    def _extract_dao_from_expression(self, expression: Any) -> Optional[type]:
        """
        Extract the base DAO class from an expression node.

        Handles Attribute chains and CaseWhen nodes.
        """
        if isinstance(expression, Attribute):
            resolver = AttributeChainResolver()
            return resolver.extract_base_dao(expression)
        if isinstance(expression, CaseWhen):
            return self._extract_dao_from_expression(expression.then_value)
        if isinstance(expression, Aggregator):
            if hasattr(expression, "_child_"):
                return self._extract_dao_from_expression(expression._child_)
        return None

    def _extract_dao_from_where_clause(self) -> Optional[type]:
        """
        Extract a base DAO class by scanning the WHERE clause for variable types.

        Used as a fallback when the selected expressions (e.g. ``count_all()``) carry no
        DAO information of their own.

        :return: The first DAO class found in the WHERE clause, or None.
        """
        if self.eql_query._where_expression_ is None:
            return None
        return self._find_dao_in_expression(self.eql_query._where_expression_)

    def _find_dao_in_expression(self, expression: Any) -> Optional[type]:
        """
        Recursively walk an EQL expression tree to find the first DAO-bearing variable.

        :param expression: The EQL expression node to search.
        :return: The first DAO class found, or None.
        """
        if isinstance(expression, Attribute):
            return AttributeChainResolver().extract_base_dao(expression)
        if isinstance(expression, Variable) and not isinstance(expression, Literal):
            dao = get_dao_class(expression._type_)
            if dao is not None:
                return dao
        for child_attr in (
            "_child_",
            "left",
            "right",
            "condition",
            "then_value",
            "else_value",
        ):
            child = getattr(expression, child_attr, None)
            if child is not None:
                result = self._find_dao_in_expression(child)
                if result is not None:
                    return result
        if hasattr(expression, "_children_"):
            for child in expression._children_:
                result = self._find_dao_in_expression(child)
                if result is not None:
                    return result
        return None

    def _apply_clauses(self) -> None:
        """
        Apply WHERE, GROUP BY, HAVING, ORDER BY and LIMIT to the SQL query.
        """
        if self.eql_query._where_expression_ is not None:
            conditions = self.translate_condition(self.eql_query._where_expression_)
            if conditions is not None:
                self.sql_query = self.sql_query.where(conditions)

        if self.eql_query._grouped_by_builder_ is not None:
            columns = [
                self.translate_attribute(var)
                for var in self.eql_query._grouped_by_builder_.variables_to_group_by
                if isinstance(var, Attribute)
            ]
            if columns:
                self.sql_query = self.sql_query.group_by(*columns)

        if self.eql_query._having_builder_ is not None:
            having = self.translate_condition(
                self.eql_query._having_builder_.conditions_expression
            )
            if having is not None:
                self.sql_query = self.sql_query.having(having)

        if self.eql_query._ordered_by_builder_ is not None:
            ordered_by_variable = self.eql_query._ordered_by_builder_.variable
            if isinstance(ordered_by_variable, Attribute):
                col = self.translate_attribute(ordered_by_variable)
            else:
                col = self._translate_comparator_operand(ordered_by_variable)
            if self.eql_query._ordered_by_builder_.descending:
                col = col.desc()
            self.sql_query = self.sql_query.order_by(col)

        if self.eql_query._limit_ is not None:
            self.sql_query = self.sql_query.limit(self.eql_query._limit_)

        if self.eql_query._distinct_on:
            self.sql_query = self.sql_query.distinct()

    def evaluate(self) -> List[Any]:
        """
        Evaluate the translated SQL query.

        For entity() queries, returns a list of DAO objects. For set_of() queries with
        multiple variables, returns a list of dicts mapping each EQL variable to its
        corresponding DAO object.

        :return: Query results
        """
        if isinstance(self.select_like, SetOf):
            return self._evaluate_set_of()

        bound_query = self.session.scalars(self.sql_query)

        if issubclass(self.quantifier_type, The):
            return [bound_query.one()]

        elif issubclass(self.quantifier_type, An):
            return bound_query.all()

        raise UnsupportedQuantifierError(self.quantifier_type)

    def _evaluate_set_of(self) -> List[Any]:
        """
        Evaluate a set_of() query.

        For Attribute variables: returns a list of dicts mapping each EQL variable
        to its corresponding column value.
        For Entity variables: returns a list of dicts mapping each EQL variable
        to its corresponding DAO object.

        :return: List of dicts mapping each variable to its value
        """
        selected = self.select_like._selected_variables_
        all_variables = all(
            isinstance(v, Variable) and not isinstance(v, Attribute) for v in selected
        )

        rows = self.session.execute(self.sql_query).all()

        if all_variables:
            # Entity variables — map each variable to its DAO object per row
            return [
                UnificationDict({var: dao for var, dao in zip(selected, row)})
                for row in rows
            ]

        # Attribute variables — map each variable to its column value per row
        return [
            UnificationDict({var: value for var, value in zip(selected, row)})
            for row in rows
        ]

    def __iter__(self):
        """
        Iterate over evaluation results.
        """
        yield from self.evaluate()

    def translate_query(self, query: SymbolicExpression) -> Optional[Any]:
        """
        Translate an EQL query expression to SQL.

        :param query: The EQL query expression
        :return: SQLAlchemy expression or None
        """
        match query:
            case AND():
                return self.translate_and(query)
            case OR():
                return self.translate_or(query)
            case Not():
                return self._translate_negation(query._child_)
            case EQLExists():
                return self._translate_exists(query)
            case Comparator():
                return self.translate_comparator(query)
            case Attribute():
                return self.translate_attribute(query)
            case Where():
                return self.translate_condition(query.condition)
            case CaseWhen():
                return self.translate_case_when(query)
            case Variable():
                return None
            case _:
                raise UnsupportedQueryTypeError(query)

    def translate_case_when(self, query: CaseWhen) -> Any:
        """
        Translate EQL-node CaseWhen in a native SQLAlchemy case()-construct.
        """
        compiled_condition = self.translate_query(query.condition)

        compiled_then = self._translate_comparator_operand(query.then_value)

        compiled_else = None
        if query.else_value is not None:
            compiled_else = self._translate_comparator_operand(query.else_value)

        return case((compiled_condition, compiled_then), else_=compiled_else)

    def translate_and(self, query: AND) -> Optional[Any]:
        """
        Translate an eql.AND query into an sql.AND.

        :param query: EQL query
        :return: SQL expression or None if all parts are handled via JOINs.
        """
        parts = self._collect_logical_parts(query)
        return self._combine_logical_parts(parts, and_)

    def translate_or(self, query: OR) -> Optional[Any]:
        """
        Translate an eql.OR query into an sql.OR.

        :param query: EQL query
        :return: SQL expression or None if all parts are handled via JOINs.
        """
        parts = self._collect_logical_parts(query)
        return self._combine_logical_parts(parts, or_)

    def _collect_logical_parts(self, query: Any) -> List[Any]:
        """
        Collect parts from a binary logical expression.

        :param query: The logical expression (AND/OR)
        :return: List of translated parts
        """
        parts = []

        if hasattr(query, "left") and hasattr(query, "right"):
            left_part = self.translate_condition(query.left)
            right_part = self.translate_condition(query.right)
            if left_part is not None:
                parts.append(left_part)
            if right_part is not None:
                parts.append(right_part)
        else:
            children = query._children_ if hasattr(query, "_children_") else []
            for child in children:
                part = self.translate_condition(child)
                if part is not None:
                    parts.append(part)

        return parts

    def _combine_logical_parts(self, parts: List[Any], combiner: Any) -> Optional[Any]:
        """
        Combine logical parts using a combiner function.

        :param parts: List of parts to combine
        :param combiner: The combining function (and_ or or_)
        :return: Combined expression or None
        """
        if not parts:
            return None
        if len(parts) == 1:
            return parts[0]
        return combiner(*parts)

    def translate_comparator(self, query: Comparator) -> Optional[Any]:
        """
        Translate an eql.Comparator query into a SQLAlchemy expression.

        :param query: The comparator query
        :return: SQLAlchemy expression or None if handled via JOIN
        """
        if self._is_membership_in_collection(query):
            return self._translate_membership(query.left, query.right)

        if not self.collection_mode and self._is_attribute_equality_join(query):
            join_result = self._handle_attribute_equality_join(query)
            if join_result is not None:
                return None

        left = self._translate_comparator_operand(query.left)
        right = self._translate_comparator_operand(query.right)

        operation = query.operation
        operator_name = operation.__name__

        if operation is operator.contains or operator_name in (
            "contains",
            "not_contains",
            "in_",
        ):
            return self._handle_contains_operator(query, left, right, operator_name)

        mapper = OperatorMapper()
        return mapper.map_comparison_operator(operation, left, right)

    def _is_membership_in_collection(self, query: Comparator) -> bool:
        """
        :return: True if the comparator tests whether an item is an element of a
            collection-valued attribute, as ``contains(s.takes_course, c)`` does.
        """
        is_membership = query.operation is operator.contains or (
            query.operation.__name__ in ("contains", "in_")
        )
        return (
            is_membership
            and isinstance(query.left, Attribute)
            and self._ends_in_collection(query.left)
        )

    def _ends_in_collection(self, attribute: Attribute) -> bool:
        """
        :return: True if the last attribute of the chain is a collection-valued
            relationship, determined from the DAO classes without joining anything.
        """
        root = self._chain_root(attribute)
        current = get_dao_class(root._type_) if root._type_ is not None else None
        names = self._collect_attribute_chain(attribute)
        for index, name in enumerate(names):
            if current is None:
                return False
            current, relationship = self._resolve_relationship(
                current, name, join=False
            )
            if relationship is None:
                return False
            if index == len(names) - 1:
                return relationship.uselist
            current = relationship.entity.class_
        return False

    def _translate_membership(self, collection: Attribute, item: Any) -> Any:
        """
        Translate ``contains(collection, item)`` into a correlated EXISTS over the
        relationships of the collection.

        :return: An EXISTS expression that holds when an element of the collection has the
            database id of the item.
        """
        names = self._collect_attribute_chain(collection)
        owner = self._walk_references(
            self._start_of_chain(collection), names[:-1], collection
        )
        owner, steps = self._collection_steps(owner, names[-1], collection)
        links = self._aliased_links(owner, steps)
        element = links[-1][3]
        return self._exists_along(links, element.database_id == self._identity_of(item))

    def _identity_of(self, item: Any) -> Any:
        """
        :return: The SQL expression of the database id of an item: the id column of a
            variable or flattened collection, the reference column of an attribute, or the
            id of a data access object given as a literal.
        :raises UnsupportedTranslationError: When the item is a domain object, which has no
            identity in the database.
        """
        if isinstance(item, Attribute):
            return self.translate_attribute(item)
        if isinstance(item, FlatVariable) or (
            isinstance(item, Variable) and not isinstance(item, Literal)
        ):
            return self._element_of(item).database_id
        value = DomainValueExtractor(self.session).extract_from_literal(item)
        if hasattr(value, "database_id"):
            return value.database_id
        raise UnsupportedTranslationError(
            item,
            "a domain object has no identity in the database; use a variable with a "
            "condition on its attributes",
        )

    def _is_attribute_equality_join(self, query: Comparator) -> bool:
        """
        Check if a comparator represents an attribute equality join.

        :param query: The comparator query
        :return: True if it's an attribute equality join
        """
        operation_name = query.operation.__name__
        is_equality = query.operation is operator.eq or operation_name == "eq"
        both_attributes = isinstance(query.left, Attribute) and isinstance(
            query.right, Attribute
        )
        variable_and_attribute = (
            isinstance(query.left, Variable)
            and not isinstance(query.left, Literal)
            and isinstance(query.right, Attribute)
        ) or (
            isinstance(query.left, Attribute)
            and isinstance(query.right, Variable)
            and not isinstance(query.right, Literal)
        )

        return is_equality and (both_attributes or variable_and_attribute)

    def _handle_attribute_equality_join(self, query: Comparator) -> Optional[bool]:
        """
        Handle an attribute equality join.

        :param query: The comparator query
        :return: True if JOIN was performed, None otherwise
        """
        resolver = AttributeChainResolver()
        rel_resolver = RelationshipResolver()

        # Normalize: ensure right side is always the Attribute
        if isinstance(query.left, Attribute) and isinstance(query.right, Variable):
            attribute_side = query.left
            variable_side = query.right
        elif isinstance(query.left, Variable) and isinstance(query.right, Attribute):
            attribute_side = query.right
            variable_side = query.left
        else:
            attribute_side = None
            variable_side = None

        if attribute_side is not None:
            attribute_dao = resolver.extract_base_dao(attribute_side)
            variable_dao = get_dao_class(variable_side._type_)

            if attribute_dao is None or variable_dao is None:
                return None

            attribute_name = attribute_side._attribute_name_
            relationship, foreign_key = (
                rel_resolver.resolve_relationship_and_foreign_key(
                    attribute_dao, attribute_name
                )
            )

            if relationship is None:
                return None

            variable_primary_key = variable_dao.database_id
            if variable_primary_key is None:
                return None

            if not self.join_manager.is_table_joined(attribute_dao):
                onclause = foreign_key == variable_dao.database_id
                self.sql_query = self.sql_query.join(attribute_dao, onclause=onclause)
                self.join_manager.add_table_join(attribute_dao)
                return True
            elif not self.join_manager.is_table_joined(variable_dao):
                onclause = foreign_key == variable_dao.database_id
                self.sql_query = self.sql_query.join(variable_dao, onclause=onclause)
                self.join_manager.add_table_join(variable_dao)
                return True
            else:
                # Table already joined — add as WHERE condition instead
                return None

        left_leaf = resolver.extract_leaf_variable(query.left)
        right_leaf = resolver.extract_leaf_variable(query.right)
        left_dao = resolver.extract_base_dao(query.left)
        right_dao = resolver.extract_base_dao(query.right)

        if left_leaf is right_leaf or left_dao is None or right_dao is None:
            return None

        left_attribute_name = query.left._attribute_name_
        right_attribute_name = query.right._attribute_name_

        left_rel, left_foreign_key = rel_resolver.resolve_relationship_and_foreign_key(
            left_dao, left_attribute_name
        )
        right_rel, right_foreign_key = (
            rel_resolver.resolve_relationship_and_foreign_key(
                right_dao, right_attribute_name
            )
        )

        if left_rel is None or right_rel is None:
            return None

        if isinstance(self.select_like, Entity):
            # The DAO class of the variable being selected (the "main" table in the query)
            selected_dao = self._require_dao_class(
                self.select_like.selected_variable._type_
            )
            if left_dao is selected_dao:
                target_dao, target_foreign_key, source_foreign_key = (
                    right_dao,
                    right_foreign_key,
                    left_foreign_key,
                )
            else:
                target_dao, target_foreign_key, source_foreign_key = (
                    left_dao,
                    left_foreign_key,
                    right_foreign_key,
                )
        else:
            if not self.join_manager.is_table_joined(left_dao):
                target_dao, target_foreign_key, source_foreign_key = (
                    left_dao,
                    left_foreign_key,
                    right_foreign_key,
                )
            elif not self.join_manager.is_table_joined(right_dao):
                target_dao, target_foreign_key, source_foreign_key = (
                    right_dao,
                    right_foreign_key,
                    left_foreign_key,
                )
            else:
                return None

        if not self.join_manager.is_table_joined(target_dao):
            onclause = target_foreign_key == source_foreign_key
            self.sql_query = self.sql_query.join(target_dao, onclause=onclause)
            self.join_manager.add_table_join(target_dao)

        return True

    def _translate_comparator_operand(self, operand: Any) -> Any:
        """
        Translate a comparator operand to SQL.

        :param operand: The operand
        :return: Translated SQL value or expression
        """
        if isinstance(operand, Attribute):
            return self.translate_attribute(operand)

        if isinstance(operand, FlatVariable):
            return self._element_of(operand).database_id

        if isinstance(operand, CountAll):
            return func.count()

        if isinstance(operand, Count):
            col = self.translate_query(operand._child_)
            return func.count() if col is None else func.count(col)

        if isinstance(operand, Max):
            col = self.translate_query(operand._child_)
            return func.max(col)

        if isinstance(operand, Min):
            col = self.translate_query(operand._child_)
            return func.min(col)

        if isinstance(operand, Average):
            col = self.translate_query(operand._child_)
            return func.avg(col)

        if isinstance(operand, Sum):
            col = self.translate_query(operand._child_)
            return func.sum(col)

        if isinstance(operand, CaseWhen):
            condition = self.translate_query(operand.condition)
            then_value = self._translate_comparator_operand(operand.then_value)
            if operand.else_value is not None:
                else_value = self._translate_comparator_operand(operand.else_value)
                return case((condition, then_value), else_=else_value)
            return case((condition, then_value))

        if isinstance(operand, Literal):
            extractor = DomainValueExtractor(self.session)
            return extractor.extract_from_literal(operand)

        if self.collection_mode and self._is_plain_variable(operand):
            return self._element_of(operand).database_id

        if isinstance(operand, Variable):
            variable_dao = get_dao_class(operand._type_)
            if variable_dao is not None:
                return variable_dao.database_id
            extractor = DomainValueExtractor(self.session)
            return extractor.extract_from_variable(operand)

        return operand

    def _handle_contains_operator(
        self, query: Comparator, left: Any, right: Any, operator_name: str
    ) -> Any:
        """
        Handle contains/in operators with special cases.

        :param query: The comparator query
        :param left: Left operand (translated)
        :param right: Right operand (translated)
        :param operator_name: Name of the operator
        :return: SQLAlchemy expression
        """
        is_negated = operator_name == "not_contains"

        if (
            operator_name in ("contains", "in_")
            and isinstance(query.left, Literal)
            and isinstance(query.right, Attribute)
        ):
            extractor = DomainValueExtractor(self.session)
            values = extractor.extract_from_literal(query.left)

            if not isinstance(values, list):
                values = [values]

            if len(values) == 1 and isinstance(values[0], (list, tuple)):
                values = values[0]

            if len(values) != 1 or (values and not isinstance(values[0], str)):
                column = self.translate_attribute(query.right)
                expression = column.in_(values)
                return sa_not(expression) if is_negated else expression

        mapper = OperatorMapper()
        return mapper.map_contains_operator(query.operation, left, right)

    def translate_attribute(self, query: Attribute) -> Any:
        """
        Translate an eql.Attribute query into a SQLAlchemy column.

        :param query: The attribute query
        :return: SQLAlchemy column expression
        """
        attribute_names = self._collect_attribute_chain(query)
        start = self._start_of_chain(query)
        return self._walk_attribute_chain(start, attribute_names, query)

    def translate_condition(self, condition: Any) -> Optional[Any]:
        """
        Translate an EQL expression used as a condition. An attribute used as a condition
        holds when its value is true in Python: a collection when it is not empty, a
        reference when it is set, and a value by its truth value.

        :param condition: The EQL condition.
        :return: SQLAlchemy boolean expression or None if handled via JOINs.
        """
        if isinstance(condition, Attribute):
            return self._attribute_condition(condition)
        return self.translate_query(condition)

    def _attribute_condition(self, attribute: Attribute) -> Any:
        """
        :return: The condition that the value of an attribute is true.
        """
        names = self._collect_attribute_chain(attribute)
        start = self._start_of_chain(attribute)
        owner = self._walk_references(start, names[:-1], attribute)
        owner, relationship = self._resolve_relationship(owner, names[-1])
        if relationship is not None and relationship.uselist:
            return getattr(owner, names[-1]).any()
        column = self._walk_attribute_chain(start, names, attribute)
        if relationship is not None:
            return column.is_not(None)
        return self._truth_value(column)

    @staticmethod
    def _truth_value(column: Any) -> Any:
        """
        :return: The condition that a column's value is true in Python: not missing, and
            not False, zero or the empty string.
        """
        if isinstance(column.type, Boolean):
            return column.is_(true())
        if isinstance(column.type, (Integer, Numeric)):
            return and_(column.is_not(None), column != 0)
        if isinstance(column.type, String):
            return and_(column.is_not(None), column != "")
        return column.is_not(None)

    def _translate_negation(self, condition: Any) -> Any:
        """
        Translate negation as failure: the negation holds when the condition is not true,
        also when SQL evaluates the condition to NULL because a value is missing.
        """
        inner = self.translate_condition(condition)
        return inner.is_not(true())

    def _collect_attribute_chain(self, query: Attribute) -> List[str]:
        """
        Collect attribute names from the chain.

        :param query: The attribute query
        :return: List of attribute names (reversed, from base to leaf)
        """
        names = []
        node = query
        while isinstance(node, Attribute):
            names.append(node._attribute_name_)
            node = node._child_
        return list(reversed(names))

    def _extract_base_class(self, query: Attribute) -> Optional[type]:
        """
        Extract the base class from an attribute chain.

        :param query: The attribute query
        :return: The base class or None
        """
        node = query
        while isinstance(node, Attribute):
            node = node._child_

        base_class = node._type_
        if base_class is None:
            if hasattr(node, "_var_"):
                var = node._var_
                if var is not None:
                    base_class = var._type_ if hasattr(var, "_type_") else None

        return base_class

    def _walk_attribute_chain(
        self, current_dao: Any, names: List[str], chain: Any = None
    ) -> Any:
        """
        Walk the attribute chain and return the final column.

        :param current_dao: The starting DAO class or alias
        :param names: List of attribute names to walk
        :param chain: The EQL attribute chain, for error messages
        :return: SQLAlchemy column expression
        :raises UnsupportedTranslationError: When the chain ends in a collection, which has
            no single value.
        """
        if not names:
            raise EmptyAttributeChainError(current_dao, names)
        current = self._walk_references(current_dao, names[:-1], chain)
        current, relationship = self._resolve_relationship(current, names[-1])
        if relationship is not None:
            if relationship.uselist:
                raise UnsupportedTranslationError(
                    chain,
                    f"{names[-1]} is a collection, which has no single value; range over "
                    "its elements with flat_variable or test membership with contains",
                )
            local_column = next(iter(relationship.local_columns))
            return getattr(current, local_column.key)
        if not hasattr(current, names[-1]):
            raise MissingColumnError(current, names[-1])
        return getattr(current, names[-1])

    def _apply_relationship_join(
        self, dao_class: type, attribute_name: str, relationship: Any
    ) -> Any:
        """
        Apply a JOIN for a relationship if not already joined.

        This uses an explicit SQLAlchemy alias for the relationship target and joins
        using the relationship attribute itself, allowing SQLAlchemy to derive the ON
        clause while still binding subsequent column references to the correct FROM
        element. This mirrors the default Core/ORM behavior for join(<entity>) that the
        tests compare against, but avoids implicit joins by returning the alias for
        downstream attribute resolution.

        :param dao_class: The DAO class where the relationship is defined
        :param attribute_name: The relationship attribute name on dao_class
        :param relationship: The SQLAlchemy relationship object
        """
        if self.join_manager.is_path_joined(dao_class, attribute_name):
            # Return the existing alias so downstream uses the same FROM element
            return self.join_manager.get_alias_for_path(dao_class, attribute_name)
        self._require_joins_allowed(attribute_name)

        # Resolve target DAO class and create a dedicated alias for this path
        target_dao = relationship.entity.class_
        aliased_target = aliased(target_dao, flat=True)

        # Relationship attribute on the source class, e.g., PoseDAO.position
        relationship_attr = getattr(dao_class, attribute_name)

        # Perform the join using the relationship attribute so SQLAlchemy
        # determines the ON clause, while we control aliasing of the right side
        self.sql_query = self.sql_query.join(aliased_target, relationship_attr)

        # Record both the logical path and the table as joined to avoid duplicates
        self.join_manager.add_path_join(dao_class, attribute_name, aliased_target)
        # Track underlying table class as joined; alias class type differs but table is the same
        self.join_manager.add_table_join(target_dao)

        return aliased_target

    def _translate_exists(self, exists_node: EQLExists) -> Any:
        """
        Translate an EQL
        :class:`~krrood.entity_query_language.operators.logical_quantifiers.Exists` node
        into a SQLAlchemy correlated EXISTS subquery.

        The existential variable's type must map to a DAO class. Conditions in the
        EXISTS body are translated without touching the outer query's JOINs so that
        outer-variable references become correlated column references.

        :param exists_node: The EQL Exists node (variable + condition).
        :return: A SQLAlchemy EXISTS expression.
        :raises NoDAOFoundForTypeError: When the existential variable type has no DAO.
        """
        existential_variable = exists_node.variable
        condition = exists_node.condition
        if isinstance(existential_variable, FlatVariable):
            return self._translate_exists_over_elements(existential_variable, condition)
        if self.collection_mode:
            return self._translate_exists_over_variable(existential_variable, condition)
        dao_class = self._require_dao_class(existential_variable._type_)
        sub_where = self._translate_exists_condition(condition)
        sub_query = select(literal(1)).select_from(dao_class)
        if sub_where is not None:
            sub_query = sub_query.where(sub_where)
        return sqlalchemy_exists(sub_query)

    def _translate_exists_condition(self, condition: Any) -> Optional[Any]:
        """
        Translate a condition expression for use inside an EXISTS subquery.

        Unlike :meth:`translate_query`, this method does not mutate the outer query's
        JOIN state. Attribute-to-variable comparisons produce direct column comparisons
        (FK == PK) so that the outer variable acts as a correlated reference rather than
        triggering a JOIN.

        :param condition: The EQL condition expression.
        :return: SQLAlchemy predicate or None.
        """
        if isinstance(condition, Comparator):
            left = self._translate_comparator_operand(condition.left)
            right = self._translate_comparator_operand(condition.right)
            return OperatorMapper().map_comparison_operator(
                condition.operation, left, right
            )
        if isinstance(condition, AND):
            children = self._extract_logical_children(condition)
            parts = [self._translate_exists_condition(child) for child in children]
            return self._combine_logical_parts(
                [part for part in parts if part is not None], and_
            )
        if isinstance(condition, OR):
            children = self._extract_logical_children(condition)
            parts = [self._translate_exists_condition(child) for child in children]
            return self._combine_logical_parts(
                [part for part in parts if part is not None], or_
            )
        if isinstance(condition, Not):
            inner = self._translate_exists_condition(condition._child_)
            return inner.is_not(true()) if inner is not None else None
        raise UnsupportedTranslationError(
            condition,
            "inside an existential quantifier over a variable, only comparisons combined "
            "with and, or and not are translated",
        )

    def _translate_exists_over_elements(
        self, quantified: FlatVariable, condition: Any
    ) -> Any:
        """
        Translate ``exists(e, condition)`` for a flattened collection ``e`` into correlated
        EXISTS subqueries, one per flattened collection between ``e`` and the nearest node
        that is bound in the enclosing query, as in
        ``Student.is_student_of.of_type(A).any(A.is_part_of.of_type(B).any(condition))``.

        :param quantified: The flattened collection that is quantified.
        :param condition: The condition on its elements.
        :return: A SQLAlchemy EXISTS expression.
        """
        chain = self._unbound_collections(quantified)
        owner = self._element_of(self._chain_root(chain[0]._child_))
        links = []
        try:
            with self._subquery_scope():
                for flat in chain:
                    if links and isinstance(flat._child_, Attribute):
                        owner = self._narrow_last_link(
                            links, flat._child_._attribute_name_
                        )
                    links.extend(self._bind_element_in_subquery(owner, flat))
                    owner = links[-1][3]
                criterion = self.translate_condition(condition)
        finally:
            for flat in chain:
                self.elements_by_node.pop(id(flat), None)
        return self._exists_along(links, criterion)

    def _translate_exists_over_variable(
        self, quantified: Variable, condition: Any
    ) -> Any:
        """
        Translate ``exists(v, condition)`` for a variable ``v`` into an EXISTS subquery over
        an alias of its DAO class that is bound only inside the subquery.

        :return: A SQLAlchemy EXISTS expression.
        """
        alias = aliased(self._require_dao_class(quantified._type_), flat=True)
        self.elements_by_node[id(quantified)] = alias
        try:
            with self._subquery_scope():
                criterion = self.translate_condition(condition)
        finally:
            self.elements_by_node.pop(id(quantified), None)
        sub_query = select(literal(1)).select_from(alias)
        if criterion is not None:
            sub_query = sub_query.where(criterion)
        return sqlalchemy_exists(sub_query)

    def _unbound_collections(self, quantified: FlatVariable) -> List[FlatVariable]:
        """
        :return: The flattened collections from the outermost one that is not bound in the
            enclosing query to ``quantified``.
        """
        chain = []
        node = quantified
        while isinstance(node, FlatVariable) and id(node) not in self.elements_by_node:
            chain.insert(0, node)
            node = self._chain_root(node._child_)
        return chain

    def _bind_element_in_subquery(
        self, owner: Any, flat: FlatVariable
    ) -> List[tuple[Any, str, Any, Any]]:
        """
        Bind a flattened collection, reached directly from ``owner``, to a new alias of
        its element DAO without joining it to the enclosing query.

        :return: The relationship steps from ``owner`` to the alias.
        :raises UnsupportedTranslationError: When the collection is not an attribute of
            ``owner`` itself.
        """
        collection = flat._child_
        if not isinstance(collection, Attribute) or isinstance(
            collection._child_, Attribute
        ):
            raise UnsupportedTranslationError(
                flat,
                "an existential quantifier ranges over a collection attribute of a "
                "bound element",
            )
        owner, steps = self._collection_steps(owner, collection._attribute_name_, flat)
        links = self._aliased_links(owner, steps)
        self.elements_by_node[id(flat)] = links[-1][3]
        return links

    def _extract_logical_children(self, node: Any) -> List[Any]:
        """
        Extract child conditions from an AND/OR node.

        :param node: AND or OR node.
        :return: List of child expressions.
        """
        if hasattr(node, "left") and hasattr(node, "right"):
            return [node.left, node.right]
        if hasattr(node, "_children_"):
            return list(node._children_)
        return []


def eql_to_sql(
    query: Query, session: Session, as_common_table_expression: Optional[str] = None
) -> Union[EQLTranslator, Any]:
    """
    Translate an EQL query to SQL.

    .. code-block:: python

        # Normal translation:
        translator = eql_to_sql(query, session)

        # As common table expression:
        large_bodies = eql_to_sql(inner_query, session, as_common_table_expression="large_bodies")
        outer_translator = eql_to_sql(outer_query, session)
        outer_translator.sql_query = (
            outer_translator.sql_query
            .join(large_bodies, large_bodies.c.database_id == ContainerDAO.database_id)
        )

    :param query: The EQL query
    :param session: The SQLAlchemy session
    :param as_common_table_expression: If provided, returns a SQLAlchemy common table expression with this name.
    The name is required because SQL common table expressions must have an explicit alias
    (e.g. WITH large_bodies AS (SELECT ...))
    :return: EQLTranslator or SQLAlchemy common table expression
    """
    query.build()
    result = EQLTranslator(query, session)
    result.translate()

    if as_common_table_expression is not None:
        return result.sql_query.cte(as_common_table_expression)

    return result
