from dataclasses import dataclass

from krrood.entity_query_language.factories import variable_from
from krrood.patterns.role import Role
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.spatial_types.role_mixins.spatial_types_role_mixins import (
    RoleForPose,
)


@dataclass
class RoleForPose(Role[Pose], RoleForPose):

    pose: Pose

    @classmethod
    def role_taker_attribute(cls) -> Pose:
        return variable_from(cls).pose
