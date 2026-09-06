from typing_extensions import Sequence

from krrood.class_diagrams.class_diagram import ClassDiagram
from krrood.class_diagrams.utils import get_type_hints_of_object

from ..dataset.class_named_like_a_typing_alias import Sequence as SequenceTheDomainClass
from ..dataset.class_with_a_sequence_of_pieces import (
    ClassWithASequenceOfPieces,
    Piece,
)


def test_a_field_reads_the_alias_its_own_module_imported_over_a_class_of_the_same_name():
    """
    An annotation must resolve to what the module it was written in binds the name to,
    even when a class in the diagram answers to the same name.

    The diagram offers its classes by bare name while resolving an annotation, which is
    what lets a name reach a type its module only imports for type checking. Offered
    ahead of the module's own bindings, though, a domain class called ``Sequence``
    replaced the alias the annotating module had imported, and the field failed to
    resolve at all.
    """
    get_type_hints_of_object.cache_clear()

    diagram = ClassDiagram([SequenceTheDomainClass, Piece, ClassWithASequenceOfPieces])
    wrapped_class = diagram.get_wrapped_class(ClassWithASequenceOfPieces)
    (wrapped_field,) = [
        field for field in wrapped_class.fields if field.name == "pieces"
    ]

    assert wrapped_field.resolved_type == Sequence[Piece]
