from __future__ import annotations

from dataclasses import dataclass

import pytest

from typing_extensions import Any

from krrood.entity_query_language.causality.causal_model import CausalModel
from krrood.entity_query_language.causality.exceptions import (
    NotAnInferredInstanceError,
)
from krrood.entity_query_language.explanation.explanation import explain_inference
from krrood.entity_query_language.factories import entity, variable, why
from krrood.entity_query_language.questions.cause import Cause, CauseSet
from ...dataset.montessori_scene import (
    In,
    MontessoriObject,
    build_montessori_scene,
)


def _inferred_placement_named(scene, object_name: str) -> In:
    """Evaluate the over-general rule and return the inferred placement of the named object."""
    for placement in scene.over_general_placement_query().evaluate():
        if placement.object_.name == object_name:
            return placement
    raise AssertionError(f"No inferred placement for {object_name!r}.")


def test_over_general_rule_attaches_real_inference_explanation():
    """The over-general rule produces placements that carry a non-empty inference explanation."""
    scene = build_montessori_scene()
    placement = _inferred_placement_named(scene, "cylinder")

    explanation = explain_inference(placement)

    assert explanation is not None
    assert len(explanation.get_satisfied_conditions_and_their_bindings()) > 0


def test_why_returns_cause_set_for_inferred_placement():
    """``why`` over an inferred placement returns a non-empty cause set about that placement."""
    scene = build_montessori_scene()
    placement = _inferred_placement_named(scene, "cylinder")

    cause_set = why(entity(variable(In, domain=[placement]))).first()

    assert isinstance(cause_set, CauseSet)
    assert cause_set.instance is placement
    assert not cause_set.is_empty
    assert all(isinstance(cause, Cause) for cause in cause_set.causes)


def test_why_denotation_matches_inference_explanation():
    """The cause set's conditions are exactly the placement's satisfied inference conditions."""
    scene = build_montessori_scene()
    placement = _inferred_placement_named(scene, "cylinder")

    cause_set = why(entity(variable(In, domain=[placement]))).first()
    expected = explain_inference(placement).get_satisfied_conditions_and_their_bindings()

    assert len(cause_set.causes) == len(expected)
    assert [cause.condition._id_ for cause in cause_set.causes] == [
        condition_and_bindings.condition._id_ for condition_and_bindings in expected
    ]


def test_why_on_non_inferred_instance_raises():
    """Asking why about a directly constructed (non-inferred) object is an error."""
    scene = build_montessori_scene()
    cylinder = scene.object_named("cylinder")

    with pytest.raises(NotAnInferredInstanceError):
        why(entity(variable(MontessoriObject, domain=[cylinder]))).first()


def test_why_uses_injected_causal_model():
    """``why`` consults the injected causal model rather than inference explanations."""
    scene = build_montessori_scene()
    placement = _inferred_placement_named(scene, "cylinder")
    fixed_cause_set = CauseSet(instance=placement, causes=())

    @dataclass
    class FixedCauseSetCausalModel(CausalModel):
        """A causal model that always reports the same cause set, for isolating the operator."""

        def explain(self, instance: Any) -> CauseSet:
            return fixed_cause_set

    cause_set = why(
        entity(variable(In, domain=[placement])),
        causal_model=FixedCauseSetCausalModel(),
    ).first()

    assert cause_set is fixed_cause_set
