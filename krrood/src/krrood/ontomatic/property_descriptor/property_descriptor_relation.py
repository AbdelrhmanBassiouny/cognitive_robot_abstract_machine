from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from functools import cached_property, lru_cache
from collections import defaultdict

from krrood.class_diagrams.utils import Role
from line_profiler import profile

from krrood.ontomatic.property_descriptor.mixins import (
    HasEquivalentProperties,
    SymmetricProperty,
)

from typing_extensions import (
    Any,
    ClassVar,
    Dict,
    Optional,
    Type,
    Iterable,
    Tuple,
    TYPE_CHECKING,
    Iterator,
    List,
)

from .mixins import TransitiveProperty, HasInverseProperty, HasChainAxioms
from ..failures import NoObjectOfIndividualDeclaresProperty
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
    CHAIN = "chain"
    SYMMETRIC_TRANSITIVE_COMPONENT = "symmetric_transitive_component"


@dataclass(eq=False)
class SymmetricTransitiveComponent:
    """
    A weakly connected component of the relation graph of a property that is both symmetric and transitive. The
    property relates every two members of the component, and each member to itself unless the property is
    irreflexive. When the property implies no other property, the facts of the component are stored only in the
    attributes of its members, and the component is their explanation.
    """

    property_descriptor_class: Type[PropertyDescriptor]
    """
    The symmetric and transitive property.
    """
    identifier: int
    """
    The index of the component among the components of the property.
    """
    members: Dict[int, WrappedInstance]
    """
    The members of the component by their index in the symbol graph.
    """
    reflexive: bool
    """
    Whether the property relates each member to itself.
    """

    def relates(self, source: WrappedInstance, target: WrappedInstance) -> bool:
        """
        :return: True if the component entails that the property relates the source to the target.
        """
        return (
            self.members.get(source.index) is source
            and self.members.get(target.index) is target
            and (self.reflexive or source is not target)
        )

    def relation(
        self, source: WrappedInstance, target: WrappedInstance
    ) -> PropertyDescriptorRelation:
        """
        :return: The relation from the source to the target, explained by this component. It is not added to the
         symbol graph.
        """
        wrapped_field = self.property_descriptor_class.get_descriptor_instance_for_domain_type(
            source.instance_type
        ).wrapped_field
        return PropertyDescriptorRelation(
            source,
            target,
            wrapped_field,
            inferred=True,
            inference_explanation=(
                InferredThrough.SYMMETRIC_TRANSITIVE_COMPONENT,
                self.property_descriptor_class.__name__,
                self.identifier,
                len(self.members),
            ),
        )


@dataclass(eq=False, repr=False)
class PropertyDescriptorRelation(PredicateClassRelation):
    """
    Edge data representing a relation between two wrapped instances that is represented structurally by a property
    descriptor attached to the source instance.
    """

    inference_explanation: Optional[Tuple[Any, ...]] = field(
        default=None, compare=False, hash=False
    )
    """
    How an inferred relation was derived: a tuple whose first element is the :class:`InferredThrough` rule and whose
    remaining elements are the premises. The premises are relations for EQUIVALENT, SUPER, INVERSE and SYMMETRY (one
    premise), TRANSITIVE (the two composed relations) and CHAIN (the relations of the chain, in order). For
    SYMMETRIC_TRANSITIVE_COMPONENT the premises are the name of the property descriptor, the identifier of the weakly
    connected component of its relation graph that entails the relation, and the size of the component (see
    :class:`SymmetricTransitiveComponent`). Asserted relations have no explanation.
    """

    eager_symmetric_transitive_closure: ClassVar[bool] = False
    """
    Whether relations of properties that are both symmetric and transitive are closed eagerly, relation by relation,
    while they are added. By default this is disabled and the closure is computed once after loading from the weakly
    connected components of the relation graph (see ``OwlLoader.add_inferences_from_transitive_symmetric_relations``).
    Enabling it reproduces the behaviour before the connected-components optimisation and is only meant for the
    ablation experiment.
    """

    symmetric_transitive_components: ClassVar[
        Dict[Tuple[str, int], SymmetricTransitiveComponent]
    ] = {}
    """
    The components whose facts are stored only in the attributes of their members, by the attribute name and the
    symbol-graph index of each member. :meth:`find` uses them to explain these facts.
    """

    same_individual_role_takers: ClassVar[Dict[Any, List[Any]]] = {}
    """
    For a root role taker, the other root role takers that represent the same individual. An individual is usually
    represented by one root object and its roles. When an individual has a type whose role taker type it cannot be,
    such as a research group that is entailed to be an employee (a role of a person), its role has a separate root,
    and the loader links the two roots here.
    """

    @staticmethod
    def root_role_taker(instance: Any) -> Any:
        """
        :param instance: Any object.
        :return: The object at the end of the role-taker chain of the instance, or the instance if it is not a role.
        """
        while isinstance(instance, Role):
            instance = instance.role_taker
        return instance

    @classmethod
    def objects_of_individual(cls, instance: Any) -> List[Any]:
        """
        :param instance: An object of the individual.
        :return: The objects that represent the same individual as the instance: its root role taker followed by the
         roles of that root in the order they were created (``Role._role_taker_roles`` lists the roles of roles under
         the root as well), then the same for every root linked in :attr:`same_individual_role_takers`. Roles compare
         equal to their root, so the objects are told apart by identity.
        """
        root = cls.root_role_taker(instance)
        objects = []
        seen_identities = set()
        for linked_root in [root, *cls.same_individual_role_takers.get(root, ())]:
            for individual_object in [
                linked_root,
                *Role._role_taker_roles.get(linked_root, ()),
            ]:
                if id(individual_object) not in seen_identities:
                    seen_identities.add(id(individual_object))
                    objects.append(individual_object)
        return objects

    @classmethod
    def nodes_of_individual(cls, node: WrappedInstance) -> List[WrappedInstance]:
        """
        :param node: A node of the symbol graph.
        :return: The node and the nodes of the roots linked to it in :attr:`same_individual_role_takers`.
        """
        linked_nodes = (
            SymbolGraph().get_wrapped_instance(root)
            for root in cls.same_individual_role_takers.get(node.instance, ())
        )
        return [node, *(linked for linked in linked_nodes if linked is not None)]

    @classmethod
    def holder_of_property(
        cls, instance: Any, property_descriptor_class: Type[PropertyDescriptor]
    ) -> Optional[Tuple[WrappedInstance, WrappedField]]:
        """
        Find where a fact of the property about the individual of the instance is stored.

        The objects of the individual are checked in the order of :meth:`objects_of_individual`, so the root comes
        first. This order matters only for where the fact is stored, not for what it means: all objects of the
        individual denote it. The class hierarchy of each object is walked from its most specific class; a role class
        does not inherit from its role taker type, so a property declared on the role taker type is found on the root.

        :param instance: An object of the individual.
        :param property_descriptor_class: The property.
        :return: The node of the root role taker of the first object of the individual whose class declares the
         property, and the wrapped field of the declaration; None if no object of the individual declares the
         property.
        """
        descriptors = property_descriptor_class.descriptor_instances_by_domain_type[
            property_descriptor_class
        ]
        for individual_object in cls.objects_of_individual(instance):
            for object_type in type(individual_object).__mro__:
                if object_type in descriptors:
                    node = SymbolGraph().ensure_wrapped_instance(
                        cls.root_role_taker(individual_object)
                    )
                    return node, descriptors[object_type].wrapped_field
        return None

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
        if self.inference_explanation and self.inference_explanation[0] in (
            InferredThrough.SYMMETRY,
            InferredThrough.SYMMETRIC_TRANSITIVE_COMPONENT,
        ):
            # The component of a symmetric-transitive property already contains both directions.
            return
        if issubclass(self.property_descriptor_class, SymmetricProperty):
            self.add_inferred_relation(
                self.target.instance,
                self.property_descriptor_class,
                self.source,
                (InferredThrough.SYMMETRY, self),
            )

    def add_inferred_relation(
        self,
        source_instance: Any,
        property_descriptor_class: Type[PropertyDescriptor],
        target: WrappedInstance,
        inference_explanation: Tuple[Any, ...],
    ):
        """
        Store an inferred fact of the property about the individual of the source instance on the object of that
        individual that declares the property (see :meth:`holder_of_property`), add it to the symbol graph and apply
        its implications. Nothing is stored if no object of the individual declares the property.

        :param source_instance: An object of the subject individual.
        :param property_descriptor_class: The property of the inferred fact.
        :param target: The node of the value.
        :param inference_explanation: The rule and premises of the inference (see :attr:`inference_explanation`).
        """
        holder = self.holder_of_property(source_instance, property_descriptor_class)
        if holder is None:
            return
        source, wrapped_field = holder
        self.__class__(
            source,
            target,
            wrapped_field,
            inferred=True,
            inference_explanation=inference_explanation,
        ).update_source_and_add_to_graph_and_apply_implications()

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

        for equivalent_descriptor in self.equivalent_descriptors:
            self.add_inferred_relation(
                self.source.instance,
                equivalent_descriptor,
                self.target,
                (InferredThrough.EQUIVALENT, self),
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
        descriptor = self.wrapped_field.property_descriptor
        holder = next(
            (
                individual_object
                for individual_object in self.objects_of_individual(
                    self.source.instance
                )
                if isinstance(individual_object, descriptor.domain)
            ),
            None,
        )
        if holder is None:
            raise NoObjectOfIndividualDeclaresProperty(
                self.source.instance, type(descriptor)
            )
        return descriptor.update_value(holder, self.target.instance)

    def infer_super_relations(self):
        """
        Infer all super relations of this relation.
        """
        for super_descriptor_type in self.property_descriptor_class.super_classes():
            self.add_inferred_relation(
                self.source.instance,
                super_descriptor_type,
                self.target,
                (InferredThrough.SUPER, self),
            )

    def infer_inverse_relation(self):
        """
        Infer the inverse relation if it exists.
        """
        if self.inverse_of and not (
            self.inference_explanation
            and self.inference_explanation[0] == InferredThrough.INVERSE
        ):
            self.add_inferred_relation(
                self.target.instance,
                self.inverse_of,
                self.source,
                (InferredThrough.INVERSE, self),
            )

    def infer_transitive_relations(self):
        """
        Add all transitive relations of this relation type that results from adding this relation to the graph.
        """
        if self.is_inferred_from_equivalence_relation:
            return

        if (
            issubclass(self.property_descriptor_class, SymmetricProperty)
            and not self.eager_symmetric_transitive_closure
        ):
            return

        if self.transitive:
            self.infer_transitive_relations_outgoing_from_source()
            self.infer_transitive_relations_incoming_to_target()

    def infer_transitive_relations_outgoing_from_source(self):
        """
        Infer transitive relations outgoing from the source.
        """

        for relation in list(self.target_outgoing_relations_with_same_descriptor_type):
            self.__class__(
                self.source,
                relation.target,
                self.wrapped_field,
                inferred=True,
                inference_explanation=(InferredThrough.TRANSITIVE, self, relation),
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

        for relation in list(self.source_incoming_relations_with_same_descriptor_type):
            self.__class__(
                relation.source,
                self.target,
                self.wrapped_field,
                inferred=True,
                inference_explanation=(InferredThrough.TRANSITIVE, relation, self),
            ).update_source_and_add_to_graph_and_apply_implications()

    @property
    def target_outgoing_relations_with_same_descriptor_type(
        self,
    ) -> Iterator[PredicateClassRelation]:
        """
        Get the outgoing relations from the target that have the same property descriptor type as this relation.
        """
        for node in self.nodes_of_individual(self.target):
            yield from SymbolGraph().get_outgoing_relations_with_condition(
                node,
                lambda rel: rel.property_descriptor_class
                == self.property_descriptor_class,
            )

    @property
    def source_incoming_relations_with_same_descriptor_type(
        self,
    ) -> Iterator[PredicateClassRelation]:
        """
        Get the incoming relations from the source that have the same property descriptor type as this relation.
        """
        for node in self.nodes_of_individual(self.source):
            yield from SymbolGraph().get_incoming_relations_with_condition(
                node,
                lambda rel: rel.property_descriptor_class
                == self.property_descriptor_class,
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

                for start_node, prefix_relations in self._find_nodes_backward(
                    self.source, prefix
                ):
                    for end_node, suffix_relations in self._find_nodes_forward(
                        self.target, suffix
                    ):
                        self._apply_inferred_chain_relation(
                            start_node,
                            end_node,
                            target_class,
                            prefix_relations + (self,) + suffix_relations,
                        )

    def _find_nodes_backward(
        self, end_node: WrappedInstance, chain: Tuple[Type[PropertyDescriptor], ...]
    ) -> Iterable[Tuple[WrappedInstance, Tuple[PropertyDescriptorRelation, ...]]]:
        """
        :return: The start nodes of paths that follow ``chain`` and end in ``end_node`` (or in a node of the same
         individual, see :meth:`nodes_of_individual`), each with the relations of its path in order.
        """
        if not chain:
            yield end_node, ()
            return

        last_property_descriptor = chain[-1]
        remaining = chain[:-1]

        incoming_relations = [
            relation
            for node in self.nodes_of_individual(end_node)
            for relation in SymbolGraph().get_incoming_relations_by_descriptor_class(
                node, last_property_descriptor
            )
        ]
        for relation in incoming_relations:
            for start_node, path in self._find_nodes_backward(
                relation.source, remaining
            ):
                yield start_node, path + (relation,)

    def _find_nodes_forward(
        self,
        start_node: WrappedInstance,
        chain: Tuple[Type[PropertyDescriptor], ...],
    ) -> Iterable[Tuple[WrappedInstance, Tuple[PropertyDescriptorRelation, ...]]]:
        """
        :return: The end nodes of paths that start in ``start_node`` (or in a node of the same individual, see
         :meth:`nodes_of_individual`) and follow ``chain``, each with the relations of its path in order.
        """
        if not chain:
            yield start_node, ()
            return

        first_property_descriptor = chain[0]
        remaining = chain[1:]

        outgoing_relations = [
            relation
            for node in self.nodes_of_individual(start_node)
            for relation in SymbolGraph().get_outgoing_relations_by_descriptor_class(
                node, first_property_descriptor
            )
        ]
        for relation in outgoing_relations:
            for end_node, path in self._find_nodes_forward(relation.target, remaining):
                yield end_node, (relation,) + path

    def _apply_inferred_chain_relation(
        self,
        source: WrappedInstance,
        target: WrappedInstance,
        target_property_descriptor_class: Type[PropertyDescriptor],
        chain_relations: Tuple[PropertyDescriptorRelation, ...] = (),
    ):
        self.add_inferred_relation(
            source.instance,
            target_property_descriptor_class,
            target,
            (InferredThrough.CHAIN, *chain_relations),
        )

    @property
    def rule(self) -> Optional[InferredThrough]:
        """
        :return: The rule that inferred this relation, or None if the relation was asserted.
        """
        return self.inference_explanation[0] if self.inference_explanation else None

    @property
    def premises(self) -> Tuple[Any, ...]:
        """
        :return: The premises of the rule that inferred this relation (see :attr:`inference_explanation`).
        """
        return tuple(self.inference_explanation[1:]) if self.inference_explanation else ()

    def explain(self, depth: int = 3) -> Dict[str, Any]:
        """
        Explain how this relation was obtained.

        :param depth: How many levels of premises to expand.
        :return: A nested mapping with the fact (source, field, target), the rule (None for asserted relations) and
         the explanations of the premises.
        """
        explanation: Dict[str, Any] = {
            "fact": (
                getattr(self.source.instance, "uri", self.source.instance),
                self.wrapped_field.name,
                getattr(self.target.instance, "uri", self.target.instance),
            ),
            "rule": self.rule.value if self.rule else None,
        }
        if self.inference_explanation and depth > 0:
            explanation["premises"] = [
                (
                    premise.explain(depth - 1)
                    if isinstance(premise, PropertyDescriptorRelation)
                    else premise
                )
                for premise in self.premises
            ]
        return explanation

    @classmethod
    def find(
        cls, source_instance: Any, field_name: str, target_instance: Any
    ) -> Optional[PropertyDescriptorRelation]:
        """
        Find the relation stored in the symbol graph for a fact.

        :param source_instance: The object that holds the attribute.
        :param field_name: The attribute name.
        :param target_instance: The value.
        :return: The relation, or None if the fact is neither in the symbol graph nor entailed by a symmetric and
         transitive component.
        """
        wrapped_source = SymbolGraph().get_wrapped_instance(source_instance)
        if wrapped_source is None:
            return None
        for relation in SymbolGraph()._relation_index.get(field_name, {}).get(
            wrapped_source.index, ()
        ):
            if relation.target.instance is target_instance:
                return relation
        component = cls.symmetric_transitive_components.get(
            (field_name, wrapped_source.index)
        )
        wrapped_target = SymbolGraph().get_wrapped_instance(target_instance)
        if (
            component is not None
            and wrapped_target is not None
            and component.relates(wrapped_source, wrapped_target)
        ):
            return component.relation(wrapped_source, wrapped_target)
        return None

    @cached_property
    def property_descriptor_class(self) -> Type[PropertyDescriptor]:
        """
        Return the property descriptor class of the relation.
        """
        return type(self.wrapped_field.property_descriptor)
