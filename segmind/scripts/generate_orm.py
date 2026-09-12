# ----------------------------------------------------------------------------------------------------------------------
# This script generates the ORM classes for the semantic_digital_twin package.
# Dataclasses can be mapped automatically to the ORM model
# using the ORMatic library, they just have to be registered in the classes list.
# Classes that are self_mapped and explicitly_mapped are already mapped in the model.py file. Look there for more
# information on how to map them.
# ----------------------------------------------------------------------------------------------------------------------
from __future__ import annotations
import logging
import os
from dataclasses import is_dataclass
from pathlib import Path

import numpy as np

import segmind

# imported so that every symbolic operation segmind declares is declared by the time the
# ignored classes below are read
import segmind.detectors.rules

# imported for its alternative mappings, which are collected through a global subclass
# scan: without it segmind's spatial fields degrade to JSON columns
import semantic_digital_twin.orm.model
import semantic_digital_twin.orm.ormatic_interface
from krrood.ormatic.custom_types import NumpyType
from krrood.adapters.json_serializer import SubclassJSONSerializer
from krrood.entity_query_language.predicate import SymbolicCallable
from krrood.ormatic.ormatic import ORMatic
from krrood.utils import recursive_subclasses

ignored_classes = {
    SubclassJSONSerializer,
    # A symbolic operation is a step of a rule, not something an episode stores, so none
    # of them is mapped.
    *recursive_subclasses(SymbolicCallable),
}

dependencies = [semantic_digital_twin.orm.ormatic_interface]

type_mappings = {np.ndarray: NumpyType}

# Create an ORMatic object with the classes to be mapped
ormatic = ORMatic.from_package([segmind], dependencies, ignored_classes, type_mappings)
logging.getLogger("krrood").setLevel(logging.DEBUG)


# Generate the ORM classes
ormatic.make_all_tables()

ormatic_interface_path = (
    Path(__file__).parents[1] / "src" / "segmind" / "orm" / "ormatic_interface.py"
)
with open(ormatic_interface_path, "w") as f:
    ormatic.to_sqlalchemy_file(f)
