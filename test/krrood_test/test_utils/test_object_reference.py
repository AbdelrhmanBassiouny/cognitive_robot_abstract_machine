from __future__ import annotations

import json

import pytest

from krrood.adapters.json_serializer import to_json
from krrood.adapters.object_reference import IdentifiedObject
from krrood.patterns.exceptions import InterfaceInstantiationError

from ..dataset.identified_objects import Landmark, LandmarkReference, LandmarkTracker

# %% writing and resolving references


@pytest.fixture
def lighthouse() -> Landmark:
    return Landmark(name="lighthouse")


def test_an_identified_object_cannot_be_instantiated():
    with pytest.raises(InterfaceInstantiationError):
        IdentifiedObject()


def test_a_reference_carries_the_identifier_and_name_under_its_subject(lighthouse):
    data = {}

    LandmarkReference("harbour").write(data, lighthouse)

    assert data == {
        "harbour_id": to_json(lighthouse.id),
        "harbour_name": lighthouse.name,
    }


def test_a_written_reference_resolves_to_the_object_it_names(lighthouse):
    reference = LandmarkReference("harbour")
    data = {}
    reference.write(data, lighthouse)
    tracker = LandmarkTracker()
    tracker.add(lighthouse.id, lighthouse)

    resolved = reference.resolve(
        json.loads(json.dumps(data)), **tracker.create_kwargs()
    )

    assert resolved is lighthouse
