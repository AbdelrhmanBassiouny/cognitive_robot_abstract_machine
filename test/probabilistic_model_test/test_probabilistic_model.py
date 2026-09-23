import unittest
from dataclasses import dataclass
from typing import Tuple

from random_events.variable import Continuous, Variable

from probabilistic_model.probabilistic_model import ProbabilisticModel


# %% models declaring their variables in different ways


@dataclass
class VariablesAsFieldModel(ProbabilisticModel):
    """
    A model that stores its variables in a dataclass field instead of computing them in
    a property. It is never queried, so every inference method is left unimplemented.
    """

    variables: Tuple[Variable, ...]

    def support(self):
        raise NotImplementedError

    def log_likelihood(self, events):
        raise NotImplementedError

    def probability_of_simple_event(self, event):
        raise NotImplementedError

    def log_mode(self):
        raise NotImplementedError

    def log_truncated(self, event, singleton_allowed=False):
        raise NotImplementedError

    def log_conditional(self, point):
        raise NotImplementedError

    def sample(self, amount):
        raise NotImplementedError


# %% tests


class VariablesAsFieldTestCase(unittest.TestCase):

    x = Continuous("x")
    y = Continuous("y")

    def test_variables_are_stored(self):
        model = VariablesAsFieldModel((self.x, self.y))
        self.assertEqual(model.variables, (self.x, self.y))

    def test_base_class_reads_the_field(self):
        model = VariablesAsFieldModel((self.x, self.y))
        self.assertIs(model.get_variable_by_name(self.y.name), self.y)
