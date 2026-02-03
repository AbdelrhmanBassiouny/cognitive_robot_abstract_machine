from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np

from giskardpy.motion_statechart.auxilary_variable_manager import (
    create_vector3,
    create_point,
    AuxiliaryVariable,
)
from krrood.symbolic_math.symbolic_math import FloatVariable
from semantic_digital_twin.collision_checking.collision_detector import (
    CollisionCheckingResult,
    Collision,
)
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types import Vector3, Point3
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import (
    Body,
    KinematicStructureEntity,
)


@dataclass
class CollisionExpressionManager:
    external_monitored_links: dict[Body, int] = field(default_factory=dict)
    self_monitored_links: dict[tuple[Body, Body], int] = field(default_factory=dict)

    external_collision_data: np.ndarray = field(
        default_factory=lambda: np.zeros(0, dtype=float)
    )
    self_collision_data: np.ndarray = field(
        default_factory=lambda: np.zeros(0, dtype=float)
    )

    def monitor_link_for_external(self, body: Body, idx: int):
        self.external_monitored_links[body] = max(
            idx, self.external_monitored_links.get(body, 0)
        )

    def set_collision_result(self, collision_result: CollisionCheckingResult):
        self.external_collision_data = collision_result[
            : len(self.external_monitored_links)
        ]
        self.self_collision_data = collision_result[
            len(self.external_monitored_links) :
        ]

    def transform_external_collision(
        self, collision: Collision, world: World
    ) -> GiskardCollision:
        body_a = collision.original_body_a
        movable_joint = body_a.parent_connection

        while movable_joint != world.root:
            if is_joint_movable(movable_joint):
                break
            movable_joint = movable_joint.parent.parent_connection
        else:
            raise Exception(
                f"{body_a.name} has no movable parent connection "
                f"and should't have collision checking enabled."
            )
        new_a = movable_joint.child
        collision.body_a = new_a
        if collision.map_P_pa is not None:
            new_a_T_map = world.compute_forward_kinematics_np(new_a, world.root)
            collision.fixed_parent_of_a_P_pa = new_a_T_map @ collision.map_P_pa
        else:
            new_a_T_a = world.compute_forward_kinematics_np(
                new_a, collision.original_body_a
            )
            collision.fixed_parent_of_a_P_pa = new_a_T_a @ collision.a_P_pa

        return collision

    def get_external_collision_symbol(self) -> list[FloatVariable]:
        symbols = []
        for body, max_idx in self.external_monitored_links.items():
            for idx in range(max_idx + 1):
                symbols.append(self.external_link_b_hash_symbol(body, idx))

                v = self.external_map_V_n_symbol(body, idx)
                symbols.extend(
                    [
                        v.x.free_variables()[0],
                        v.y.free_variables()[0],
                        v.z.free_variables()[0],
                    ]
                )

                symbols.append(self.external_contact_distance_symbol(body, idx))

                p = self.external_new_a_P_pa_symbol(body, idx)
                symbols.extend(
                    [
                        p.x.free_variables()[0],
                        p.y.free_variables()[0],
                        p.z.free_variables()[0],
                    ]
                )

            symbols.append(self.external_number_of_collisions_symbol(body))
        if len(symbols) != self.external_collision_data.shape[0]:
            self.external_collision_data = np.zeros(len(symbols), dtype=float)
        return symbols

    @lru_cache
    def external_map_V_n_symbol(self, body: Body, idx: int) -> Vector3:
        return create_vector3(
            name=PrefixedName(f"closest_point({body.name})[{idx}].map_V_n.x"),
            provider=lambda n=body, i=idx: self.closest_points.get_external_collisions(
                n
            )[i].map_V_n,
        )

    @lru_cache
    def external_new_a_P_pa_symbol(self, body: Body, idx: int) -> Point3:
        return create_point(
            name=PrefixedName(f"closest_point({body.name})[{idx}].new_a_P_pa"),
            provider=lambda n=body, i=idx: self.closest_points.get_external_collisions(
                n
            )[i].fixed_parent_of_a_P_pa,
        )

    @lru_cache
    def get_variable_buffer_zone_distance(self, body: Body) -> FloatVariable: ...

    @lru_cache
    def get_variable_violated_distance(self, body: Body) -> FloatVariable: ...

    @lru_cache
    def external_contact_distance_symbol(
        self, body: Body, idx: int | None = None, body_b: Body | None = None
    ) -> AuxiliaryVariable:
        if body_b is None:
            assert idx is not None
            provider = (
                lambda n=body, i=idx: self.closest_points.get_external_collisions(n)[
                    i
                ].contact_distance
            )
            return AuxiliaryVariable(
                name=str(
                    PrefixedName(f"closest_point({body.name})[{idx}].contact_distance")
                ),
                provider=provider,
            )
        assert body_b is not None
        provider = lambda l1=body, l2=body_b: (
            self.closest_points.get_external_collisions_long_key(
                l1, l2
            ).contact_distance
        )
        return AuxiliaryVariable(
            name=str(
                PrefixedName(
                    f"closest_point({body.name}, {body_b.name}).contact_distance"
                )
            ),
            provider=provider,
        )

    @lru_cache
    def external_link_b_hash_symbol(
        self, body: Body, idx: int | None = None, body_b: Body | None = None
    ) -> AuxiliaryVariable:
        if body_b is None:
            assert idx is not None
            provider = (
                lambda n=body, i=idx: self.closest_points.get_external_collisions(n)[
                    i
                ].link_b_hash
            )
            return AuxiliaryVariable(
                name=str(
                    PrefixedName(f"closest_point({body.name})[{idx}].link_b_hash")
                ),
                provider=provider,
            )
        assert body_b is not None
        provider = lambda l1=body, l2=body_b: (
            self.closest_points.get_external_collisions_long_key(l1, l2).link_b_hash
        )
        return AuxiliaryVariable(
            name=str(
                PrefixedName(f"closest_point({body.name}, {body_b.name}).link_b_hash")
            ),
            provider=provider,
        )

    @lru_cache
    def external_number_of_collisions_symbol(
        self, body: KinematicStructureEntity
    ) -> AuxiliaryVariable:
        provider = lambda n=body: self.closest_points.get_number_of_external_collisions(
            n
        )
        return AuxiliaryVariable(
            name=str(PrefixedName(f"len(closest_point({body.name}))")),
            provider=provider,
        )
