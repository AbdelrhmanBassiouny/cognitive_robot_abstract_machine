"""
Prototype: generating giskard QP constraints from a declarative distance quantity.

Demonstrates the load-bearing capability behind an ``Achieve`` performative: a constraint *quantity* (the
distance between two bodies) is a **symbolic** expression, and a threshold on it compiles into a giskard
inequality constraint -- the very :class:`~krrood.symbolic_math.symbolic_math.Scalar` the QP consumes.

..note:: A prototype. It uses bodies whose position is given directly (symbolic when built with variables),
    standing in for a forward-kinematics pose, so it runs without a ROS robot fixture. Wiring real forward
    kinematics and running the QP solve is the ROS-CI step.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import krrood.symbolic_math.symbolic_math as sm
from krrood.entity_query_language.verbalization.fragments.base import (
    PhraseFragment,
    VerbalizationFragment,
    WordFragment,
)
from krrood.entity_query_language.verbalization.fragments.features import Separator
from giskardpy.qp.constraint_collection import ConstraintCollection
from semantic_digital_twin.spatial_types.spatial_types import Point3


@dataclass
class PosedEntity:
    """An entity with a position -- a stand-in for a forward-kinematics-backed pose."""

    name: str
    """A label used to name generated constraints."""

    position: Point3
    """The entity's position; symbolic when backed by variables, as an FK pose would be."""

    @classmethod
    def symbolic(cls, name: str) -> "PosedEntity":
        """:return: an entity whose position is three free variables, as an FK-backed pose would be."""
        return cls(name=name, position=Point3.create_with_variables(name))


@dataclass
class MinDistance:
    """The Euclidean distance between two posed entities, as a symbolic quantity."""

    body_a: PosedEntity
    """The first entity."""

    body_b: PosedEntity
    """The second entity."""

    def symbolic_value(self) -> sm.Scalar:
        """:return: the distance as a symbolic :class:`~krrood.symbolic_math.symbolic_math.Scalar`."""
        return self.body_a.position.euclidean_distance(self.body_b.position)


@dataclass
class MinDistanceConstraint:
    """A declarative *"keep at least this far apart"* constraint over a :class:`MinDistance` quantity."""

    quantity: MinDistance
    """The distance being constrained."""

    lower_bound: float
    """The minimum allowed distance, in metres."""

    reference_velocity: float = 0.2
    """The velocity used to normalise the constraint, in m/s."""

    quadratic_weight: float = 1.0
    """How expensive it is to violate the constraint."""

    def compile_into(self, collection: ConstraintCollection) -> ConstraintCollection:
        """Add this constraint to *collection* as a giskard inequality on the symbolic distance.

        :return: the same collection, for chaining.
        """
        distance = self.quantity.symbolic_value()
        collection.add_inequality_constraint(
            name=f"min_distance/{self.quantity.body_a.name}-{self.quantity.body_b.name}",
            task_expression=distance,
            lower_error=sm.Scalar(self.lower_bound) - distance,
            upper_error=sm.Scalar(1e6),
            reference_velocity=self.reference_velocity,
            quadratic_weight=self.quadratic_weight,
        )
        return collection


@dataclass
class GiskardGoal(ABC):
    """A declarative motion goal: it both verbalizes and compiles into giskard QP constraints.

    This is the content an ``Achieve`` speech act drives -- the bridge that lets a robot *state* its goal
    in natural language and *solve* it through the same object.
    """

    @abstractmethod
    def as_fragment(self) -> VerbalizationFragment:
        """:return: the goal as a verbalization fragment (the proposition the act asserts)."""

    @abstractmethod
    def compile_into(self, collection: ConstraintCollection) -> ConstraintCollection:
        """Add this goal's constraints to *collection*.

        :return: the same collection, for chaining.
        """


@dataclass
class MinClearance(GiskardGoal):
    """Keep two bodies at least a minimum distance apart -- a *"keep clear"* motion goal."""

    body_a: str
    """The name of the first body."""

    body_b: str
    """The name of the second body."""

    minimum: float
    """The minimum allowed distance between the bodies, in metres."""

    def as_fragment(self) -> VerbalizationFragment:
        return PhraseFragment(
            parts=[
                WordFragment(text="the distance between"),
                WordFragment(text=self.body_a),
                WordFragment(text="and"),
                WordFragment(text=self.body_b),
                WordFragment(text="is at least"),
                WordFragment(text=f"{self.minimum} metres"),
            ],
            separator=Separator.SPACE,
        )

    def compile_into(self, collection: ConstraintCollection) -> ConstraintCollection:
        quantity = MinDistance(
            PosedEntity.symbolic(self.body_a), PosedEntity.symbolic(self.body_b)
        )
        return MinDistanceConstraint(quantity, lower_bound=self.minimum).compile_into(
            collection
        )


@dataclass
class ReachPosition(GiskardGoal):
    """Bring a tip to within a tolerance of a target -- a *reach* motion goal (vs. a *keep-clear*
    constraint)."""

    tip: str
    """The name of the moving body (e.g. the gripper tip)."""

    target: str
    """The name of the target the tip should reach."""

    tolerance: float = 0.0
    """The allowed distance from the target at the goal, in metres."""

    def as_fragment(self) -> VerbalizationFragment:
        return PhraseFragment(
            parts=[
                WordFragment(text=self.tip),
                WordFragment(text="is at"),
                WordFragment(text=self.target),
            ],
            separator=Separator.SPACE,
        )

    def compile_into(self, collection: ConstraintCollection) -> ConstraintCollection:
        distance = MinDistance(
            PosedEntity.symbolic(self.tip), PosedEntity.symbolic(self.target)
        ).symbolic_value()
        collection.add_inequality_constraint(
            name=f"reach/{self.tip}-{self.target}",
            task_expression=distance,
            lower_error=sm.Scalar(-1e6),
            upper_error=sm.Scalar(self.tolerance) - distance,
            reference_velocity=0.2,
            quadratic_weight=1.0,
        )
        return collection
