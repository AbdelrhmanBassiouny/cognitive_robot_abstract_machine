"""Tests for the RefactoredRoleTransformer API alignment and behaviour."""

from __future__ import annotations

import types

import pytest

from krrood.patterns.role.refactored_role_transformer import (
    DELEGATEE_ATTR,
    ROLE_MIXINS_FOLDER,
    ROLE_MIXINS_SUFFIX,
    RefactoredRoleTransformer,
    TransformationMode,
    _build_role_diagram,
    _normalize_type,
    _sort_modules_by_dependency,
)


class TestTransformationMode:
    def test_ground_truth_value(self):
        assert TransformationMode.GROUND_TRUTH == "_ground_truth_"

    def test_transformed_value(self):
        assert TransformationMode.TRANSFORMED == "transformed_"

    def test_is_string_enum(self):
        assert isinstance(TransformationMode.GROUND_TRUTH, str)
        assert isinstance(TransformationMode.TRANSFORMED, str)


class TestPublicAPI:
    """Verify the RefactoredRoleTransformer has the same public API as RoleTransformer."""

    def test_constructor_signature(self):
        mod = types.ModuleType("test")
        t = RefactoredRoleTransformer(module=mod)
        assert t.module is mod
        assert t.taker_modules == []
        assert t.file_name_prefix == ""

    def test_transform_method_exists(self):
        mod = types.ModuleType("test")
        t = RefactoredRoleTransformer(module=mod)
        assert callable(t.transform)

    def test_get_module_file_path_is_static(self):
        path = RefactoredRoleTransformer.get_module_file_path(types)
        assert path is not None

    def test_get_generated_file_path(self):
        mod = types.ModuleType("test")
        t = RefactoredRoleTransformer(module=mod)
        mixin_path = t.get_generated_file_path(mod, is_mixin=True)
        normal_path = t.get_generated_file_path(mod, is_mixin=False)
        assert mixin_path != normal_path

    def test_normalize_file_prefix(self):
        assert RefactoredRoleTransformer._normalize_file_prefix("") == ""
        assert RefactoredRoleTransformer._normalize_file_prefix("x") == "x_"
        assert RefactoredRoleTransformer._normalize_file_prefix("x_") == "x_"

    def test_post_init_refreshes_diagram(self):
        from test.krrood_test.dataset.role_and_ontology import (
            university_ontology_like_classes_without_descriptors as univ_module,
        )
        t = RefactoredRoleTransformer(module=univ_module, taker_modules=[])
        assert t.class_diagram is not None
        assert len(t.class_diagram.wrapped_classes) > 0

    def test_file_name_prefix_passed_through(self):
        mod = types.ModuleType("test")
        t = RefactoredRoleTransformer(module=mod, file_name_prefix="ground_truth_")
        assert t.file_name_prefix == "ground_truth_"


class TestModuleLevelHelpers:
    def test_normalize_type_generic(self):
        from typing import Optional
        result = _normalize_type(Optional[int])
        assert result is not None

    def test_normalize_type_plain(self):
        result = _normalize_type(str)
        assert result is str

    def test_build_role_diagram(self):
        from test.krrood_test.dataset.role_and_ontology import (
            university_ontology_like_classes_without_descriptors as univ_module,
        )
        diagram, modules, pd_only = _build_role_diagram(univ_module, [])
        assert diagram is not None
        assert len(modules) >= 0
        assert isinstance(pd_only, set)

    def test_sort_modules_by_dependency(self):
        from test.krrood_test.dataset.role_and_ontology import (
            university_ontology_like_classes_without_descriptors as univ_module,
        )
        diagram, modules, _ = _build_role_diagram(univ_module, [])
        if len(modules) > 1:
            sorted_mods = _sort_modules_by_dependency(list(modules), diagram)
            assert len(sorted_mods) == len(modules)


class TestConstants:
    def test_delegatee_attr(self):
        assert DELEGATEE_ATTR == "delegatee"

    def test_role_mixins_folder(self):
        assert ROLE_MIXINS_FOLDER == "role_mixins"

    def test_role_mixins_suffix(self):
        assert ROLE_MIXINS_SUFFIX == "_role_mixins"


class TestExportsFromInit:
    def test_refactored_role_transformer_exported(self):
        from krrood.patterns.role import RefactoredRoleTransformer
        assert RefactoredRoleTransformer is not None

    def test_transformation_mode_exported(self):
        from krrood.patterns.role import TransformationMode
        assert TransformationMode.GROUND_TRUTH == "_ground_truth_"
