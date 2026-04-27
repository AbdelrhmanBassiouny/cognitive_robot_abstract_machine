import pytest

from krrood.patterns.role.role_transformer import RoleTransformer, TRANSFORMED
from .helpers import get_module_comparators
from ..dataset.role_and_ontology import (
    university_ontology_like_classes_without_descriptors,
    reproduction_module,
)

import libcst as cst
from krrood.patterns.role.role_transformer import RoleModuleTransformer
from libcst.codemod import CodemodContext

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


def test_missing_imports_in_mixins():
    """
    Tests that missing imports in role mixins are resolved.
    In reproduction_module, Taker inherits from BaseTaker.
    BaseTaker.get_external() returns ExternalType.
    TakerRoleAttributes should include get_external() and import ExternalType.
    """
    transformer = RoleTransformer(reproduction_module, file_name_prefix=TRANSFORMED)
    results = transformer.transform()

    # reproduction_module should be in results
    assert reproduction_module in results
    transformed_source, mixin_source = results[reproduction_module]

    # Check mixin_source for ExternalType import
    assert (
        "from test.krrood_test.dataset.role_and_ontology.external_types import ExternalType"
        in mixin_source
    )

    # Check for generic type handling: List[ExternalType] should NOT have full path
    # and ExternalType should be imported (covered above)
    print(f"DEBUG: mixin_source:\n{mixin_source}")
    assert (
        "List[test.krrood_test.dataset.role_and_ontology.external_types.ExternalType]"
        not in mixin_source
    )
    assert "list[ExternalType]" in mixin_source or "List[ExternalType]" in mixin_source


def test_transformation_idempotency():
    """
    Tests that rerunning the transformation does not duplicate base classes.
    """
    transformer = RoleTransformer(reproduction_module, file_name_prefix=TRANSFORMED)
    results = transformer.transform()
    transformed_source, _ = results[reproduction_module]

    # Now simulate rerunning on the transformed source
    tree = cst.parse_module(transformed_source)
    context = CodemodContext()
    mod_transformer = RoleModuleTransformer(
        context=context,
        class_diagram=transformer.class_diagram,
        module=reproduction_module,
        taker_modules=transformer.taker_modules,
        file_name_prefix=TRANSFORMED,
    )

    # We need to make sure mod_transformer uses the same logic as transform()
    mod_transformer.transform_module(tree)
    retransformed_source = mod_transformer.transformed_module.code

    # Check for duplicates in retransformed_source
    # Taker should have TakerRoleAttributes exactly once in the base list
    # and once in the import.
    assert retransformed_source.count("TakerRoleAttributes") == 2


def test_no_init_or_post_init_in_role_for():
    """
    Tests that __init__ and __post_init__ are NOT present in the generated RoleFor class.
    """
    # We add them to Taker for this test
    from test.krrood_test.dataset.role_and_ontology.reproduction_module import Taker

    # Save original methods if any
    orig_init = getattr(Taker, "__init__", None)
    orig_post_init = getattr(Taker, "__post_init__", None)

    try:

        def mock_init(self, some_arg):
            pass

        def mock_post_init(self):
            pass

        Taker.__init__ = mock_init
        Taker.__post_init__ = mock_post_init

        transformer = RoleTransformer(reproduction_module, file_name_prefix=TRANSFORMED)
        results = transformer.transform()

        assert reproduction_module in results
        _, mixin_source = results[reproduction_module]

        # RoleForTaker should be generated for Taker
        assert "class RoleForTaker" in mixin_source

        # Ensure __init__ and __post_init__ are not present as methods in RoleForTaker
        assert "def __init__" not in mixin_source
        assert "def __post_init__" not in mixin_source
    finally:
        # Restore (or remove if they didn't exist)
        if orig_init:
            Taker.__init__ = orig_init
        else:
            if hasattr(Taker, "__init__"):
                del Taker.__init__

        if orig_post_init:
            Taker.__post_init__ = orig_post_init
        else:
            if hasattr(Taker, "__post_init__"):
                del Taker.__post_init__
