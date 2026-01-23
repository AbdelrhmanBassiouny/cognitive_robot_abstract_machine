from __future__ import annotations

import logging
import os.path
import time
from abc import ABC
from collections import defaultdict
from dataclasses import fields, is_dataclass, dataclass, field
from functools import lru_cache
from types import ModuleType

import rdflib
import rustworkx as rx
from rdflib import RDF, URIRef, Literal, OWL, RDFS
from ripple_down_rules import RDRDecorator
from tqdm import tqdm
from typing_extensions import Any, Dict, Iterable, List, Optional, Tuple, Type, Union, ClassVar

from .ontology_info import AnonymousClass
from ..property_descriptor.attribute_introspector import (
    DescriptorAwareIntrospector,
)
from ..property_descriptor.mixins import (
    IsBaseClass,
    TransitiveProperty,
    SymmetricProperty,
    IrreflexiveProperty,
    ReflexiveProperty,
)
from ..property_descriptor.property_descriptor import PropertyDescriptor
from ..utils import (
    get_non_class_attribute_names_of_instance,
    get_most_specific_types,
    NamingRegistry,
)
from ...class_diagrams.class_diagram import Association, ClassDiagram
from ...class_diagrams.utils import (
    issubclass_or_role,
    Role,
    sort_classes_by_role_aware_inheritance_path_length,
)
from ...entity_query_language.mixins import HasPythonAxiom
from ...entity_query_language.predicate import Symbol
from ...entity_query_language.symbol_graph import SymbolGraph
from ...class_diagrams.utils import classes_of_module

logger = logging.Logger("owl_loader")
logger.setLevel(logging.DEBUG)

# Handler
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)  # <-- this filters out DEBUG messages
logger.addHandler(handler)


class OwlInstancesRegistry:
    """Registry of instances created from an OWL/RDF instances file.

    Provides access to instances per Python model class and tracks URIRef to instance mapping.
    """

    def __init__(self, symbol_graph: Optional[SymbolGraph] = None) -> None:
        self._by_uri: Dict[URIRef, List[Any]] = defaultdict(list)

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
        self.assign_all_properties_to_explict_types_and_apply_on_time_forward_chaining()
        self.add_inferences_from_transitive_symmetric_relations()
        return self.registry

    def infer_all_types_for_the_anonymous_instances(self):
        for instance in self.anonymous_instances.values():
            instance.final_sorted_types = get_most_specific_types(tuple(instance.types))
        for instance in self.anonymous_instances.values():
            descriptors = self.get_descriptors_of_instance(instance)
            if len(descriptors) == 0:
                py_cls = self.metadata.get_python_class(
                    NamingRegistry.uri_to_python_name(instance.uri)
                )
                if py_cls:
                    if not any(
                            issubclass_or_role(t, py_cls)
                            for t in instance.final_sorted_types
                    ):
                        instance.final_sorted_types.append(py_cls)
            for desc in descriptors:
                domains = desc.all_domains[desc]
                if len(domains) == 1:
                    self._update_inferred_types_given_descriptor_domain_and_range(
                        instance, desc, list(domains)[0]
                    )
                    continue
                domains = list(
                    reversed(
                        sort_classes_by_role_aware_inheritance_path_length(
                            tuple(domains), with_levels=True
                        )
                    )
                )
                found_level = -1
                for dom, level in domains:
                    if level < found_level:
                        break
                    if isinstance(dom, HasPythonAxiom) and dom.check_axiom_python(instance):
                        self._update_inferred_types_given_descriptor_domain_and_range(
                            instance, desc, dom
                        )
                        found_level = level
                        continue
                    try:
                        range_ = desc.get_descriptor_instance_for_domain_type(dom).range
                    except ValueError:
                        continue
                    for range_inst in getattr(instance, desc.get_field_name()):
                        if any(
                                issubclass_or_role(it, range_)
                                for it in range_inst.final_sorted_types
                        ):
                            if not any(
                                    issubclass_or_role(t, dom)
                                    for t in instance.final_sorted_types
                            ) and not isinstance(dom, HasPythonAxiom):
                                instance.final_sorted_types.append(dom)
                                found_level = level
                            break

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
        if not any(issubclass_or_role(t, dom) for t in instance.final_sorted_types):
            instance.final_sorted_types.append(dom)
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
                range_inst.final_sorted_types.append(range_)

    def add_inferences_from_transitive_symmetric_relations(self):
        transitive_symmetric_descriptor_types = [
            d
            for p, d in self.metadata.descriptor_by_name.items()
            if issubclass(d, TransitiveProperty) and issubclass(d, SymmetricProperty)
        ]
        for descriptor_type in transitive_symmetric_descriptor_types:
            descriptor_induced_subgraph = SymbolGraph().descriptor_subgraph(
                descriptor_type
            )
            wcc = rx.weakly_connected_components(descriptor_induced_subgraph)
            for comp in wcc:
                comp = list(comp)
                for i, node in enumerate(comp):
                    node_instance = descriptor_induced_subgraph[node]
                    descriptor_instance: PropertyDescriptor = (
                        descriptor_type.get_descriptor_instance_for_domain_type(
                            node_instance.instance_type
                        )
                    )
                    if issubclass(descriptor_type, ReflexiveProperty) or not issubclass(
                            descriptor_type, IrreflexiveProperty
                    ):
                        descriptor_instance.update_value(
                            node_instance.instance,
                            node_instance.instance,
                            inferred=True,
                        )
                    for node2 in comp[i + 1:]:
                        node2_instance = descriptor_induced_subgraph[node2]
                        descriptor_instance.update_value(
                            node_instance.instance,
                            node2_instance.instance,
                            inferred=True,
                        )
                        descriptor_instance.update_value(
                            node2_instance.instance,
                            node_instance.instance,
                            inferred=True,
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

    def assign_all_properties_to_all_anonymous_instances(self):
        """Iterates through all properties of all instances and assigns properties to the instances."""
        for s, instance in self.anonymous_instances.items():
            self._assign_all_properties_to_instance(instance)

    def _assign_all_properties_to_instance(self, instance: AnonymousClass):
        """Iterates through all properties of all instances and assigns properties to the instances."""
        for p, o in self._triples_by_subject[instance.uri]:
            if p in [
                RDF.type,
                RDFS.subClassOf,
                OWL.equivalentClass,
                OWL.disjointWith,
                OWL.disjointUnionOf,
                OWL.sameAs,
            ]:
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
            OWL.disjointUnionOf,
            OWL.sameAs,
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
        if len(subj_roles) == 1:
            subj = subj_roles[0]
        else:
            try:
                subj = [
                    s
                    for s in subj_roles
                    if not must_have_attr or hasattr(s, field_name)
                ][0]
            except IndexError:
                import pdbpp

                pdbpp.set_trace()
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
        if obj_roles and len(obj_roles) > 1:
            obj = self.best_fit_object_role(field_name, tuple(obj_roles))
        else:
            obj = obj_roles[0] if obj_roles else None
        if obj is None:
            raise ValueError(f"Could not find object for {subj_roles}.{field_name}")
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
