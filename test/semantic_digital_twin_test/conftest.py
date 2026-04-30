import sys

from krrood.class_diagrams import ClassDiagram
from krrood.class_diagrams.class_diagram import WrappedSpecializedGeneric
from krrood.patterns.role.helpers import transform_roles_in_class_diagram
from krrood.patterns.role.role import Role
from krrood.patterns.role.role_transformer import RoleTransformer
from krrood.symbol_graph.symbol_graph import SymbolGraph, Symbol
from krrood.ontomatic.property_descriptor.attribute_introspector import (
    DescriptorAwareIntrospector,
)
from krrood.utils import recursive_subclasses

from semantic_digital_twin.world import World
import runpy
from pathlib import Path


def pytest_configure(config):
    # Ensure ORM classes are generated before tests run
    repo_root = Path(__file__).resolve().parents[2]
    generate_orm_path = (
        repo_root / "semantic_digital_twin" / "scripts" / "generate_orm.py"
    )
    # Execute the ORM generation script as a standalone module
    runpy.run_path(str(generate_orm_path), run_name="__main__")

    # Build the symbol graph
    SymbolGraph.clear()
    class_diagram = ClassDiagram(
        recursive_subclasses(Symbol) + [World],
        introspector=DescriptorAwareIntrospector(),
    )
    SymbolGraph(_class_diagram=class_diagram)

    transform_roles_in_class_diagram(class_diagram)
