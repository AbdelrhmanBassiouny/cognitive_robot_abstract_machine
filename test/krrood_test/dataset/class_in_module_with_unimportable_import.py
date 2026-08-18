from __future__ import annotations

from dataclasses import dataclass

from .class_with_type_checking_only_annotation import (
    ClassWithTypeCheckingOnlyAnnotation,
)


def _unimportable_module_import() -> None:
    """
    Names a module that cannot be imported from inside a function body.

    The module is never executed, so importing this file succeeds; extracting its
    imports, however, still meets the from-import. This mirrors modules such as
    ``semantic_digital_twin.adapters.ros.world_synchronizer``, which import their own
    not-yet-generated ORM interface from inside method bodies.
    """
    from non_existent_krrood_test_module_xyz import SomethingUnavailable  # noqa: F401


@dataclass
class ClassInModuleWithUnimportableImport(ClassWithTypeCheckingOnlyAnnotation):
    """
    A dataclass whose own module carries a from-import of a module that cannot be
    imported.

    Inherits :class:`ClassWithTypeCheckingOnlyAnnotation`, whose field is typed by a
    ``TYPE_CHECKING``-only import, so resolving this class's hints must look past its
    own module (which contains the un-importable import) into the base's module.
    """
