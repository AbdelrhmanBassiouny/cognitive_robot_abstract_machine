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
    def test_dir_surfaces_case_type_fields(self):
        v = variable(Animal, domain=[])
        listed = set(dir(v))
        # Both undefaulted fields (annotations-only) and defaulted ones must appear.
        self.assertTrue({"name", "hair", "milk", "legs", "species"} <= listed)

    def test_dir_does_not_change_getattr(self):
        v = variable(Animal, domain=[])
        # Every attribute access is still symbolic, including names not on the type.
        self.assertIsInstance(v.milk, Attribute)
        self.assertIsInstance(v.totally_made_up, Attribute)
        self.assertIsInstance(v.milk == True, Comparator)

    def test_chained_attribute_reflects_its_own_type(self):
        v = variable(Animal, domain=[])
        # ``species`` is an Enum-typed attribute; its dir reflects the Enum, not Animal.
        species_listed = set(dir(v.species))
        self.assertIn("mammal", species_listed)
        self.assertNotIn("milk", species_listed)


if __name__ == "__main__":
    unittest.main()
