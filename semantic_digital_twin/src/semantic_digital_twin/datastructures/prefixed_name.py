from dataclasses import dataclass, field

from typing_extensions import Optional

from krrood.entity_query_language.predicate import Symbol
from krrood.entity_query_language.verbalization.grammar_metadata import GrammarMetadata


@dataclass
class PrefixedName(Symbol):
    name: str = field(
        metadata=GrammarMetadata(stands_for_its_owner=True).as_dict(),
    )
    """
    The local name identifying the entity.

    A prefixed name is a name and the namespace telling it apart from an equal one
    elsewhere, so this field is the whole of what it is: reading it says the name it
    belongs to and stops, rather than saying the word twice.
    """

    prefix: Optional[str] = None
    """
    Optional namespace that disambiguates the name from equally named entities in other
    scopes.
    """

    def __hash__(self):
        return hash((self.prefix, self.name))

    def __str__(self):
        if self.prefix is None or self.prefix == "":
            return self.name
        return f"{self.prefix}/{self.name}"

    def __repr__(self):
        return f"{self.__class__.__name__}('{self.prefix}/{self.name}')"

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        return self.prefix == other.prefix and self.name == other.name

    def __lt__(self, other):
        return str(self) < str(other)

    def __le__(self, other):
        return str(self) <= str(other)

    def __gt__(self, other):
        return str(self) > str(other)

    def __ge__(self, other):
        return str(self) >= str(other)
