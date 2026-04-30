from copy import deepcopy
from dataclasses import is_dataclass
from functools import partial

import pytest

try:
    import rclpy
except ModuleNotFoundError:
    pass
from sqlalchemy.orm import sessionmaker

import pycram
from krrood.class_diagrams import ClassDiagram
from krrood.ormatic.utils import create_engine, drop_database, classes_of_package
from krrood.patterns.role.helpers import transform_roles_in_class_diagram

try:
    from pycram.datastructures.dataclasses import Context
except ModuleNotFoundError:
    pass

try:
    from pycram.orm.ormatic_interface import Base
except ModuleNotFoundError:
    pass
try:
    from semantic_digital_twin.adapters.ros.visualization.viz_marker import (
        VizMarkerPublisher,
    )
except ModuleNotFoundError:
    pass
from semantic_digital_twin.robots.pr2 import PR2


@pytest.fixture(scope="session")
def viz_marker_publisher():
    rclpy.init()
    node = rclpy.create_node("test_viz_marker_publisher")
    # VizMarkerPublisher(world, node)  # Initialize the publisher
    yield partial(VizMarkerPublisher, node=node)
    rclpy.shutdown()


@pytest.fixture(scope="function")
def mutable_model_world(pr2_apartment_world):
    world = deepcopy(pr2_apartment_world)
    pr2 = PR2.from_world(world)
    return world, pr2, Context(world, pr2)


@pytest.fixture(scope="function")
def immutable_model_world(pr2_apartment_world):
    world = pr2_apartment_world
    pr2 = pr2_apartment_world.get_semantic_annotations_by_type(PR2)[0]
    state = deepcopy(world.state._data)
    yield world, pr2, Context(world, pr2)
    world.state._data[:] = state
    world.notify_state_change()


@pytest.fixture
def immutable_simple_pr2_world(simple_pr2_world_setup):
    world, robot_view, context = simple_pr2_world_setup
    state = deepcopy(world.state._data)
    yield world, robot_view, context
    world.state._data[:] = state
    world.notify_state_change()


@pytest.fixture
def mutable_simple_pr2_world(simple_pr2_world_setup):
    world, robot_view, context = simple_pr2_world_setup
    copy_world = deepcopy(world)
    robot_view = world.get_semantic_annotations_by_type(PR2)[0]
    return world, robot_view, Context(copy_world, robot_view)


@pytest.fixture(scope="function")
def pycram_testing_session():
    engine = create_engine("sqlite:///:memory:")
    session_maker = sessionmaker(engine)
    session = session_maker()
    Base.metadata.create_all(bind=session.bind)
    yield session
    drop_database(session.bind)
    session.close()
    engine.dispose()


def pytest_configure(config):
    all_classes = set(classes_of_package(pycram))
    # all_classes -= set(classes_of_module(semantic_digital_twin.orm.ormatic_interface))
    # all_classes -= set(classes_of_package(semantic_digital_twin.adapters))
    # all_classes |= set(
    #     classes_of_package(semantic_digital_twin.adapters.sage_10k_dataset)
    # )
    # # remove classes that should not be mapped
    # all_classes -= {
    #     ResetStateContextManager,
    #     WorldModelUpdateContextManager,
    #     ForwardKinematicsManager,
    #     semantic_digital_twin.adapters.procthor.procthor_resolver.ProcthorResolver,
    #     ContainsType,
    #     SemanticDirection,
    #     SubclassJSONSerializer,
    # }
    # keep only dataclasses that are NOT AlternativeMapping subclasses
    all_classes = {
        c
        for c in all_classes
        if is_dataclass(c)  # and not issubclass(c, AlternativeMapping)
    }
    class_diagram = ClassDiagram(list(all_classes))
    transform_roles_in_class_diagram(class_diagram)
