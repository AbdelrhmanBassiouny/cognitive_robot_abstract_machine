"""Tests for action base classes, concrete actions, ActionPlan, and ActionExecutor."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from tempfile import TemporaryDirectory

import libcst
import pytest

from krrood.patterns.code_generation.actions.base import (
    Action,
    GenerationAction,
    TransformationAction,
)
from krrood.patterns.code_generation.actions.plan import (
    ActionExecutor,
    ActionPlan,
    ActionResult,
)
from krrood.patterns.code_generation.actions.transform import (
    AddBaseClass,
    AddDecorator,
    AddImport,
    AddMethod,
    AddProperty,
    EnsureSuperInitCall,
    RemoveBaseClass,
)
from krrood.patterns.code_generation.exceptions import ClassNotFoundError
from krrood.patterns.code_generation.actions.generate import (
    CreateClass,
    WriteModule,
)
from krrood.patterns.code_generation.specs.specs import BaseClassSpec

# ── helpers ───────────────────────────────────────────────────────────


def parse_module(src: str) -> libcst.Module:
    return libcst.parse_module(src)


PERSON_CLASS = """\
class Person:
    name: str
    age: int = 0
"""

PERSON_WITH_INIT = """\
@dataclass(eq=False, init=False)
class Person:
    name: str
    age: int = 0

    def __init__(self, name: str, age: int = 0):
        self.name = name
        self.age = age
"""


# ── Action ABC tests ──────────────────────────────────────────────────


class TestActionABC:
    def test_cannot_instantiate_abstract_action(self):
        with pytest.raises(TypeError):
            Action()

    def test_cannot_instantiate_abstract_transformation(self):
        with pytest.raises(TypeError):
            TransformationAction()

    def test_cannot_instantiate_abstract_generation(self):
        with pytest.raises(TypeError):
            GenerationAction()

    def test_concrete_subclass_works(self):
        @dataclasses.dataclass
        class NoOp(TransformationAction):
            desc: str = "no-op"

            @property
            def description(self) -> str:
                return self.desc

            def apply(self, module):
                return module

            def reverse(self, module):
                return module

        action = NoOp()
        mod = parse_module("x = 1")
        assert action.apply(mod) is not None
        assert action.reverse(mod) is not None
        assert action.description == "no-op"
        assert action.precondition(mod) is True


# ── ActionPlan tests ──────────────────────────────────────────────────


class TestActionPlan:
    def test_empty_plan_does_nothing(self):
        plan = ActionPlan(description="empty")
        mod = parse_module("x = 1")
        result = plan.apply(mod)
        assert result.code == mod.code

    def test_apply_applies_in_order(self):
        mod = parse_module(PERSON_CLASS)
        plan = ActionPlan(
            [
                AddBaseClass("Person", BaseClassSpec(name="HasRoles")),
                AddMethod(
                    "Person",
                    libcst.parse_statement("def greet(self) -> str: ..."),
                ),
            ],
            description="test",
        )
        result = plan.apply(mod)
        assert "HasRoles" in result.code
        assert "def greet" in result.code

    def test_reverse_is_lifo(self):
        mod = parse_module(PERSON_CLASS)
        plan = ActionPlan(
            [
                AddBaseClass("Person", BaseClassSpec(name="HasRoles")),
                AddMethod(
                    "Person",
                    libcst.parse_statement("def x(self) -> str: ..."),
                ),
            ],
            description="test",
        )
        transformed = plan.apply(mod)
        reversed_mod = plan.reverse(transformed)
        assert "HasRoles" not in reversed_mod.code
        assert "def x" not in reversed_mod.code

    def test_nested_plans(self):
        mod = parse_module(PERSON_CLASS)
        inner = ActionPlan(
            [
                AddMethod(
                    "Person",
                    libcst.parse_statement("def inner_method(self) -> int: ..."),
                ),
            ],
            description="inner",
        )
        outer = ActionPlan(
            [
                AddBaseClass("Person", BaseClassSpec(name="HasRoles")),
                inner,
            ],
            description="outer",
        )
        result = outer.apply(mod)
        assert "HasRoles" in result.code
        assert "def inner_method" in result.code

    def test_len(self):
        plan = ActionPlan(
            [
                AddBaseClass("Person", BaseClassSpec(name="HasRoles")),
                AddBaseClass("Person", BaseClassSpec(name="ABC")),
            ],
            description="test",
        )
        assert len(plan) == 2

    def test_bool_false_for_empty(self):
        assert not bool(ActionPlan(description="empty"))

    def test_bool_true_for_nonempty(self):
        plan = ActionPlan(
            [AddBaseClass("Person", BaseClassSpec(name="HasRoles"))],
            description="test",
        )
        assert bool(plan)


# ── ActionExecutor tests ──────────────────────────────────────────────


class TestActionExecutor:
    def test_successful_execution(self):
        executor = ActionExecutor()
        mod = parse_module(PERSON_CLASS)
        plan = ActionPlan(
            [
                AddBaseClass("Person", BaseClassSpec(name="HasRoles")),
            ],
            description="test",
        )
        result = executor.execute(plan, mod)
        assert result.success is True
        assert result.module is not None
        assert "HasRoles" in result.module.code
        assert len(result.actions_applied) == 1

    def test_rollback_on_failure(self):
        @dataclasses.dataclass
        class FailingAction(TransformationAction):
            desc: str = "fails"
            applied: bool = dataclasses.field(default=False, init=False)

            @property
            def description(self) -> str:
                return self.desc

            def apply(self, module):
                self.applied = True
                raise RuntimeError("simulated failure")

            def reverse(self, module):
                self.applied = False
                return module

        executor = ActionExecutor()
        mod = parse_module(PERSON_CLASS)
        plan = ActionPlan(
            [
                AddBaseClass("Person", BaseClassSpec(name="HasRoles")),
                FailingAction(),
            ],
            description="test",
        )
        result = executor.execute(plan, mod)
        assert result.success is False
        assert "simulated failure" in str(result.error)
        # The first action should have been rolled back
        assert "HasRoles" not in mod.code  # original module unchanged
        assert len(result.actions_applied) == 1


# ── AddBaseClass tests ────────────────────────────────────────────────


class TestAddBaseClass:
    def test_add_single_base(self):
        mod = parse_module(PERSON_CLASS)
        action = AddBaseClass("Person", BaseClassSpec(name="HasRoles"))
        result = action.apply(mod)
        assert "class Person(HasRoles):" in result.code

    def test_add_second_base(self):
        mod = parse_module("class Person(HasRoles):\n    name: str\n")
        action = AddBaseClass("Person", BaseClassSpec(name="ABC"))
        result = action.apply(mod)
        assert "class Person(HasRoles, ABC):" in result.code

    def test_reverse_removes_base(self):
        mod = parse_module(PERSON_CLASS)
        action = AddBaseClass("Person", BaseClassSpec(name="HasRoles"))
        applied = action.apply(mod)
        reversed_mod = action.reverse(applied)
        assert "HasRoles" not in reversed_mod.code
        assert "class Person:" in reversed_mod.code

    def test_nonexistent_class_raises(self):
        mod = parse_module(PERSON_CLASS)
        action = AddBaseClass("Nonexistent", BaseClassSpec(name="ABC"))
        with pytest.raises(ClassNotFoundError, match="Nonexistent"):
            action.apply(mod)

    def test_description(self):
        action = AddBaseClass("Person", BaseClassSpec(name="HasRoles"))
        assert "HasRoles" in action.description
        assert "Person" in action.description


# ── RemoveBaseClass tests ─────────────────────────────────────────────


class TestRemoveBaseClass:
    def test_remove_existing_base(self):
        mod = parse_module("class Person(HasRoles, ABC):\n    name: str\n")
        action = RemoveBaseClass("Person", "HasRoles")
        result = action.apply(mod)
        assert "HasRoles" not in result.code
        assert "class Person(ABC):" in result.code

    def test_reverse_reads_base(self):
        mod = parse_module("class Person(HasRoles):\n    name: str\n")
        action = RemoveBaseClass("Person", "HasRoles")
        applied = action.apply(mod)
        reversed_mod = action.reverse(applied)
        assert "HasRoles" in reversed_mod.code

    def test_non_existent_class_is_noop(self):
        mod = parse_module(PERSON_CLASS)
        action = RemoveBaseClass("Nonexistent", "ABC")
        result = action.apply(mod)
        assert result.code == mod.code


# ── AddMethod tests ───────────────────────────────────────────────────


class TestAddMethod:
    def test_add_method_to_class(self):
        mod = parse_module(PERSON_CLASS)
        method = libcst.parse_statement("def greet(self) -> str: ...")
        action = AddMethod("Person", method)
        result = action.apply(mod)
        assert "def greet" in result.code

    def test_reverse_removes_method(self):
        mod = parse_module(PERSON_CLASS)
        method = libcst.parse_statement("def greet(self) -> str: ...")
        action = AddMethod("Person", method)
        applied = action.apply(mod)
        reversed_mod = action.reverse(applied)
        assert "def greet" not in reversed_mod.code

    def test_nonexistent_class_raises(self):
        mod = parse_module(PERSON_CLASS)
        method = libcst.parse_statement("def x(self): ...")
        action = AddMethod("Nonexistent", method)
        with pytest.raises(ClassNotFoundError):
            action.apply(mod)

    def test_description_includes_method_name(self):
        method = libcst.parse_statement("def get_name(self) -> str: ...")
        action = AddMethod("Person", method)
        assert "get_name" in action.description
        assert "Person" in action.description


# ── AddProperty tests ─────────────────────────────────────────────────


class TestAddProperty:
    def test_add_getter_only(self):
        mod = parse_module(PERSON_CLASS)
        getter = libcst.parse_statement("@property\ndef delegatee(self) -> Person: ...")
        action = AddProperty("Person", getter)
        result = action.apply(mod)
        assert "@property" in result.code
        assert "def delegatee" in result.code

    def test_add_getter_and_setter(self):
        mod = parse_module(PERSON_CLASS)
        getter = libcst.parse_statement("@property\ndef age(self) -> int: ...")
        setter = libcst.parse_statement("@age.setter\ndef age(self, value: int) -> None: ...")
        action = AddProperty("Person", getter, setter)
        result = action.apply(mod)
        assert "def age" in result.code
        assert "age.setter" in result.code

    def test_reverse_removes_both(self):
        mod = parse_module(PERSON_CLASS)
        getter = libcst.parse_statement("@property\ndef x(self) -> int: ...")
        setter = libcst.parse_statement("@x.setter\ndef x(self, value): ...")
        action = AddProperty("Person", getter, setter)
        applied = action.apply(mod)
        reversed_mod = action.reverse(applied)
        assert "def x" not in reversed_mod.code


# ── AddDecorator tests ────────────────────────────────────────────────


class TestAddDecorator:
    def test_add_decorator_to_class(self):
        mod = parse_module(PERSON_CLASS)
        deco = libcst.Decorator(decorator=libcst.Name("dataclass"))
        action = AddDecorator("Person", deco)
        result = action.apply(mod)
        assert "@dataclass" in result.code

    def test_reverse_removes_decorator(self):
        mod = parse_module(PERSON_CLASS)
        deco = libcst.Decorator(decorator=libcst.Name("dataclass"))
        action = AddDecorator("Person", deco)
        applied = action.apply(mod)
        reversed_mod = action.reverse(applied)
        assert "@dataclass" not in reversed_mod.code


# ── AddImport tests ───────────────────────────────────────────────────


class TestAddImport:
    def test_add_single_import(self):
        mod = parse_module("x = 1\n")
        action = AddImport("typing", ["List"])
        result = action.apply(mod)
        assert "from typing import List" in result.code

    def test_add_multiple_names(self):
        mod = parse_module("x = 1\n")
        action = AddImport("typing", ["List", "Optional"])
        result = action.apply(mod)
        assert "from typing import List, Optional" in result.code

    def test_empty_names_is_noop(self):
        mod = parse_module("x = 1\n")
        action = AddImport("typing", [])
        result = action.apply(mod)
        assert result.code == mod.code

    def test_reverse_removes_import(self):
        mod = parse_module("x = 1\n")
        action = AddImport("typing", ["List"])
        applied = action.apply(mod)
        reversed_mod = action.reverse(applied)
        assert "from typing import List" not in reversed_mod.code

    def test_description(self):
        action = AddImport("typing", ["List", "Optional"])
        assert "typing" in action.description
        assert "List" in action.description


# ── EnsureSuperInitCall tests ─────────────────────────────────────────


class TestEnsureSuperInitCall:
    def test_adds_call_to_init(self):
        mod = parse_module(PERSON_WITH_INIT)
        action = EnsureSuperInitCall("Person", "HasRoles")
        result = action.apply(mod)
        assert "HasRoles.__init__(self)" in result.code

    def test_noop_if_call_already_exists(self):
        src = """\
@dataclass(eq=False, init=False)
class Person:
    name: str
    def __init__(self, name: str):
        HasRoles.__init__(self)
        self.name = name
"""
        mod = parse_module(src)
        action = EnsureSuperInitCall("Person", "HasRoles")
        result = action.apply(mod)
        assert result.code == mod.code

    def test_noop_if_no_init_method(self):
        mod = parse_module(PERSON_CLASS)
        action = EnsureSuperInitCall("Person", "HasRoles")
        result = action.apply(mod)
        assert result.code == mod.code

    def test_reverse_removes_call(self):
        mod = parse_module(PERSON_WITH_INIT)
        action = EnsureSuperInitCall("Person", "HasRoles")
        applied = action.apply(mod)
        reversed_mod = action.reverse(applied)
        assert "HasRoles.__init__(self)" not in reversed_mod.code


# ── CreateClass tests ─────────────────────────────────────────────────


class TestCreateClass:
    def test_create_class_in_module(self):
        mod = parse_module(PERSON_CLASS)
        body = [
            libcst.parse_statement("delegatee: Person"),
            libcst.parse_statement("def get_name(self) -> str: ..."),
        ]
        action = CreateClass(
            class_name="DelegatorForPerson",
            bases=[BaseClassSpec(name="ABC")],
            body=body,
        )
        result = action.apply(mod)
        assert "class DelegatorForPerson" in result.code
        assert "delegatee: Person" in result.code

    def test_reverse_removes_class(self):
        mod = parse_module(PERSON_CLASS)
        action = CreateClass(
            class_name="Helper",
            bases=[BaseClassSpec(name="ABC")],
            body=[],
        )
        applied = action.apply(mod)
        reversed_mod = action.reverse(applied)
        assert "class Helper" not in reversed_mod.code

    def test_description(self):
        action = CreateClass("Helper", bases=[], body=[])
        assert "Helper" in action.description


# ── WriteModule tests ─────────────────────────────────────────────────


class TestWriteModule:
    def test_write_new_file(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_module.py"
            mod = parse_module("x = 1")
            action = WriteModule(path, mod.code)
            action.apply(mod)
            assert path.exists()
            assert path.read_text() == mod.code

    def test_reverse_deletes_new_file(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_module.py"
            mod = parse_module("x = 1")
            action = WriteModule(path, mod.code)
            action.apply(mod)
            action.reverse(mod)
            assert not path.exists()

    def test_backup_and_restore_existing_file(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "existing.py"
            path.write_text("original content")
            mod = parse_module("x = 1\n")
            action = WriteModule(path, mod.code)
            action.apply(mod)
            assert path.read_text() == mod.code
            action.reverse(mod)
            assert path.read_text() == "original content"

    def test_creates_parent_directories(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "subdir" / "nested" / "module.py"
            mod = parse_module("x = 1")
            action = WriteModule(path, mod.code)
            action.apply(mod)
            assert path.exists()
