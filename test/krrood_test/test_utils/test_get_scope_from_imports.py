import ast
import math
import sys
from pathlib import Path
from collections import defaultdict
from typing import Any, Dict

import pytest

from krrood.utils import (
    ModuleMock,
    MockImportResult,
    find_module_source_path,
    get_scope_from_imports,
)
from krrood.exceptions import SourceDataNotProvided


# ---------------------------------------------------------------------------
# Basic scope extraction
# ---------------------------------------------------------------------------


def test_scope_from_simple_imports():
    source = "import os\nimport math as m"
    scope = get_scope_from_imports(source=source)
    import os
    assert scope["os"] is os
    assert scope["m"] is math


def test_scope_from_from_imports():
    source = "from pathlib import Path\nfrom collections import defaultdict as dd"
    scope = get_scope_from_imports(source=source)
    assert scope["Path"] is Path
    assert scope["dd"] is defaultdict


def test_scope_from_wildcard_import():
    source = "from math import *"
    scope = get_scope_from_imports(source=source)
    assert scope["sin"] is math.sin
    assert scope["cos"] is math.cos
    assert scope["pi"] == math.pi


def test_scope_from_ast_tree():
    source = "import os"
    tree = ast.parse(source)
    scope = get_scope_from_imports(tree=tree)
    import os
    assert scope["os"] is os


def test_scope_raises_when_no_input():
    with pytest.raises(SourceDataNotProvided):
        get_scope_from_imports()


# ---------------------------------------------------------------------------
# Graceful handling of unimportable modules
# ---------------------------------------------------------------------------


def test_unimportable_regular_import_is_skipped():
    source = "import non_existent_module_xyz"
    scope = get_scope_from_imports(source=source)
    assert "non_existent_module_xyz" not in scope


def test_unimportable_from_import_is_skipped():
    source = "from non_existent_module_xyz import Foo"
    scope = get_scope_from_imports(source=source)
    assert "Foo" not in scope


# ---------------------------------------------------------------------------
# Relative import resolution
# ---------------------------------------------------------------------------


def test_scope_from_relative_import(tmp_path):
    root = tmp_path / "my_package"
    root.mkdir()
    (root / "__init__.py").touch()

    sub = root / "sub"
    sub.mkdir()
    (sub / "__init__.py").touch()

    (sub / "module_a.py").write_text("class A: pass")
    (sub / "module_b.py").write_text("from .module_a import A")

    sys.path.append(str(tmp_path))
    try:
        scope = get_scope_from_imports(file_path=str(sub / "module_b.py"))
        assert "A" in scope
        from my_package.sub.module_a import A
        assert scope["A"] is A
    finally:
        sys.path.remove(str(tmp_path))


# ---------------------------------------------------------------------------
# Mock-import fallback: imported names in the failing module
# ---------------------------------------------------------------------------


def test_fallback_resolves_imported_name_from_unimportable_module(tmp_path):
    """
    When a local module cannot be imported due to a broken external dependency,
    get_scope_from_imports should mock the external dep and still resolve names
    that the failing module re-exports from other importable modules.
    """
    pkg = tmp_path / "fallback_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").touch()
    (pkg / "base.py").write_text(
        "import non_existent_rclpy\nfrom pathlib import Path\n"
    )
    (pkg / "consumer.py").write_text("from fallback_pkg.base import Path\n")

    sys.path.insert(0, str(tmp_path))
    try:
        scope = get_scope_from_imports(file_path=str(pkg / "consumer.py"))
        assert "Path" in scope
        assert scope["Path"] is Path
    finally:
        sys.path.remove(str(tmp_path))


# ---------------------------------------------------------------------------
# Mock-import fallback: locally defined classes in the failing module
# ---------------------------------------------------------------------------


def test_fallback_resolves_locally_defined_class(tmp_path):
    """
    When the requested name is a class *defined* (not imported) inside an
    unimportable module, mock-importing the module should yield the real class
    object — not a stub — so methods and module metadata are accurate.
    """
    pkg = tmp_path / "real_class_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").touch()
    (pkg / "provider.py").write_text(
        "import non_existent_rclpy\n\nclass Foo:\n    def greet(self): return 'hello'\n"
    )
    (pkg / "consumer.py").write_text("from real_class_pkg.provider import Foo\n")

    sys.path.insert(0, str(tmp_path))
    try:
        scope = get_scope_from_imports(file_path=str(pkg / "consumer.py"))
        assert "Foo" in scope
        assert scope["Foo"].__name__ == "Foo"
        assert scope["Foo"].__module__ == "real_class_pkg.provider"
        assert scope["Foo"]().greet() == "hello"
    finally:
        sys.path.remove(str(tmp_path))


# ---------------------------------------------------------------------------
# Mock-import fallback: class inheriting from an external mocked base
# ---------------------------------------------------------------------------


def test_fallback_includes_class_with_external_mocked_base(tmp_path):
    """
    A class that inherits from an external (mocked) base class should still be
    included in scope. The user accepts this trade-off: the base is a stub type
    but the subclass itself is the real object with the correct __module__.
    """
    pkg = tmp_path / "mocked_base_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").touch()
    (pkg / "nodes.py").write_text(
        "from non_existent_rclpy import Node\n\n"
        "class MyNode(Node):\n"
        "    def custom(self): return 42\n"
    )
    (pkg / "consumer.py").write_text("from mocked_base_pkg.nodes import MyNode\n")

    sys.path.insert(0, str(tmp_path))
    try:
        scope = get_scope_from_imports(file_path=str(pkg / "consumer.py"))
        assert "MyNode" in scope
        assert scope["MyNode"].__name__ == "MyNode"
        assert scope["MyNode"].__module__ == "mocked_base_pkg.nodes"
        assert scope["MyNode"]().custom() == 42
    finally:
        sys.path.remove(str(tmp_path))


# ---------------------------------------------------------------------------
# Mock-import fallback: mocked objects are not added to scope
# ---------------------------------------------------------------------------


def test_fallback_skips_objects_originating_from_mocked_module(tmp_path):
    """
    Objects that originate directly from a mocked external module (i.e. they are
    stub types produced by ModuleMock) must not be added to the scope.
    """
    pkg = tmp_path / "filter_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").touch()
    (pkg / "source.py").write_text(
        "from non_existent_rclpy import Node\n\n"
        "class LocalClass:\n    pass\n"
    )
    (pkg / "consumer.py").write_text(
        "from filter_pkg.source import Node, LocalClass\n"
    )

    sys.path.insert(0, str(tmp_path))
    try:
        scope = get_scope_from_imports(file_path=str(pkg / "consumer.py"))
        assert "Node" not in scope
        assert "LocalClass" in scope
    finally:
        sys.path.remove(str(tmp_path))


# ---------------------------------------------------------------------------
# External package: skipped without recursion
# ---------------------------------------------------------------------------


def test_external_package_is_skipped(tmp_path, monkeypatch):
    """
    When the source of a failing module lives under site-packages or dist-packages
    it is treated as an external package and skipped entirely.
    """
    fake_site = tmp_path / "site-packages" / "some_ros_pkg"
    fake_site.mkdir(parents=True)
    (fake_site / "__init__.py").write_text("from pathlib import Path\n")

    def fake_find(module_name):
        if module_name == "some_ros_pkg":
            return str(fake_site / "__init__.py")
        return None

    monkeypatch.setattr("krrood.utils.find_module_source_path", fake_find)

    scope = get_scope_from_imports(source="from some_ros_pkg import Path")
    assert "Path" not in scope


# ---------------------------------------------------------------------------
# Cycle protection
# ---------------------------------------------------------------------------


def test_circular_local_imports_do_not_cause_infinite_recursion(tmp_path):
    """
    Mutually importing local modules must terminate without a RecursionError
    and return an empty-but-valid scope.
    """
    pkg = tmp_path / "circular_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").touch()
    (pkg / "a.py").write_text("from circular_pkg.b import B\n")
    (pkg / "b.py").write_text("from circular_pkg.a import A\n")

    sys.path.insert(0, str(tmp_path))
    try:
        scope = get_scope_from_imports(file_path=str(pkg / "a.py"))
        assert isinstance(scope, dict)
    finally:
        sys.path.remove(str(tmp_path))


# ---------------------------------------------------------------------------
# sys.modules is not polluted after fallback
# ---------------------------------------------------------------------------


def test_mock_import_does_not_pollute_sys_modules(tmp_path):
    """
    After the mock-import fallback runs, neither the target module nor any of
    its mocked dependencies should remain in sys.modules.
    """
    pkg = tmp_path / "clean_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").touch()
    (pkg / "base.py").write_text(
        "import non_existent_rclpy\nfrom pathlib import Path\n"
    )
    (pkg / "consumer.py").write_text("from clean_pkg.base import Path\n")

    sys.path.insert(0, str(tmp_path))
    modules_before = set(sys.modules.keys())
    try:
        get_scope_from_imports(file_path=str(pkg / "consumer.py"))
        added = set(sys.modules.keys()) - modules_before
        assert "clean_pkg.base" not in added
        assert "non_existent_rclpy" not in added
    finally:
        sys.path.remove(str(tmp_path))
        for key in set(sys.modules.keys()) - modules_before:
            sys.modules.pop(key, None)


# ---------------------------------------------------------------------------
# ModuleMock unit tests
# ---------------------------------------------------------------------------


def test_module_mock_provides_correct_module_metadata():
    mock = ModuleMock(module_name="rclpy.node")
    assert mock.__name__ == "rclpy.node"
    assert mock.__package__ == "rclpy"
    assert mock.__path__ == []
    assert mock.__spec__ is None
    assert mock.__file__ is None


def test_module_mock_returns_unique_type_per_attribute():
    mock = ModuleMock(module_name="rclpy")
    node_type = mock.Node
    assert isinstance(node_type, type)
    assert node_type.__name__ == "Node"
    assert node_type.__module__ == "rclpy"


def test_module_mock_caches_attribute_types():
    mock = ModuleMock(module_name="rclpy")
    assert mock.Node is mock.Node


def test_module_mock_different_attributes_are_different_types():
    mock = ModuleMock(module_name="rclpy")
    assert mock.Node is not mock.Publisher


# ---------------------------------------------------------------------------
# MockImportResult unit tests
# ---------------------------------------------------------------------------


def test_mock_import_result_succeeded_property():
    import os
    result_success = MockImportResult(module=os, external_mocked_names=frozenset())
    result_failure = MockImportResult(module=None, external_mocked_names=frozenset())
    assert result_success.succeeded is True
    assert result_failure.succeeded is False
