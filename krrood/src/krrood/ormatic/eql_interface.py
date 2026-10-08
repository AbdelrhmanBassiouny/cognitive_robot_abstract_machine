from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing_extensions import (
    Callable,
    Dict,
    Iterator,
    List,
    Any,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
)
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
from sqlalchemy import Column, Table
from sqlalchemy.orm import (
    ColumnProperty,
    RelationshipDirection,
    RelationshipProperty,
    Session,
    aliased,
)
from sqlalchemy.sql.expression import ColumnElement, FromClause
from sqlalchemy.types import Boolean, Date, DateTime, Integer, Numeric, String, Time

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
        if isinstance(self.expression, str):
            name = self.expression
        else:
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
class CollectionLink:
    """
    One relationship step from a FROM element towards the elements of a collection.
    """

    source: Any
    """The FROM element the step starts from."""

    attribute_name: str
    """The name of the relationship attribute of the source."""

    relationship: Any
    """The SQLAlchemy relationship of the attribute."""

    alias: Any
    """The alias of the target of the step."""

    def quantified(self, criterion: Optional[Any]) -> Any:
        """
        :param criterion: A condition on the alias, or None for none.
        :return: A correlated EXISTS that holds when a target of the step satisfies the
            criterion.
        """
        attribute = getattr(self.source, self.attribute_name).of_type(self.alias)
        quantify = attribute.any if self.relationship.uselist else attribute.has
        return quantify() if criterion is None else quantify(criterion)


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

    element_mode: bool = False
    """
    True if the query uses a collection-valued attribute. Every variable is then bound to a
    FROM element of its own, so that all uses of a variable refer to the same rows and
    different variables range independently.
    """

    outer_node_ids: Set[int] = field(default_factory=set)
    """
    The ids of the EQL nodes that occur outside every existential quantifier, which the
    outer query binds.
    """

    conditional_depth: int = 0
    """
    The number of ``or_`` and ``not_`` around the condition being translated. A new inner
    JOIN there would drop the rows that satisfy another alternative.
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
        self._scan_query()
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

    def _scan_query(self) -> None:
        """
        Find the nodes outside every existential quantifier, and whether the query needs a
        FROM element per variable because it uses a collection.
        """
        uses_collection = False
        visited = set()
        pending = [(root, True) for root in self._query_roots()]
        while pending:
            node, outer = pending.pop()
            if (id(node), outer) in visited:
                continue
            visited.add((id(node), outer))
            if outer:
                self.outer_node_ids.add(id(node))
            if self._is_collection_node(node):
                uses_collection = True
            inside_outer_query = outer and not isinstance(node, EQLExists)
            pending.extend(
                (child, inside_outer_query) for child in self._children_of(node)
            )
        self.element_mode = uses_collection

    def _query_roots(self) -> List[SymbolicExpression]:
        """
        :return: The expressions of the query: its condition, its selection, and the
            expressions it groups, filters and orders by.
        """
        query = self.eql_query
        roots = [query._where_expression_, *self.select_like._selected_variables_]
        if query._having_builder_ is not None:
            roots.append(query._having_builder_.conditions_expression)
        if query._grouped_by_builder_ is not None:
            roots.extend(query._grouped_by_builder_.variables_to_group_by)
        if query._ordered_by_builder_ is not None:
            roots.append(query._ordered_by_builder_.variable)
        return [root for root in roots if isinstance(root, SymbolicExpression)]

    def _is_collection_node(self, node: Any) -> bool:
        """
        :return: True if the node is a flattened collection or a membership test on a
            collection-valued attribute.
        """
        return isinstance(node, FlatVariable) or (
            isinstance(node, Comparator) and self._is_membership_in_collection(node)
        )

    @staticmethod
    def _children_of(expression: Any) -> List[SymbolicExpression]:
        """
        :return: The children of an EQL expression in its expression tree. They are read
            from the instance dictionary, because reading a missing attribute of a symbolic
            variable builds a new symbolic attribute instead of failing.
        """
        fields = vars(expression) if hasattr(expression, "__dict__") else {}
        return [
            child
            for child in fields.get("_children_", ()) or ()
            if isinstance(child, SymbolicExpression)
        ]

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
        if self.element_mode:
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

        if self.element_mode:
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
        self._require_joins_allowed(variable, conditional=False)
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

    @staticmethod
    def _exists_along(links: List[CollectionLink], criterion: Optional[Any]) -> Any:
        """
        Nest correlated EXISTS subqueries along relationship steps, innermost last.

        :param links: The steps from an outer FROM element to the quantified alias.
        :param criterion: The condition on the innermost alias, or None for none.
        :return: The outermost EXISTS expression.
        """
        for link in reversed(links):
            criterion = link.quantified(criterion)
        return criterion

    @staticmethod
    def _aliased_links(
        owner: Any, steps: List[tuple[str, Any]]
    ) -> List[CollectionLink]:
        """
        :param owner: The FROM element the first step starts from.
        :param steps: Pairs of an attribute name and its relationship.
        :return: The steps from ``owner``, each with a new alias of its target.
        """
        links = []
        for name, relationship in steps:
            alias = aliased(relationship.entity.class_, flat=True)
            links.append(CollectionLink(owner, name, relationship, alias))
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
            or (self.element_mode and self._is_plain_variable(root))
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

        :param current: The FROM element or DAO class to search.
        :param name: The attribute name.
        :param join: Whether the role taker or subclass that has the attribute is joined.
        :return: The FROM element that has the attribute, and its relationship or None if
            the attribute is not a relationship.
        """
        resolver = RelationshipResolver()
        while True:
            mapper = sqlalchemy.inspection.inspect(current)
            relationship = resolver._find_relationship(mapper, name)
            if relationship is not None or self._declares(current, name):
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
    def _mapper_of(current: Any) -> Any:
        """
        :return: The SQLAlchemy mapper of a DAO class or of an alias of one.
        """
        inspected = sqlalchemy.inspection.inspect(current)
        return getattr(inspected, "mapper", inspected)

    def _declares(self, current: Any, name: str) -> bool:
        """
        :return: True if the DAO of ``current`` has an ORM attribute ``name``.
        """
        return name in self._mapper_of(current).all_orm_descriptors

    def _subclass_declaring(self, current: Any, name: str) -> Optional[type]:
        """
        :return: The DAO class of the subclass of ``current`` that declares the attribute
            ``name``, or None if no subclass declares it.
        :raises UnsupportedTranslationError: When several subclasses declare it, so that
            narrowing to one of them would drop the instances of the others.
        """
        mapper = self._mapper_of(current)
        declaring = [
            descendant.class_
            for descendant in mapper.self_and_descendants
            if descendant is not mapper
            and name in descendant.attrs
            and (descendant.inherits is None or name not in descendant.inherits.attrs)
        ]
        if len(declaring) > 1:
            raise UnsupportedTranslationError(
                name,
                f"several subclasses of {mapper.class_.__name__} declare it, so the "
                "query cannot range over one of them",
            )
        return declaring[0] if declaring else None

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

    def _narrow_last_link(self, links: List[CollectionLink], name: str) -> Any:
        """
        When the target of the last link lacks the attribute ``name`` that a subclass
        declares, replace its alias by an alias of the subclass, so that the next
        quantifier ranges only over the instances that have the attribute. The element
        bound to the old alias is rebound to the new one.

        :param links: The links built so far.
        :param name: The attribute that the next quantifier reads.
        :return: The alias of the last link.
        """
        last = links[-1]
        if self._declares(last.alias, name):
            return last.alias
        subclass = self._subclass_declaring(last.alias, name)
        if subclass is None:
            return last.alias
        narrowed = aliased(subclass, flat=True)
        links[-1] = CollectionLink(
            last.source, last.attribute_name, last.relationship, narrowed
        )
        for node_id, element in list(self.elements_by_node.items()):
            if element is last.alias:
                self.elements_by_node[node_id] = narrowed
        return narrowed

    def _require_joins_allowed(self, expression: Any, conditional: bool = True) -> None:
        """
        :param expression: The expression that needs the join, for the error message.
        :param conditional: Whether the join restricts rows, so that it must not be added
            inside ``or_`` or ``not_``.
        :raises UnsupportedTranslationError: While translating inside an EXISTS subquery,
            or, for a restricting join, inside ``or_`` or ``not_``.
        """
        if self.joins_forbidden:
            raise UnsupportedTranslationError(
                expression,
                "inside an existential quantifier over a collection, conditions may "
                "only read the columns of the quantified elements and of the outer "
                "elements",
            )
        if conditional and self.conditional_depth > 0:
            raise UnsupportedTranslationError(
                expression,
                "a join inside or_ or not_ would drop the rows that satisfy another "
                "alternative; test the collection with exists or contains instead",
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

    @contextmanager
    def _conditional_scope(self) -> Iterator[None]:
        """
        Mark the translation of an alternative of ``or_`` or of the condition of ``not_``.
        """
        self.conditional_depth += 1
        try:
            yield
        finally:
            self.conditional_depth -= 1

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

        Each alternative is translated without joins that restrict rows, which would drop
        the rows that satisfy another alternative.

        :param query: EQL query
        :return: SQL expression.
        :raises UnsupportedTranslationError: When an alternative has no SQL condition.
        """
        with self._conditional_scope():
            parts = [
                self.translate_condition(child)
                for child in self._extract_logical_children(query)
            ]
        if any(part is None for part in parts):
            raise UnsupportedTranslationError(
                query, "an alternative of or_ has no SQL condition"
            )
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

        if self.element_mode and self._compares_elements(query):
            self._require_related(
                self._element_of(query.left), self._element_of(query.right), query
            )

        if (
            not self.element_mode
            and self.conditional_depth == 0
            and self._is_attribute_equality_join(query)
        ):
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
        return (
            query.operation is operator.contains
            and isinstance(query.left, Attribute)
            and self._ends_in_collection(query.left)
        )

    def _compares_elements(self, query: Comparator) -> bool:
        """
        :return: True if both operands of the comparator are variables or flattened
            collections, which compare by database id.
        """
        return all(
            isinstance(operand, FlatVariable) or self._is_plain_variable(operand)
            for operand in (query.left, query.right)
        )

    def _require_related(self, first: Any, second: Any, expression: Any) -> None:
        """
        :param first: A FROM element.
        :param second: Another FROM element.
        :param expression: The expression that compares them, for the error message.
        :raises UnsupportedTranslationError: When the DAO classes of the elements are not
            in one class hierarchy, so that their database ids identify unrelated rows.
        """
        first_class = self._mapper_of(first).class_
        second_class = self._mapper_of(second).class_
        if not (
            issubclass(first_class, second_class)
            or issubclass(second_class, first_class)
        ):
            raise UnsupportedTranslationError(
                expression,
                f"{first_class.__name__} and {second_class.__name__} are unrelated, so "
                "their database ids do not identify the same objects",
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
        element = links[-1].alias
        identity = self._identity_of(item)
        if isinstance(item, FlatVariable) or self._is_plain_variable(item):
            self._require_related(element, self._element_of(item), collection)
        return self._exists_along(links, element.database_id == identity)

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

        if self.element_mode and self._is_plain_variable(operand):
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
        :param attribute: The attribute used as a condition.
        :return: The condition that the value of the attribute is true in Python: a
            collection is not empty, a reference is set, and a value is true.
        """
        names = self._collect_attribute_chain(attribute)
        owner = self._walk_references(
            self._start_of_chain(attribute), names[:-1], attribute
        )
        owner, relationship = self._resolve_relationship(owner, names[-1])
        if relationship is not None:
            reference = getattr(owner, names[-1])
            return reference.any() if relationship.uselist else reference.has()
        if not self._declares(owner, names[-1]):
            raise MissingColumnError(owner, names[-1])
        return self._truth_value(getattr(owner, names[-1]), attribute)

    @staticmethod
    def _truth_value(column: Any, expression: Any) -> Any:
        """
        :param column: The column of a value.
        :param expression: The EQL attribute of the column, for the error message.
        :return: The condition that the column's value is true in Python: not missing, and
            not False, zero or the empty string.
        :raises UnsupportedTranslationError: For column types whose Python truth value has
            no SQL equivalent, such as JSON, in which an empty list is false.
        """
        if isinstance(column.type, Boolean):
            return column.is_(true())
        if isinstance(column.type, (Integer, Numeric)):
            return and_(column.is_not(None), column != 0)
        if isinstance(column.type, String):
            return and_(column.is_not(None), column != "")
        if isinstance(column.type, (Date, DateTime, Time)):
            return column.is_not(None)
        raise UnsupportedTranslationError(
            expression,
            f"the truth value of a {type(column.type).__name__} column has no SQL "
            "equivalent",
        )

    def _translate_negation(self, condition: Any) -> Any:
        """
        Translate negation as failure: the negation holds when the condition is not true,
        also when SQL evaluates the condition to NULL because a value is missing.

        :param condition: The negated EQL condition.
        :return: The SQL condition.
        :raises UnsupportedTranslationError: When the negated condition has no SQL
            condition of its own.
        """
        with self._conditional_scope():
            inner = self.translate_condition(condition)
        if inner is None:
            raise UnsupportedTranslationError(
                condition, "the negated condition has no SQL condition"
            )
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
        if self.element_mode and id(existential_variable) in self.outer_node_ids:
            # The outer query binds the quantified variable, so the quantifier only checks
            # its condition for that binding.
            return self.translate_condition(condition)
        if isinstance(existential_variable, FlatVariable):
            return self._translate_exists_over_elements(existential_variable, condition)
        if self.element_mode:
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
        if not chain:
            return self.translate_condition(condition)
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
                    owner = links[-1].alias
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

        :param quantified: The quantified variable, which occurs only inside the quantifier.
        :param condition: The condition on it.
        :return: A SQLAlchemy EXISTS expression.
        """
        alias = aliased(self._require_dao_class(quantified._type_), flat=True)
        previous = self.elements_by_node.get(id(quantified))
        self.elements_by_node[id(quantified)] = alias
        try:
            with self._subquery_scope():
                criterion = self.translate_condition(condition)
        finally:
            if previous is None:
                self.elements_by_node.pop(id(quantified), None)
            else:
                self.elements_by_node[id(quantified)] = previous
        sub_query = select(literal(1)).select_from(alias)
        if criterion is not None:
            sub_query = sub_query.where(criterion)
        return sqlalchemy_exists(sub_query)

    def _unbound_collections(self, quantified: FlatVariable) -> List[FlatVariable]:
        """
        :param quantified: The quantified flattened collection.
        :return: The flattened collections from the outermost one that the enclosing query
            does not bind to ``quantified``.
        """
        chain = []
        node = quantified
        while (
            isinstance(node, FlatVariable)
            and id(node) not in self.elements_by_node
            and id(node) not in self.outer_node_ids
        ):
            chain.insert(0, node)
            node = self._chain_root(node._child_)
        return chain

    def _bind_element_in_subquery(
        self, owner: Any, flat: FlatVariable
    ) -> List[CollectionLink]:
        """
        Bind a flattened collection, reached directly from ``owner``, to a new alias of
        its element DAO without joining it to the enclosing query.

        :param owner: The FROM element whose collection attribute is flattened.
        :param flat: The flattened collection.
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
        self.elements_by_node[id(flat)] = links[-1].alias
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


# %% Selection of database identifiers


@dataclass
class QueryScope:
    """
    The FROM clause and the conditions of one SELECT statement under construction when
    identifiers are selected: the outer query, or the subquery of an EXISTS. Tables are
    combined with inner joins, so that a row of the scope is a combination of table rows
    that satisfies every join condition.
    """

    from_clause: Optional[FromClause] = None
    """The tables joined so far, or None while the scope has none."""

    tables: List[FromClause] = field(default_factory=list)
    """The aliases of the tables of the scope."""

    conditions: List[ColumnElement] = field(default_factory=list)
    """
    Conditions of the WHERE clause: the join condition of the first table of a subquery,
    which refers to the enclosing query, the conditions that references are set, and the
    condition of the query.
    """

    def join(self, table: FromClause, condition: Optional[ColumnElement]) -> None:
        """
        Add a table to the FROM clause with an inner join.

        :param table: The alias of the table.
        :param condition: The join condition, or None for a table each row of which
            combines with every row of the scope.
        """
        self.tables.append(table)
        if self.from_clause is None:
            self.from_clause = table
            if condition is not None:
                self.conditions.append(condition)
            return
        self.from_clause = self.from_clause.join(
            table, true() if condition is None else condition
        )

    def select(self, *columns: Any) -> Select:
        """
        :param columns: The selected columns.
        :return: The SELECT statement of the scope.
        """
        statement = select(*columns)
        if self.from_clause is not None:
            statement = statement.select_from(self.from_clause)
        if self.conditions:
            statement = statement.where(*self.conditions)
        return statement

    def exists(self, criterion: Optional[ColumnElement]) -> ColumnElement:
        """
        :param criterion: A further condition on the rows of the scope, or None for none.
        :return: The correlated EXISTS that holds when the scope has a row that satisfies
            the criterion. Every table that is not one of the scope is correlated with an
            enclosing query, also with one that encloses the subquery indirectly.
        """
        statement = self.select(literal(1)).correlate_except(*self.tables)
        if criterion is not None:
            statement = statement.where(criterion)
        return sqlalchemy_exists(statement)


@dataclass(eq=False)
class IdentifiedElement:
    """
    What a variable, a flattened collection or a reference ranges over when identifiers
    are selected: the column that holds the database id of its rows, and the tables of its
    class hierarchy that are joined on that id so far. All tables of a joined-inheritance
    hierarchy share the database id, so a column of the element is read by joining only
    the table that declares the column, on the id.
    """

    dao_class: type
    """The data access object class of the values that the element ranges over."""

    identifier: ColumnElement
    """
    The column that holds the database id: a foreign key column, such as the source or
    target column of an association table or the column of a reference, or the primary key
    of a table of the class hierarchy.
    """

    scope: QueryScope
    """The scope that binds the element, into which the tables of the element are joined."""

    restricted_class: type
    """
    The most specific data access object class to whose rows the identifier is known to
    refer: the class of the table that the foreign key of the identifier references, or the
    class whose table was joined to restrict the element. It is ``dao_class`` or one of its
    subclasses.
    """

    tables: Dict[Table, FromClause] = field(default_factory=dict)
    """The alias of every table of the class hierarchy joined on the identifier, by table."""

    def table(self, table: Table) -> FromClause:
        """
        :param table: A table of the class hierarchy of ``restricted_class``.
        :return: The alias of the table joined on the identifier; it is joined on first use.
            Every row of the element has a row in the table, so the join does not change the
            rows of the scope.
        """
        alias = self.tables.get(table)
        if alias is None:
            alias = table.alias()
            self.scope.join(alias, primary_key_of(alias) == self.identifier)
            self.tables[table] = alias
        return alias

    def column(self, column: Column) -> ColumnElement:
        """
        :param column: A column of a table of the class hierarchy of ``restricted_class``.
        :return: The column of the element: the identifier for a primary key, else the column
            of the alias of its table.
        """
        if column.primary_key:
            return self.identifier
        return self.table(column.table).corresponding_column(column)


def own_table_of(dao_class: type) -> Table:
    """
    :param dao_class: A data access object class.
    :return: The table that holds a row for every instance of the class and of its
        subclasses only, its own table in joined-table inheritance.
    :raises UnsupportedTranslationError: When the class shares the table of its superclass
        (single-table inheritance), so that no table of its own restricts rows to it.
    """
    mapper = sqlalchemy.inspection.inspect(dao_class)
    if (
        mapper.inherits is not None
        and mapper.local_table is mapper.inherits.local_table
    ):
        raise UnsupportedTranslationError(
            dao_class.__name__,
            "the class shares the table of its superclass, so selecting identifiers "
            "cannot restrict rows to it",
        )
    return mapper.local_table


def primary_key_of(table: FromClause) -> ColumnElement:
    """
    :param table: A table of a data access object or an alias of one.
    :return: Its primary key column, the database id.
    """
    return next(iter(table.primary_key))


@dataclass
class IdentifierSelectingTranslator(EQLTranslator):
    """
    Translate an EQL query into SQL that selects the database id of every selected variable
    and flattened collection, the identity of the answer, instead of its data access
    object. The translation joins a table only when it is needed:

    * A variable or flattened element is represented by the column that holds its database
      id. A flattened element of a collection stored in an association table is the target
      column of the association table, and a variable whose first use is to range over one
      of its collections is the source column of that association table, so that
      ``set_of(p, flat_variable(p.is_member_of))`` becomes
      ``SELECT source_id, target_id FROM association``.
    * A column of a variable is read by joining, on the database id, only the table of its
      class hierarchy that declares the column, not the whole inheritance chain.
    * A foreign key restricts the class of the rows it refers to. A variable of class ``C``
      represented by a foreign key that references the table of ``C`` or of a subclass of
      ``C`` needs no join; a foreign key that references the table of a superclass of ``C``
      is restricted to ``C`` by joining the table of ``C`` on the id.
    * In a query that returns distinct answers, a membership test
      ``contains(v.collection, item)`` among the conditions that all answers satisfy, for a
      variable ``v`` that is not yet bound, joins the association table on its target column
      and binds ``v`` to its source column, instead of testing an EXISTS subquery for every
      combination of rows.

    Every variable ranges over the rows of its class independently, as when the query uses
    a collection-valued attribute (see ``EQLTranslator.element_mode``). The guards of the
    translation of collections apply unchanged: a join that would restrict rows inside
    ``or_`` or ``not_``, or inside an existential quantifier, is rejected. A join that only
    reads a column of a bound element on its database id does not restrict rows and is
    therefore always allowed. The translation relies on the foreign keys of the schema:
    an identifier held by a foreign key column refers to a row of the referenced table.
    """

    outer_scope: QueryScope = field(default_factory=QueryScope)
    """The scope of the outer query."""

    references: Dict[Tuple[IdentifiedElement, str], IdentifiedElement] = field(
        default_factory=dict
    )
    """
    The elements of the single-valued references followed so far, by the element they
    start from (compared by identity) and the name of the reference, so that following a
    reference twice refers to the same rows.
    """

    classes_by_table: Dict[Table, type] = field(default_factory=dict)
    """The data access object class whose own table each table is, filled on first use."""

    conjunct_ids: Set[int] = field(default_factory=set)
    """
    The ids of the conditions that every answer satisfies: the condition of the query and,
    recursively, the operands of a conjunction among them.
    """

    def translate(self) -> None:
        """
        Translate the query: bind the selected flattened collections, translate the
        condition, then select the identifiers and columns of the selection.
        """
        self._reject_inference()
        self._scan_query()
        self.element_mode = True
        self._reject_grouping()
        self._collect_conjuncts()
        selected = list(self.select_like._selected_variables_)
        for expression in selected:
            self._require_selectable(expression)
        for expression in selected:
            root = self._chain_root(expression)
            if isinstance(root, FlatVariable):
                self._element_of(root)
        if self.eql_query._where_expression_ is not None:
            condition = self.translate_condition(self.eql_query._where_expression_)
            if condition is not None:
                self.outer_scope.conditions.append(condition)
        columns = [self._selected_column(expression) for expression in selected]
        order = self._order_column()
        self.sql_query = self.outer_scope.select(*columns)
        if order is not None:
            self.sql_query = self.sql_query.order_by(order)
        if self.eql_query._limit_ is not None:
            self.sql_query = self.sql_query.limit(self.eql_query._limit_)
        if self.eql_query._distinct_on:
            self.sql_query = self.sql_query.distinct()

    def _collect_conjuncts(self) -> None:
        """
        Collect the conditions that every answer satisfies (see ``conjunct_ids``).
        """
        pending = [self.eql_query._where_expression_]
        while pending:
            condition = pending.pop()
            if condition is None:
                continue
            self.conjunct_ids.add(id(condition))
            if isinstance(condition, Where):
                pending.append(condition.condition)
            elif isinstance(condition, AND):
                pending.extend(self._extract_logical_children(condition))

    def _reject_grouping(self) -> None:
        """
        :raises UnsupportedTranslationError: When the query groups its results, which
            selects aggregates instead of the identities of answers.
        """
        if (
            self.eql_query._grouped_by_builder_ is not None
            or self.eql_query._having_builder_ is not None
        ):
            raise UnsupportedTranslationError(
                self.eql_query,
                "a grouped query selects aggregates, not identifiers; translate it "
                "without select_identifiers",
            )

    def _require_selectable(self, expression: Any) -> None:
        """
        :param expression: A selected expression.
        :raises UnsupportedTranslationError: When it is not a variable, a flattened
            collection or an attribute, which have an identifier or a column.
        """
        if not (
            isinstance(expression, (FlatVariable, Attribute))
            or self._is_plain_variable(expression)
        ):
            raise UnsupportedTranslationError(
                expression,
                "only variables, flattened collections and attributes are selected as "
                "identifiers or columns",
            )

    def _selected_column(self, expression: Any) -> Any:
        """
        :return: The identifier of a selected variable or flattened collection, or the
            column of a selected attribute.
        """
        if isinstance(expression, Attribute):
            return self.translate_attribute(expression)
        return self._element_of(expression).identifier

    def _order_column(self) -> Optional[Any]:
        """
        :return: The column the query is ordered by, or None if it is not ordered.
        """
        builder = self.eql_query._ordered_by_builder_
        if builder is None:
            return None
        column = self._translate_comparator_operand(builder.variable)
        return column.desc() if builder.descending else column

    # %% Binding variables and flattened collections

    def _element_of(self, node: Any) -> IdentifiedElement:
        """
        :param node: A variable or a flattened collection.
        :return: The element the node ranges over; it is bound on first use.
        :raises UnsupportedTranslationError: When the node is neither.
        """
        element = self.elements_by_node.get(id(node))
        if element is not None:
            return element
        if isinstance(node, FlatVariable):
            element = self._bind_flattened(node)
        elif self._is_plain_variable(node):
            element = self._bind_variable(node)
        else:
            raise UnsupportedTranslationError(
                node, "only variables and flattened collections range over tables"
            )
        self.elements_by_node[id(node)] = element
        return element

    def _bind_variable(self, variable: Variable) -> IdentifiedElement:
        """
        Bind a variable to its own table, the table of its class, added to the outer query
        as a table each row of which combines with every row, since the variable ranges over
        all instances independently. A variable that occurs outside every existential
        quantifier is bound by the outer query also when its first use is inside one.

        :return: The element of the variable.
        :raises UnsupportedTranslationError: For a variable that occurs only inside an
            existential quantifier without being quantified by it.
        """
        if id(variable) not in self.outer_node_ids:
            self._require_joins_allowed(variable, conditional=False)
        return self._table_element(
            self._require_dao_class(variable._type_), self.outer_scope
        )

    @staticmethod
    def _table_element(dao_class: type, scope: QueryScope) -> IdentifiedElement:
        """
        :param dao_class: A data access object class.
        :param scope: The scope to bind the element in.
        :return: An element over the rows of the own table of the class, joined into the
            scope as a table each row of which combines with every row of the scope.
        """
        table = own_table_of(dao_class)
        alias = table.alias()
        scope.join(alias, None)
        return IdentifiedElement(
            dao_class, primary_key_of(alias), scope, dao_class, {table: alias}
        )

    def _bind_flattened(self, flat: FlatVariable) -> IdentifiedElement:
        """
        Bind a flattened collection in the outer query. When its owner is a variable that
        is not bound yet, the variable is bound to the source column of the association
        table (see :meth:`_link_unbound_root`); otherwise the association table is joined
        to the bound owner.

        :return: The element of the flattened collection.
        :raises UnsupportedTranslationError: When the collection is not reached by
            attribute access or is not stored, or when the join is not allowed here.
        """
        collection = flat._child_
        if not isinstance(collection, Attribute):
            raise UnsupportedTranslationError(
                flat, "only collections reached by attribute access are stored"
            )
        self._require_joins_allowed(flat)
        names = self._collect_attribute_chain(collection)
        root = self._chain_root(collection)
        if len(names) == 1 and self._can_link_unbound_root(root, names[0]):
            link, relationship = self._link_unbound_root(root, names[0], None)
            return self._target_of_link(link, relationship, self.outer_scope)
        owner = self._walk_references(self._element_of(root), names[:-1], collection)
        owner, relationship = self._resolve_on_element(
            owner, names[-1], collection_in_scope=owner.scope is self.outer_scope
        )
        self._require_collection(relationship, names[-1], collection)
        return self._collection_element(owner, relationship, self.outer_scope)

    @staticmethod
    def _require_collection(relationship: Any, name: str, expression: Any) -> None:
        """
        :raises UnsupportedTranslationError: When ``relationship`` is not a stored
            collection.
        """
        if (
            not isinstance(relationship, RelationshipProperty)
            or not relationship.uselist
        ):
            raise UnsupportedTranslationError(
                expression, f"{name} is not a stored collection"
            )

    def _can_link_unbound_root(self, root: Any, name: str) -> bool:
        """
        :param root: The node an attribute chain starts from.
        :param name: The name of the collection of the root.
        :return: True if the root is a variable that is not bound yet and whose collection
            ``name`` is stored in a table that refers to its owner by database id, so that
            the variable can be bound to the column of that table.
        """
        if not self._is_plain_variable(root) or id(root) in self.elements_by_node:
            return False
        relationship = self._declared_relationship(
            self._require_dao_class(root._type_), name
        )
        if relationship is None or not relationship.uselist:
            return False
        if relationship.direction is not RelationshipDirection.ONETOMANY:
            return False
        if relationship.secondary is not None:
            return False
        local, _ = self._column_pair(relationship)
        return local.primary_key

    def _declared_relationship(self, dao_class: type, name: str) -> Optional[Any]:
        """
        :return: The relationship ``name`` of the class, or of the one subclass that
            declares it, or None if neither has such a relationship.
        """
        mapper = sqlalchemy.inspection.inspect(dao_class)
        if name in mapper.attrs:
            relationship = mapper.attrs[name]
            return (
                relationship if isinstance(relationship, RelationshipProperty) else None
            )
        if "role_taker" in mapper.relationships:
            return None
        subclass = self._subclass_declaring(dao_class, name)
        if subclass is None:
            return None
        return self._declared_relationship(subclass, name)

    def _link_unbound_root(
        self, root: Variable, name: str, item_identifier: Optional[ColumnElement]
    ) -> Tuple[IdentifiedElement, Any]:
        """
        Bind a variable that is not bound yet to the column of the table that stores its
        collection ``name`` and refers to the owner by database id: the source column of an
        association table. The table becomes part of the outer query. The variable is
        restricted to its class if the foreign key references the table of a superclass.

        :param root: The variable; :meth:`_can_link_unbound_root` holds for it.
        :param name: The name of the collection.
        :param item_identifier: The identifier that an element of the collection must have,
            as the join condition of the table, or None for no condition.
        :return: The element of the row of the table, and the relationship of the
            collection.
        """
        dao_class = self._require_dao_class(root._type_)
        relationship = self._declared_relationship(dao_class, name)
        local, remote = self._column_pair(relationship)
        table_class = self._class_of_table(remote.table, relationship)
        alias = remote.table.alias()
        condition = None
        if item_identifier is not None:
            target = self._association_target(relationship)
            element_column = (
                primary_key_of(alias)
                if target is None
                else alias.corresponding_column(self._column_pair(target)[0])
            )
            condition = element_column == item_identifier
        self.outer_scope.join(alias, condition)
        root_element = IdentifiedElement(
            dao_class, alias.corresponding_column(remote), self.outer_scope, dao_class
        )
        if remote.nullable:
            self.outer_scope.conditions.append(root_element.identifier.is_not(None))
        self._restrict(
            root_element, self._class_of_table(local.table, relationship), root
        )
        self.elements_by_node[id(root)] = root_element
        link = IdentifiedElement(
            relationship.mapper.class_,
            primary_key_of(alias),
            self.outer_scope,
            table_class,
            {remote.table: alias},
        )
        self._restrict(link, table_class, relationship.key)
        return link, relationship

    def _collection_element(
        self, owner: IdentifiedElement, relationship: Any, scope: QueryScope
    ) -> IdentifiedElement:
        """
        :param owner: The element that owns the collection.
        :param relationship: The relationship of the collection.
        :param scope: The scope that the tables of the collection are joined into.
        :return: The element of the elements of the collection.
        """
        link = self._follow(owner, relationship, scope)
        return self._target_of_link(link, relationship, scope)

    def _target_of_link(
        self, link: IdentifiedElement, relationship: Any, scope: QueryScope
    ) -> IdentifiedElement:
        """
        ORMatic stores a collection as association objects, each of which refers to one
        element through its ``target``.

        :param link: The element of the rows that the relationship of a collection leads to.
        :param relationship: The relationship of the collection.
        :param scope: The scope of the link.
        :return: The element of the targets of the association objects, or the link itself
            when the collection is stored without association objects.
        """
        target = self._association_target(relationship)
        if target is None:
            return link
        return self._follow(link, target, scope)

    @staticmethod
    def _association_target(relationship: Any) -> Optional[Any]:
        """
        :return: The ``target`` relationship of the association objects of a collection, or
            None when the collection does not consist of association objects.
        """
        association = relationship.mapper.class_
        if not issubclass(association, AssociationDataAccessObject):
            return None
        return relationship.mapper.relationships["target"]

    def _follow(
        self, element: IdentifiedElement, relationship: Any, scope: QueryScope
    ) -> IdentifiedElement:
        """
        Follow one relationship from an element.

        A many-to-one relationship, such as a reference or the target of an association
        object, is followed without a join: the element it leads to is the foreign key
        column. When the column may be empty, the rows in which it is are dropped, as an
        inner join drops them. A one-to-many relationship, such as the association objects
        of a collection, joins the table that holds the foreign key into ``scope``.

        :param element: The element the relationship starts from.
        :param relationship: The relationship.
        :param scope: The scope a joined table is added to.
        :return: The element the relationship leads to.
        """
        local, remote = self._column_pair(relationship)
        target_class = relationship.mapper.class_
        if relationship.direction is RelationshipDirection.MANYTOONE:
            identifier = element.column(local)
            if local.nullable:
                element.scope.conditions.append(identifier.is_not(None))
            reference = IdentifiedElement(
                target_class, identifier, element.scope, target_class
            )
            self._restrict(
                reference,
                self._class_of_table(remote.table, relationship),
                relationship.key,
            )
            return reference
        alias = remote.table.alias()
        scope.join(alias, alias.corresponding_column(remote) == element.column(local))
        table_class = self._class_of_table(remote.table, relationship)
        linked = IdentifiedElement(
            target_class,
            primary_key_of(alias),
            scope,
            table_class,
            {remote.table: alias},
        )
        self._restrict(linked, table_class, relationship.key)
        return linked

    @staticmethod
    def _column_pair(relationship: Any) -> Tuple[Column, Column]:
        """
        :return: The local and the remote column of a relationship.
        :raises UnsupportedTranslationError: When the relationship is not through one
            foreign key column.
        """
        pairs = relationship.local_remote_pairs
        if relationship.secondary is not None or len(pairs) != 1:
            raise UnsupportedTranslationError(
                relationship.key,
                "only relationships through one foreign key column are translated when "
                "identifiers are selected",
            )
        return pairs[0]

    def _class_of_table(self, table: Table, relationship: Any) -> type:
        """
        :param table: The own table of a data access object class.
        :param relationship: A relationship of the registry of the class.
        :return: The class.
        """
        if not self.classes_by_table:
            for mapper in relationship.parent.registry.mappers:
                if mapper.inherits is None or (
                    mapper.local_table is not mapper.inherits.local_table
                ):
                    self.classes_by_table[mapper.local_table] = mapper.class_
        return self.classes_by_table[table]

    def _restrict(
        self, element: IdentifiedElement, known_class: type, expression: Any
    ) -> None:
        """
        Restrict an element to its class, given the class whose rows its identifier is known
        to refer to. A known class that is the class of the element or one of its subclasses
        needs nothing; for a superclass, the own table of the element's class is joined on
        the id, which keeps the rows of that class only.

        :param element: The element; its ``dao_class`` is the class it must range over.
        :param known_class: The class of the rows the identifier refers to.
        :param expression: The expression that binds the element, for the error message.
        :raises UnsupportedTranslationError: When the classes are unrelated.
        """
        if issubclass(known_class, element.dao_class):
            element.restricted_class = known_class
            return
        if not issubclass(element.dao_class, known_class):
            raise UnsupportedTranslationError(
                expression,
                f"{element.dao_class.__name__} and {known_class.__name__} are unrelated, "
                "so their database ids do not identify the same objects",
            )
        element.table(own_table_of(element.dao_class))
        element.restricted_class = element.dao_class

    def _narrow(
        self,
        element: IdentifiedElement,
        subclass: type,
        name: str,
        guarded: bool = True,
        collection_in_scope: bool = False,
    ) -> IdentifiedElement:
        """
        Narrow an element to the instances of one of its subclasses, as in Python only the
        instances of a subclass have the attributes it declares, by joining the own table of
        the subclass on the id. When ``name`` is a collection whose table is joined into the
        scope of the element next and refers to its owner by a foreign key to the table of
        the subclass, that join already keeps the instances of the subclass only, and the
        table of the subclass is not joined.

        :param element: The element.
        :param subclass: The data access object class of the subclass.
        :param name: The attribute of the subclass that is read.
        :param guarded: Whether the narrowing must be allowed by the context, which is not
            required for an element that a subquery under construction binds.
        :param collection_in_scope: Whether ``name`` is a collection whose table is joined
            into the scope of the element next.
        :return: The element.
        """
        if guarded:
            self._require_joins_allowed(subclass)
        table = own_table_of(subclass)
        if not (
            collection_in_scope and self._refers_by_identifier(subclass, name, table)
        ):
            element.table(table)
        element.restricted_class = subclass
        return element

    def _refers_by_identifier(self, dao_class: type, name: str, table: Table) -> bool:
        """
        :param dao_class: A data access object class.
        :param name: The name of one of its attributes.
        :param table: A table.
        :return: True if the attribute is a collection whose table refers to its owner by a
            foreign key to the database id of ``table``.
        """
        relationship = sqlalchemy.inspection.inspect(dao_class).attrs[name]
        if not isinstance(relationship, RelationshipProperty):
            return False
        if relationship.direction is not RelationshipDirection.ONETOMANY:
            return False
        local, _ = self._column_pair(relationship)
        return local.primary_key and local.table is table

    def _resolve_on_element(
        self,
        element: IdentifiedElement,
        name: str,
        guarded: bool = True,
        collection_in_scope: bool = False,
    ) -> Tuple[IdentifiedElement, Any]:
        """
        Find the attribute ``name`` of an element. A role declares only its own attributes
        and delegates the others to its role taker, which is followed; when only a subclass
        declares ``name``, the element is narrowed to the subclass (see :meth:`_narrow`).

        :param element: The element to search.
        :param name: The attribute name.
        :param guarded: Whether narrowing must be allowed by the context.
        :param collection_in_scope: Whether ``name`` is read as a collection whose table is
            joined into the scope of the element next.
        :return: The element that has the attribute, and the mapped property of the
            attribute, or None if it is not mapped.
        """
        while True:
            mapper = sqlalchemy.inspection.inspect(element.restricted_class)
            if name in mapper.attrs:
                return element, mapper.attrs[name]
            if name in mapper.all_orm_descriptors:
                return element, None
            if "role_taker" in mapper.relationships:
                element = self._reference(
                    element, "role_taker", mapper.relationships["role_taker"]
                )
                continue
            subclass = self._subclass_declaring(element.restricted_class, name)
            if subclass is None:
                return element, None
            element = self._narrow(
                element, subclass, name, guarded, collection_in_scope
            )

    def _reference(
        self, element: IdentifiedElement, name: str, relationship: Any
    ) -> IdentifiedElement:
        """
        :param element: The element the reference starts from.
        :param name: The name of the single-valued reference.
        :param relationship: Its relationship.
        :return: The element of the referenced rows, the same for every use.
        :raises UnsupportedTranslationError: When following the reference, which drops the
            rows in which it is not set, is not allowed here.
        """
        key = (element, name)
        reference = self.references.get(key)
        if reference is None:
            self._require_joins_allowed(name)
            reference = self._follow(element, relationship, element.scope)
            self.references[key] = reference
        return reference

    def _walk_references(
        self, current: IdentifiedElement, names: List[str], chain: Any
    ) -> IdentifiedElement:
        """
        Follow the single-valued references named by ``names``, starting at ``current``.

        :return: The element reached.
        :raises UnsupportedTranslationError: When a name is a collection.
        :raises NonRelationshipInChainError: When a name is not a relationship.
        """
        for name in names:
            current, relationship = self._resolve_on_element(current, name)
            if not isinstance(relationship, RelationshipProperty):
                raise NonRelationshipInChainError(current.restricted_class, name)
            if relationship.uselist:
                raise UnsupportedTranslationError(
                    chain,
                    f"{name} is a collection; range over its elements with flat_variable",
                )
            current = self._reference(current, name, relationship)
        return current

    def _chain_owner(self, attribute: Attribute) -> Tuple[IdentifiedElement, Any]:
        """
        :param attribute: An attribute chain that starts at a variable or a flattened
            collection.
        :return: The element that has the last attribute of the chain, and the mapped
            property of the last attribute, or None if it is not mapped.
        """
        names = self._collect_attribute_chain(attribute)
        owner = self._walk_references(
            self._element_of(self._chain_root(attribute)), names[:-1], attribute
        )
        return self._resolve_on_element(owner, names[-1])

    # %% Conditions and values

    def translate_attribute(self, query: Attribute) -> Any:
        """
        :param query: An attribute chain.
        :return: The column of the attribute: of a value, or the foreign key column of a
            reference, which holds the database id of the referenced object.
        :raises UnsupportedTranslationError: When the attribute is a collection, which has
            no single value.
        :raises MissingColumnError: When the attribute is not a column.
        """
        owner, mapped = self._chain_owner(query)
        name = query._attribute_name_
        if isinstance(mapped, RelationshipProperty):
            if mapped.uselist:
                raise UnsupportedTranslationError(
                    query,
                    f"{name} is a collection, which has no single value; range over "
                    "its elements with flat_variable or test membership with contains",
                )
            return owner.column(self._column_pair(mapped)[0])
        if isinstance(mapped, ColumnProperty):
            return owner.column(mapped.columns[0])
        raise MissingColumnError(owner.restricted_class, name)

    def _attribute_condition(self, attribute: Attribute) -> Any:
        """
        :param attribute: The attribute used as a condition.
        :return: The condition that the value of the attribute is true in Python: a
            collection is not empty, a reference is set, and a value is true.
        """
        owner, mapped = self._chain_owner(attribute)
        if isinstance(mapped, RelationshipProperty):
            if not mapped.uselist:
                return owner.column(self._column_pair(mapped)[0]).is_not(None)
            scope = QueryScope()
            self._follow(owner, mapped, scope)
            return scope.exists(None)
        if isinstance(mapped, ColumnProperty):
            return self._truth_value(owner.column(mapped.columns[0]), attribute)
        raise MissingColumnError(owner.restricted_class, attribute._attribute_name_)

    def _translate_comparator_operand(self, operand: Any) -> Any:
        """
        :param operand: An operand of a comparator.
        :return: Its SQL expression; a variable or flattened collection is its identifier.
        """
        if isinstance(operand, Attribute):
            return self.translate_attribute(operand)
        if isinstance(operand, FlatVariable) or self._is_plain_variable(operand):
            return self._element_of(operand).identifier
        return super()._translate_comparator_operand(operand)

    def _require_related(self, first: Any, second: Any, expression: Any) -> None:
        """
        :param first: An element.
        :param second: Another element.
        :param expression: The expression that compares them, for the error message.
        :raises UnsupportedTranslationError: When the classes of the elements are not in one
            class hierarchy, so that their database ids identify unrelated rows.
        """
        if not (
            issubclass(first.dao_class, second.dao_class)
            or issubclass(second.dao_class, first.dao_class)
        ):
            raise UnsupportedTranslationError(
                expression,
                f"{first.dao_class.__name__} and {second.dao_class.__name__} are "
                "unrelated, so their database ids do not identify the same objects",
            )

    def _identity_of(self, item: Any) -> Any:
        """
        :return: The SQL expression of the database id of an item: the identifier of a
            variable or flattened collection, the foreign key column of a reference, or the
            id of a data access object given as a literal.
        :raises UnsupportedTranslationError: When the item is a domain object, which has no
            identity in the database.
        """
        if isinstance(item, FlatVariable) or self._is_plain_variable(item):
            return self._element_of(item).identifier
        return super()._identity_of(item)

    def translate_comparator(self, query: Comparator) -> Optional[Any]:
        """
        Translate a comparator; a membership test that all answers satisfy, a conjunct of
        the condition of the query, is a join when :meth:`_join_membership` applies.

        :param query: The comparator.
        :return: The SQL condition, or None when the comparator became a join.
        """
        if (
            id(query) in self.conjunct_ids
            and self._is_membership_in_collection(query)
            and self.eql_query._distinct_on
            and self.conditional_depth == 0
            and not self.joins_forbidden
            and self._join_membership(query.left, query.right)
        ):
            return None
        return super().translate_comparator(query)

    def _join_membership(self, collection: Attribute, item: Any) -> bool:
        """
        Translate ``contains(v.collection, item)`` into a join, when ``v`` is a variable that
        is not bound yet and ``item`` is a variable or flattened collection: the association
        table is joined on its target column equal to the identifier of the item, and ``v``
        is bound to its source column. It is only used in a query that returns distinct
        answers and for a condition that all answers satisfy, because the join yields one row
        per association object where the existential test yields one row.

        :param collection: The collection attribute.
        :param item: The item tested for membership.
        :return: True if the membership test became a join, False if it does not apply.
        """
        if not (isinstance(item, FlatVariable) or self._is_plain_variable(item)):
            return False
        names = self._collect_attribute_chain(collection)
        root = self._chain_root(collection)
        if len(names) != 1 or not self._can_link_unbound_root(root, names[0]):
            return False
        item_element = self._element_of(item)
        if id(root) in self.elements_by_node:
            return False
        link, relationship = self._link_unbound_root(
            root, names[0], item_element.identifier
        )
        element = self._target_of_link(link, relationship, self.outer_scope)
        self._require_related(element, item_element, collection)
        return True

    def _translate_membership(self, collection: Attribute, item: Any) -> Any:
        """
        Translate ``contains(collection, item)`` into an EXISTS subquery over the tables
        of the collection.

        :return: An EXISTS expression that holds when an element of the collection has the
            database id of the item.
        """
        identity = self._identity_of(item)
        owner, relationship = self._chain_owner(collection)
        self._require_collection(relationship, collection._attribute_name_, collection)
        scope = QueryScope()
        element = self._collection_element(owner, relationship, scope)
        if isinstance(item, FlatVariable) or self._is_plain_variable(item):
            self._require_related(element, self._element_of(item), collection)
        return scope.exists(element.identifier == identity)

    # %% Existential quantifiers

    def _translate_exists_over_elements(
        self, quantified: FlatVariable, condition: Any
    ) -> Any:
        """
        Translate ``exists(e, condition)`` for a flattened collection ``e`` into one EXISTS
        subquery that joins the tables of the flattened collections between ``e`` and the
        nearest node that the enclosing query binds, and is correlated with that node.

        :param quantified: The flattened collection that is quantified.
        :param condition: The condition on its elements.
        :return: The EXISTS expression.
        """
        chain = self._unbound_collections(quantified)
        if not chain:
            return self.translate_condition(condition)
        owner = self._element_of(self._chain_root(chain[0]._child_))
        scope = QueryScope()
        try:
            with self._subquery_scope():
                for flat in chain:
                    owner = self._bind_element_in_subquery(owner, flat, scope)
                criterion = self.translate_condition(condition)
        finally:
            for flat in chain:
                self.elements_by_node.pop(id(flat), None)
        return scope.exists(criterion)

    def _bind_element_in_subquery(
        self, owner: IdentifiedElement, flat: FlatVariable, scope: QueryScope
    ) -> IdentifiedElement:
        """
        Bind a flattened collection, reached directly from ``owner``, to its tables in the
        subquery ``scope``.

        :param owner: The element whose collection attribute is flattened.
        :param flat: The flattened collection.
        :param scope: The scope of the subquery.
        :return: The element of the flattened collection.
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
        name = collection._attribute_name_
        owner, relationship = self._resolve_on_element(
            owner,
            name,
            guarded=owner.scope is not scope,
            collection_in_scope=owner.scope is scope,
        )
        self._require_collection(relationship, name, flat)
        element = self._collection_element(owner, relationship, scope)
        self.elements_by_node[id(flat)] = element
        return element

    def _translate_exists_over_variable(
        self, quantified: Variable, condition: Any
    ) -> Any:
        """
        Translate ``exists(v, condition)`` for a variable ``v`` into an EXISTS subquery over
        the own table of its class, bound only inside the subquery.

        :param quantified: The quantified variable, which occurs only inside the quantifier.
        :param condition: The condition on it.
        :return: The EXISTS expression.
        """
        scope = QueryScope()
        element = self._table_element(self._require_dao_class(quantified._type_), scope)
        previous = self.elements_by_node.get(id(quantified))
        self.elements_by_node[id(quantified)] = element
        try:
            with self._subquery_scope():
                criterion = self.translate_condition(condition)
        finally:
            if previous is None:
                self.elements_by_node.pop(id(quantified), None)
            else:
                self.elements_by_node[id(quantified)] = previous
        return scope.exists(criterion)


def eql_to_sql(
    query: Query,
    session: Session,
    as_common_table_expression: Optional[str] = None,
    select_identifiers: bool = False,
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

    The translated query answers the query over the stored data: every variable ranges
    over the rows of its class in the database, whatever domain it was given in memory.
    Missing values follow Python where Python is defined: ``!=`` holds between a missing
    and a present value, an attribute used as a condition holds when its value is true,
    and ``not_`` is negation as failure. An order comparison with a missing value, which
    raises a ``TypeError`` in Python, is false. A construct without such a translation
    raises :class:`UnsupportedTranslationError` instead of returning different answers.

    :param query: The EQL query
    :param session: The SQLAlchemy session
    By default, the translation selects the data access objects of the selected variables.
    With ``select_identifiers=True``, it selects the database id of every selected variable
    and flattened collection instead, the identity of each answer, and the columns of
    selected attributes. It then joins a table only where one of its columns is read or
    where it restricts the class of a variable, and represents a variable by the foreign
    key column that already holds its id, so that, for example,
    ``an(set_of(p, flat_variable(p.is_member_of)))`` becomes
    ``SELECT source_id, target_id FROM association_table``
    (see :class:`IdentifierSelectingTranslator`):

    .. code-block:: python

        translator = eql_to_sql(query, session, select_identifiers=True)
        for answer in translator.evaluate():
            person = session.get(PersonDAO, answer[p])

    :param query: The EQL query
    :param session: The SQLAlchemy session
    :param as_common_table_expression: If provided, returns a SQLAlchemy common table expression with this name.
    The name is required because SQL common table expressions must have an explicit alias
    (e.g. WITH large_bodies AS (SELECT ...))
    :param select_identifiers: Whether to select database ids instead of data access objects.
    :return: EQLTranslator or SQLAlchemy common table expression
    """
    query.build()
    translator_class = (
        IdentifierSelectingTranslator if select_identifiers else EQLTranslator
    )
    result = translator_class(query, session)
    result.translate()

    if as_common_table_expression is not None:
        return result.sql_query.cte(as_common_table_expression)

    return result
