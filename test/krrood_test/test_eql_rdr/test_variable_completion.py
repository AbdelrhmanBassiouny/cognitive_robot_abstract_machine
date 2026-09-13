"""
``__dir__`` on an EQL variable should surface the wrapped case type's attributes so an
interactive expert gets useful ``case_variable.<tab>`` completion — without altering the
``__getattr__`` behaviour that makes every name a symbolic attribute.
"""

import unittest

from krrood.entity_query_language.core.mapped_variable import Attribute
from krrood.entity_query_language.factories import variable
from krrood.entity_query_language.operators.comparator import Comparator

from .animal import Animal, Species


class TestVariableCompletion(unittest.TestCase):
    """
    Tests for ``__dir__`` on an EQL variable.
    """

    def test_dir_surfaces_case_type_fields(self):
        """
        ``dir()`` on a variable lists the wrapped case type's fields, both undefaulted
        (annotations-only) and defaulted ones.
        """
        v = variable(Animal, domain=[])
        listed = set(dir(v))
        self.assertTrue({"name", "hair", "milk", "legs", "species"} <= listed)

    def test_dir_does_not_change_getattr(self):
        """
        Surfacing field names in ``dir()`` does not change ``__getattr__``: every
        attribute access, including a name not on the type, is still symbolic.
        """
        v = variable(Animal, domain=[])
        self.assertIsInstance(v.milk, Attribute)
        self.assertIsInstance(v.totally_made_up, Attribute)
        self.assertIsInstance(v.milk == True, Comparator)

    def test_chained_attribute_reflects_its_own_type(self):
        """
        ``dir()`` on an Enum-typed attribute reflects the Enum's members, not the
        wrapped case type's fields.
        """
        v = variable(Animal, domain=[])
        species_listed = set(dir(v.species))
        self.assertIn("mammal", species_listed)
        self.assertNotIn("milk", species_listed)


if __name__ == "__main__":
    unittest.main()
