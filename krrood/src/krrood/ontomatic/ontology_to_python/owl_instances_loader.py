from __future__ import annotations

import logging
import os.path
import time
from abc import ABC
from collections import defaultdict
from enum import Enum
from dataclasses import fields, is_dataclass, dataclass, field
from functools import lru_cache
from types import ModuleType
from typing import Any, Dict, Iterable, List, Optional, Tuple, Type, Union, ClassVar

import rdflib
import rustworkx as rx
from krrood.ontomatic.utils import NamingRegistry
from rdflib import RDF, URIRef, Literal, OWL, RDFS
from ripple_down_rules import RDRDecorator
from tqdm import tqdm

from ..property_descriptor.attribute_introspector import (
    DescriptorAwareIntrospector,
)
from ..property_descriptor.mixins import (
    HasEquivalentProperties,
    HasInverseProperty,
    IsBaseClass,
    TransitiveProperty,
    SymmetricProperty,
    IrreflexiveProperty,
    ReflexiveProperty,
)
from ..property_descriptor.property_descriptor import PropertyDescriptor
from ..property_descriptor.property_descriptor_relation import (
    PropertyDescriptorRelation,
    SymmetricTransitiveComponent,
)
from ..utils import (
    get_non_class_attribute_names_of_instance,
    get_most_specific_types,
    AnonymousClass,
)
from ...class_diagrams.class_diagram import Association, ClassDiagram
from ...class_diagrams.utils import (
    issubclass_or_role,
    Role,
    sort_classes_by_role_aware_inheritance_path_length,
)
from ...entity_query_language.predicate import Symbol
from ...entity_query_language.symbol_graph import SymbolGraph
from ...ormatic.utils import classes_of_module

logger = logging.Logger("owl_loader")
logger.setLevel(logging.DEBUG)

# Handler
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)  # <-- this filters out DEBUG messages
logger.addHandler(handler)


class TypeInferredThrough(Enum):
    """
    How the loader obtained a type of an individual.
    """

    ASSERTED = "asserted"
    """
    An rdf:type statement of the data. Premise: the class.
    """
    DOMAIN = "domain"
    """
    The declared domain of a property of the individual (OWL 2 RL rule prp-dom). Premise: (subject, property, value).
    """
    RANGE = "range"
    """
    The declared range of a property whose value is the individual (OWL 2 RL rule prp-rng).
    Premise: (subject, property, value).
    """
    AXIOM = "axiom"
    """
    The individual satisfies a sufficient condition (owl:equivalentClass definition or general class axiom) of the
    class. Premise: the class whose axiom held.
    """
    BASE_CLASS = "base_class"
    """
    The individual has no asserted or inferred type, it is represented by the ontology base class (owl:Thing).
    Premise: none.
    """


@dataclass(frozen=True)
class TypeExplanation:
    """
    The explanation of a type of an individual.
    """

    rule: TypeInferredThrough
    """
    The rule that added the type.
    """
    premises: Tuple[Any, ...]
    """
    The premises of the rule, see :class:`TypeInferredThrough`.
    """


class OwlInstancesRegistry:
    """Registry of instances created from an OWL/RDF instances file.

    Provides access to instances per Python model class and tracks URIRef to instance mapping.
    """

    def __init__(self, symbol_graph: Optional[SymbolGraph] = None) -> None:
        self._by_uri: Dict[URIRef, List[Any]] = defaultdict(list)
        self.type_explanations: Dict[URIRef, Dict[Type, TypeExplanation]] = (
            defaultdict(dict)
        )

    def record_type(
        self, uri: URIRef, cls: Type, rule: TypeInferredThrough, *premises: Any
    ) -> None:
        """
        Record why an individual has a type. The first explanation of a type is kept.
        """
        self.type_explanations[uri].setdefault(cls, TypeExplanation(rule, premises))

    def explain_type(self, uri: Union[str, URIRef], cls: Type) -> Optional[TypeExplanation]:
        """
        :param uri: The individual.
        :param cls: A class of the individual.
        :return: The explanation of the type, or of the recorded type it is implied by (a subclass or role of
         ``cls``), or None if no recorded type implies ``cls``.
        """
        explanations = self.type_explanations.get(URIRef(uri), {})
        if cls in explanations:
            return explanations[cls]
        for recorded_cls, explanation in explanations.items():
            if issubclass_or_role(recorded_cls, cls):
                return explanation
        return None

    def get_or_create_for(
        self, uri: URIRef, factory: Type, symbol_graph, *args, **kwargs
    ) -> Any:
        instances = self.resolve(uri)

        if instances and any(isinstance(inst, factory) for inst in instances):
            # If an instance of the desired factory already exists, return it
            return next(i for i in instances if isinstance(i, factory))

        role_taker_field, role_taker = OwlLoader.get_and_construct_role_taker(
            self, factory, uri, symbol_graph, **kwargs
        )
        if role_taker_field:
            kwargs[role_taker_field.name] = role_taker

        inst = factory(*args, **kwargs)

        # Set URI if not already set
        local = str(uri)
        # if hasattr(inst, "uri") and getattr(inst, "uri") is None:
        setattr(inst, "uri", local)

        # Update instance mappings
        self._by_uri[uri].append(inst)
        return inst

    def resolve(self, uri: URIRef) -> Optional[Any]:
        if isinstance(uri, str):
            uri = URIRef(uri)
        return self._by_uri.get(uri)


@lru_cache(maxsize=None)
def local_name(uri: Union[str, URIRef]) -> str:
    s = str(uri)
    if "#" in s:
        return s.rsplit("#", 1)[1]
    return s.rstrip("/").rsplit("/", 1)[-1]


@lru_cache(maxsize=None)
def to_snake(name: str) -> str:
    out = []
    for i, ch in enumerate(name):
        if ch.isupper() and i > 0 and (not name[i - 1].isupper()):
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


@lru_cache(maxsize=None)
def to_pascal(name: str) -> str:
    parts = []
    cur = []
    for ch in name:
        if ch == "_":
            if cur:
                parts.append("".join(cur))
                cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur))
    return "".join(p.capitalize() for p in parts)


class ModelMetadata:
    """Metadata about the Python model classes and their relationship to OWL.

    Maintains mappings from RDF class names to Python classes, and from RDF predicates to
    Python attributes and property descriptors.
    """

    def __init__(
        self,
        model_modules: Union[ModuleType, Iterable[ModuleType]],
        symbol_graph: SymbolGraph,
    ):
        """Initializes ModelMetadata by scanning the provided modules.

        Args:
            model_modules: A single module or an iterable of modules containing the model classes.
        """
        self.class_by_name: Dict[str, Type] = {}
        self.descriptor_by_name: Dict[str, Type] = {}
        self.symbol_graph = symbol_graph
        self.ontology_base_class: Optional[Type] = None
        self._collect(model_modules)

    def _collect(self, model_modules: Union[ModuleType, Iterable[ModuleType]]):
        """Orchestrates the collection of metadata from the model modules.

        Args:
            model_modules: Modules to scan for classes and descriptors.
        """
        if isinstance(model_modules, (ModuleType, type)):
            model_modules = [model_modules]
        self._collect_classes_and_descriptors(model_modules)

    def _collect_classes_and_descriptors(self, model_modules: Iterable[ModuleType]):
        """Scans modules for dataclasses and PropertyDescriptor subclasses.

        Args:
            model_modules: Iterable of modules to scan.
        """
        modules_objects = {}
        for model_module in model_modules:
            modules_objects.update(
                {
                    attr_name: getattr(model_module, attr_name)
                    for attr_name in dir(model_module)
                }
            )

        for attr_name, obj in modules_objects.items():

            # Collect model classes (dataclasses used to represent OWL classes)
            if isinstance(obj, type) and is_dataclass(obj):
                self.class_by_name[attr_name] = obj
                if IsBaseClass in obj.__bases__:
                    self.ontology_base_class = obj

            # Collect descriptor classes available in the module for quick lookup by name
            if (
                isinstance(obj, type)
                and issubclass(obj, PropertyDescriptor)
                and obj is not PropertyDescriptor
            ):
                self.descriptor_by_name[obj.__name__] = obj

    def get_python_class(self, rdf_class: URIRef) -> Optional[Type]:
        """Returns the Python class corresponding to the given RDF class URI.

        Args:
            rdf_class: The URIRef of the RDF class.

        Returns:
            The Python class if found, otherwise None.
        """
        name = local_name(rdf_class)
        # Expect PascalCase names in model equal to RDF local name
        return self.class_by_name.get(name)

    @lru_cache
    def get_descriptor_base(
        self, pred_local: str
    ) -> Optional[Type[PropertyDescriptor]]:
        """Finds the PropertyDescriptor base class for a given predicate local name.

        Args:
            pred_local: The local name of the RDF predicate.

        Returns:
            The PropertyDescriptor subclass if found, otherwise None.
        """
        return self.descriptor_by_name.get(to_pascal(pred_local))


@dataclass(unsafe_hash=True)
class URIType:
    """
    Represents a pairing of a URI and its associated Python type.
    """

    uri: URIRef
    """
    The URI of the entity.
    """
    type: Type
    """
    The associated Python type.
    """

    def __str__(self):
        return f"URIType(uri={self.uri}, type={self.type.__name__})"

    def __repr__(self):
        return self.__str__()


@dataclass
class OwlLoader:
    """Loader for OWL/RDF instances into Python model instances."""

    owl_path: str
    model_modules: Union[ModuleType, Iterable[ModuleType]]
    symbol_graph: SymbolGraph
    registry: OwlInstancesRegistry
    graph: rdflib.Graph = field(default_factory=rdflib.Graph)
    anonymous_instances: Dict[URIRef, AnonymousClass] = field(default_factory=dict)
    literals: Dict[URIRef, Dict[str, Literal]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    _triples_by_subject: Dict[URIRef, List[Tuple[URIRef, Any]]] = field(
        default_factory=lambda: defaultdict(list)
    )

    @dataclass
    class Case:
        instance: AnonymousClass
        self_: OwlLoader
        output_: List[Type]

    @staticmethod
    def ask_now(case: Case):
        # return str(case.instance.uri) == "http://benchmark/OWL2Bench#U0"
        # return str(case.instance.uri) == "http://benchmark/OWL2Bench#U0C0D0AP0"
        return False

    metadata: ModelMetadata = field(init=False)
    _type_rdr: ClassVar[RDRDecorator] = RDRDecorator(
        os.path.join(os.path.dirname(__file__), "rdrs"),
        (URIType,),
        False,
        fit=True,
        ask_now=ask_now,
        update_existing_rules=False,
        use_generated_classifier=False,
        regenerate_model=False,
    )

    def __post_init__(self):
        PropertyDescriptor.update_domains_that_are_axiomatized_on_properties()
        self.metadata = ModelMetadata(self.model_modules, self.symbol_graph)

    def index_triples(self):
        """Indexes all triples in the graph for faster lookup by subject."""
        self._triples_by_subject.clear()
        for s, p, o in self.graph:
            self._triples_by_subject[s].append((p, o))

    def load(self) -> OwlInstancesRegistry:
        """Parses the OWL file and loads instances into the registry.

        Returns:
            The populated OwlInstancesRegistry.
        """
        self.graph.parse(self.owl_path)
        self.index_triples()
        self.create_anonymous_instances()
        self.assign_all_properties_to_all_anonymous_instances()
        self.infer_all_types_for_the_anonymous_instances()
        self.keep_most_specific_types_and_sort_from_least_to_most_specific()
        self.create_explicit_instances_from_inferred_types_of_anonymous_instances()
        self.sort_explicit_types_from_most_to_least_specific()
        self.link_role_takers_of_the_same_individual()
        self.assign_all_properties_to_explict_types_and_apply_on_time_forward_chaining()
        if not PropertyDescriptorRelation.eager_symmetric_transitive_closure:
            self.add_inferences_from_transitive_symmetric_relations()
        return self.registry

    def link_role_takers_of_the_same_individual(self):
        """
        Link the root role takers of the objects of every individual that has more than one (see
        :attr:`PropertyDescriptorRelation.same_individual_role_takers`), so that inferred facts about the individual
        are stored on whichever of its objects declares the property.
        """
        same_individual_role_takers = (
            PropertyDescriptorRelation.same_individual_role_takers
        )
        same_individual_role_takers.clear()
        for objects in self.registry._by_uri.values():
            roots = []
            for individual_object in objects:
                root = PropertyDescriptorRelation.root_role_taker(individual_object)
                if not any(root is known_root for known_root in roots):
                    roots.append(root)
            if len(roots) < 2:
                continue
            for root in roots:
                same_individual_role_takers[root] = [
                    other for other in roots if other is not root
                ]

    def infer_all_types_for_the_anonymous_instances(self):
        """
        Infer the types of every individual from the properties it has. Only OWL 2 RL entailed types are added:

        * the declared domain of every property of the individual (rule prp-dom), and its declared range for the
          values (rule prp-rng);
        * every class that declares a sufficient condition (an owl:equivalentClass definition or a general class axiom
          with the class as superclass, rendered as its own ``axiom_python``) that the individual satisfies.

        Necessary conditions (restrictions in superclass position) and range specialisations of subclasses are not
        used for classification, since they are not entailed in the direction from the property to the class.

        Inferred types are also added to ``instance.types`` so that the type checks of the axioms (e.g. the
        ``Student`` conjunct of ``Student and (hasMajor some Science) SubClassOf ScienceStudent``) see them, and the
        inference is repeated until no new type is added (fixpoint).
        """
        declared_domains: Dict[Type[PropertyDescriptor], Tuple[Type, ...]] = {}
        sufficient_domains: Dict[Type[PropertyDescriptor], Tuple[Type, ...]] = {}
        for instance in self.anonymous_instances.values():
            instance.final_sorted_types = get_most_specific_types(tuple(instance.types))
        number_of_types = -1
        while number_of_types != self._number_of_inferred_types():
            number_of_types = self._number_of_inferred_types()
            self._infer_types_once(declared_domains, sufficient_domains)
        self.represent_untyped_individuals_by_the_base_class()

    def represent_untyped_individuals_by_the_base_class(self) -> None:
        """
        An individual without any asserted or inferred type is only an owl:Thing; it is represented by an instance of
        the ontology base class. (It is not typed with a class it happens to be named after, e.g. the individual
        ``Engineering`` used as a value of hasCollegeDiscipline is not an instance of the class ``Engineering``.)
        """
        base_class = self.metadata.ontology_base_class
        if base_class is None:
            return
        for instance in self.anonymous_instances.values():
            if not instance.final_sorted_types:
                self._add_inferred_type(instance, base_class)
                self.registry.record_type(
                    instance.uri, base_class, TypeInferredThrough.BASE_CLASS
                )

    def _number_of_inferred_types(self) -> int:
        return sum(len(i.final_sorted_types) for i in self.anonymous_instances.values())

    def _add_inferred_type(self, instance: AnonymousClass, cls: Type) -> None:
        """
        Add an inferred type to an individual, visible to the axioms of the next inference pass.
        """
        instance.final_sorted_types.append(cls)
        instance.add_type(cls)

    def _infer_types_once(
        self,
        declared_domains: Dict[Type[PropertyDescriptor], Tuple[Type, ...]],
        sufficient_domains: Dict[Type[PropertyDescriptor], Tuple[Type, ...]],
    ) -> None:
        """
        One pass of the type inference over all individuals, see :meth:`infer_all_types_for_the_anonymous_instances`.
        """
        for instance in self.anonymous_instances.values():
            descriptors = self.get_descriptors_of_instance(instance)
            for desc in descriptors:
                if desc not in declared_domains:
                    declared_domains[desc] = self.declared_domains(desc)
                    sufficient_domains[desc] = self.domains_with_sufficient_conditions(
                        desc
                    )
                if self.has_declared_domains_and_ranges(desc):
                    for dom in declared_domains[desc]:
                        self._add_domain_type(instance, desc, dom)
                    for range_ in self.declared_ranges(desc):
                        for value in getattr(instance, desc.get_field_name()):
                            self._add_range_type(instance, desc, value, range_)
                else:
                    for dom in declared_domains[desc]:
                        self._update_inferred_types_given_descriptor_domain_and_range(
                            instance, desc, dom
                        )
                for dom in sufficient_domains[desc]:
                    if dom.axiom_python(instance) and not any(
                        issubclass_or_role(t, dom) for t in instance.final_sorted_types
                    ):
                        self._add_inferred_type(instance, dom)
                        self.registry.record_type(
                            instance.uri, dom, TypeInferredThrough.AXIOM, dom
                        )

    @staticmethod
    def has_declared_domains_and_ranges(desc: Type[PropertyDescriptor]) -> bool:
        """
        :return: Whether the generated descriptor lists the rdfs:domain and rdfs:range of its property (models
         generated before this information was emitted do not).
        """
        return "rdfs_domains" in vars(desc)

    def _resolve_class_names(self, names: Iterable[str]) -> Tuple[Type, ...]:
        return tuple(
            self.metadata.class_by_name[name]
            for name in names
            if name in self.metadata.class_by_name
        )

    def declared_ranges(self, desc: Type[PropertyDescriptor]) -> Tuple[Type, ...]:
        """
        :return: The classes declared with rdfs:range for the property of the descriptor.
        """
        return self._resolve_class_names(vars(desc).get("rdfs_ranges", ()))

    def _add_domain_type(self, instance: AnonymousClass, desc: Type, dom: Type) -> None:
        """
        Type an individual with the declared domain of one of its properties (prp-dom).
        """
        if any(issubclass_or_role(t, dom) for t in instance.final_sorted_types):
            return
        self._add_inferred_type(instance, dom)
        first_value = getattr(instance, desc.get_field_name())[0]
        self.registry.record_type(
            instance.uri,
            dom,
            TypeInferredThrough.DOMAIN,
            (instance.uri, desc.__name__, getattr(first_value, "uri", first_value)),
        )

    def _add_range_type(
        self, instance: AnonymousClass, desc: Type, value: AnonymousClass, range_: Type
    ) -> None:
        """
        Type a value with the declared range of the property (prp-rng).
        """
        if value is None or any(
            issubclass_or_role(t, range_) for t in value.final_sorted_types
        ):
            return
        self._add_inferred_type(value, range_)
        self.registry.record_type(
            value.uri,
            range_,
            TypeInferredThrough.RANGE,
            (instance.uri, desc.__name__, value.uri),
        )

    def declared_domains(self, desc: Type[PropertyDescriptor]) -> Tuple[Type, ...]:
        """
        :param desc: A property descriptor class.
        :return: The classes declared with rdfs:domain for the property of the descriptor. For models generated
         without this information, the most general domains of the descriptor (the domains that are not a subclass or
         role of another domain of the descriptor).
        """
        if self.has_declared_domains_and_ranges(desc):
            return self._resolve_class_names(vars(desc)["rdfs_domains"])
        domains = tuple(desc.all_domains[desc])
        return tuple(
            dom
            for dom in domains
            if not any(
                other is not dom and issubclass_or_role(dom, other) for other in domains
            )
        )

    @staticmethod
    def domains_with_sufficient_conditions(
        desc: Type[PropertyDescriptor],
    ) -> Tuple[Type, ...]:
        """
        :param desc: A property descriptor class.
        :return: The domains of the descriptor that declare their own sufficient condition (``axiom_python`` defined
         in the class itself, not inherited).
        """
        return tuple(
            dom for dom in desc.all_domains[desc] if "axiom_python" in vars(dom)
        )

    def keep_most_specific_types_and_sort_from_least_to_most_specific(
        self,
    ) -> None:
        for instance in self.anonymous_instances.values():
            result = get_most_specific_types(tuple(instance.final_sorted_types))
            instance.final_sorted_types = list(
                sort_classes_by_role_aware_inheritance_path_length(
                    tuple(result),
                    common_ancestor=self.metadata.ontology_base_class,
                    classes_to_remove_from_common_ancestor=(
                        Symbol,
                        ABC,
                        object,
                    ),
                )
            )

    def sort_explicit_types_from_most_to_least_specific(
        self,
    ) -> None:
        for uri, instances in self.registry._by_uri.items():
            if len(instances) <= 1:
                continue
            types = tuple(type(instance) for instance in instances)
            sorted_types = list(
                reversed(
                    sort_classes_by_role_aware_inheritance_path_length(
                        types,
                        common_ancestor=self.metadata.ontology_base_class,
                        classes_to_remove_from_common_ancestor=(
                            Symbol,
                            ABC,
                            object,
                        ),
                    )
                )
            )
            sorted_instances = list()
            for st in sorted_types:
                for instance in instances:
                    if type(instance) is st:
                        sorted_instances.append(instance)
                        break
            self.registry._by_uri[uri] = sorted_instances

    @lru_cache
    def get_descriptors_of_instance(
        self, instance: AnonymousClass
    ) -> List[Type[PropertyDescriptor]]:
        non_class_fields = get_non_class_attribute_names_of_instance(instance)
        descriptors = [self.metadata.get_descriptor_base(f) for f in non_class_fields]
        return [d for d in descriptors if d is not None]

    def _update_inferred_types_given_descriptor_domain_and_range(
        self,
        instance: AnonymousClass,
        desc: Type[PropertyDescriptor],
        dom: Type,
        range_: Optional[Type] = None,
        range_inst: Optional[AnonymousClass] = None,
    ):
        values = getattr(instance, desc.get_field_name(), None) or [None]
        if not any(issubclass_or_role(t, dom) for t in instance.final_sorted_types):
            self._add_inferred_type(instance, dom)
            first_value = values[0]
            self.registry.record_type(
                instance.uri,
                dom,
                TypeInferredThrough.DOMAIN,
                (
                    instance.uri,
                    desc.__name__,
                    getattr(first_value, "uri", first_value),
                ),
            )
        if not range_:
            try:
                range_ = desc.get_descriptor_instance_for_domain_type(dom).range
            except ValueError:
                return
        if not range_inst:
            range_instances = getattr(instance, desc.get_field_name())
        else:
            range_instances = [range_inst]
        for range_inst in range_instances:
            if not any(
                issubclass_or_role(t, range_) for t in range_inst.final_sorted_types
            ):
                self._add_inferred_type(range_inst, range_)
                self.registry.record_type(
                    range_inst.uri,
                    range_,
                    TypeInferredThrough.RANGE,
                    (instance.uri, desc.__name__, range_inst.uri),
                )

    def add_inferences_from_transitive_symmetric_relations(self):
        """
        Close every property that is both symmetric and transitive: all individuals in a weakly connected component of
        the relation graph of such a property are related to each other (and to themselves, unless the property is
        irreflexive).

        If the property implies other properties (see :meth:`implies_other_properties`), each entailed fact is added
        as a relation of the symbol graph with the explanation SYMMETRIC_TRANSITIVE_COMPONENT, so the super-property,
        inverse, chain and equivalence rules are applied to it. Otherwise, these rules derive nothing from the facts,
        so the facts are only stored in the attributes of the members and the component is registered once as their
        explanation (see :class:`SymmetricTransitiveComponent`). Transitive chaining is not repeated for these facts,
        the component already closes them.
        """
        PropertyDescriptorRelation.symmetric_transitive_components.clear()
        transitive_symmetric_descriptor_types = [
            d
            for p, d in self.metadata.descriptor_by_name.items()
            if issubclass(d, TransitiveProperty) and issubclass(d, SymmetricProperty)
        ]
        for descriptor_type in transitive_symmetric_descriptor_types:
            reflexive = issubclass(descriptor_type, ReflexiveProperty) or not issubclass(
                descriptor_type, IrreflexiveProperty
            )
            descriptor_induced_subgraph = SymbolGraph().descriptor_subgraph(
                descriptor_type
            )
            wcc = rx.weakly_connected_components(descriptor_induced_subgraph)
            for component_id, comp in enumerate(wcc):
                component = SymmetricTransitiveComponent(
                    descriptor_type,
                    component_id,
                    {
                        member.index: member
                        for member in (
                            descriptor_induced_subgraph[node] for node in comp
                        )
                    },
                    reflexive,
                )
                if self.implies_other_properties(descriptor_type):
                    self.add_component_relations_to_the_graph(component)
                else:
                    self.add_component_facts_to_the_attributes(component)

    @staticmethod
    def implies_other_properties(descriptor_type: Type[PropertyDescriptor]) -> bool:
        """
        :param descriptor_type: A property descriptor class.
        :return: True if a fact of the property entails facts of other properties, that is, if the property has a
         super-property, an inverse other than itself or an equivalent property, or occurs in a property chain.
        """
        has_inverse = (
            issubclass(descriptor_type, HasInverseProperty)
            and descriptor_type.get_inverse() not in (None, descriptor_type)
        )
        has_equivalent = issubclass(
            descriptor_type, HasEquivalentProperties
        ) and bool(descriptor_type.get_equivalent_properties())
        occurs_in_chain = bool(PropertyDescriptor.chain_axioms.get(descriptor_type))
        return bool(
            descriptor_type.super_classes()
            or has_inverse
            or has_equivalent
            or occurs_in_chain
        )

    @staticmethod
    def add_component_relations_to_the_graph(
        component: SymmetricTransitiveComponent,
    ):
        """
        Add every fact entailed by the component as an explained relation of the symbol graph and apply the rules of
        the property to it.
        """
        for source in component.members.values():
            for target in component.members.values():
                if component.relates(source, target):
                    component.relation(
                        source, target
                    ).update_source_and_add_to_graph_and_apply_implications()

    @staticmethod
    def add_component_facts_to_the_attributes(
        component: SymmetricTransitiveComponent,
    ):
        """
        Store every fact entailed by the component in the attribute of its source and register the component as the
        explanation of these facts.
        """
        for source in component.members.values():
            descriptor = component.property_descriptor_class.get_descriptor_instance_for_domain_type(
                source.instance_type
            )
            PropertyDescriptorRelation.symmetric_transitive_components[
                (descriptor.wrapped_field.name, source.index)
            ] = component
            for target in component.members.values():
                if component.relates(source, target):
                    descriptor.update_value(
                        source.instance, target.instance, inferred=True
                    )

    def create_anonymous_instances(self):
        """Creates instances for all anonymous subjects in the graph."""
        for s in self.graph.subjects(RDF.type, OWL.NamedIndividual, unique=True):
            ac = AnonymousClass(s)
            self.anonymous_instances[s] = ac
            for o_class in self.graph.objects(s, RDF.type):
                py_cls = self.metadata.get_python_class(o_class)
                if py_cls:
                    ac.add_type(py_cls)
                    self.registry.record_type(
                        s, py_cls, TypeInferredThrough.ASSERTED, o_class
                    )
        if self.anonymous_instances:
            return
        for s, o_class in self.graph.subject_objects(RDF.type):
            if not isinstance(s, URIRef):
                continue
            if s in self.anonymous_instances:
                continue
            if o_class in [
                OWL.Class,
                RDFS.Class,
                OWL.Ontology,
                OWL.ObjectProperty,
                OWL.DatatypeProperty,
                OWL.FunctionalProperty,
            ]:
                continue
            self.anonymous_instances[s] = AnonymousClass(s)
            py_cls = self.metadata.get_python_class(o_class)
            if py_cls:
                self.anonymous_instances[s].add_type(py_cls)
                self.registry.record_type(
                    s, py_cls, TypeInferredThrough.ASSERTED, o_class
                )

    def assign_all_properties_to_all_anonymous_instances(self):
        """Iterates through all properties of all instances and assigns properties to the instances."""
        for s, instance in self.anonymous_instances.items():
            self._assign_all_properties_to_instance(instance)
        self.add_implied_property_values_to_anonymous_instances()

    def add_implied_property_values_to_anonymous_instances(self):
        """
        Before the types are inferred, add to every individual the values of the properties implied by its asserted
        object property values through super-properties (OWL 2 RL rule prp-spo1), equivalent properties (prp-eqp1/2),
        inverse properties (prp-inv1/2) and symmetry (prp-symp). The domains of these properties and the sufficient
        conditions that use them are then taken into account when the types are inferred (e.g.
        ``isCrazyAbout SubPropertyOf loves`` makes ``Person and (loves some Sports) SubClassOf SportsLover``
        applicable, and ``hasResearchProject SubPropertyOf hasWork`` with ``hasWork`` having the domain Employee).
        """
        closures: Dict[Type[PropertyDescriptor], Tuple[Tuple[str, bool], ...]] = {}
        for subject, instance in self.anonymous_instances.items():
            for predicate, value in self._triples_by_subject[subject]:
                if isinstance(value, Literal):
                    continue
                value_instance = self.anonymous_instances.get(value)
                if value_instance is None:
                    continue
                descriptor = self.metadata.get_descriptor_base(
                    to_snake(local_name(predicate))
                )
                if descriptor is None:
                    continue
                if descriptor not in closures:
                    closures[descriptor] = self._implied_properties(descriptor)
                for field_name, inverted in closures[descriptor]:
                    source, target = (
                        (value_instance, instance) if inverted else (instance, value_instance)
                    )
                    values = getattr(source, field_name, None)
                    if values is None:
                        setattr(source, field_name, [target])
                    elif target not in values:
                        values.append(target)

    @staticmethod
    def _implied_properties(
        descriptor: Type[PropertyDescriptor],
    ) -> Tuple[Tuple[str, bool], ...]:
        """
        :param descriptor: An object property descriptor class.
        :return: The field names of the properties implied by an assertion of ``descriptor`` (excluding itself), each
         with a flag that is True if the implied assertion has subject and object swapped.
        """
        implied = {(descriptor, False)}
        frontier = [(descriptor, False)]
        while frontier:
            current, inverted = frontier.pop()
            neighbours = [(parent, inverted) for parent in current.super_classes()]
            if issubclass(current, HasEquivalentProperties):
                neighbours += [
                    (equivalent, inverted)
                    for equivalent in current.get_equivalent_properties()
                ]
            if issubclass(current, HasInverseProperty) and current.get_inverse():
                neighbours.append((current.get_inverse(), not inverted))
            if issubclass(current, SymmetricProperty):
                neighbours.append((current, not inverted))
            for neighbour in neighbours:
                if neighbour not in implied:
                    implied.add(neighbour)
                    frontier.append(neighbour)
        implied.discard((descriptor, False))
        return tuple(
            (implied_descriptor.get_field_name(), inverted)
            for implied_descriptor, inverted in implied
        )

    def _assign_all_properties_to_instance(self, instance: AnonymousClass):
        """Iterates through all properties of all instances and assigns properties to the instances."""
        for p, o in self._triples_by_subject[instance.uri]:
            if p in [RDF.type, RDFS.subClassOf, OWL.equivalentClass, OWL.disjointWith]:
                continue
            field_name = to_snake(local_name(p))
            obj = o
            if isinstance(obj, Literal):
                if self._assign_data_property(
                    [instance], field_name, obj, must_have_attr=False
                ):
                    self.literals[instance.uri][field_name] = obj
            else:
                obj_inst = self.anonymous_instances.get(obj)
                if not hasattr(instance, field_name):
                    setattr(instance, field_name, [obj_inst])
                else:
                    getattr(instance, field_name).append(obj_inst)

    def create_explicit_instances_from_inferred_types_of_anonymous_instances(self):
        """Creates instances for all subjects with an explicit rdf:type in the graph."""
        so_iterator = (
            (s, o_class)
            for s, ai in self.anonymous_instances.items()
            for o_class in ai.final_sorted_types
        )
        for s, py_cls in so_iterator:
            existing_roles = self.registry.resolve(s)
            existing_roles = existing_roles or []
            role_types = list(map(type, existing_roles)) + [py_cls]
            # if any(
            #     "Woman" == t.__name__
            #     for t in self.anonymous_instances[URIRef(s)].final_sorted_types
            # ) and any(
            #     r.__class__.__name__ in ["Chair", "Professor", "FullProfessor"]
            #     for r in self.anonymous_instances[URIRef(s)].final_sorted_types
            # ):
            #     import pdbpp
            #
            #     pdbpp.set_trace()
            kwargs = self._get_common_role_taker_kwargs(existing_roles, py_cls)
            self.registry.get_or_create_for(s, py_cls, self.symbol_graph, **kwargs)

    def _get_common_role_taker_kwargs(
        self, existing_roles: Optional[List[Any]], target_cls: Type
    ) -> Dict[str, Any]:
        """Finds common role-taker associations between existing roles and a target class.

        Args:
            existing_roles: List of already created roles for the same URI.
            target_cls: The class of the new role to be created.

        Returns:
            A dictionary of keyword arguments for the target class constructor.
        """
        kwargs = {}
        if not existing_roles:
            return kwargs
        for er in existing_roles:
            (
                assoc1,
                assoc2,
            ) = self.symbol_graph.class_diagram.get_common_role_taker_associations(
                type(er), target_cls
            )
            if not assoc1 or not assoc2 or assoc2.field.public_name in kwargs:
                continue
            kwargs[assoc2.field.public_name] = getattr(er, assoc1.field.public_name)
        return kwargs

    def assign_all_properties_to_explict_types_and_apply_on_time_forward_chaining(self):
        """Iterates through all triples in the graph and assigns properties to instances."""
        skip_ps = {
            RDF.type,
            OWL.disjointWith,
            RDFS.subClassOf,
            OWL.equivalentClass,
            OWL.Class,
        }
        filtered_triples = [
            (s, p, o)
            for s, p_o in self._triples_by_subject.items()
            for p, o in p_o
            if p not in skip_ps and self._get_all_instances_of_uri(s)
        ]
        total = len(filtered_triples)

        max_time = 0

        with tqdm(total=total, desc="Assigning properties") as pbar:
            for s, p, o in filtered_triples:
                subject_roles = self._get_all_instances_of_uri(s)
                if not subject_roles:
                    continue
                predicate_name = to_snake(local_name(p))
                start = time.time()
                self._assign_property(subject_roles, predicate_name, o)
                duration = time.time() - start

                if duration > max_time:
                    max_time = duration
                    pbar.set_postfix(slowest=f"{predicate_name} ({max_time:.4f}s)")

                pbar.update(1)

    def _assign_property(
        self,
        subj_roles: List[Symbol],
        field_name: str,
        obj_uri: Union[URIRef, Literal],
    ):
        """Assigns a property to an instance based on the predicate name and object URI. It handles both data and
         object properties.
        Args:
            subj_roles: The subject instances.
            field_name: name of the field to assign the property to.
            obj_uri: The RDF node of the object.
        """
        if isinstance(obj_uri, Literal):
            self._assign_data_property(subj_roles, field_name, obj_uri)
        else:
            self._assign_object_property(subj_roles, field_name, obj_uri)

    def _get_all_instances_of_uri(self, subject_uri: URIRef) -> Optional[List[Any]]:
        """Resolves or ensures instances for a given subject URI.

        Args:
            subject_uri: The URIRef of the subject.

        Returns:
            A list of subject roles if found or created, otherwise None.
        """
        return self.registry.resolve(subject_uri)

    def _get_role_taker_val(self, subj: Any, subj_cls: Type) -> Optional[Any]:
        """Retrieves the role-taker instance for a given subject, if it exists.

        Args:
            subj: The subject instance.
            subj_cls: The class of the subject instance.

        Returns:
            The role-taker instance or None.
        """
        role_taker_association = (
            self.symbol_graph.class_diagram.get_role_taker_associations_of_cls(subj_cls)
        )
        return (
            getattr(subj, role_taker_association.field.public_name, None)
            if role_taker_association
            else None
        )

    def _assign_data_property(
        self,
        subj_roles: List[Symbol],
        field_name: Optional[str],
        literal: Literal,
        must_have_attr: bool = True,
    ) -> bool:
        """Assigns a data property to an instance, coercing the literal value if possible.

        Args:
            subj_roles: The subject instances.
            field_name: The determined field name on the subject.
            literal: The RDF literal value.
            must_have_attr: Whether the subject must have the attribute before assigning.
        Returns:
            True if the property was assigned successfully, False otherwise.
        """
        if not field_name:
            return False
        subj = next(
            (s for s in subj_roles if not must_have_attr or hasattr(s, field_name)),
            subj_roles[0],
        )
        if not must_have_attr or hasattr(subj, field_name):
            # Coerce to field annotated type
            try:
                ftypes = {f.name: f.type for f in fields(type(subj))}
            except TypeError:
                ftypes = {}
            coerced = self._coerce_literal(literal, ftypes.get(field_name))
            setattr(subj, field_name, coerced)
            return True
        return False

    @lru_cache
    def best_fit_object_role(
        self, field_name: str, obj_roles: Tuple[Any]
    ) -> Optional[Type]:
        """Finds the best fitting object role type for a given object type.

        Args:
            descriptor_base: The base PropertyDescriptor class.
            obj_type: The type of the object instance.

        Returns:
            The best fitting object role type if found, otherwise None.
        """
        descriptor_base = self.metadata.get_descriptor_base(field_name)
        descriptor_ranges = tuple(PropertyDescriptor.all_ranges[descriptor_base])
        obj = next(
            (
                obj_role
                for obj_role in obj_roles
                if issubclass_or_role(type(obj_role), descriptor_ranges)
            ),
            None,
        )
        return obj

    def _assign_object_property(
        self,
        subj_roles: List[Symbol],
        field_name: str,
        obj_node: Union[URIRef, Literal],
    ):
        """Assigns an object property by resolving the object node and finding the correct attribute.

        Args:
            subj_roles: The subject instances.
            field_name: The determined field name on the subject.
            obj_node: The RDF node of the object.
        """
        subj = None
        obj_roles = (
            self._get_all_instances_of_uri(obj_node)
            if isinstance(obj_node, URIRef)
            else None
        )
        if len(obj_roles) > 1:
            obj = self.best_fit_object_role(field_name, tuple(obj_roles))
        else:
            obj = obj_roles[0] if obj_roles else None
        if obj is None:
            raise ValueError(f"Could not find object for {subj_roles}.{field_name}")
        descriptor_base = self.metadata.get_descriptor_base(field_name)
        declaration = (
            PropertyDescriptorRelation.declaring_object(
                subj_roles[0], descriptor_base, obj
            )
            if descriptor_base is not None
            else None
        )
        if declaration is not None:
            subj = declaration[0]
        else:
            subject_roles_with_field_name = [
                s for s in subj_roles if hasattr(s, field_name)
            ]
            if subject_roles_with_field_name:
                subj = subject_roles_with_field_name[0]
        matched_obj = None
        # Look for the super, and the inverse properties of the current property,
        # and try to assign their values as well. So call self._assign_object_property()
        if subj and field_name and hasattr(subj, field_name):
            obj = matched_obj or obj
            if self._assign_to_attribute(subj, field_name, obj):
                return
        raise ValueError(f"Could not find {subj_roles}.{field_name} = {obj}")

    def _assign_to_attribute(self, target: Any, attr_name: str, value: Any) -> bool:
        """Assigns a value to an attribute, or adds to it if it's a collection.

        Args:
            target: The object to assign the value to.
            attr_name: The name of the attribute.
            value: The value to assign.

        Returns:
            True if assigned, False otherwise.
        """
        if value is None:
            return False

        attr_val = getattr(target, attr_name, None)
        if isinstance(attr_val, set):
            # logger.info(
            #     f"[OwlLoader] Assigning property {attr_name} to {target.uri} with object {value.uri}"
            # )
            attr_val.add(value)
        elif isinstance(attr_val, list):
            attr_val.append(value)
        else:
            setattr(target, attr_name, value)
        return True

    @staticmethod
    def _coerce_literal(val: Literal, target_type: Optional[Type] = None) -> Any:
        """Coerces an RDF literal to a Python type.

        Args:
            val: The RDF literal.
            target_type: The target Python type.

        Returns:
            The coerced Python value.
        """
        if target_type is None:
            return val.toPython()
        try:
            # Unwrap Optional[T]
            origin = getattr(target_type, "__origin__", None)
            if origin is Union:
                args = [
                    a
                    for a in getattr(target_type, "__args__", ())
                    if a is not type(None)
                ]  # noqa: E721
                if args:
                    target_type = args[0]
            if target_type in (str, int, float, bool):
                return target_type(val.toPython())
        except Exception:
            pass
        return val.toPython()

    @staticmethod
    def get_and_construct_role_taker(
        registry, cls_: Type, uri_ref: URIRef, symbol_graph: SymbolGraph, **kwargs
    ) -> Tuple[Optional[Association], Optional[Symbol]]:
        """Recursively finds or constructs role-takers for a given class.

        Args:
            cls_: The target class.
            uri_ref: The URI of the instance.
            symbol_graph: The symbol graph for lookups.
            **kwargs: Additional arguments for constructor.

        Returns:
            A tuple of (Association, RoleTakerInstance) if found/created, else (None, None).
        """
        if not issubclass(cls_, Role):
            return None, None

        role_taker_cls = cls_.get_role_taker_type()
        role_taker_field = cls_.role_taker_field()
        if role_taker_field.name in kwargs:
            return None, None

        role_taker = None
        try:
            registry_instances = registry.resolve(uri_ref)
            if registry_instances:
                role_taker = next(
                    (
                        inst
                        for inst in registry_instances
                        if isinstance(inst, role_taker_cls)
                    ),
                    None,
                )
        except AttributeError:
            raise
        if role_taker:
            return role_taker_field, role_taker

        (
            inner_role_taker_field,
            inner_role_taker,
        ) = OwlLoader.get_and_construct_role_taker(
            registry, role_taker_cls, uri_ref, symbol_graph
        )
        if inner_role_taker_field:
            kwargs[inner_role_taker_field.name] = inner_role_taker
        role_taker = role_taker_cls(**kwargs)
        role_taker.uri = str(uri_ref)

        return role_taker_field, role_taker

    @staticmethod
    def create_symbol_graph(
        model_modules: Iterable[Union[str, ModuleType]],
    ) -> SymbolGraph:
        """Creates and initializes a SymbolGraph from model modules.

        Args:
            model_modules: Iterable of modules or module names.

        Returns:
            The initialized SymbolGraph.
        """
        modules = [
            (__import__(m, fromlist=["*"]) if isinstance(m, str) else m)
            for m in model_modules
        ]

        SymbolGraph().clear()
        classes = set()
        for model_module in modules:
            classes.update(classes_of_module(model_module))
        class_diagram = ClassDiagram(
            list(classes), introspector=DescriptorAwareIntrospector()
        )
        return SymbolGraph(_class_diagram=class_diagram)

    @staticmethod
    def load_instances(
        owl_path: str,
        base_module: Union[str, ModuleType],
        classes_module: Union[str, ModuleType],
        properties_module: Union[str, ModuleType],
        symbol_graph: Optional[SymbolGraph] = None,
        registry: Optional[OwlInstancesRegistry] = None,
    ) -> OwlInstancesRegistry:
        """Loads OWL instances into a registry.

        Args:
            owl_path: Path to the OWL file.
            base_module: Module containing base classes.
            classes_module: Module containing model classes.
            properties_module: Module containing property descriptors.
            symbol_graph: Optional existing SymbolGraph.
            registry: Optional existing registry.

        Returns:
            The populated OwlInstancesRegistry.
        """
        model_modules = [base_module, classes_module, properties_module]
        if not symbol_graph:
            symbol_graph = OwlLoader.create_symbol_graph(model_modules)

        # Ensure model_modules are modules, not just names, for OwlLoader
        modules = [
            (__import__(m, fromlist=["*"]) if isinstance(m, str) else m)
            for m in model_modules
        ]

        if registry is None:
            registry = OwlInstancesRegistry()

        loader = OwlLoader(owl_path, modules, symbol_graph, registry)
        return loader.load()

    @staticmethod
    def load_multi_file_instances(
        owl_paths: Iterable[str],
        base_module: Union[str, ModuleType],
        classes_module: Union[str, ModuleType],
        properties_module: Union[str, ModuleType],
    ) -> OwlInstancesRegistry:
        """Loads instances from multiple OWL files into a single registry.

        Args:
            owl_paths: Iterable of OWL file paths.
            base_module: Module containing base classes.
            classes_module: Module containing model classes.
            properties_module: Module containing property descriptors.

        Returns:
            The populated OwlInstancesRegistry.
        """
        combined_registry = OwlInstancesRegistry()
        model_modules = [base_module, classes_module, properties_module]
        symbol_graph = OwlLoader.create_symbol_graph(model_modules)

        for path in owl_paths:
            OwlLoader.load_instances(
                path,
                base_module,
                classes_module,
                properties_module,
                symbol_graph=symbol_graph,
                registry=combined_registry,
            )
        return combined_registry

    def __hash__(self):
        return hash(id(self))

    def __str__(self):
        return f"OwlLoader(owl_path={self.owl_path})"

    def __repr__(self):
        return self.__str__()
