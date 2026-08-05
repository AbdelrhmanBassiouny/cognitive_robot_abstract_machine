import os

import pytest

import semantic_digital_twin
from krrood.class_diagrams.class_diagram import ClassDiagram
from krrood.entity_query_language.testing.result_generation import (
    regenerate_verbalization_results,
)
from krrood.symbol_graph.symbol_graph import SymbolGraph, Symbol
from krrood.ontomatic.property_descriptor.attribute_introspector import (
    DescriptorAwareIntrospector,
)
from krrood.utils import recursive_subclasses
from semantic_digital_twin.adapters.urdf import URDFParser

from semantic_digital_twin.world import World
import runpy
from pathlib import Path

# Generate verbalization_results.py on every run, so an intentional wording change shows
# up as an ordinary diff to review instead of a failing test.
regenerate_verbalization_results(
    semantic_digital_twin,
    os.path.join(os.path.dirname(__file__), "test_worlds", "verbalization_results.py"),
)


def pytest_configure(config):

    worker = os.environ.get("PYTEST_XDIST_WORKER")

    if not worker:
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


@pytest.fixture
def table_world():
    urdf_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "..",
        "semantic_digital_twin",
        "resources",
        "urdf",
    )
    table_path = os.path.join(urdf_dir, "table.urdf")

    return URDFParser.from_file(file_path=table_path).parse()
