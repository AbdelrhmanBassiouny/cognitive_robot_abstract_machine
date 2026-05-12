"""
File writer for generated module sources.
"""

from __future__ import annotations

import ast
import dataclasses
import logging
import shutil
from pathlib import Path
from types import ModuleType
from typing import Callable

from typing_extensions import Dict, Tuple

from krrood.utils import run_black_on_file, run_ruff_on_file

log = logging.getLogger(__name__)


def has_class_definitions(source: str) -> bool:
    """Return *True* if *source* contains at least one class definition.

    Used to decide whether a generated mixin file is worth writing to disk.
    Falls back to *True* on :exc:`SyntaxError` (assume content is present
    to avoid accidentally skipping a file that simply failed to parse).

    :param source: Python source code string to inspect.
    :return: *True* if any ``class`` statement is present.
    """
    try:
        return any(
            isinstance(node, ast.ClassDef) for node in ast.walk(ast.parse(source))
        )
    except SyntaxError:
        return True


@dataclasses.dataclass
class GeneratedCodeFileWriter:
    """
    Writes transformed module sources and generated sources to the file system.

    Mixin files whose generated content contains no class definitions are
    **not** written.  If an existing mixin file is found where the new content
    would be empty, the file is deleted.  The ``role_mixins/`` package folder
    (and its ``__init__.py``) is created only when at least one mixin file with
    content will be written to it, and deleted when it becomes empty (contains
    only an empty ``__init__.py`` and possibly a ``__pycache__/``).
    """

    def write(
        self,
        module_sources: Dict[ModuleType, Tuple[str, str]],
        get_path_fn: Callable[[ModuleType, bool], Path],
    ) -> None:
        """Write all transformed sources to disk and run formatters on each file.

        :param module_sources: Mapping of module to
            ``(transformed_source, mixin_source)`` tuples.
        :param get_path_fn: Callable accepting ``(module, is_mixin)`` that
            returns the target :class:`~pathlib.Path`.
        """
        mixin_dirs_with_content: set[Path] = set()
        files_to_write: list[tuple[Path, str]] = []
        mixin_files_to_delete: list[Path] = []

        for module, (module_source, mixin_source) in module_sources.items():
            original_path = get_path_fn(module, False)
            mixin_path = get_path_fn(module, True)

            files_to_write.append((original_path, module_source))

            if has_class_definitions(mixin_source):
                mixin_dirs_with_content.add(mixin_path.parent)
                files_to_write.append((mixin_path, mixin_source))
            elif mixin_path.exists():
                mixin_files_to_delete.append(mixin_path)

        for dir_ in mixin_dirs_with_content:
            self._ensure_package_exists(dir_)

        written: list[Path] = []
        for path, content in files_to_write:
            with open(path, "w") as f:
                f.write(content)
            written.append(path)

        for path in mixin_files_to_delete:
            path.unlink()

        dirs_to_check = (
            {p.parent for p in mixin_files_to_delete} - mixin_dirs_with_content
        )
        for dir_ in dirs_to_check:
            self._cleanup_empty_generated_package(dir_)

        for path in written:
            try:
                run_ruff_on_file(str(path))
            except Exception:
                log.warning("ruff failed on %s", path, exc_info=True)
            try:
                run_black_on_file(str(path))
            except Exception:
                log.warning("black failed on %s", path, exc_info=True)

    @staticmethod
    def _ensure_package_exists(folder: Path) -> None:
        """Create the package directory and its ``__init__.py`` if they do not exist."""
        folder.mkdir(exist_ok=True)
        init_file = folder / "__init__.py"
        if not init_file.exists():
            init_file.touch()

    @staticmethod
    def _cleanup_empty_generated_package(folder: Path) -> None:
        """Delete *folder* when it contains only an empty generated ``__init__.py``.

        The folder is considered a candidate for deletion when the only
        non-``__pycache__`` entry is an empty ``__init__.py`` — i.e. the
        folder was created solely by this writer and now has no mixin files
        left.  Any other content (user files, non-empty ``__init__.py``) is
        left untouched.
        """
        if not folder.exists():
            return
        non_cache = {f for f in folder.iterdir() if f.name != "__pycache__"}
        init = folder / "__init__.py"
        if non_cache == {init} and init.stat().st_size == 0:
            init.unlink()
            pycache = folder / "__pycache__"
            if pycache.exists():
                shutil.rmtree(pycache)
            folder.rmdir()
