from __future__ import annotations

from copy import copy
import os
import weakref
from collections import defaultdict, deque
from dataclasses import dataclass, field, InitVar
from functools import lru_cache, cached_property

from krrood.ontomatic.property_descriptor.mixins import SymmetricProperty
from line_profiler import profile
from rustworkx import PyDiGraph
from rustworkx.rustworkx import NoEdgeBetweenNodes
from typing_extensions import (
    TYPE_CHECKING,
    Any,
    Iterable,
    Optional,
    List,
    Set,
    Type,
    Dict,
    DefaultDict,
    Callable,
    Tuple,
)

from .. import logger
from ..class_diagrams import ClassDiagram
from ..class_diagrams.wrapped_field import WrappedField
from ..ontomatic.property_descriptor.attribute_introspector import (
    DescriptorAwareIntrospector,
)
from ..ontomatic.property_descriptor.mixins import RoleForMixin
from ..singleton import SingletonMeta
from ..utils import recursive_subclasses, T

if TYPE_CHECKING:
    from .predicate import Symbol
    from ..ontomatic.property_descriptor.property_descriptor import (
        PropertyDescriptor,
    )


@dataclass(eq=False)
class PredicateClassRelation:
    """
    Edge data representing a predicate-based relation between two wrapped instances.

    The relation carries a flag indicating whether it was inferred or added directly.
    """

    source: WrappedInstance
    """
    The source of the predicate
    """
    target: WrappedInstance
    """
    The target of the predicate
    """
    wrapped_field: WrappedField
    """
    The dataclass field in the source class that represents this relation with the target.
    """
    inferred: bool = field(default=False, compare=False, hash=False)
    """
    Whether it was inferred or not.
    """

    def __post_init__(self):
        self.source = SymbolGraph().ensure_wrapped_instance(self.source)
        self.target = SymbolGraph().ensure_wrapped_instance(self.target)

    @profile
    def add_to_graph(self) -> bool:
        """
        Add the relation to the graph.

        :return: True if the relation was newly added, False if it already existed.
        """
        return SymbolGraph().add_relation(self)

    @profile
    def add_to_graph_and_apply_implications(self):
        """
        Add this relation to the graph and apply all implications of this relation.
        """
        SymbolGraph().apply_implications(self)

    def infer_and_apply_implications(self):
        """
        Infer all implications of adding this relation.
        """
        pass

    def __str__(self):
        """Return the predicate type name for labeling the edge."""
        return self.__class__.__name__

    def __repr__(self):
        return str(self)

    @property
    def color(self) -> str:
        return "red" if self.inferred else "black"

    def __hash__(self):
        return hash(
            (
                self.source.index,
                self.target.index,
                self.wrapped_field.public_name,
            )
        )

    def __eq__(self, other):
        if not isinstance(other, PredicateClassRelation):
            return False
        return (
            self.source.index == other.source.index
            and self.target.index == other.target.index
            and self.wrapped_field.public_name == other.wrapped_field.public_name
        )


@dataclass
class WrappedInstance:
    """
    A node wrapper around a concrete Symbol instance used in the instance graph.
    """

    instance: InitVar[Symbol]
    """
    The instance to wrap. Only passed as initialization variable.
    """

    instance_reference: weakref.ReferenceType[Symbol] = field(init=False, default=None)
    """
    A weak reference to the symbol instance this wraps.
    """

    index: Optional[int] = field(init=False, default=None)
    """
    Index in the instance graph of the symbol graph that manages this object.
    """

    symbol_graph: Optional[SymbolGraph] = field(
        init=False, hash=False, default=None, repr=False
    )
    """
    The symbol graph that manages this object.
    """

    inferred: bool = False
    """
    Rather is instance was inferred or constructed.
    """

    instance_type: Type[Symbol] = field(init=False, default=None)
    """
    The type of the instance.
    This is needed to clean it up from the cache after the instance reference died.
    """

    def __post_init__(self, instance: Symbol):
        self.instance_reference = weakref.ref(instance)
        self.instance_type = type(instance)

    @cached_property
    def roles(self) -> Tuple[WrappedInstance, ...]:
        """
        :return: All roles that point to this instance.
        """
        return self.symbol_graph.get_roles_for_instance(self)

    @property
    def instance(self) -> Optional[Symbol]:
        """
        :return: The symbol that is referenced to. Can return None if this symbol is garbage collected already.
        """
        return self.instance_reference()

    @property
    def name(self):
        """Return a unique display name composed of class name and node index."""
        return self.instance.__class__.__name__ + str(self.index)

    @property
    def color(self) -> str:
        return "red" if self.inferred else "black"

    def __eq__(self, other):
        return (
            self.instance == other.instance
            if self.instance is not None and other.instance is not None
            else False
        )

    def __hash__(self):
        return id(self.instance)


@dataclass(eq=False)
class SymbolGraph(metaclass=SingletonMeta):
    """
    A singleton combination of a class and instance diagram.
    This class tracks the life cycles `Symbol` instance created in the python process.
    Furthermore, relations between instances are also tracked.

    Relations are represented as edges where each edge has a relation object attached to it. The relation object
    contains also the Predicate object that represents the relation.

    The construction of this object will do nothing if a singleton instance of this already exists.
    Make sure to call `clear()` before constructing this object if you want a new one.
    """

    _class_diagram: ClassDiagram = field(default=None)
    """
    The class diagram of all registered classes.
    """

    _instance_graph: PyDiGraph[WrappedInstance, PredicateClassRelation] = field(
        default_factory=PyDiGraph, init=False
    )
    """
    A directed graph that stores all instances of `Symbol` and how they relate to each other.
    """

    _instance_index: Dict[int, WrappedInstance] = field(
        default_factory=dict, init=False, repr=False
    )
    """
    Dictionary that maps the ids of objects to wrapped instances.
    Used for faster access when only the WrappedInstance.instance is available.
    """

    _class_to_wrapped_instances: DefaultDict[Type, List[WrappedInstance]] = field(
        init=False, default_factory=lambda: defaultdict(list)
    )
    """
    A dictionary that sorts the wrapped instances by the type inside them.
    This enables quick behavior similar to selecting everything from an entire table in SQL.
    """

    _relation_index: DefaultDict[str, DefaultDict[int, Set[PredicateClassRelation]]] = (
        field(init=False, default_factory=lambda: defaultdict(lambda: defaultdict(set)))
    )

    _relation_index_incoming: DefaultDict[
        str, DefaultDict[int, Set[PredicateClassRelation]]
    ] = field(init=False, default_factory=lambda: defaultdict(lambda: defaultdict(set)))

    _inference_queue: deque[PredicateClassRelation] = field(
        init=False, default_factory=deque, repr=False
    )
    """
    A queue of relations that need to be added to the graph and their implications applied.
    """

    _is_inferring: bool = field(init=False, default=False, repr=False)
    """
    A flag that indicates whether the graph is currently applying implications.
    """

    @profile
    def apply_implications(self, relation: PredicateClassRelation):
        """
        Add the given relation to the inference queue and apply all implications in a breadth-first manner.

        :param relation: The relation to apply the implications for.
        """
        if not relation.add_to_graph():
            return

        self._inference_queue.append(relation)
        if self._is_inferring:
            return

        self._is_inferring = True
        try:
            while len(self._inference_queue) > 0:
                relation_to_process = self._inference_queue.popleft()
                relation_to_process.infer_and_apply_implications()
        finally:
            self._is_inferring = False

    def __post_init__(self):
        if self._class_diagram is None:
            # fetch all symbols and construct the graph
            from .predicate import Symbol

            self._class_diagram = ClassDiagram(
                list(recursive_subclasses(Symbol)),
                introspector=DescriptorAwareIntrospector(),
            )

    def descriptor_subgraph(
        self, descriptor_type: Type[PropertyDescriptor]
    ) -> PyDiGraph:
        """
        Get a subgraph of the instance graph containing only relations of the have a property
        descriptor of the given type.

        :param descriptor_type: The type of the descriptor to filter for.
        :return: A subgraph containing only relations of the given type.
        """
        subgraph = self._instance_graph.edge_subgraph(
            [
                (e.source.index, e.target.index)
                for e in self.relations()
                if isinstance(e.wrapped_field.property_descriptor, descriptor_type)
            ]
        )
        return subgraph

    @property
    def class_diagram(self) -> ClassDiagram:
        return self._class_diagram

    @lru_cache(maxsize=None)
    def get_roles_for_instance(self, instance: Any) -> Tuple[WrappedInstance, ...]:
        condition = lambda edge: isinstance(
            edge, PredicateClassRelation
        ) and isinstance(edge.wrapped_field.property_descriptor, RoleForMixin)
        roles = [
            relation.source
            for relation in self.get_incoming_relations_with_condition(
                self.get_wrapped_instance(instance), condition
            )
        ]
        return tuple(roles)

    def add_node(self, wrapped_instance: WrappedInstance):
        """
        Add a wrapped instance to the cache.

        :param wrapped_instance: The instance to add.
        """
        wrapped_instance.index = self._instance_graph.add_node(wrapped_instance)
        wrapped_instance.symbol_graph = self
        self._instance_index[id(wrapped_instance.instance)] = wrapped_instance
        self._class_to_wrapped_instances[wrapped_instance.instance_type].append(
            wrapped_instance
        )

    def remove_node(self, wrapped_instance: WrappedInstance):
        """
        Remove a wrapped instance from the cache.

        :param wrapped_instance: The instance to remove.
        """
        self._instance_index.pop(id(wrapped_instance.instance), None)
        self._class_to_wrapped_instances[wrapped_instance.instance_type].remove(
            wrapped_instance
        )
        self._instance_graph.remove_node(wrapped_instance.index)

    def remove_dead_instances(self):
        for node in self._instance_graph.nodes():
            if node.instance is None:
                self.remove_node(node)

    def get_instances_of_type(self, type_: Type[Symbol]) -> Iterable[Symbol]:
        """
        Get all wrapped instances of the given type and all its subclasses.

        :param type_: The symbol type to look for
        :return: All wrapped instances that refer to an instance of the given type.
        """
        yield from (
            instance.instance
            for cls in [type_] + recursive_subclasses(type_)
            for instance in list(self._class_to_wrapped_instances[cls])
        )

    def get_wrapped_instance(self, instance: Any) -> Optional[WrappedInstance]:
        if isinstance(instance, WrappedInstance):
            return instance
        return self._instance_index.get(id(instance), None)

    def ensure_wrapped_instance(self, instance: Any) -> WrappedInstance:
        """
        Ensures that the given instance is wrapped into a `WrappedInstance`. If the
        instance is not already wrapped, creates a new `WrappedInstance` object and
        adds it as a node. Returns the wrapped instance.

        :param instance: The object to be checked and wrapped if necessary.:
        :return: WrappedInstance: The wrapped object.
        """
        wrapped_instance = self.get_wrapped_instance(instance)
        if wrapped_instance is None:
            wrapped_instance = WrappedInstance(instance)
            self.add_node(wrapped_instance)
        return wrapped_instance

    def clear(self) -> None:
        SingletonMeta.clear_instance(type(self))
        self._class_diagram.clear()

    # Adapters to align with ORM alternative mapping expectations
    def add_instance(self, wrapped_instance: WrappedInstance) -> None:
        """Add a wrapped instance to the graph.

        This is an adapter that delegates to add_node to keep API compatibility with
        SymbolGraphMapping.create_from_dao.
        """
        self.add_node(wrapped_instance)

    _fields_by_descriptor_class: DefaultDict[Type, List[WrappedField]] = field(
        init=False, default_factory=lambda: defaultdict(list)
    )
    """
    A mapping from property descriptor class to the wrapped fields that use it.
    """

    @profile
    def add_relation(self, relation: PredicateClassRelation) -> bool:
        """Add a relation edge to the instance graph."""
        if self.relation_exists(relation):
            return False

        self._instance_graph.add_edge(
            relation.source.index, relation.target.index, relation
        )
        self._relation_index[relation.wrapped_field.name][relation.source.index].add(
            relation
        )
        self._relation_index_incoming[relation.wrapped_field.name][
            relation.target.index
        ].add(relation)

        descriptor_class = type(relation.wrapped_field.property_descriptor)
        if (
            relation.wrapped_field
            not in self._fields_by_descriptor_class[descriptor_class]
        ):
            self._fields_by_descriptor_class[descriptor_class].append(
                relation.wrapped_field
            )

        return True

    def relation_exists(self, relation: PredicateClassRelation) -> bool:
        return relation in self._relation_index.get(
            relation.wrapped_field.name, {}
        ).get(relation.source.index, set())

    def relations(self) -> Iterable[PredicateClassRelation]:
        yield from self._instance_graph.edges()

    @property
    def wrapped_instances(self) -> List[WrappedInstance]:
        return self._instance_graph.nodes()

    def get_incoming_relations_with_type(
        self,
        wrapped_instance: WrappedInstance,
        relation_type: Type[PredicateClassRelation],
    ) -> Iterable[PredicateClassRelation]:
        """
        Get all relations with the given type that are incoming to the given wrapped instance.

        :param wrapped_instance: The wrapped instance to get the relations from.
        :param relation_type: The type of the relation to filter for.
        """
        yield from self.get_incoming_relations_with_condition(
            wrapped_instance, lambda edge: isinstance(edge, relation_type)
        )

    def get_incoming_relations_with_condition(
        self,
        wrapped_instance: WrappedInstance,
        edge_condition: Callable[[PredicateClassRelation], bool],
    ) -> Iterable[PredicateClassRelation]:
        """
        Get all relations with the given condition that are incoming to the given wrapped instance.

        :param wrapped_instance: The wrapped instance to get the relations from.
        :param edge_condition: The condition to filter for.
        """
        yield from filter(edge_condition, self.get_incoming_relations(wrapped_instance))

    def get_incoming_relations(
        self,
        wrapped_instance: WrappedInstance,
    ) -> Iterable[PredicateClassRelation]:
        """
        Get all relations incoming to the given wrapped instance.

        :param wrapped_instance: The wrapped instance to get the relations from.
        """
        wrapped_instance = self.get_wrapped_instance(wrapped_instance)
        if not wrapped_instance:
            return
        yield from (
            edge for _, _, edge in self._instance_graph.in_edges(wrapped_instance.index)
        )

    def get_outgoing_relations_with_type(
        self,
        wrapped_instance: WrappedInstance,
        relation_type: Type[PredicateClassRelation],
    ) -> Iterable[PredicateClassRelation]:
        """
        Get all relations with the given type that are outgoing from the given wrapped instance.

        :param wrapped_instance: The wrapped instance to get the relations from.
        :param relation_type: The type of the relation to filter for.
        """
        yield from self.get_outgoing_relations_with_condition(
            wrapped_instance, lambda edge: isinstance(edge, relation_type)
        )

    def get_outgoing_relations_with_condition(
        self,
        wrapped_instance: WrappedInstance,
        edge_condition: Callable[[PredicateClassRelation], bool],
    ) -> Iterable[PredicateClassRelation]:
        """
        Get all relations with the given condition that are outgoing from the given wrapped instance.

        :param wrapped_instance: The wrapped instance to get the relations from.
        :param edge_condition: The condition to filter for.
        """
        yield from filter(edge_condition, self.get_outgoing_relations(wrapped_instance))

    def get_outgoing_relations(
        self,
        wrapped_instance: WrappedInstance,
    ) -> Iterable[PredicateClassRelation]:
        """
        Get all relations outgoing from the given wrapped instance.

        :param wrapped_instance: The wrapped instance to get the relations from.
        """
        wrapped_instance = self.get_wrapped_instance(wrapped_instance)
        if not wrapped_instance:
            return
        yield from (
            edge
            for _, _, edge in self._instance_graph.out_edges(wrapped_instance.index)
        )

    def get_outgoing_relations_for_wrapped_field(
        self, wrapped_instance: WrappedInstance, wrapped_field: WrappedField
    ) -> Iterable[PredicateClassRelation]:
        """
        Get all relations with the given wrapped field that are outgoing from the given wrapped instance.

        :param wrapped_instance: The wrapped instance to get the relations from.
        :param wrapped_field: The wrapped field to filter for.
        """
        wrapped_instance = self.get_wrapped_instance(wrapped_instance)
        if not wrapped_instance:
            return
        yield from self._relation_index.get(wrapped_field.name, {}).get(
            wrapped_instance.index, set()
        )

    def get_incoming_relations_for_wrapped_field(
        self, wrapped_instance: WrappedInstance, wrapped_field: WrappedField
    ) -> Iterable[PredicateClassRelation]:
        """
        Get all relations with the given wrapped field that are incoming to the given wrapped instance.

        :param wrapped_instance: The wrapped instance to get the relations from.
        :param wrapped_field: The wrapped field to filter for.
        """
        wrapped_instance = self.get_wrapped_instance(wrapped_instance)
        if not wrapped_instance:
            return
        yield from self._relation_index_incoming.get(wrapped_field.name, {}).get(
            wrapped_instance.index, set()
        )

    def get_outgoing_relations_by_descriptor_class(
        self,
        wrapped_instance: WrappedInstance,
        descriptor_class: Type,
    ) -> Iterable[PredicateClassRelation]:
        """
        Get all relations whose property descriptor class is a subclass of the given descriptor class
        and are outgoing from the given wrapped instance.
        """
        for cls, fields in list(self._fields_by_descriptor_class.items()):
            if issubclass(cls, descriptor_class):
                for wrapped_field in list(fields):
                    yield from self.get_outgoing_relations_for_wrapped_field(
                        wrapped_instance, wrapped_field
                    )

    def get_incoming_relations_by_descriptor_class(
        self,
        wrapped_instance: WrappedInstance,
        descriptor_class: Type,
    ) -> Iterable[PredicateClassRelation]:
        """
        Get all relations whose property descriptor class is a subclass of the given descriptor class
        and are incoming to the given wrapped instance.
        """
        for cls, fields in list(self._fields_by_descriptor_class.items()):
            if issubclass(cls, descriptor_class):
                for wrapped_field in list(fields):
                    yield from self.get_incoming_relations_for_wrapped_field(
                        wrapped_instance, wrapped_field
                    )

    def to_dot(
        self,
        filepath: str,
        format_="svg",
        graph_type="instance",
        graph: Optional[PyDiGraph] = None,
        without_inherited_associations: bool = True,
    ) -> None:
        """
        Generate a dot file from the instance graph, requires graphviz and pydot libraries.

        :param filepath: The path to the dot file.
        :param format_: The format of the dot file (svg, png, ...).
        :param graph_type: The type of the graph to generate (instance, type).
        :param without_inherited_associations: Whether to include inherited associations in the graph.
        """
        import pydot

        if not graph and graph_type == "type":
            if without_inherited_associations:
                graph = self.class_diagram.to_subdiagram_without_inherited_associations(
                    True
                )._dependency_graph
            else:
                graph = self.class_diagram._dependency_graph
        elif not graph:
            graph = self._instance_graph
        if not filepath.endswith(f".{format_}"):
            filepath += f".{format_}"
        dot_str = graph.to_dot(
            lambda node: dict(
                color="black",
                fillcolor="lightblue",
                style="filled",
                label=node.name,
            ),
            lambda edge: dict(color=edge.color, style="solid", label=str(edge)),
            dict(rankdir="LR"),
        )
        dot = pydot.graph_from_dot_data(dot_str)[0]
        try:
            dot.write(filepath, format=format_)
        except FileNotFoundError:
            tmp_filepath = filepath.replace(f".{format_}", ".dot")
            dot.write(tmp_filepath, format="raw")
            try:
                os.system(f"/usr/bin/dot -T{format_} {tmp_filepath} -o {filepath}")
                os.remove(tmp_filepath)
            except Exception as e:
                logger.error(e)

    def __hash__(self):
        return hash(id(self._instance_graph))


def role_aware_recursive_subclasses(cls: Type[T]) -> List[Type[T]]:
    """
    Recursively get all subclasses of a class, including those that are subclasses of subclasses, while also considering role inheritance.
    This function is role-aware, meaning it will include subclasses that are also roles of the given class.
    """
    all_sub_classes = (
        cls.__subclasses__() + SymbolGraph().class_diagram.get_roles_of_class(cls)
    )
    return all_sub_classes + [
        g for s in all_sub_classes for g in role_aware_recursive_subclasses(s)
    ]
