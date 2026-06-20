"""
Tests for field linguistic metadata (ROUND 10):

- the runtime :class:`FieldMetadataRegistry` lookup (mapping / MRO resolution / JSON artifact);
- the deterministic display-name override applied during verbalization (``begin`` -> *"beginning"*),
  with an empty registry reproducing the raw-identifier output exactly;
- the offline generator's pure pipeline (schema enumeration, artifact assembly, report rendering),
  exercised with a fake suggestion source so no LLM / SDK is needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from krrood.entity_query_language.factories import variable
from krrood.entity_query_language.verbalization.context import MicroplanningServices
from krrood.entity_query_language.verbalization.field_metadata import (
    FieldMetadata,
    FieldMetadataRegistry,
)
from krrood.entity_query_language.verbalization.pipeline import VerbalizationPipeline
from krrood.entity_query_language.verbalization.tools import (
    generate_field_metadata as gen,
)

from ...dataset import semantic_world_like_classes
from ...dataset.semantic_world_like_classes import GraspConfig

# ── local schema mirroring the motivating example ────────────────────────────────


@dataclass
class Bound:
    month: int


@dataclass
class Period:
    begin: Bound
    end: Bound


def _verbalize(expression, registry: FieldMetadataRegistry) -> str:
    services = MicroplanningServices.from_expression(expression)
    services.field_metadata = registry
    return VerbalizationPipeline.plain().verbalize(expression, services)


# ── registry lookup ──────────────────────────────────────────────────────────────


def test_from_mapping_resolves_display_name():
    registry = FieldMetadataRegistry.from_mapping({(Period, "begin"): "beginning"})
    assert registry.display_name(Period, "begin") == "beginning"
    assert registry.display_name(Period, "end") is None


def test_empty_registry_resolves_nothing():
    assert FieldMetadataRegistry().display_name(Period, "begin") is None


def test_mro_resolution_from_base_entry():
    @dataclass
    class Base:
        x: float

    @dataclass
    class Sub(Base):
        y: float

    registry = FieldMetadataRegistry.from_mapping(
        {(Base, "x"): FieldMetadata("the x value")}
    )
    # An attribute declared on the base resolves when accessed through the subclass.
    assert registry.display_name(Sub, "x") == "the x value"
    # A subclass-only entry does not leak onto the base.
    assert (
        FieldMetadataRegistry.from_mapping({(Sub, "y"): "why"}).display_name(Base, "y")
        is None
    )


def test_from_json_loads_committed_artifact():
    artifact = Path(semantic_world_like_classes.__file__).parent / "field_metadata.json"
    registry = FieldMetadataRegistry.from_json(artifact)
    assert registry.display_name(GraspConfig, "rotate_gripper") == "gripper rotation"


def test_relation_verb_phrase_lookup_and_mro():
    @dataclass
    class Base:
        owner: float

    @dataclass
    class Sub(Base):
        pass

    registry = FieldMetadataRegistry.from_mapping(
        {(Base, "owner"): FieldMetadata(relation_verb_phrase="owned by")}
    )
    assert registry.relation_verb_phrase(Base, "owner") == "owned by"
    assert registry.relation_verb_phrase(Sub, "owner") == "owned by"  # resolved via MRO
    assert registry.relation_verb_phrase(Base, "missing") is None
    assert FieldMetadataRegistry().relation_verb_phrase(Base, "owner") is None


def test_from_json_loads_relation_verb_phrase(tmp_path):
    artifact = tmp_path / "field_metadata.json"
    artifact.write_text(
        '{"Car": {"owner": {"relation_verb_phrase": "owned by"},'
        ' "begin": {"display_name": "beginning"}}}'
    )
    registry = FieldMetadataRegistry.from_json(artifact)

    @dataclass
    class Car:
        owner: int
        begin: int

    assert registry.relation_verb_phrase(Car, "owner") == "owned by"
    assert registry.display_name(Car, "begin") == "beginning"


# ── deterministic runtime override ───────────────────────────────────────────────


def test_display_name_overrides_attribute_in_chain():
    expression = variable(Period, []).begin.month
    raw = _verbalize(expression, FieldMetadataRegistry())
    assert raw == "the month of the begin of a Period"

    named = _verbalize(
        expression, FieldMetadataRegistry.from_mapping({(Period, "begin"): "beginning"})
    )
    assert named == "the month of the beginning of a Period"


def test_committed_artifact_overrides_real_dataset_field():
    artifact = Path(semantic_world_like_classes.__file__).parent / "field_metadata.json"
    registry = FieldMetadataRegistry.from_json(artifact)
    expression = variable(GraspConfig, []).rotate_gripper
    assert "gripper rotation" in _verbalize(expression, registry)
    assert "rotate_gripper" not in _verbalize(expression, registry)


@dataclass
class _Owner:
    pass


@dataclass
class _Vehicle:
    keeper: _Owner  # a plain noun — the name heuristic cannot tell it is a relation


def test_metadata_makes_a_noun_field_render_as_relational_absence():
    """A relation the name heuristic cannot detect (a noun-named field) reads as a passive absence
    once metadata supplies the verb phrase — *"<owner> has not been <phrase> any <Type>"* — while an
    empty registry keeps the plain *"has no <field>"*."""
    vehicle = variable(_Vehicle, [])
    absence = vehicle.keeper == None

    assert _verbalize(absence, FieldMetadataRegistry()) == "a _Vehicle has no keeper"

    registry = FieldMetadataRegistry.from_mapping(
        {(_Vehicle, "keeper"): FieldMetadata(relation_verb_phrase="kept by")}
    )
    assert _verbalize(absence, registry) == "a _Vehicle has not been kept by any _Owner"


# ── offline generator: pure pipeline (no LLM / SDK) ──────────────────────────────


def test_iter_type_fields_enumerates_dataclass_fields():
    fields = gen.iter_type_fields([semantic_world_like_classes])
    assert {"rotate_gripper", "approach_direction", "manipulation_offset"} <= set(
        fields["GraspConfig"]
    )


def test_build_runtime_artifact_keeps_only_real_overrides():
    suggestions = {
        "GraspConfig": [
            gen.FieldSuggestion("rotate_gripper", "gripper rotation"),
            gen.FieldSuggestion(
                "approach_direction", "approach_direction"
            ),  # unchanged
        ]
    }
    artifact = gen.build_runtime_artifact(suggestions)
    assert artifact == {
        "GraspConfig": {"rotate_gripper": {"display_name": "gripper rotation"}}
    }


def test_build_runtime_artifact_includes_relation_verb_phrase():
    """A field annotated with a relational verb phrase is emitted (with or without a display name);
    a plain noun field is omitted."""
    suggestions = {
        "Car": [
            gen.FieldSuggestion("owner", "owner", relation_verb_phrase="owned by"),
            gen.FieldSuggestion("color", "color"),  # plain noun → omitted
        ]
    }
    assert gen.build_runtime_artifact(suggestions) == {
        "Car": {"owner": {"relation_verb_phrase": "owned by"}}
    }


def test_render_suggestions_md_lists_renames():
    suggestions = {
        "GraspConfig": [
            gen.FieldSuggestion(
                "rotate_gripper",
                "gripper rotation",
                suggested_rename="gripper_rotation",
                rationale="reads as an action",
                confidence="medium",
            )
        ]
    }
    report = gen.render_suggestions_md(suggestions)
    assert "## GraspConfig" in report
    assert "`gripper_rotation`" in report
    assert "gripper rotation" in report


def test_generate_runs_pipeline_with_a_fake_parse_fn():
    def fake_parse(type_name, field_names):
        return [
            gen.FieldSuggestion(
                name,
                "gripper rotation" if name == "rotate_gripper" else name,
            )
            for name in field_names
        ]

    suggestions = gen.generate([semantic_world_like_classes], fake_parse)
    artifact = gen.build_runtime_artifact(suggestions)
    assert artifact["GraspConfig"]["rotate_gripper"] == {
        "display_name": "gripper rotation"
    }
