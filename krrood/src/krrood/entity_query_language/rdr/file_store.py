"""
Filesystem lifecycle manager for a single ``@rdr``-decorated function's model file.

The file contains two sections: the ``FunctionCase`` subclass definition (generated
from the original function's signature) followed by the EQL rule tree.  Both sections
are regenerated together on every save so the file is always a self-contained,
importable Python module.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

from typing_extensions import Callable, Type

if TYPE_CHECKING:
    from krrood.entity_query_language.rdr.function_case import FunctionCase
    from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR

#: Directory name under the function's module directory where RDR model
#: files are stored by default.
_RDR_MODELS_DIR: str = "_rdr_models"


@dataclass
class RDRFileStore:
    """Owns the path and combined class + rule-tree file lifecycle for one decorated function.

    :param func: The original decorated function; used to locate its source module
        (via :func:`inspect.getfile`) and to generate the :class:`FunctionCase`
        subclass definition on first save.
    :param filename: User-supplied filename.  If relative, it is joined under a
        ``_rdr_models/`` subdirectory beside the function's module file.  If
        absolute, it is used as-is.
    """

    func: Callable
    filename: str

    @cached_property
    def path(self) -> str:
        """Resolved absolute path to the model ``.py`` file."""
        return self._resolve_path(self.func, self.filename)

    def exists(self) -> bool:
        """Return ``True`` if the model file already exists on disk."""
        return Path(self.path).is_file()

    def load_case_type(self) -> Type[FunctionCase]:
        """Import the :class:`FunctionCase` subclass from the existing model file.

        The file must have been written by :meth:`save` first.  The class is
        identified by the ``RDR_CASE_TYPE`` stable handle written at the bottom
        of every model file.

        :returns: The ``FunctionCase`` subclass defined in the file.
        :raises FileNotFoundError: If the model file does not exist.
        """
        from krrood.entity_query_language.rdr.serialization import (
            _load_module_from_path,
        )

        if not Path(self.path).is_file():
            raise FileNotFoundError(
                f"RDR model file not found: {self.path!r}. "
                "Call save() before load_case_type()."
            )
        module = _load_module_from_path(self.path)
        return module.RDR_CASE_TYPE

    def save(self, rdr: EQLSingleClassRDR) -> None:
        """Write the model file (class header + rule tree) to :attr:`path`.

        Creates the parent directory if it does not exist.

        :param rdr: A fitted :class:`EQLSingleClassRDR` whose case type is a
            :class:`FunctionCase` subclass.
        """
        from krrood.entity_query_language.rdr.serialization import save_rdr_with_case

        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        save_rdr_with_case(rdr, self.path)

    @staticmethod
    def _resolve_path(func: Callable, filename: str) -> str:
        """Resolve *filename* relative to the function's module directory.

        :param func: The callable whose source location anchors the path.
        :param filename: A relative or absolute filename.
        :returns: The absolute path as a ``str``.
        """
        if Path(filename).is_absolute():
            return filename
        module_dir = Path(inspect.getfile(func)).parent
        return str(module_dir / _RDR_MODELS_DIR / filename)
