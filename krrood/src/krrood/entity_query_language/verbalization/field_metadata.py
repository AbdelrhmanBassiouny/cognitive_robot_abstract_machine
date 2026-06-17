from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from typing_extensions import Dict, Mapping, Optional, Tuple, Union


@dataclass(frozen=True)
class FieldMetadata:
    """
    The linguistic metadata for one ``(owner type, attribute)`` pair.

    Only :attr:`display_name` is consumed at runtime — it overrides the surface word used for an
    attribute (e.g. the field ``begin`` renders as *"beginning"*). Richer, advisory output (a
    suggested *source* rename, rationale) lives in the human-readable report the offline generator
    writes, not here.
    """

    display_name: Optional[str] = None
    """The preferred surface word for the attribute, or ``None`` to keep the raw identifier."""


_Key = Tuple[str, str]


@dataclass(frozen=True)
class FieldMetadataRegistry:
    """
    A deterministic lookup of per-field linguistic metadata, keyed by ``(owner type name,
    attribute name)``.

    This is the runtime half of the field-metadata feature: the verbalizer consults it through a
    single realisation pass (:class:`FieldMetadataProcessor`) and never calls anything
    non-deterministic. The metadata itself is produced offline (and committed) by
    :mod:`krrood.entity_query_language.verbalization.tools.generate_field_metadata`.

    The registry is keyed by type *name* (a ``str``) rather than the class object so a committed
    JSON artifact is stable and diffable, and so the dataclass-vs-generated-DAO duality of the same
    entity resolves to one entry. An empty registry (the default) is a no-op: every attribute keeps
    its raw identifier, reproducing the pre-metadata behaviour exactly.
    """

    by_key: Dict[_Key, FieldMetadata] = field(default_factory=dict)
    """The metadata indexed by ``(owner_type_name, attribute_name)``."""

    def display_name(self, owner: type, attribute: str) -> Optional[str]:
        """
        Resolve the preferred surface word for *owner*.*attribute*.

        The owner's MRO is walked by name so an attribute declared on a base class resolves when it
        is accessed through a subclass (and vice versa, since the generator records every dataclass
        in the hierarchy).

        :param owner: The class that owns the attribute.
        :param attribute: The canonical attribute name.
        :return: The display name override, or ``None`` when no entry applies.
        """
        for klass in getattr(owner, "__mro__", (owner,)):
            name = getattr(klass, "__name__", None)
            if name is None:
                continue
            meta = self.by_key.get((name, attribute))
            if meta is not None and meta.display_name is not None:
                return meta.display_name
        return None

    @classmethod
    def from_mapping(
        cls, mapping: Mapping[Tuple[type, str], Union[str, FieldMetadata]]
    ) -> FieldMetadataRegistry:
        """
        Build a registry from an in-memory ``{(type, attribute): display_name | FieldMetadata}``
        mapping — the convenient form for tests and programmatic callers.

        :param mapping: Per-field metadata keyed by the owner *class* and attribute name.
        :return: A registry keyed by ``(owner_type_name, attribute_name)``.
        """
        by_key: Dict[_Key, FieldMetadata] = {}
        for (owner, attribute), value in mapping.items():
            meta = value if isinstance(value, FieldMetadata) else FieldMetadata(value)
            by_key[(owner.__name__, attribute)] = meta
        return cls(by_key=by_key)

    @classmethod
    def from_json(cls, path: Union[str, Path]) -> FieldMetadataRegistry:
        """
        Load a registry from a committed JSON artifact.

        The artifact is nested ``{"TypeName": {"attribute": {"display_name": "…"}, …}, …}`` (a
        bare string value is also accepted as shorthand for ``display_name``), matching what the
        offline generator writes.

        :param path: Path to the JSON artifact.
        :return: The loaded registry (empty when the file holds an empty object).
        """
        data = json.loads(Path(path).read_text())
        by_key: Dict[_Key, FieldMetadata] = {}
        for type_name, fields_ in data.items():
            for attribute, entry in fields_.items():
                display = (
                    entry.get("display_name") if isinstance(entry, dict) else entry
                )
                by_key[(type_name, attribute)] = FieldMetadata(display_name=display)
        return cls(by_key=by_key)
