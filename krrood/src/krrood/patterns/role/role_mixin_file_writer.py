"""
File writer for generated role mixin and transformed original module sources.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Callable

from krrood.utils import run_black_on_file, run_ruff_on_file


@dataclasses.dataclass
class RoleMixinFileWriter:
    """
    Writes transformed module sources and generated mixin sources to the file system.
    """

    file_name_prefix: str = ""

    def write(
        self,
        module_sources: dict,
        get_path_fn: Callable,
    ) -> None:
        """
        Write all transformed sources to disk and run formatters on each file.

        :param module_sources: Mapping of module to (transformed_source, mixin_source) tuples.
        :param get_path_fn: Callable that accepts (module, is_mixin) and returns a Path.
        """
        generated_paths: list[Path] = []
        for module, (module_source, mixin_source) in module_sources.items():
            original_path = get_path_fn(module, is_mixin=False)
            mixin_path = get_path_fn(module, is_mixin=True)
            for path, content in [
                (original_path, module_source),
                (mixin_path, mixin_source),
            ]:
                with open(path, "w") as f:
                    f.write(content)
                generated_paths.append(path)

        for path in generated_paths:
            run_ruff_on_file(str(path))
            run_black_on_file(str(path))
