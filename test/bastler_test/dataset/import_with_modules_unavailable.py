"""
Import one module with a named set of top-level modules made unimportable.

Run as a subprocess by ``test_package_contract.py`` to hold the tiers
:mod:`bastler.package_layout` declares to their stated shape: a module that claims to need
nothing beyond the standard library has to import with every third-party module made
unavailable, and one below the top tier has to import without the render layer's
dependencies.

Made unavailable here rather than by uninstalling anything, because the test asserts what
a *module* reaches, not what an environment happens to hold - and the environment running
the suite legitimately has all of it installed.

Usage::

    python3 import_with_modules_unavailable.py --unavailable jinja2,markdown <module>

Exits 0 when the import succeeds, 1 when it fails, printing the failure.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from dataclasses import dataclass
from importlib.abc import MetaPathFinder
from importlib.machinery import ModuleSpec
from pathlib import Path
from typing import Sequence

REPOSITORY_ROOT = Path(__file__).parent.parent.parent.parent
"""
The repository root, which :mod:`bastler` is a plain top-level directory of.

Inserted below rather than inherited: an interpreter running a script by its path puts
that script's own directory on ``sys.path``, not the working directory, so the package
would be unimportable here however the caller was invoked.
"""

sys.path.insert(0, str(REPOSITORY_ROOT))


@dataclass(frozen=True)
class UnavailableModuleFinder(MetaPathFinder):
    """
    A module finder that refuses the top-level modules it names.

    Installed at the front of ``sys.meta_path``, so it answers before any real finder
    and an unavailable module raises ``ModuleNotFoundError`` exactly as it would on a
    machine where it was never installed.
    """

    unavailable_module_names: frozenset[str]
    """
    The top-level module names to refuse, e.g. ``{"jinja2", "markdown"}``.

    A submodule of an unavailable module is refused too, since importing one imports its
    parent first.
    """

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None = None,
        target: object | None = None,
    ) -> ModuleSpec | None:
        """
        Refuse an unavailable module, and defer to the rest of ``sys.meta_path``
        otherwise.

        Named as :mod:`importlib` requires: it is the method the import machinery calls
        on every entry of ``sys.meta_path``, so this one is not ours to rename.

        :param fullname: The dotted name being imported.
        :param path: The parent package's search path, unused here.
        :param target: The module being reloaded, unused here.
        :raises ModuleNotFoundError: If ``fullname``'s top-level name is unavailable.
        :return: Always ``None`` for a name that is available, which lets the next
            finder answer.
        """
        if fullname.split(".")[0] in self.unavailable_module_names:
            raise ModuleNotFoundError(f"No module named {fullname!r}", name=fullname)
        return None


def import_with_modules_unavailable(
    module_name: str, unavailable_module_names: frozenset[str]
) -> None:
    """
    Import ``module_name`` with ``unavailable_module_names`` made unimportable.

    :param module_name: The dotted module to import.
    :param unavailable_module_names: Top-level module names to refuse.
    :raises ModuleNotFoundError: If the import reaches an unavailable module.
    """
    # Drop anything already imported, so a module cached by this interpreter's own
    # startup cannot satisfy an import the block is meant to refuse.
    for cached_name in list(sys.modules):
        if cached_name.split(".")[0] in unavailable_module_names:
            del sys.modules[cached_name]
    sys.meta_path.insert(0, UnavailableModuleFinder(unavailable_module_names))
    importlib.import_module(module_name)


def main() -> int:
    """
    Parse arguments, attempt the import, and report the outcome.

    See the module docstring for the command-line contract.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("module", help="The dotted module to import")
    parser.add_argument(
        "--unavailable",
        required=True,
        help="Comma-separated top-level module names to make unimportable",
    )
    arguments = parser.parse_args()
    unavailable_module_names = frozenset(
        name for name in arguments.unavailable.split(",") if name
    )
    try:
        import_with_modules_unavailable(arguments.module, unavailable_module_names)
    except BaseException as import_failure:  # noqa: BLE001 - reported, not handled
        print(f"{type(import_failure).__name__}: {import_failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
