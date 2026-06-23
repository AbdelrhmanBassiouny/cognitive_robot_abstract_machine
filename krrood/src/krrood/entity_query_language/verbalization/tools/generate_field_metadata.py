"""
Offline generator for the field linguistic-metadata artifact consumed by the verbalizer.

This is the *judgment* half of the field-metadata feature, deliberately kept out of the runtime
path: it runs once (or whenever the schema changes), asks an LLM to classify every
``(Type, attribute)`` pair, and writes two committed artifacts —

* ``field_metadata.json`` — the runtime artifact: per-field ``display_name`` overrides
  (e.g. ``begin`` → *"beginning"*), loaded by
  :meth:`~krrood.entity_query_language.verbalization.field_metadata.FieldMetadataRegistry.from_json`.
* ``field_metadata_suggestions.md`` — an advisory report for developers: a genuinely better
  *source* field name (e.g. ``begin`` → ``start``) with rationale, to adopt in the code or not.

At runtime nothing here is imported or called; the verbalizer only reads the committed JSON. The
LLM dependency (the official Anthropic SDK) is imported lazily inside :func:`anthropic_parse_fn`,
so the pure pieces — schema enumeration, artifact assembly, report rendering — run (and are tested)
without the SDK installed.

Re-running regenerates both files; review the ``git diff`` like any other change.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, fields as dataclass_fields, is_dataclass
from pathlib import Path
from types import ModuleType

from typing_extensions import Callable, Dict, List, Optional, Union

from krrood.ormatic.utils import classes_of_module

#: A boundary callable: given a type name and its field names, return one suggestion per field.
#: The real implementation calls the LLM; tests pass a fake.
ParseFn = Callable[[str, List[str]], "List[FieldSuggestion]"]


@dataclass(frozen=True)
class FieldSuggestion:
    """One field's LLM-proposed linguistic metadata."""

    field_name: str
    """The canonical (source) attribute name."""

    display_name: str
    """The preferred surface word for verbalization (may equal *field_name* when already good)."""

    relation_verb_phrase: Optional[str] = None
    """The passive verb phrase when the field names a *relation* as a verb (``assigned_to`` →
    *"assigned to"*), else ``None`` — drives the absence form *"has not been <phrase> any <Type>"*."""

    countable: Optional[bool] = None
    """Whether the attribute's noun is countable, or ``None`` to defer to the curated mass-noun
    lexicon. ``False`` marks a mass noun (``money``, ``water``) so a genitive hop drops the article
    (*"the amount of money"*); ``True`` is an explicit countable assertion."""

    suggested_rename: Optional[str] = None
    """A genuinely better *source* identifier, or ``None`` — advisory only, never auto-applied."""

    rationale: str = ""
    """Why the display name / rename was chosen — surfaced in the developer report."""

    confidence: str = "medium"
    """The model's confidence (``low`` / ``medium`` / ``high``)."""


# ── Schema enumeration (pure) ────────────────────────────────────────────────────


def iter_type_fields(modules: List[ModuleType]) -> Dict[str, List[str]]:
    """
    Enumerate every dataclass and its public field names across *modules*.

    Mirrors the dataclass introspection the rest of the project uses (``dataclasses.fields``,
    skipping private ``_``-prefixed names).

    :param modules: The schema modules to introspect.
    :return: An ordered ``{TypeName: [field_name, …]}`` mapping (types sorted by name).
    """
    discovered: Dict[str, List[str]] = {}
    classes = {c for module in modules for c in classes_of_module(module)}
    for klass in sorted(
        (c for c in classes if is_dataclass(c)), key=lambda c: c.__name__
    ):
        names = [f.name for f in dataclass_fields(klass) if not f.name.startswith("_")]
        if names:
            discovered[klass.__name__] = names
    return discovered


# ── Artifact assembly (pure) ─────────────────────────────────────────────────────


def build_runtime_artifact(
    suggestions_by_type: Dict[str, List[FieldSuggestion]],
) -> Dict[str, Dict[str, Dict[str, Union[str, bool]]]]:
    """
    Build the runtime JSON artifact, keeping only the entries that actually carry an override.

    A field is emitted when its display name differs from the raw identifier, it is annotated with a
    relational verb phrase, or it is marked uncountable (any combination).

    :param suggestions_by_type: The per-type suggestions.
    :return: ``{TypeName: {field: {"display_name"?: …, "relation_verb_phrase"?: …,
        "countable"?: false}}}`` (types with no override are omitted).
    """
    artifact: Dict[str, Dict[str, Dict[str, Union[str, bool]]]] = {}
    for type_name, suggestions in suggestions_by_type.items():
        overrides: Dict[str, Dict[str, Union[str, bool]]] = {}
        for s in suggestions:
            entry: Dict[str, Union[str, bool]] = {}
            if s.display_name and s.display_name != s.field_name:
                entry["display_name"] = s.display_name
            if s.relation_verb_phrase:
                entry["relation_verb_phrase"] = s.relation_verb_phrase
            if s.countable is False:
                entry["countable"] = False
            if entry:
                overrides[s.field_name] = entry
        if overrides:
            artifact[type_name] = overrides
    return artifact


def render_suggestions_md(
    suggestions_by_type: Dict[str, List[FieldSuggestion]],
) -> str:
    """
    Render the advisory developer report — display names and proposed source renames per type.

    :param suggestions_by_type: The per-type suggestions.
    :return: A Markdown document (only rows that propose a display change or a rename are listed).
    """
    lines: List[str] = [
        "# Field metadata — suggestions",
        "",
        "Generated by `verbalization/tools/generate_field_metadata.py`. The `display_name` column",
        "feeds the runtime artifact (`field_metadata.json`); `suggested_rename` is **advisory** —",
        "adopt it in the source or not. Re-run the tool to regenerate; review the diff.",
        "",
    ]
    for type_name in sorted(suggestions_by_type):
        rows = [
            s
            for s in suggestions_by_type[type_name]
            if (s.display_name and s.display_name != s.field_name)
            or s.relation_verb_phrase
            or s.suggested_rename
        ]
        if not rows:
            continue
        lines += [
            f"## {type_name}",
            "",
            "| field | display_name | relation_verb_phrase | suggested_rename | confidence | rationale |",
            "|---|---|---|---|---|---|",
        ]
        for s in rows:
            lines.append(
                f"| `{s.field_name}` | {s.display_name} | "
                f"{s.relation_verb_phrase or '—'} | "
                f"{('`' + s.suggested_rename + '`') if s.suggested_rename else '—'} | "
                f"{s.confidence} | {s.rationale} |"
            )
        lines.append("")
    return "\n".join(lines)


def generate(
    modules: List[ModuleType], parse_fn: ParseFn
) -> Dict[str, List[FieldSuggestion]]:
    """
    Run the enumeration → suggestion pipeline (pure given *parse_fn*).

    :param modules: The schema modules to introspect.
    :param parse_fn: The per-type suggestion boundary (LLM-backed in production, faked in tests).
    :return: The per-type suggestions, in type-name order.
    """
    return {
        type_name: parse_fn(type_name, field_names)
        for type_name, field_names in iter_type_fields(modules).items()
    }


# ── LLM boundary (lazily imports the Anthropic SDK) ──────────────────────────────

_SYSTEM_PROMPT = """\
You assign human-readable surface words to the attributes of a data model, for a system that \
verbalizes database queries into English. For each attribute you are given its type and field \
name. Return, per field:

- display_name: the noun phrase to SAY for this attribute in a sentence like \
"the <display_name> of the <Type>". Rules: nominalize verb-like names (begin -> "beginning", \
end -> "end"); expand snake_case to spaced words (amount_details -> "amount details"); keep \
established domain terms; do NOT prepend the type name (NOT "Employee salary", just "salary"); \
keep it lowercase unless it is a proper noun/acronym. If the raw name already reads well, return \
it unchanged.
- relation_verb_phrase: when the field names a RELATION as a verb (a thing this object is \
connected to via an action), the passive verb phrase to SAY in "the object has not been \
<relation_verb_phrase> any <RelatedType>". E.g. assigned_to -> "assigned to", owner -> "owned by", \
manages -> "managing" is wrong; use "managed by" only if the field holds the manager. Set it ONLY \
for genuine verb/relation fields (assigned_to, owned_by, reports_to, manager, parent for a \
containment); for a plain noun attribute (name, battery, color) return null. This is the override \
for relations the runtime name-heuristic cannot detect on its own.
- countable: false ONLY when the attribute's noun is a mass/uncountable noun (money, water, \
information, advice, equipment) — so it reads "the amount of money", never "the amount of the \
money". For an ordinary countable noun (battery, salary, department) return null; do not return \
true unless the noun looks uncountable in general English but is countable in THIS domain. Judge \
the display_name word, not the field name.
- suggested_rename: a genuinely better SOURCE identifier when the field name is poorly chosen \
(begin -> "start"), else null. This is advice for developers, not applied automatically.
- rationale: one short clause explaining the choice.
- confidence: "low" | "medium" | "high".
"""


def anthropic_parse_fn(model: str = "claude-opus-4-8") -> ParseFn:
    """
    Build the production :data:`ParseFn` backed by the Anthropic SDK (lazily imported).

    Uses ``client.messages.parse()`` with a Pydantic schema, adaptive thinking, and a cached
    system prompt. Requires ``anthropic`` and ``pydantic`` to be installed and ``ANTHROPIC_API_KEY``
    to be set in the environment.

    :param model: The Claude model id (defaults to the current Opus).
    :return: A :data:`ParseFn` that calls the model once per type.
    """
    import anthropic  # lazy: keeps the pure pipeline importable without the SDK
    from pydantic import BaseModel

    class _Suggestion(BaseModel):
        field_name: str
        display_name: str
        relation_verb_phrase: Optional[str] = None
        countable: Optional[bool] = None
        suggested_rename: Optional[str] = None
        rationale: str = ""
        confidence: str = "medium"

    class _TypeSuggestions(BaseModel):
        suggestions: List[_Suggestion]

    client = anthropic.Anthropic()

    def parse_fn(type_name: str, field_names: List[str]) -> List[FieldSuggestion]:
        prompt = f"Type: {type_name}\nFields:\n" + "\n".join(
            f"- {name}" for name in field_names
        )
        response = client.messages.parse(
            model=model,
            max_tokens=4096,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            system=[
                {
                    "type": "text",
                    "text": _SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": prompt}],
            output_format=_TypeSuggestions,
        )
        parsed = response.parsed_output
        return [
            FieldSuggestion(
                field_name=s.field_name,
                display_name=s.display_name,
                relation_verb_phrase=s.relation_verb_phrase,
                countable=s.countable,
                suggested_rename=s.suggested_rename,
                rationale=s.rationale,
                confidence=s.confidence,
            )
            for s in parsed.suggestions
        ]

    return parse_fn


def write_artifacts(
    suggestions_by_type: Dict[str, List[FieldSuggestion]],
    json_path: Path,
    report_path: Path,
) -> None:
    """
    Write the runtime JSON artifact and the advisory Markdown report.

    :param suggestions_by_type: The per-type suggestions.
    :param json_path: Destination for the runtime ``field_metadata.json``.
    :param report_path: Destination for the ``field_metadata_suggestions.md`` report.
    """
    artifact = build_runtime_artifact(suggestions_by_type)
    json_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    report_path.write_text(render_suggestions_md(suggestions_by_type))


def main() -> None:  # pragma: no cover - thin CLI wiring, needs the SDK + an API key
    """Generate the field-metadata artifacts for the test dataset (requires ``ANTHROPIC_API_KEY``)."""
    from test.krrood_test.dataset import example_classes, semantic_world_like_classes

    dataset_dir = Path(example_classes.__file__).parent
    suggestions = generate(
        [example_classes, semantic_world_like_classes], anthropic_parse_fn()
    )
    write_artifacts(
        suggestions,
        dataset_dir / "field_metadata.json",
        dataset_dir / "field_metadata_suggestions.md",
    )


if __name__ == "__main__":  # pragma: no cover
    main()
