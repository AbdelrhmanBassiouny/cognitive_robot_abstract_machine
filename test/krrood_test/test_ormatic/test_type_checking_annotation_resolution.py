from krrood.class_diagrams.utils import get_type_hints_of_object

from ..dataset.annotation_only_referenced_type import TypeReferencedOnlyInAnnotations
from ..dataset.class_in_module_with_unimportable_import import (
    ClassInModuleWithUnimportableImport,
)
from ..dataset.class_with_type_checking_only_annotation import (
    ClassWithTypeCheckingOnlyAnnotation,
)


def test_type_checking_only_field_annotation_resolves_to_referenced_type():
    """
    A field typed by a ``TYPE_CHECKING``-only import must still resolve to that exact
    type.

    ``ClassWithTypeCheckingOnlyAnnotation.annotation_only_field`` is annotated with
    :class:`TypeReferencedOnlyInAnnotations`, which is imported only inside a ``TYPE_CHECKING``
    block - the same annotation-only pattern that ``semantic_digital_twin`` and ``coraplex`` use for
    fields such as ``GraspDescription.end_effector``. The name is therefore absent from the module's
    runtime namespace, so a naive ``get_type_hints`` raises ``NameError`` and the resolver must
    recover the type from the module's type-checking imports instead of raising
    ``CouldNotResolveType``.
    """
    resolved_type_hints = get_type_hints_of_object(ClassWithTypeCheckingOnlyAnnotation)

    assert (
        resolved_type_hints["annotation_only_field"] is TypeReferencedOnlyInAnnotations
    )


def test_type_checking_annotation_resolves_across_module_with_unimportable_import():
    """
    A ``TYPE_CHECKING``-only annotation resolves even when the class's own module
    imports a module that cannot be imported.

    ``ClassInModuleWithUnimportableImport`` inherits its annotated field from
    ``ClassWithTypeCheckingOnlyAnnotation``, and its own module contains a from-import of a
    module that does not exist. Resolving the hint raises the same ``NameError``, and the
    resolver must skip the class's own module - whose import extraction cannot complete -
    and find the type in the base's module instead of failing the whole resolution.
    """
    resolved_type_hints = get_type_hints_of_object(ClassInModuleWithUnimportableImport)

    assert (
        resolved_type_hints["annotation_only_field"] is TypeReferencedOnlyInAnnotations
    )
