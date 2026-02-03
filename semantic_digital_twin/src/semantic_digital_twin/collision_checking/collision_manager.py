from __future__ import annotations

from dataclasses import dataclass, field

from rustworkx import rustworkx
from typing_extensions import List, TYPE_CHECKING

from .collision_detector import CollisionMatrix
from .collision_matrix import (
    CollisionRule,
    MaxAvoidedCollisionsRule,
    DefaultMaxAvoidedCollisions,
)
from .collision_rules import (
    Updatable,
    AllowCollisionForAdjacentPairs,
    AllowNonRobotCollisions,
)
from ..callbacks.callback import ModelChangeCallback
from ..world_description.connections import ActiveConnection

if TYPE_CHECKING:
    from ..world_description.world_entity import Body, KinematicStructureEntity


@dataclass
class CollisionGroup:
    """
    Bodies in this group are viewed as a single body.
    """

    root: KinematicStructureEntity
    bodies: set[Body] = field(default_factory=set)


@dataclass
class CollisionManager(ModelChangeCallback):
    """
    Manages collision rules and turn them into collision matrices.
    1. apply default rules
    2. apply temporary rules
    3. apply final rules
        this is usually allow collisions, like the self collision matrix
    """

    low_priority_rules: List[CollisionRule] = field(default_factory=list)
    normal_priority_rules: List[CollisionRule] = field(default_factory=list)
    high_priority_rules: List[CollisionRule] = field(default_factory=list)

    max_avoided_bodies_rules: List[MaxAvoidedCollisionsRule] = field(
        default_factory=lambda: [DefaultMaxAvoidedCollisions()]
    )

    collision_groups: dict[KinematicStructureEntity, CollisionGroup] = field(
        default_factory=dict
    )

    def __post_init__(self):
        super().__post_init__()
        self.high_priority_rules.extend(
            [AllowNonRobotCollisions(), AllowCollisionForAdjacentPairs()]
        )
        self._notify()

    def _notify(self):
        if self.world.is_empty():
            return
        for rule in self.rules:
            if isinstance(rule, Updatable):
                rule.update(self.world)
        self.update_collision_groups()

    def get_collision_group(self, body: Body) -> CollisionGroup:
        for group in self.collision_groups.values():
            if body in group.bodies or body == group.root:
                return group
        raise Exception(f"No collision group found for {body}")

    def update_collision_groups(self):
        self.collision_groups = {}
        for parent, childs in rustworkx.bfs_successors(
            self.world.kinematic_structure, self.world.root.index
        ):
            try:
                collision_group = self.get_collision_group(parent)
            except Exception:
                collision_group = CollisionGroup(parent)
                self.collision_groups[parent] = collision_group
            for child in childs:
                parent_C_child = self.world.get_connection(parent, child)
                if not parent_C_child.is_controlled and child.has_collision():
                    collision_group.bodies.add(child)
        for group in list(self.collision_groups.values()):
            if len(group.bodies) == 0:
                del self.collision_groups[group.root]

    def get_max_avoided_bodies(self, body: Body) -> int:
        for rule in reversed(self.max_avoided_bodies_rules):
            max_avoided_bodies = rule.get_max_avoided_collisions(body)
            if max_avoided_bodies is not None:
                return max_avoided_bodies
        raise Exception(f"No rule found for {body}")

    def get_buffer_zone_distance(self, body: Body) -> float: ...

    def get_violated_violated_distance(self, body: Body) -> float: ...

    def get_possible_collision_bodies(self, body: Body) -> set[Body]: ...

    @property
    def rules(self) -> List[CollisionRule]:
        return (
            self.low_priority_rules
            + self.normal_priority_rules
            + self.high_priority_rules
        )

    def create_collision_matrix(self) -> CollisionMatrix:
        collision_matrix = CollisionMatrix()
        for rule in self.low_priority_rules:
            rule.apply_to_collision_matrix(collision_matrix)
        for rule in self.normal_priority_rules:
            rule.apply_to_collision_matrix(collision_matrix)
        for rule in self.high_priority_rules:
            rule.apply_to_collision_matrix(collision_matrix)
        return collision_matrix
