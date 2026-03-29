import pytest

from krrood.patterns.role.role_stub_generator_v2 import RoleStubGeneratorV2
from .helpers import get_module_comparators
from ..dataset.role_and_ontology import (
    university_ontology_like_classes_without_descriptors,
)

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_generator():
    generator = RoleStubGeneratorV2(
        university_ontology_like_classes_without_descriptors
    )
    return generator


@pytest.fixture
def stub_comparators(stub_generator):
    return get_module_comparators(
        stub_generator.generate_stub(), stubs=True
    )  # no cleanup needed — no sys.modules pollution


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.order("first")
def test_stub_generation_smoke(stub_generator):
    _ = stub_generator.generate_stub(write=True)
    assert stub_generator.path.exists()


def test_full_stub_comparison_class_existence(stub_comparators):
    """Tests that all classes defined in the expected stub exist in the generated stub."""
    for stub_comparator in stub_comparators:
        stub_comparator.compare_class_existence()


def test_full_stub_comparison_class_hierarchy(stub_comparators):
    """Tests that the class hierarchy (base classes) matches between stubs."""
    for stub_comparator in stub_comparators:
        stub_comparator.compare_class_hierarchy()


def test_full_stub_comparison_field_details(stub_comparators):
    """Tests that all fields, their types, and defaults match between stubs."""
    for stub_comparator in stub_comparators:
        stub_comparator.compare_field_details()


def test_full_stub_comparison_dataclass_params(stub_comparators):
    """Tests that @dataclass decorator arguments match between stubs."""
    for stub_comparator in stub_comparators:
        stub_comparator.compare_dataclass_params()


def test_full_stub_comparison_field_order(stub_comparators):
    """Tests that fields appear in the same order between stubs."""
    for stub_comparator in stub_comparators:
        stub_comparator.compare_field_order()
