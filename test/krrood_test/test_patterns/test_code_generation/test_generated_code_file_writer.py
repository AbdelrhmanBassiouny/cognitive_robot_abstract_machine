"""
Tests for GeneratedCodeFileWriter and has_class_definitions.
"""

from __future__ import annotations

from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from krrood.patterns.code_generation.generated_code_file_writer import (
    GeneratedCodeFileWriter,
    has_class_definitions,
)


# ── has_class_definitions ─────────────────────────────────────────────────────


class TestHasClassDefinitions:
    def test_source_with_class_returns_true(self):
        assert has_class_definitions("class Foo:\n    pass\n")

    def test_source_with_multiple_classes_returns_true(self):
        src = "class Foo:\n    pass\nclass Bar:\n    pass\n"
        assert has_class_definitions(src)

    def test_source_without_class_returns_false(self):
        assert not has_class_definitions("x = 1\ndef foo(): pass\n")

    def test_empty_source_returns_false(self):
        assert not has_class_definitions("")

    def test_imports_only_returns_false(self):
        assert not has_class_definitions("from __future__ import annotations\nimport os\n")

    def test_syntax_error_falls_back_to_true(self):
        assert has_class_definitions("def (broken syntax")

    def test_nested_class_returns_true(self):
        src = "def outer():\n    class Inner:\n        pass\n"
        assert has_class_definitions(src)


# ── GeneratedCodeFileWriter.write ─────────────────────────────────────────────


def _make_module(name: str) -> ModuleType:
    m = MagicMock(spec=ModuleType)
    m.__name__ = name
    return m


class TestGeneratedCodeFileWriterWrite:
    """Tests for the write() method using a tmp_path filesystem."""

    @pytest.fixture
    def writer(self):
        return GeneratedCodeFileWriter()

    def _get_path_fn(self, base: Path):
        """Returns a get_path_fn that places files under base/."""

        def fn(module: ModuleType, is_mixin: bool) -> Path:
            if is_mixin:
                return base / "role_mixins" / f"{module.__name__}_role_mixins.py"
            return base / f"{module.__name__}.py"

        return fn

    def test_mixin_with_classes_is_written(self, writer, tmp_path):
        mod = _make_module("mymod")
        mixin_src = "class FooMixin:\n    pass\n"
        module_src = "x = 1\n"

        with patch("krrood.patterns.code_generation.generated_code_file_writer.run_ruff_on_file"), \
             patch("krrood.patterns.code_generation.generated_code_file_writer.run_black_on_file"):
            writer.write({mod: (module_src, mixin_src)}, self._get_path_fn(tmp_path))

        mixin_path = tmp_path / "role_mixins" / "mymod_role_mixins.py"
        assert mixin_path.exists()
        assert "FooMixin" in mixin_path.read_text()

    def test_mixin_without_classes_is_not_written(self, writer, tmp_path):
        mod = _make_module("mymod")
        mixin_src = "from __future__ import annotations\n"
        module_src = "x = 1\n"

        with patch("krrood.patterns.code_generation.generated_code_file_writer.run_ruff_on_file"), \
             patch("krrood.patterns.code_generation.generated_code_file_writer.run_black_on_file"):
            writer.write({mod: (module_src, mixin_src)}, self._get_path_fn(tmp_path))

        mixin_path = tmp_path / "role_mixins" / "mymod_role_mixins.py"
        assert not mixin_path.exists()

    def test_role_mixins_folder_not_created_when_no_mixin_content(self, writer, tmp_path):
        mod = _make_module("mymod")

        with patch("krrood.patterns.code_generation.generated_code_file_writer.run_ruff_on_file"), \
             patch("krrood.patterns.code_generation.generated_code_file_writer.run_black_on_file"):
            writer.write({mod: ("x = 1\n", "import os\n")}, self._get_path_fn(tmp_path))

        assert not (tmp_path / "role_mixins").exists()

    def test_existing_empty_mixin_file_is_deleted(self, writer, tmp_path):
        mod = _make_module("mymod")
        mixin_dir = tmp_path / "role_mixins"
        mixin_dir.mkdir()
        init = mixin_dir / "__init__.py"
        init.touch()
        mixin_path = mixin_dir / "mymod_role_mixins.py"
        mixin_path.write_text("import os\n")

        with patch("krrood.patterns.code_generation.generated_code_file_writer.run_ruff_on_file"), \
             patch("krrood.patterns.code_generation.generated_code_file_writer.run_black_on_file"):
            writer.write({mod: ("x = 1\n", "import os\n")}, self._get_path_fn(tmp_path))

        assert not mixin_path.exists()

    def test_empty_role_mixins_folder_is_cleaned_up(self, writer, tmp_path):
        mod = _make_module("mymod")
        mixin_dir = tmp_path / "role_mixins"
        mixin_dir.mkdir()
        init = mixin_dir / "__init__.py"
        init.touch()
        mixin_path = mixin_dir / "mymod_role_mixins.py"
        mixin_path.write_text("import os\n")

        with patch("krrood.patterns.code_generation.generated_code_file_writer.run_ruff_on_file"), \
             patch("krrood.patterns.code_generation.generated_code_file_writer.run_black_on_file"):
            writer.write({mod: ("x = 1\n", "import os\n")}, self._get_path_fn(tmp_path))

        assert not mixin_dir.exists()

    def test_folder_not_deleted_when_other_mixin_files_remain(self, writer, tmp_path):
        mod = _make_module("mymod")
        mixin_dir = tmp_path / "role_mixins"
        mixin_dir.mkdir()
        init = mixin_dir / "__init__.py"
        init.touch()
        mixin_path = mixin_dir / "mymod_role_mixins.py"
        mixin_path.write_text("import os\n")
        other = mixin_dir / "other_role_mixins.py"
        other.write_text("class OtherMixin:\n    pass\n")

        with patch("krrood.patterns.code_generation.generated_code_file_writer.run_ruff_on_file"), \
             patch("krrood.patterns.code_generation.generated_code_file_writer.run_black_on_file"):
            writer.write({mod: ("x = 1\n", "import os\n")}, self._get_path_fn(tmp_path))

        assert mixin_dir.exists()
        assert other.exists()

    def test_module_source_always_written(self, writer, tmp_path):
        mod = _make_module("mymod")

        with patch("krrood.patterns.code_generation.generated_code_file_writer.run_ruff_on_file"), \
             patch("krrood.patterns.code_generation.generated_code_file_writer.run_black_on_file"):
            writer.write({mod: ("x = 42\n", "import os\n")}, self._get_path_fn(tmp_path))

        assert (tmp_path / "mymod.py").read_text() == "x = 42\n"


# ── _cleanup_empty_generated_package ─────────────────────────────────────────


class TestCleanupEmptyGeneratedPackage:
    def test_deletes_folder_with_only_empty_init(self, tmp_path):
        folder = tmp_path / "role_mixins"
        folder.mkdir()
        (folder / "__init__.py").touch()
        GeneratedCodeFileWriter._cleanup_empty_generated_package(folder)
        assert not folder.exists()

    def test_deletes_pycache_alongside_empty_init(self, tmp_path):
        folder = tmp_path / "role_mixins"
        folder.mkdir()
        (folder / "__init__.py").touch()
        pycache = folder / "__pycache__"
        pycache.mkdir()
        (pycache / "something.pyc").write_bytes(b"fake")
        GeneratedCodeFileWriter._cleanup_empty_generated_package(folder)
        assert not folder.exists()

    def test_leaves_folder_with_nonempty_init(self, tmp_path):
        folder = tmp_path / "role_mixins"
        folder.mkdir()
        (folder / "__init__.py").write_text("# not empty\n")
        GeneratedCodeFileWriter._cleanup_empty_generated_package(folder)
        assert folder.exists()

    def test_leaves_folder_with_extra_files(self, tmp_path):
        folder = tmp_path / "role_mixins"
        folder.mkdir()
        (folder / "__init__.py").touch()
        (folder / "extra.py").write_text("class X: pass\n")
        GeneratedCodeFileWriter._cleanup_empty_generated_package(folder)
        assert folder.exists()

    def test_no_error_when_folder_does_not_exist(self, tmp_path):
        GeneratedCodeFileWriter._cleanup_empty_generated_package(tmp_path / "nonexistent")
