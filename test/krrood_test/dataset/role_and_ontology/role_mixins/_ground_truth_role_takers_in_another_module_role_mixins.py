from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from typing_extensions import TYPE_CHECKING

if TYPE_CHECKING:
    from test.krrood_test.dataset.role_and_ontology.university_ontology_like_classes_without_descriptors import (
        PersonInRoleAndOntology,
    )
    from test.krrood_test.dataset.role_and_ontology.role_takers_in_another_module import RoleTakerInAnotherModule


@dataclass(eq=False)
class RoleForRoleTakerInAnotherModule(ABC):

    @property
    @abstractmethod
    def role_taker(self) -> RoleTakerInAnotherModule: ...

    @property
    def original_attribute(self) -> str:
        return self.role_taker.original_attribute

    @original_attribute.setter
    def original_attribute(self, value: str):
        self.role_taker.original_attribute = value

    @property
    def attribute_with_annotation_from_role_module(self) -> PersonInRoleAndOntology:
        return self.role_taker.attribute_with_annotation_from_role_module

    @attribute_with_annotation_from_role_module.setter
    def attribute_with_annotation_from_role_module(
        self, value: PersonInRoleAndOntology
    ):
        self.role_taker.attribute_with_annotation_from_role_module = value
