from __future__ import annotations

import unittest

from random_events.variable import Continuous

from krrood.ormatic.dao import to_dao
from krrood.probabilistic_knowledge.parameterizer import Parameterizer
from test.krrood_test.dataset.example_classes import OptionalTestCase
from test.krrood_test.dataset.example_classes import Position, Pose, Orientation


def test_parameterize_position():
    """
    Test parameterization of the Position class.
    """
    position = Position(None, None, None)
    parameterizer = Parameterizer()
    variables = parameterizer.parameterize_dao(to_dao(position), "Position")[0]
    expected_variables = [
        Continuous("Position.x"),
        Continuous("Position.y"),
        Continuous("Position.z"),
    ]
    assert variables == expected_variables


def test_parameterize_orientation():
    """
    Test parameterization of the Orientation class.
    """
    orientation = Orientation(None, None, None, None)
    parameterizer = Parameterizer()
    variables = parameterizer.parameterize_dao(to_dao(orientation), "Orientation")[0]
    expected_variables = [
        Continuous("Orientation.x"),
        Continuous("Orientation.y"),
        Continuous("Orientation.z"),
    ]

    assert variables == expected_variables


def test_parameterize_pose():
    """
    Test parameterization of the Pose class.
    """
    pose = Pose(
        position=Position(None, None, None),
        orientation=Orientation(None, None, None, None),
    )
    parameterizer = Parameterizer()
    variables = parameterizer.parameterize_dao(to_dao(pose), "Pose")[0]
    expected_variables = [
        Continuous("Pose.position.x"),
        Continuous("Pose.position.y"),
        Continuous("Pose.position.z"),
        Continuous("Pose.orientation.x"),
        Continuous("Pose.orientation.y"),
        Continuous("Pose.orientation.z"),
    ]

    assert variables == expected_variables


def test_create_fully_factorized_distribution():
    """
    Test for a fully factorized distribution.
    """
    variables = [
        Continuous("Variable.A"),
        Continuous("Variable.B"),
    ]
    parameterizer = Parameterizer()
    parameterizer.variables = variables
    probabilistic_circuit = parameterizer.create_fully_factorized_distribution()
    assert len(probabilistic_circuit.variables) == 2
    assert set(probabilistic_circuit.variables) == set(variables)


class TestDAOParameterizer(unittest.TestCase):

    def setUp(self):
        self.parameterizer = Parameterizer()

    def test_parameterize_flat_dao(self):
        pos = Position(x=1.0, y=2.0, z=3.0)
        pos_dao = to_dao(pos)
        variables, event = self.parameterizer.parameterize_dao(pos_dao, "pos")

        self.assertEqual(len(variables), 3)
        var_names = {v.name for v in variables}
        self.assertIn("pos.x", var_names)
        self.assertIn("pos.y", var_names)
        self.assertIn("pos.z", var_names)

        for var in variables:
            self.assertIsInstance(var, Continuous)
            self.assertEqual(
                event[var].simple_sets[0].lower,
                getattr(pos, var.name.split(".")[-1]),
            )

    def test_parameterize_nested_dao(self):
        pose = Pose(
            position=Position(x=1.0, y=2.0, z=3.0),
            orientation=Orientation(x=0.0, y=0.0, z=0.0, w=1.0),
        )
        pose_dao = to_dao(pose)
        variables, event = self.parameterizer.parameterize_dao(pose_dao, "pose")

        # Position has x, y, z (3)
        # Orientation has x, y, z, w (4)
        # Total = 7
        self.assertEqual(len(variables), 7)

        var_names = {v.name for v in variables}
        self.assertIn("pose.position.x", var_names)
        self.assertIn("pose.orientation.w", var_names)

        # Check values in event
        for var in variables:
            parts = var.name.split(".")
            if parts[1] == "position":
                val = getattr(pose.position, parts[2])
            else:
                val = getattr(pose.orientation, parts[2])
            self.assertEqual(event[var].simple_sets[0].lower, val)

    def test_parameterize_dao_set_value(self):
        optional = OptionalTestCase(1)
        optional_dao = to_dao(optional)
        variables, event = self.parameterizer.parameterize_dao(optional_dao, "optional")

        self.assertEqual(1, len(variables))

    def test_parameterize_dao_none_value(self):
        optional = OptionalTestCase(None)
        optional_dao = to_dao(optional)
        variables, event = self.parameterizer.parameterize_dao(optional_dao, "optional")

        self.assertEqual(len(variables), 1)

    def test_parameterize_dao_set_value_set_optional(self):
        optional = OptionalTestCase(1, Position(1.0, 2.0, 3.0))
        optional_dao = to_dao(optional)
        variables, event = self.parameterizer.parameterize_dao(optional_dao, "optional")

        self.assertEqual(len(variables), 4)

    def test_parameterize_dao_none_value_underspecified_optional(self):
        optional = OptionalTestCase(None, Position(1.0, None, 3.0))
        optional_dao = to_dao(optional)
        variables, event = self.parameterizer.parameterize_dao(optional_dao, "optional")

        self.assertEqual(len(variables), 4)

    def test_parameterize_dao_set_value_set_relationship(self):
        optional = OptionalTestCase(
            1, list_of_orientations=[Orientation(0.0, 0.0, 0.0, 1.0)]
        )
        optional_dao = to_dao(optional)
        variables, event = self.parameterizer.parameterize_dao(optional_dao, "optional")

        self.assertEqual(len(variables), 5)

    def test_parameterize_dao_set_value_underspecified_relationship(self):
        optional = OptionalTestCase(
            1, list_of_orientations=[Orientation(0.0, 0.0, None, 1.0)]
        )
        optional_dao = to_dao(optional)
        variables, event = self.parameterizer.parameterize_dao(optional_dao, "optional")

        self.assertEqual(len(variables), 5)

    def test_parameterize_dao_set_value_set_builtin(self):
        optional = OptionalTestCase(1, list_of_values=[0])
        optional_dao = to_dao(optional)
        variables, event = self.parameterizer.parameterize_dao(optional_dao, "optional")

        self.assertEqual(len(variables), 2)

    def test_parameterize_dao_set_value_underspecified_builtin(self):
        optional = OptionalTestCase(1, list_of_values=[None])
        optional_dao = to_dao(optional)
        variables, event = self.parameterizer.parameterize_dao(optional_dao, "optional")

        self.assertEqual(len(variables), 2)

    def test_parameterize_dao_with_optional_filled(self):
        # Orientation with w=None
        orient = Orientation(x=0.0, y=0.0, z=None, w=1.0)
        orient_dao = to_dao(orient)
        variables, event = self.parameterizer.parameterize_dao(orient_dao, "orient")

        self.assertEqual(len(variables), 4)
        z_var = next(v for v in variables if v.name == "orient.z")
        # Since SimpleEvent fills missing variables with reals(), orient.w should be a full interval
        self.assertTrue(event[z_var].simple_sets[0].lower < -1e10)
        self.assertTrue(event[z_var].simple_sets[0].upper > 1e10)


if __name__ == "__main__":
    unittest.main()
