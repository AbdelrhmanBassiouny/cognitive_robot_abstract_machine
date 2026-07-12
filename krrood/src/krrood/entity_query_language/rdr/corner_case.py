"""
Corner-case provenance store for the EQL-native RDR.

Every rule in an RDR is created to handle one specific exception case — the *corner
case*. This module provides :class:`CornerCaseStore`, which records that case against
the rule's condition node and survives the save/load round-trip via a stable positional
index (see :func:`~krrood.entity_query_language.rdr.serialization.walk_rules_in_emission_order`).

Serialization of corner-case instances is delegated to a pluggable
:class:`CaseSerializer`. The default implementation, :class:`AsdictCaseSerializer`,
handles flat and nested dataclasses (scalars, enums, nested dataclasses).
"""

from __future__ import annotations

import dataclasses
import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing_extensions import Any, Dict, List, Optional, Set, Type
from uuid import UUID

from krrood.class_diagrams.utils import get_type_hints_of_object
from krrood.code_generation.type_hints import value_to_source
from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.rdr.exceptions import CaseNotSerializableError

# ---------------------------------------------------------------------------
# CaseSource
# ---------------------------------------------------------------------------


@dataclass
class CaseSource:
    """The eval-able Python constructor source for a case, plus its type dependencies."""

    source: str
    """Eval-able Python constructor expression, e.g. ``Animal(name='Rex')``."""

    referenced_types: Set[Type]
    """Every type referenced in :attr:`source` that must be imported for it to evaluate."""


# ---------------------------------------------------------------------------
# CaseSerializer ABC
# ---------------------------------------------------------------------------


@dataclass
class CaseSerializer(ABC):
    """Abstract base for pluggable corner-case serialization strategies.

    Implementations convert a case instance to Python constructor source (for the
    saved ``.py`` file) and reconstruct it on load. The default implementation is
    :class:`AsdictCaseSerializer`.
    """

    @abstractmethod
    def to_source(self, case: Any) -> CaseSource:
        """Return the constructor source and referenced types for ``case``.

        :param case: A dataclass instance to serialize.
        :return: The Python constructor expression (eval-able) and the set of types
            that must be imported for the expression to evaluate.
        """

    @abstractmethod
    def from_data(self, data: Any, case_type: Type) -> Any:
        """Reconstruct a case instance from ``data``.

        This method is part of the extension contract for :class:`CaseSerializer`
        implementations. The default save/load path (``rdr_to_python`` / ``load_rdr``)
        does not call this method — it uses ``eval`` of the constructor source emitted
        by :meth:`to_source`. Subclasses may use this method in their own round-trip
        strategy (for example, reconstructing from a DAO dict).

        :param data: The data representation of the case as stored by the subclass.
        :param case_type: The expected type of the reconstructed instance.
        :return: A case instance equal to the original.
        """


# ---------------------------------------------------------------------------
# AsdictCaseSerializer — default implementation
# ---------------------------------------------------------------------------


@dataclass
class AsdictCaseSerializer(CaseSerializer):
    """Serialize dataclass case instances via ``dataclasses.asdict`` + constructor source.

    :class:`AsdictCaseSerializer` supports:

    * flat dataclasses whose fields are ``None``, ``bool``, ``int``, ``float``,
      ``str``, or ``enum.Enum`` members;
    * dataclasses with nested dataclass fields (recursed);
    * enum members (emitted as ``EnumType.member``).

    It raises :class:`CaseNotSerializableError` for field values outside this set
    (e.g. a ``set``, ``list``, or arbitrary object) rather than falling back to
    ``repr()``.

    **Documented constraint:** case types must be ``dataclasses.asdict``-safe — no
    circular object references, and all fields must be settable via the constructor.
    For complex production types that violate this, implement a custom
    :class:`CaseSerializer`.
    """

    def to_source(self, case: Any) -> CaseSource:
        """Emit ``CaseType(field=value, ...)`` constructor source for ``case``.

        :param case: A dataclass instance to serialize.
        :raises CaseNotSerializableError: When a field value cannot be emitted.
        """
        if not dataclasses.is_dataclass(case) or isinstance(case, type):
            raise CaseNotSerializableError(case)
        referenced: Set[Type] = {type(case)}
        field_parts = []
        for f in dataclasses.fields(case):
            value = getattr(case, f.name)
            value_source = self._emit_value(value)
            referenced.update(value_source.referenced_types)
            field_parts.append(f"{f.name}={value_source.source}")
        source = f"{type(case).__name__}({', '.join(field_parts)})"
        return CaseSource(source, referenced)

    def _emit_value(self, value: Any) -> CaseSource:
        """Emit a single field value as source, recursing into nested dataclasses."""
        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            return self.to_source(value)
        if value is None or isinstance(value, (bool, int, float, str, enum.Enum)):
            ref_types: Set[Type] = set()
            if isinstance(value, enum.Enum):
                ref_types.add(type(value))
            return CaseSource(value_to_source(value), ref_types)
        raise CaseNotSerializableError(value)

    def from_data(self, data: Any, case_type: Type) -> Any:
        """Reconstruct a case instance from a ``dataclasses.asdict``-style dict.

        :param data: A plain dict as produced by ``dataclasses.asdict``.
        :param case_type: The dataclass type to reconstruct.
        :return: An instance of ``case_type`` equal to the original.
        """
        if not dataclasses.is_dataclass(case_type):
            return data
        hints = get_type_hints_of_object(case_type)
        kwargs = {}
        for f in dataclasses.fields(case_type):
            val = data[f.name]
            field_type = hints.get(f.name, type(val))
            if isinstance(val, dict) and dataclasses.is_dataclass(field_type):
                kwargs[f.name] = self.from_data(val, field_type)
            else:
                kwargs[f.name] = val
        return case_type(**kwargs)


# ---------------------------------------------------------------------------
# CornerCaseStore
# ---------------------------------------------------------------------------


@dataclass
class CornerCaseStore:
    """Maps each rule's condition-node id to the case instance that triggered it."""

    cases: Dict[UUID, Any] = field(default_factory=dict)
    """Live in-memory mapping from condition-node ``_id_`` to corner case instance."""
    serializer: CaseSerializer = field(default_factory=AsdictCaseSerializer)
    """Pluggable serialization strategy. Default: :class:`AsdictCaseSerializer`."""

    def record(self, node: SymbolicExpression, case: Any) -> None:
        """Record ``case`` as the corner case for the rule whose condition is ``node``.

        :param node: The condition node of the newly created rule.
        :param case: The concrete case instance that triggered the rule's creation.
        """
        self.cases[node._id_] = case

    def get(self, node_id: Optional[UUID]) -> Optional[Any]:
        """Return the corner case recorded for ``node_id``, or ``None`` if absent.

        :param node_id: The ``_id_`` of a rule's condition node, or ``None``.
        :return: The recorded corner case, or ``None``.
        """
        if node_id is None:
            return None
        return self.cases.get(node_id)

    def to_ordered_sources(
        self,
        ordered_nodes: List[SymbolicExpression],
    ) -> Dict[int, CaseSource]:
        """Emit constructor source for every node that has a recorded corner case.

        Delegates to ``self.serializer.to_source`` for each recorded case.

        :param ordered_nodes: Rule condition nodes in the order returned by
            :func:`~krrood.entity_query_language.rdr.serialization.walk_rules_in_emission_order`.
        :return: Mapping from index to :class:`CaseSource` for nodes that have a
            recorded corner case; nodes without one are absent.
        """
        result: Dict[int, CaseSource] = {}
        for i, node in enumerate(ordered_nodes):
            case = self.cases.get(node._id_)
            if case is not None:
                result[i] = self.serializer.to_source(case)
        return result

    @classmethod
    def from_ordered_cases(
        cls,
        ordered_nodes: List[SymbolicExpression],
        cases_by_index: Dict[int, Any],
    ) -> CornerCaseStore:
        """Rebuild a store from a positional index map loaded from a saved file.

        :param ordered_nodes: Rule condition nodes in the same emission order used at
            save time (from
            :func:`~krrood.entity_query_language.rdr.serialization.walk_rules_in_emission_order`
            over the freshly loaded rule tree).
        :param cases_by_index: Mapping from positional index to case instance (as loaded
            from the ``RDR_CORNER_CASES`` module-level dict).
        :return: A new :class:`CornerCaseStore` keyed by node ``_id_``.
        """
        store = cls()
        for i, node in enumerate(ordered_nodes):
            if i in cases_by_index:
                store.cases[node._id_] = cases_by_index[i]
        return store
