from dataclasses import dataclass, field
from typing import Set, Dict, List, Tuple, Type
from krrood.entity_query_language.predicate import Symbol
from krrood.ontomatic.property_descriptor.property_descriptor import (
    PropertyDescriptor,
)
from krrood.ontomatic.property_descriptor.mixins import HasChainAxioms
from krrood.entity_query_language.symbol_graph import SymbolGraph
import pytest
from line_profiler import profile


@pytest.fixture(autouse=True)
def clear_graph():
    SymbolGraph().clear()


@dataclass(eq=False)
class Person(Symbol):
    name: str = ""
    parent_of: Set["Person"] = field(default_factory=set)
    ancestor_of: Set["Person"] = field(default_factory=set)


@dataclass
class ParentOf(PropertyDescriptor): ...


@dataclass
class AncestorOf(PropertyDescriptor, HasChainAxioms):

    @classmethod
    def get_chain_axioms(cls) -> List[Tuple[Type[PropertyDescriptor], ...]]:
        return [(ParentOf, ParentOf), (ParentOf, AncestorOf)]


Person.parent_of = ParentOf(Person, "parent_of")
Person.ancestor_of = AncestorOf(Person, "ancestor_of")


@profile
def test_property_chain_2_steps():
    a = Person("A")
    b = Person("B")
    c = Person("C")

    # A parent_of B, B parent_of C => A ancestor_of C
    a.parent_of.add(b)
    b.parent_of.add(c)

    assert c in a.ancestor_of


@profile
def test_property_chain_3_steps():
    a = Person("A")
    b = Person("B")
    c = Person("C")
    d = Person("D")

    # A parent_of B, B parent_of C, C parent_of D => A ancestor_of D
    # A parent_of B, B parent_of C => A ancestor_of C
    # A ancestor_of C, C parent_of D (Wait, chain is ParentOf o AncestorOf -> AncestorOf?)
    # The axiom (ParentOf, AncestorOf) -> AncestorOf should handle it recursively if applied in right order.

    a.parent_of.add(b)
    b.parent_of.add(c)
    c.parent_of.add(d)

    assert c in a.ancestor_of
    assert d in a.ancestor_of
