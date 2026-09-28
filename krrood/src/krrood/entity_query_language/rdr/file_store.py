"""
The model file one ``@rdr``-decorated function's rules live in.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from typing_extensions import TYPE_CHECKING, Callable, Type

from krrood.code_generation.module_loading import load_module_from_path
from krrood.entity_query_language.rdr.exceptions import ModelFileMissing
from krrood.entity_query_language.rdr.serialization import (
    _LOADED_MODULE_NAME_PREFIX,
    RDR_CASE_TYPE_NAME,
    ModelSaver,
    save_rdr_with_case,
)

if TYPE_CHECKING:
    from krrood.entity_query_language.rdr.function_case import FunctionCase
    from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR

MODELS_DIRECTORY_NAME: str = "_rdr_models"
"""
The directory a relative model filename is resolved into, beside the decorated
function's own module.
"""


@dataclass
class RDRFileStore(ModelSaver):
    """
    Persists one decorated function's RDR to a Python module, and reads back the case
    type that module defines.

    The module holds the generated :class:`FunctionCase` subclass followed by the rule
    tree, both rewritten on every save so the file stays importable on its own.
    """

    function: Callable
    """
    The decorated function, which anchors the model file's location and supplies the
    signature its case type is generated from.
    """

    filename: str
    """
    Where to keep the model, relative to :data:`MODELS_DIRECTORY_NAME` beside the
    function's module, or absolute to place it exactly.
    """

    @cached_property
    def path(self) -> str:
        """
        :return: The absolute path of the model file.
        """
        if Path(self.filename).is_absolute():
            return self.filename
        module_directory = Path(inspect.getfile(self.function)).parent
        return str(module_directory / MODELS_DIRECTORY_NAME / self.filename)

    def exists(self) -> bool:
        """
        :return: Whether the model file has been written yet.
        """
        return Path(self.path).is_file()

    def save(self, rdr: EQLSingleClassRDR) -> None:
        """
        Write the case type and the rule tree to :attr:`path`, creating its directory.

        :param rdr: The RDR to persist, over a :class:`FunctionCase` subclass.
        """
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        save_rdr_with_case(rdr, self.path)

    def load_case_type(self) -> Type[FunctionCase]:
        """
        :return: The case type defined by the saved model file.
        :raises ModelFileMissing: If nothing has been saved to :attr:`path` yet.
        """
        if not self.exists():
            raise ModelFileMissing(self.function, self.path)
        module = load_module_from_path(self.path, _LOADED_MODULE_NAME_PREFIX)
        return getattr(module, RDR_CASE_TYPE_NAME)
