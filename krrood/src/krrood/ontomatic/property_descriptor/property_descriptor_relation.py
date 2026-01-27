from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from functools import cached_property, lru_cache
from collections import defaultdict

from krrood.class_diagrams.utils import Role

from krrood.ontomatic.property_descriptor.mixins import (
    HasEquivalentProperties,
    SymmetricProperty,
)

from typing_extensions import (
    Optional,
    Type,
    Iterable,
    Tuple,
    TYPE_CHECKING,
    Union,
    Iterator,
    List,
)

from .mixins import TransitiveProperty, HasInverseProperty, HasChainAxioms
from ...class_diagrams.class_diagram import Association, AssociationThroughRoleTaker
from ...class_diagrams.wrapped_field import WrappedField
from ...entity_query_language.symbol_graph import (
    PredicateClassRelation,
    SymbolGraph,
    WrappedInstance,
)
from ...utils import recursive_subclasses

if TYPE_CHECKING:
    from .property_descriptor import PropertyDescriptor


class InferredThrough(Enum):
    """
    Enum representing different ways a property descriptor relation can be inferred.
    """

    EQUIVALENT = "equivalent"
    INVERSE = "inverse"
    SUPER = "super"
    TRANSITIVE = "transitive"
    SYMMETRY = "symmetry"


@dataclass(eq=False, repr=False)
class PropertyDescriptorRelation(PredicateClassRelation):
    """
    Edge data representing a relation between two wrapped instances that is represented structurally by a property
    descriptor attached to the source instance.
    """

    inference_explanation: Optional[
        Tuple[InferredThrough, PropertyDescriptorRelation]
    ] = field(default=None, compare=False, hash=False)

    @cached_property
    def transitive(self) -> bool:
        """
        If the relation is transitive or not.
        """
        if self.property_descriptor_class:
            return issubclass(self.property_descriptor_class, TransitiveProperty)
        else:
            return False

    @cached_property
    def inverse_of(self) -> Optional[Type[PropertyDescriptor]]:
        """
        The inverse of the relation if it exists.
        """
        if self.property_descriptor_class and issubclass(
            self.property_descriptor_class, HasInverseProperty
        ):
            return self.property_descriptor_class.get_inverse()
        else:
            return None

    def update_source_and_add_to_graph_and_apply_implications(self):
        """
        Update the source wrapped-field value, add this relation to the graph, and apply all implications of adding this
         relation.
        """
        if not self.update_source():
            # Means that the value was already set, so we don't need to infer anything.
            return
        self.add_to_graph_and_apply_implications()

    def infer_and_apply_implications(self):
        """
        Infer all implications of adding this relation and apply them to the corresponding objects.
        """
        self.infer_equivalence_relations()
        self.infer_super_relations()
        self.infer_inverse_relation()
        self.infer_transitive_relations()
        self.infer_chain_axioms()
        self.infer_symmetric_relation()

    @property
    def is_inferred_from_equivalence_relation(self) -> bool:
        """
        Check if the relation was inferred from an equivalence relation.

        :return: True if the relation was inferred from an equivalence relation, False otherwise.
        """
        return (
            self.inference_explanation is not None
            and self.inference_explanation[0] == InferredThrough.EQUIVALENT
        )

    def infer_symmetric_relation(self):
        """
        Infer all symmetric relations of this relation.
        """
        if (
            self.inference_explanation
            and self.inference_explanation[0] == InferredThrough.SYMMETRY
        ):
            return
        if issubclass(self.property_descriptor_class, SymmetricProperty):
            self.__class__(
                self.target,
                self.source,
                self.wrapped_field,
                inferred=True,
                inference_explanation=(InferredThrough.SYMMETRY, self),
            ).update_source_and_add_to_graph_and_apply_implications()
            # self.wrapped_field.property_descriptor.update_value(
            #     self.target.instance, self.source.instance
            # )

    def update_source_and_add_to_graph(self):
        """
        Update the source wrapped-field value and add this relation to the graph.
        """
        if not self.update_source():
            # Means that the value was already set, so we don't need to infer anything.
            return
        self.add_to_graph()

    def update_source(self):
        """
        Update the source wrapped-field value.
        """
        return not self.inferred or self.update_source_wrapped_field_value()

    def infer_equivalence_relations(self):
        """
        Infer all equivalence relations of this relation.
        """
        if self.is_inferred_from_equivalence_relation:
            return

        for equivalence_relation in self.equivelence_relations:
            original_source_instance = equivalence_relation.get_original_source_instance_given_this_relation_source_instance(
                self.source.instance
            )
            source = SymbolGraph().get_wrapped_instance(original_source_instance)
            self.__class__(
                source,
                self.target,
                equivalence_relation.field,
                inferred=True,
                inference_explanation=(
                    InferredThrough.EQUIVALENT,
                    self,
                ),
            ).update_source_and_add_to_graph_and_apply_implications()

    @cached_property
    def equivelence_relations(self) -> Iterable[Association]:
        for equivalence_descriptor in self.equivalent_descriptors:
            yield equivalence_descriptor.get_association_of_source_type(
                self.source.instance_type
            )

    @property
    def equivalent_descriptors(self) -> List[Type[PropertyDescriptor]]:
        if issubclass(self.property_descriptor_class, HasEquivalentProperties):
            return self.property_descriptor_class.get_equivalent_properties()
        return []

    def update_source_wrapped_field_value(self) -> bool:
        """
        Update the wrapped field value for the source instance.

        :return: True if the value of the wrapped field was updated, False otherwise (i.e., if the value was already
        set).
        """
        return self.wrapped_field.property_descriptor.update_value(
            self.source.instance, self.target.instance
        )

    def infer_super_relations(self):
        """
        Infer all super relations of this relation.
        """
        # for super_domain, super_field in self.super_relations:
        for super_descriptor_type in self.property_descriptor_class.super_classes():
            super_value = None
            try:
                super_value = getattr(
                    self.source.instance, super_descriptor_type.get_field_name()
                )
            except AttributeError:
                if self.source.instance in Role._role_taker_roles:
                    for role in Role._role_taker_roles[self.source.instance]:
                        if hasattr(role, super_descriptor_type.get_field_name()):
                            super_value = getattr(
                                role, super_descriptor_type.get_field_name()
                            )
                            break
            if super_value is None:
                continue
            super_descriptor = super_value._descriptor
            super_domain = super_value._owner
            self.__class__(
                super_domain,
                self.target,
                super_descriptor.wrapped_field,
                inferred=True,
                inference_explanation=(InferredThrough.SUPER, self),
            ).update_source_and_add_to_graph_and_apply_implications()

    def infer_inverse_relation(self):
        """
        Infer the inverse relation if it exists.
        """
        if self.inverse_of and not (
            self.inference_explanation
            and self.inference_explanation[0] == InferredThrough.INVERSE
        ):
            # inverse_domain, inverse_field = self.inverse_domain_and_field
            inverse_domain = self.target
            inverse_value = None
            try:
                inverse_value = getattr(
                    inverse_domain.instance, self.inverse_of.get_field_name()
                )
            except AttributeError:
                if inverse_domain.instance in Role._role_taker_roles:
                    for role in Role._role_taker_roles[inverse_domain.instance]:
                        if hasattr(role, self.inverse_of.get_field_name()):
                            inverse_value = getattr(
                                role, self.inverse_of.get_field_name()
                            )
                            break
            if inverse_value is None:
                return
            inverse_descriptor = inverse_value._descriptor
            self.__class__(
                inverse_domain,
                self.source,
                inverse_descriptor.wrapped_field,
                inferred=True,
                inference_explanation=(InferredThrough.INVERSE, self),
            ).update_source_and_add_to_graph_and_apply_implications()

    @cached_property
    def super_relations(self) -> Iterable[Tuple[WrappedInstance, WrappedField]]:
        """
        Find neighboring symbols connected by super edges.

        This method identifies neighboring symbols that are connected
        through edge with relation types that are superclasses of the current relation type.

        :return: An iterator over neighboring symbols and relations that are super relations.
        """
        source_type = self.source.instance_type
        property_descriptor_cls: Type[PropertyDescriptor] = (
            self.wrapped_field.property_descriptor.__class__
        )
        for association in property_descriptor_cls.get_superproperties_associations(
            source_type
        ):
            original_source_instance = association.get_original_source_instance_given_this_relation_source_instance(
                self.source.instance
            )
            source = SymbolGraph().get_wrapped_instance(original_source_instance)
            yield source, association.field

    @property
    def inverse_domain_and_field(self) -> Tuple[WrappedInstance, WrappedField]:
        """
        Get the inverse of the property descriptor.

        :return: The inverse domain instance and property descriptor field.
        """
        if not self.inverse_association:
            import pdbpp

            pdbpp.set_trace()
            raise ValueError(
                f"cannot find a field for the inverse {self.inverse_of} defined for the relation {self.source.name}-{self.wrapped_field.public_name}-{self.target.name}"
            )
        original_source_instance = self.inverse_association.get_original_source_instance_given_this_relation_source_instance(
            self.target.instance
        )
        original_source_wrapped_instance = SymbolGraph().get_wrapped_instance(
            original_source_instance
        )
        return original_source_wrapped_instance, self.inverse_association.field

    @cached_property
    def inverse_association(
        self,
    ) -> Optional[Union[Association, AssociationThroughRoleTaker]]:
        """
        Return the inverse field (if it exists) stored in the target of this relation.
        """
        value = self.inverse_of.get_association_of_source_type(
            self.target.instance_type
        )
        if value is not None:
            return value
        return value

    def infer_transitive_relations(self):
        """
        Add all transitive relations of this relation type that results from adding this relation to the graph.
        """
        if self.is_inferred_from_equivalence_relation:
            return

        if issubclass(self.property_descriptor_class, SymmetricProperty):
            return

        if self.transitive:
            self.infer_transitive_relations_outgoing_from_source()
            self.infer_transitive_relations_incoming_to_target()

    def infer_transitive_relations_outgoing_from_source(self):
        """
        Infer transitive relations outgoing from the source.
        """

        def edge_condition(relation: PredicateClassRelation) -> bool:
            return relation.property_descriptor_class is self.property_descriptor_class

        for target in SymbolGraph()._instance_graph.find_successors_by_edge(
            self.target.index, edge_condition
        ):
            self.__class__(
                self.source,
                target,
                self.wrapped_field,
                inferred=True,
            ).update_source_and_add_to_graph_and_apply_implications()

    @cached_property
    def inferred_from_symmetry(self):
        return (
            self.inference_explanation
            and self.inference_explanation[0] == InferredThrough.SYMMETRY
        )

    def infer_transitive_relations_incoming_to_target(self):
        """
        Infer transitive relations incoming to the target.
        """

        def edge_condition(relation: PredicateClassRelation) -> bool:
            return relation.property_descriptor_class is self.property_descriptor_class

        for source in SymbolGraph()._instance_graph.find_predecessors_by_edge(
            self.source.index, edge_condition
        ):
            self.__class__(
                source,
                self.target,
                self.wrapped_field,
                inferred=True,
            ).update_source_and_add_to_graph_and_apply_implications()

    @property
    def target_outgoing_relations_with_same_descriptor_type(
        self,
    ) -> Iterator[PredicateClassRelation]:
        """
        Get the outgoing relations from the target that have the same property descriptor type as this relation.
        """
        yield from SymbolGraph().get_outgoing_relations_with_condition(
            self.target,
            lambda rel: rel.property_descriptor_class == self.property_descriptor_class,
        )

    @property
    def source_incoming_relations_with_same_descriptor_type(
        self,
    ) -> Iterator[PredicateClassRelation]:
        """
        Get the incoming relations from the source that have the same property descriptor type as this relation.
        """
        yield from SymbolGraph().get_incoming_relations_with_condition(
            self.source,
            lambda rel: rel.property_descriptor_class == self.property_descriptor_class,
        )

    def infer_chain_axioms(self):
        """
        Infers relations based on property chain axioms.
        """
        chain_data = self.property_descriptor_class.chain_axioms[
            self.property_descriptor_class
        ].items()
        for (target_class, chain), indicies in chain_data:
            for index in indicies:
                prefix = chain[:index]
                suffix = chain[index + 1 :]

                for start_node in self._find_nodes_backward(self.source, prefix):
                    for end_node in self._find_nodes_forward(self.target, suffix):
                        self._apply_inferred_chain_relation(
                            start_node, end_node, target_class
                        )

    def _find_nodes_backward(
        self, end_node: WrappedInstance, chain: Tuple[Type[PropertyDescriptor], ...]
    ) -> Iterable[WrappedInstance]:
        if not chain:
            yield end_node
            return

        last_property_descriptor = chain[-1]
        remaining = chain[:-1]

        for relation in SymbolGraph().get_incoming_relations_by_descriptor_class(
            end_node, last_property_descriptor
        ):
            yield from self._find_nodes_backward(relation.source, remaining)

    def _find_nodes_forward(
        self,
        start_node: WrappedInstance,
        chain: Tuple[Type[PropertyDescriptor], ...],
    ) -> Iterable[WrappedInstance]:
        if not chain:
            yield start_node
            return

        first_property_descriptor = chain[0]
        remaining = chain[1:]

        for relation in SymbolGraph().get_outgoing_relations_by_descriptor_class(
            start_node, first_property_descriptor
        ):
            yield from self._find_nodes_forward(relation.target, remaining)

    def _apply_inferred_chain_relation(
        self,
        source: WrappedInstance,
        target: WrappedInstance,
        target_property_descriptor_class: Type[PropertyDescriptor],
    ):
        association = target_property_descriptor_class.get_association_of_source_type(
            source.instance_type
        )
        if association:
            self.__class__(
                source, target, association.field, inferred=True
            ).update_source_and_add_to_graph_and_apply_implications()

    @cached_property
    def property_descriptor_class(self) -> Type[PropertyDescriptor]:
        """
        Return the property descriptor class of the relation.
        """
        return type(self.wrapped_field.property_descriptor)
