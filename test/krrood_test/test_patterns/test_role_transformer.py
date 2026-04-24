import pytest

from krrood.patterns.role.role_transformer import RoleTransformer, TRANSFORMED
from .helpers import get_module_comparators
from ..dataset.role_and_ontology import (
    university_ontology_like_classes_without_descriptors,
)

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def module_transformer():
    return RoleTransformer(
        university_ontology_like_classes_without_descriptors,
        file_name_prefix=TRANSFORMED,
    )


@pytest.fixture
def module_comparators(module_transformer):
    return get_module_comparators(
        module_transformer.transform()
    )  # no cleanup needed — no sys.modules pollution


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.order("first")
def test_transformation_smoke(module_transformer):
    _ = module_transformer.transform(write=True)
    assert module_transformer.path.exists()


def test_class_existence(module_comparators):
    """Tests that all classes defined in the ground truth module exist in the generated module."""
    for comparator in module_comparators:
        comparator.compare_class_existence()


def test_class_hierarchy(module_comparators):
    """Tests that the class hierarchy (base classes) matches between modules."""
    for comparator in module_comparators:
        comparator.compare_class_hierarchy()


def test_field_details(module_comparators):
    """Tests that all fields, their types, and defaults match between modules."""
    for comparator in module_comparators:
        comparator.compare_field_details()


def test_dataclass_params(module_comparators):
    """Tests that @dataclass decorator arguments match between modules."""
    for comparator in module_comparators:
        comparator.compare_dataclass_params()


def test_field_order(module_comparators):
    """Tests that fields appear in the same order between modules."""
    for comparator in module_comparators:
        comparator.compare_field_order()


def test_method_details(module_comparators):
    """Tests that all methods, properties, their parameters, and return types match between modules."""
    for comparator in module_comparators:
        comparator.compare_method_details()


def test_imports(module_comparators):
    """Tests that all import statements match between modules."""
    for comparator in module_comparators:
        comparator.compare_imports()
