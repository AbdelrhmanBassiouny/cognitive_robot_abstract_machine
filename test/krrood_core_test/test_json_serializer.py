import pytest

from krrood_core.adapters.exceptions import MissingTypeError
from krrood_core.adapters.json_field import JSONField
from krrood_core.adapters.json_serializer import from_json, to_json

from .dataset.patterns import LabelledShape, Shade


def test_a_dataclass_survives_the_round_trip():
    shape = LabelledShape(
        label="square", corners=[1, 2, 3, 4], shade=Shade.DARK, weights={"a": 0.5}
    )

    assert from_json(to_json(shape)) == shape


def test_a_field_marked_not_to_serialize_is_left_out():
    document = to_json(LabelledShape(label="square", cached_area=4.0))

    assert "cached_area" not in document


def test_a_document_without_a_type_is_refused():
    document = to_json(LabelledShape(label="square"))
    del document[JSONField.TYPE]

    with pytest.raises(MissingTypeError):
        from_json(document)
