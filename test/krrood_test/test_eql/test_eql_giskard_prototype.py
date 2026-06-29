"""
Prototype test: a declarative ``MinDistance`` constraint generates a symbolic giskard constraint
expression -- the load-bearing capability behind an ``Achieve`` performative.

Lives under ``krrood_test`` (not ``giskardpy_test``) so it runs in the lean container: the giskardpy
*library* imports fine here (rclpy is mocked), while the ``giskardpy_test`` conftest requires real ROS.
"""

from __future__ import annotations

import krrood.symbolic_math.symbolic_math as sm
from giskardpy.eql.constraints import MinDistance, MinDistanceConstraint, PosedEntity
from giskardpy.qp.constraint_collection import ConstraintCollection
from semantic_digital_twin.spatial_types.spatial_types import Point3


def test_min_distance_over_concrete_points_matches_euclidean():
    a = PosedEntity("a", Point3(x=1.0, y=2.0, z=3.0))
    b = PosedEntity("b", Point3(x=4.0, y=6.0, z=3.0))   # a 3-4-5 triangle in the x-y plane
    distance = MinDistance(a, b).symbolic_value()
    assert distance.is_constant()
    assert abs(distance.to_np().item() - 5.0) < 1e-9


def test_min_distance_over_fk_backed_points_is_symbolic():
    a, b = PosedEntity.symbolic("gripper"), PosedEntity.symbolic("table")
    distance = MinDistance(a, b).symbolic_value()
    assert isinstance(distance, sm.Scalar)
    assert not distance.is_constant()                   # depends on the entities' variables


def test_constraint_compiles_into_a_giskard_inequality_on_the_symbolic_distance():
    quantity = MinDistance(PosedEntity.symbolic("gripper"), PosedEntity.symbolic("table"))
    collection = MinDistanceConstraint(quantity, lower_bound=0.010).compile_into(
        ConstraintCollection()
    )
    inequalities = collection.inequality_constraints
    assert len(inequalities) == 1
    constraint = inequalities[0]
    assert constraint.name == "min_distance/gripper-table"
    assert not constraint.expression.is_constant()      # the symbolic distance flows into the QP
