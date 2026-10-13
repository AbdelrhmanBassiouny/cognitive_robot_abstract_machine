import pytest

from krrood_core.class_property import classproperty

from .dataset.patterns import (
    HasAbstractClassConstant,
    OmitsClassConstant,
    SuppliesClassConstant,
)


def test_a_class_property_answers_on_the_class_and_on_an_instance():
    expected = SuppliesClassConstant.__name__.lower()

    assert SuppliesClassConstant.unit == expected
    assert SuppliesClassConstant().unit == expected


def test_an_abstract_class_property_answers_with_itself():
    assert isinstance(HasAbstractClassConstant.unit, classproperty)


def test_a_subclass_that_supplies_no_value_cannot_be_instantiated():
    with pytest.raises(TypeError, match="unit"):
        OmitsClassConstant()
