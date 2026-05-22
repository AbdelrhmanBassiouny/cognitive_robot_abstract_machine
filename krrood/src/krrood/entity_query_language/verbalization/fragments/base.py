from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

from krrood.entity_query_language.verbalization.fragments.roles import SemanticRole
from krrood.entity_query_language.verbalization.fragments.source_ref import SourceRef

if TYPE_CHECKING:
    from krrood.entity_query_language.core.mapped_variable import Attribute


@dataclass
class VerbFragment:
    """
    Abstract base for all verbalized output fragments.

    The fragment hierarchy forms a tree:

    * Leaf nodes: :class:`WordFragment`, :class:`RoleFragment`.
    * Inline composition: :class:`PhraseFragment`.
    * Block structure: :class:`BlockFragment`.

    Renderers traverse this tree to produce strings.
    """


@dataclass
class WordFragment(VerbFragment):
    """
    Plain neutral text with no semantic role: articles, connectives, punctuation.

    :ivar text: The raw text string (e.g. ``"the"``, ``"and"``, ``","``).
    """

    text: str


@dataclass
class RoleFragment(VerbFragment):
    """
    Text carrying a :class:`~krrood.entity_query_language.verbalization.fragments.roles.SemanticRole`
    — drives colour markup and optional source hyperlinking.

    :ivar text: Display text (e.g. ``"Robot"``, ``"is greater than"``).
    :ivar role: Semantic role determining the colour applied by the formatter.
    :ivar source_ref: Optional reference to the Python class or attribute this
        fragment represents; used by
        :class:`~krrood.entity_query_language.verbalization.rendering.source_link_resolver.SourceLinkResolver`
        to build hyperlinks.
    """

    text: str
    role: SemanticRole
    source_ref: Optional[SourceRef] = None

    @classmethod
    def for_variable(cls, label: str, expr) -> "RoleFragment":
        """
        Build a fragment for a
        :class:`~krrood.entity_query_language.core.variable.Variable`,
        :class:`~krrood.entity_query_language.core.variable.InstantiatedVariable`,
        or :class:`~krrood.entity_query_language.query.query.Entity`, linked to its type.

        :param label: Display text (type name or disambiguated label).
        :type label: str
        :param expr: Expression whose ``_type_`` attribute supplies the source reference.
        :returns: :class:`RoleFragment` with :attr:`~SemanticRole.VARIABLE` role.
        :rtype: RoleFragment
        """
        return cls(
            text=label,
            role=SemanticRole.VARIABLE,
            source_ref=SourceRef.for_type(getattr(expr, "_type_", None)),
        )

    @classmethod
    def for_attribute(cls, label: str, owner, attr_name: str) -> "RoleFragment":
        """
        Build a fragment for an attribute access, linked to its owner class.

        :param label: Display text (attribute name, possibly pluralised).
        :type label: str
        :param owner: Owner class of the attribute (used for source linking).
        :param attr_name: Canonical attribute name on *owner*.
        :type attr_name: str
        :returns: :class:`RoleFragment` with :attr:`~SemanticRole.ATTRIBUTE` role.
        :rtype: RoleFragment
        """
        return cls(
            text=label,
            role=SemanticRole.ATTRIBUTE,
            source_ref=SourceRef.for_attribute(owner, attr_name),
        )

    @classmethod
    def for_operator(cls, label: str) -> "RoleFragment":
        """
        Build a fragment for an operator or copula (no source link).

        :param label: Display text (e.g. ``"is"``, ``"not"``, ``"greater than"``).
        :type label: str
        :returns: :class:`RoleFragment` with :attr:`~SemanticRole.OPERATOR` role.
        :rtype: RoleFragment
        """
        return cls(text=label, role=SemanticRole.OPERATOR)


@dataclass
class PhraseFragment(VerbFragment):
    """
    An inline sequence of fragments joined by a separator.

    :ivar parts: Ordered list of child fragments.
    :ivar separator: String inserted between adjacent parts (default: single space).
    """

    parts: list[VerbFragment]
    separator: str = " "

    @classmethod
    def joined(cls, parts: list[VerbFragment], separator: str = " ") -> "PhraseFragment":
        """
        Create a :class:`PhraseFragment` with an explicit separator.

        :param parts: Child fragments.
        :param separator: Separator string.
        :returns: New :class:`PhraseFragment`.
        :rtype: PhraseFragment
        """
        return cls(parts=parts, separator=separator)

    @classmethod
    def spaced(cls, *parts: VerbFragment) -> "PhraseFragment":
        """
        Create a :class:`PhraseFragment` with space-separated *parts*.

        :param parts: Child fragments (varargs).
        :returns: New :class:`PhraseFragment` with ``separator=" "``.
        :rtype: PhraseFragment
        """
        return cls(parts=list(parts), separator=" ")


@dataclass
class BlockFragment(VerbFragment):
    """
    A named structural block with an optional header and a list of sub-items.

    * :class:`~krrood.entity_query_language.verbalization.rendering.renderer.ParagraphRenderer`
      flattens header + items into a single comma-separated prose string.
    * :class:`~krrood.entity_query_language.verbalization.rendering.renderer.HierarchicalRenderer`
      renders the header on one line, then each item as a bullet at the next indent level.

    :ivar header: Optional lead fragment (e.g. ``"Find Robot"`` or ``"If"``).
    :ivar items: Ordered list of sub-item fragments.
    """

    header: Optional[VerbFragment]
    items: list[VerbFragment] = field(default_factory=list)


# ── Fragment joining utilities ─────────────────────────────────────────────────


def join_with(parts: list[VerbFragment], sep: VerbFragment) -> VerbFragment:
    """
    Interleave *parts* with *sep* between each adjacent pair.

    :param parts: Fragments to join.
    :type parts: list[VerbFragment]
    :param sep: Separator fragment inserted between adjacent items.
    :type sep: VerbFragment
    :returns: A single fragment (or the sole item when ``len(parts) == 1``).
    :rtype: VerbFragment
    """
    if not parts:
        return WordFragment(text="")
    if len(parts) == 1:
        return parts[0]
    result: list[VerbFragment] = []
    for i, frag in enumerate(parts):
        result.append(frag)
        if i < len(parts) - 1:
            result.append(sep)
    return PhraseFragment(parts=result, separator="")


def oxford_and(parts: list[VerbFragment], conjunction: VerbFragment) -> VerbFragment:
    """
    Join *parts* with Oxford-comma style: ``f1, f2, conj f3``.

    :param parts: Fragments to join.
    :type parts: list[VerbFragment]
    :param conjunction: Conjunction fragment (e.g. *"and"*, *"or"*).
    :type conjunction: VerbFragment
    :returns: A single fragment representing the joined sequence.
    :rtype: VerbFragment
    """
    if not parts:
        return WordFragment(text="")
    if len(parts) == 1:
        return parts[0]
    head = parts[:-1]
    tail = parts[-1]
    result: list[VerbFragment] = []
    for f in head:
        result.append(f)
        result.append(WordFragment(text=", "))
    result.append(PhraseFragment(parts=[conjunction, tail], separator=" "))
    return PhraseFragment(parts=result, separator="")
