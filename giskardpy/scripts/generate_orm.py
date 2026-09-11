import logging
from pathlib import Path

import numpy as np

import giskardpy
import giskardpy.qp.solvers
import giskardpy.middleware.ros2.python_interface
import giskardpy.middleware.ros2.utils.utils_for_tests
import semantic_digital_twin.orm.ormatic_interface
from krrood.adapters.json_serializer import SubclassJSONSerializer
from krrood.ormatic.custom_types import NumpyType
from krrood.ormatic.ormatic import ORMatic
from krrood.ormatic.utils import classes_of_package, classes_of_module

# ----------------------------------------------------------------------------------------------------------------------
# This script generates the ORM classes for the giskardpy package.
# ..warning:: Do not import coraplex here. Alternative mappings are collected through a global
# subclass scan, so importing a downstream package leaks its mappings into this interface.
# ----------------------------------------------------------------------------------------------------------------------


ignored_classes = set(classes_of_package(giskardpy.qp.solvers))
ignored_classes |= {SubclassJSONSerializer}

# GiskardWrapper/GiskardWrapperNode wrap a live ROS2 action client and node handle, and
# GiskardWrapper._goal_result is typed through a json_msgs message only available where
# ROS message packages are installed -- unresolvable when they are not (ORM generation
# included). Neither is a record a row could hold, so neither they nor the ROS2 test
# harness classes referencing them are mapped, the same way a running system elsewhere
# in this workspace (a camera, a world mirror) is left unmapped.
ignored_classes |= {
    giskardpy.middleware.ros2.python_interface.GiskardWrapper,
    giskardpy.middleware.ros2.python_interface.GiskardWrapperNode,
}
ignored_classes |= set(
    classes_of_module(giskardpy.middleware.ros2.utils.utils_for_tests)
)

dependencies = [semantic_digital_twin.orm.ormatic_interface]

type_mappings = {np.ndarray: NumpyType}


ormatic = ORMatic.from_package(
    [giskardpy],
    dependencies,
    ignored_classes,
    type_mappings,
)
logging.getLogger("krrood").setLevel(logging.DEBUG)


ormatic.make_all_tables()

ormatic_interface_path = (
    Path(__file__).parents[1] / "src" / "giskardpy" / "orm" / "ormatic_interface.py"
)
with open(ormatic_interface_path, "w") as f:
    ormatic.to_sqlalchemy_file(f)
