from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import TYPE_CHECKING

from .role_mixins._ground_truth_role_takers_in_another_module_role_mixins import (
    RoleTakerInAnotherModuleRoleAttributes,
)

if TYPE_CHECKING:
    from .university_ontology_like_classes_without_descriptors import (
        PersonInRoleAndOntology,
    )


@dataclass(eq=False)
class RoleTakerInAnotherModule(RoleTakerInAnotherModuleRoleAttributes):
    original_attribute: str
    attribute_with_annotation_from_role_module: PersonInRoleAndOntology
