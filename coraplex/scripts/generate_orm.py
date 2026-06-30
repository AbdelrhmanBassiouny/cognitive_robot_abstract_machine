import logging
import os
from pathlib import Path
from dataclasses import is_dataclass

import numpy as np

import giskardpy  # type: ignore
import coraplex.locations.costmaps
import semantic_digital_twin.orm.ormatic_interface
from krrood.adapters.json_serializer import SubclassJSONSerializer

from krrood.ormatic.ormatic import ORMatic
from krrood.ormatic.utils import classes_of_package, classes_of_module
from coraplex.orm.model import NumpyType
import coraplex.orm.model
import giskardpy.qp.solvers
from krrood.entity_query_language.performatives import Performable
from coraplex.plans.plan_node import PerformativeNode

# ----------------------------------------------------------------------------------------------------------------------
# This script generates the ORM classes for the coraplex package
# Classes that are self_mapped and explicitly_mapped are already mapped in the model.py file. Look there for more
# information on how to map them.
# ----------------------------------------------------------------------------------------------------------------------


ignored_classes = set(classes_of_package(giskardpy.qp.solvers))
ignored_classes |= set(classes_of_module(coraplex.locations.costmaps))
ignored_classes |= {SubclassJSONSerializer}
# PerformativeNode is a runtime bridge that carries a framework-agnostic ``Performable`` act; it is a
# composition node, not a persisted plan entity, so it is not mapped. ``Performable`` is the krrood
# verbalization interface PlanNode now also implements -- an abstract mixin, never a table.
ignored_classes |= {PerformativeNode, Performable}

dependencies = [semantic_digital_twin.orm.ormatic_interface]

type_mappings = {np.ndarray: NumpyType}


# Create an ORMatic object with the classes to be mapped
ormatic = ORMatic.from_package(
    [coraplex, giskardpy], dependencies, ignored_classes, type_mappings
)
logging.getLogger("krrood").setLevel(logging.DEBUG)


# Generate the ORM classes
ormatic.make_all_tables()

ormatic_interface_path = (
    Path(__file__).parents[1] / "src" / "coraplex" / "orm" / "ormatic_interface.py"
)
with open(ormatic_interface_path, "w") as f:
    ormatic.to_sqlalchemy_file(f)
