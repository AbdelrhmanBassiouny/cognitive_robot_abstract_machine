from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from typing_extensions import Callable, Dict, Mapping, Optional, Tuple, TypeVar, Union

_Value = TypeVar("_Value")


@dataclass(frozen=True)
class FieldMetadata:
    """
    The linguistic metadata for one ``(owner type, attribute)`` pair, consumed at runtime.

    The overrides below are read by the verbalizer (richer, advisory output — a suggested *source*
    rename, rationale — lives in the human-readable report the offline generator writes, not here):
    """

    display_name: Optional[str] = None
    """The preferred surface word for the attribute, or ``None`` to keep the raw identifier
    (e.g. the field ``begin`` renders as *"beginning"*)."""

    relation_verb_phrase: Optional[str] = None
    """The passive verb phrase for a *relational* field, or ``None`` for a plain noun attribute.
    When set, an ``attribute == None`` absence reads *"<owner> has not been <phrase> any <Type>"*
    (e.g. ``owner`` → *"owned by"* gives *"has not been owned by any Person"*). This is the metadata
    override of the runtime heuristic
    (:func:`~…grammar.conditions.recognition.relational_verb_phrase`), so it covers relations the
    name-based heuristic cannot detect (irregular or non-participle namings, present-tense verbs)."""

    countable: Optional[bool] = None
    """Whether the attribute's noun is countable, or ``None`` when unspecified (treated as
    countable). ``False`` marks an uncountable (mass) noun so a genitive hop drops the article
    (*"the amount of money"*, not *"… of the money"*). Countability is authored here per field — there
    is no name-based lexicon — so an unannotated field keeps the definite article."""


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

    def _resolve(
        self,
        owner: type,
        attribute: str,
        select: Callable[[FieldMetadata], Optional[_Value]],
    ) -> Optional[_Value]:
        """
        Walk *owner*'s MRO by name and return the first non-``None`` value *select* reads from a
        matching entry — so an attribute declared on a base class resolves when accessed through a
        subclass (and vice versa, since the generator records every dataclass in the hierarchy).

        :param owner: The class that owns the attribute.
        :param attribute: The canonical attribute name.
        :param select: Reads the wanted field off a matched :class:`FieldMetadata`.
        :return: The first non-``None`` value found along the MRO, or ``None``.
        """
        for klass in owner.__mro__:
            meta = self.by_key.get((klass.__name__, attribute))
            if meta is not None and select(meta) is not None:
                return select(meta)
        return None

    def display_name(self, owner: type, attribute: str) -> Optional[str]:
        """
        :param owner: The class that owns the attribute.
        :param attribute: The canonical attribute name.
        :return: The display-name override for *owner*.*attribute*, or ``None`` when no entry applies.
        """
        return self._resolve(owner, attribute, lambda meta: meta.display_name)

    def relation_verb_phrase(self, owner: type, attribute: str) -> Optional[str]:
        """
        :param owner: The class that owns the attribute.
        :param attribute: The canonical attribute name.
        :return: The passive verb phrase override for *owner*.*attribute* (*"owned by"*), or ``None``
            when the field is not annotated as relational.
        """
        return self._resolve(owner, attribute, lambda meta: meta.relation_verb_phrase)

    def countable(self, owner: type, attribute: str) -> Optional[bool]:
        """
        :param owner: The class that owns the attribute.
        :param attribute: The canonical attribute name.
        :return: The countability override for *owner*.*attribute* (``False`` for a mass noun), or
            ``None`` when no entry applies (the hop then keeps the definite article).
        """
        return self._resolve(owner, attribute, lambda meta: meta.countable)

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

        The artifact is nested ``{"TypeName": {"attribute": {"display_name": "…",
        "relation_verb_phrase": "…", "countable": false}, …}, …}`` (a bare string value is also
        accepted as shorthand for ``display_name``), matching what the offline generator writes.

        :param path: Path to the JSON artifact.
        :return: The loaded registry (empty when the file holds an empty object).
        """
        data = json.loads(Path(path).read_text())
        by_key: Dict[_Key, FieldMetadata] = {}
        for type_name, fields_ in data.items():
            for attribute, entry in fields_.items():
                if isinstance(entry, dict):
                    meta = FieldMetadata(
                        display_name=entry.get("display_name"),
                        relation_verb_phrase=entry.get("relation_verb_phrase"),
                        countable=entry.get("countable"),
                    )
                else:
                    meta = FieldMetadata(display_name=entry)
                by_key[(type_name, attribute)] = meta
        return cls(by_key=by_key)
