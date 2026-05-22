from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SourceRef:
    """
    Carries a reference to the Python source entity that a
    :class:`~krrood.entity_query_language.verbalization.fragments.base.RoleFragment` represents.

    Used by :class:`~krrood.entity_query_language.verbalization.rendering.source_link_resolver.SourceLinkResolver`
    implementations to resolve the fragment to a documentation URL.

    Frozen (immutable) so instances can be safely shared and hashed.

    :ivar cls: The Python class this fragment refers to (always set).
    :ivar attribute: Attribute name within *cls*; ``None`` means the fragment refers
        to the class itself (e.g. for type-name labels like *"Robot"*).
    """

    cls: type
    attribute: Optional[str] = None

    @classmethod
    def for_type(cls, t) -> Optional["SourceRef"]:
        """
        Return ``SourceRef(cls=t)`` when *t* is a real ``type``, else ``None``.

        :param t: Candidate type (any value accepted; non-types return ``None``).
        :returns: A :class:`SourceRef` for the class, or ``None``.
        :rtype: SourceRef or None
        """
        return cls(cls=t) if isinstance(t, type) else None

    @classmethod
    def for_attribute(cls, owner, attr_name: str) -> Optional["SourceRef"]:
        """
        Return ``SourceRef(cls=owner, attribute=attr_name)`` when *owner* is a real ``type``,
        else ``None``.

        :param owner: Candidate owner class (any value; non-types return ``None``).
        :param attr_name: Canonical attribute name on *owner*.
        :type attr_name: str
        :returns: A :class:`SourceRef` for the attribute, or ``None``.
        :rtype: SourceRef or None
        """
        return cls(cls=owner, attribute=attr_name) if isinstance(owner, type) else None
