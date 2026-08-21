"""
Import one module with a named set of top-level modules made unimportable.

Run as a subprocess by ``test_package_contract.py`` to hold :mod:`bastler`'s dependency
tiers to their stated shape: a module that claims to need nothing beyond the standard
library has to import with every third-party module blocked, and a module a hook reaches
has to import without the render layer's dependencies present.

Blocking is done here rather than by uninstalling anything, because the test asserts what
a *module* reaches, not what an environment happens to hold - and the environment running
the suite legitimately has all of it installed.

Usage::

    python import_with_modules_blocked.py --blocked jinja2,markdown <module>

Exits 0 when the import succeeds, 1 when it fails, printing the failure.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from dataclasses import dataclass
from importlib.abc import MetaPathFinder
from importlib.machinery import ModuleSpec
from typing import Sequence


@dataclass(frozen=True)
class BlockedModuleFinder(MetaPathFinder):
    """
    A module finder that refuses the top-level modules it names.

    Installed at the front of ``sys.meta_path``, so it answers before any real finder
    and a blocked module raises ``ModuleNotFoundError`` exactly as it would on a machine
    where it was never installed.
    """

    blocked_module_names: frozenset[str]
    """
    The top-level module names to refuse, e.g. ``{"jinja2", "markdown"}``.

    A submodule of a blocked module is refused too, since importing one imports its
    parent first.
    """

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None = None,
        target: object | None = None,
    ) -> ModuleSpec | None:
        """
        Refuse a blocked module, and defer to the rest of ``sys.meta_path`` otherwise.

        :param fullname: The dotted name being imported.
        :param path: The parent package's search path, unused here.
        :param target: The module being reloaded, unused here.
        :raises ModuleNotFoundError: If ``fullname``'s top-level name is blocked.
        :return: Always ``None`` for a name that is not blocked, which lets the next
            finder answer.
        """
        if fullname.split(".")[0] in self.blocked_module_names:
            raise ModuleNotFoundError(f"No module named {fullname!r}", name=fullname)
        return None


def block_and_import(module_name: str, blocked_module_names: frozenset[str]) -> None:
    """
    Import ``module_name`` with ``blocked_module_names`` made unimportable.

    :param module_name: The dotted module to import.
    :param blocked_module_names: Top-level module names to refuse.
    :raises ModuleNotFoundError: If the import reaches a blocked module.
    """
    # Drop anything already imported, so a module cached by this interpreter's own
    # startup cannot satisfy an import the block is meant to refuse.
    for cached_name in list(sys.modules):
        if cached_name.split(".")[0] in blocked_module_names:
            del sys.modules[cached_name]
    sys.meta_path.insert(0, BlockedModuleFinder(blocked_module_names))
    importlib.import_module(module_name)


def main() -> int:
    """
    Parse arguments, attempt the import, and report the outcome.

    See the module docstring for the command-line contract.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("module", help="The dotted module to import")
    parser.add_argument(
        "--blocked",
        required=True,
        help="Comma-separated top-level module names to make unimportable",
    )
    arguments = parser.parse_args()
    blocked_module_names = frozenset(
        name for name in arguments.blocked.split(",") if name
    )
    try:
        block_and_import(arguments.module, blocked_module_names)
    except BaseException as import_failure:  # noqa: BLE001 - reported, not handled
        print(f"{type(import_failure).__name__}: {import_failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
