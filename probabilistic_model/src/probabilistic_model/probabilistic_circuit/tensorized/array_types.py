"""
Names for the kinds of numpy arrays that the layers of a layered circuit pass around.

They are plain aliases of :class:`numpy.ndarray`; they only tell the reader what an array
holds and which shape it has.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
from typing_extensions import TypeAlias

SampleArray: TypeAlias = npt.NDArray[np.float64]
"""
Samples of all variables of a circuit, shape (#samples, #variables of the circuit).
"""

SampleColumn: TypeAlias = npt.NDArray[np.float64]
"""
The values of one variable in a set of samples, shape (#samples,).
"""

SampleRows: TypeAlias = npt.NDArray[np.int64]
"""
Indices of rows of a :data:`SampleArray`.
"""

NodeValues: TypeAlias = npt.NDArray[np.float64]
"""
One value per node of a layer, shape (#nodes,).
"""

NodeMask: TypeAlias = npt.NDArray[np.bool_]
"""
One flag per node of a layer, shape (#nodes,).
"""

SampleNodeValues: TypeAlias = npt.NDArray[np.float64]
"""
One value per sample and node of a layer, shape (#samples, #nodes).
"""

VariableValues: TypeAlias = npt.NDArray[np.float64]
"""
One value per variable of a circuit, shape (#variables of the circuit,).
"""

VariableMask: TypeAlias = npt.NDArray[np.bool_]
"""
One flag per variable of a circuit, shape (#variables of the circuit,).
"""

VariableIndices: TypeAlias = npt.NDArray[np.int64]
"""
Indices of variables of a circuit.
"""

EdgeValues: TypeAlias = npt.NDArray[np.float64]
"""
One value per edge of an inner layer, in the order the layer stores its edges.
"""

EdgeMask: TypeAlias = npt.NDArray[np.bool_]
"""
One flag per edge of an inner layer, in the order the layer stores its edges.
"""
