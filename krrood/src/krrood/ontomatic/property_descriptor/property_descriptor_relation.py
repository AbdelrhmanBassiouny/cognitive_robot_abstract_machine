from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property, lru_cache
from collections import defaultdict

from typing_extensions import (
    Optional,
    Type,
    Iterable,
    Tuple,
    TYPE_CHECKING,
    Union,
    Iterator,
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


@dataclass(unsafe_hash=True, repr=False)
class PropertyDescriptorRelation(PredicateClassRelation):
    """
    Edge data representing a relation between two wrapped instances that is represented structurally by a property
    descriptor attached to the source instance.
    """

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
        source_updated = not self.inferred or self.update_source_wrapped_field_value()
        if not source_updated:
            # Means that the value was already set, so we don't need to infer anything.
            return
        self.add_to_graph_and_apply_implications()

    def add_to_graph_and_apply_implications(self):
        """
        Add this relation to the graph and apply all implications of this relation.
        """
        if self.add_to_graph():
            self.infer_and_apply_implications()

    def infer_and_apply_implications(self):
        """
        Infer all implications of adding this relation and apply them to the corresponding objects.
        """
        self.infer_super_relations()
        self.infer_inverse_relation()
        self.infer_transitive_relations()
        self.infer_chain_axioms()

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
        for super_domain, super_field in self.super_relations:
            self.__class__(
                super_domain, self.target, super_field, inferred=True
            ).update_source_and_add_to_graph_and_apply_implications()

    def infer_inverse_relation(self):
        """
        Infer the inverse relation if it exists.
        """
        if self.inverse_of:
            inverse_domain, inverse_field = self.inverse_domain_and_field
            self.__class__(
                inverse_domain, self.source, inverse_field, inferred=True
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
        roles_for_target = SymbolGraph().get_roles_for_instance(self.target)
        for role in roles_for_target:
            value = self.inverse_of.get_association_of_source_type(role.instance_type)
        return value

    def infer_transitive_relations(self):
        """
        Add all transitive relations of this relation type that results from adding this relation to the graph.
        """
        if self.transitive:
            self.infer_transitive_relations_outgoing_from_source()
            self.infer_transitive_relations_incoming_to_target()

    def infer_transitive_relations_outgoing_from_source(self):
        """
        Infer transitive relations outgoing from the source.
        """
        for nxt_relation in self.target_outgoing_relations_with_same_descriptor_type:
            self.__class__(
                self.source,
                nxt_relation.target,
                nxt_relation.wrapped_field,
                inferred=True,
            ).update_source_and_add_to_graph_and_apply_implications()

    def infer_transitive_relations_incoming_to_target(self):
        """
        Infer transitive relations incoming to the target.
        """
        for nxt_relation in self.source_incoming_relations_with_same_descriptor_type:
            self.__class__(
                nxt_relation.source,
                self.target,
                nxt_relation.wrapped_field,
                inferred=True,
            ).update_source_and_add_to_graph_and_apply_implications()

    @property
    def target_outgoing_relations_with_same_descriptor_type(
        self,
    ) -> Iterator[PredicateClassRelation]:
        """
        Get the outgoing relations from the target that have the same property descriptor type as this relation.
        """
        relation_condition = lambda relation: issubclass(
            relation.property_descriptor_class, self.property_descriptor_class
        )
        yield from SymbolGraph().get_outgoing_relations_with_condition(
            self.target, relation_condition
        )

    @property
    def source_incoming_relations_with_same_descriptor_type(
        self,
    ) -> Iterator[PredicateClassRelation]:
        """
        Get the incoming relations from the source that have the same property descriptor type as this relation.
        """
        relation_condition = lambda relation: issubclass(
            relation.property_descriptor_class, self.property_descriptor_class
        )
        yield from SymbolGraph().get_incoming_relations_with_condition(
            self.source, relation_condition
        )

    def infer_chain_axioms(self):
        """
        Infers relations based on property chain axioms.
        """
        all_axioms = self._get_all_chain_axioms()
        for target_class, chains in all_axioms.items():
            for chain in chains:
                for index, property_class in enumerate(chain):
                    if issubclass(self.property_descriptor_class, property_class):
                        prefix = chain[:index]
                        suffix = chain[index + 1 :]

                        for start_node in self._find_nodes_backward(
                            self.source, prefix
                        ):
                            for end_node in self._find_nodes_forward(
                                self.target, suffix
                            ):
                                self._apply_inferred_chain_relation(
                                    start_node, end_node, target_class
                                )

    def _get_all_chain_axioms(self):
        # Find property_descriptor_base once
        property_descriptor_base = None
        for base in self.property_descriptor_class.__mro__:
            if base.__name__ == "PropertyDescriptor":
                property_descriptor_base = base
                break
        if not property_descriptor_base:
            return {}
        return _cached_get_all_chain_axioms(property_descriptor_base)

    def _find_nodes_backward(
        self, end_node: WrappedInstance, chain: Tuple[Type[PropertyDescriptor], ...]
    ) -> Iterable[WrappedInstance]:
        if not chain:
            yield end_node
            return

        last_property_descriptor = chain[-1]
        remaining = chain[:-1]

        condition = lambda r: isinstance(r, PropertyDescriptorRelation) and issubclass(
            r.property_descriptor_class, last_property_descriptor
        )
        for relation in SymbolGraph().get_incoming_relations_with_condition(
            end_node, condition
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

        condition = lambda r: isinstance(r, PropertyDescriptorRelation) and issubclass(
            r.property_descriptor_class, first_property_descriptor
        )
        for relation in SymbolGraph().get_outgoing_relations_with_condition(
            start_node, condition
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


@lru_cache(maxsize=1)
def _cached_get_all_chain_axioms(property_descriptor_base):
    axioms = defaultdict(list)
    for cls in recursive_subclasses(property_descriptor_base):
        if issubclass(cls, HasChainAxioms):
            for target, chains in cls.get_chain_axioms().items():
                axioms[target].extend(chains)
    return axioms
