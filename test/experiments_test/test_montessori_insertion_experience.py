import datetime

from experiments.montessori.insertion_experience import ShapeInsertionExperience
from experiments.montessori.semantics import MontessoriShapeCategory


def _experience(**overrides) -> ShapeInsertionExperience:
    fields = dict(
        run_index=0,
        shape_category=MontessoriShapeCategory.CUBE,
        attempt_number=1,
        target_horizontal_offset_x=0.001,
        target_horizontal_offset_y=-0.002,
        fell_through_hole=True,
    )
    fields.update(overrides)
    return ShapeInsertionExperience(**fields)


def test_shape_insertion_experience_stores_every_given_field():
    experience = _experience()

    assert experience.run_index == 0
    assert experience.shape_category == MontessoriShapeCategory.CUBE
    assert experience.attempt_number == 1
    assert experience.target_horizontal_offset_x == 0.001
    assert experience.target_horizontal_offset_y == -0.002
    assert experience.fell_through_hole is True


def test_shape_insertion_experience_defaults_recorded_at_to_now():
    before = datetime.datetime.now()
    experience = _experience()
    after = datetime.datetime.now()

    assert before <= experience.recorded_at <= after


def test_shape_insertion_experience_gives_each_instance_its_own_recorded_at():
    first = _experience()
    second = _experience()

    assert first.recorded_at is not second.recorded_at
