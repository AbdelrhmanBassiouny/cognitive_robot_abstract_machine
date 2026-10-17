"""
Standing an executable in for the real one, on a test subprocess's ``PATH``.

Every suite that runs a script reaching GitHub or installing a dependency needs the same
moves - put a stub where the script will find it, take a real executable out of reach,
and keep the caller's own credentials out of the run - so they live here rather than in
whichever suite happened to need them first.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .constants import SCRUBBED_VARIABLE_PREFIXES, DatasetLocation


class StubbedExecutable(StrEnum):
    """
    The executables the suites replace, each backed by ``dataset/stubs/<name>.sh``.

    ``git`` has no stub of its own - the scratch repositories run it for real - and is
    named here because tests hide it to exercise what a script does without it.
    """

    GH = "gh"
    """
    The GitHub CLI: the preferred backend of the shell callers that reach GitHub, and a
    credential source for the package's own client.
    """

    CURL = "curl"
    """
    The fallback backend, used with a token when ``gh`` is absent.
    """

    PIP = "pip"
    """
    What session-start.sh installs the package's missing dependencies with.
    """

    GIT = "git"
    """
    Never stubbed, only hidden.
    """

    @property
    def stub_script(self) -> Path:
        """
        The script backing this stub.
        """
        return DatasetLocation.STUBS / f"{self.value}.sh"


@dataclass(frozen=True)
class ExecutableStubDirectory:
    """
    A directory of stubbed executables, meant to be placed first on a subprocess's
    ``PATH`` so the script under test finds the stub instead of the real thing.
    """

    path: Path
    """
    The directory itself, which is what goes on ``PATH``.
    """

    @classmethod
    def create(cls, parent: Path) -> ExecutableStubDirectory:
        """
        :param parent: Where to create the directory, typically pytest's ``tmp_path``.
        :return: An empty stub directory, ready for :meth:`install`.
        """
        path = parent / "stub-bin"
        path.mkdir()
        return cls(path)

    def install(self, *executables: StubbedExecutable) -> None:
        """
        Install stubs, each taking over the name it stands in for.

        :param executables: The executables to stub.
        """
        for executable in executables:
            destination = self.path / executable.value
            shutil.copy(executable.stub_script, destination)
            destination.chmod(0o755)

    def ahead_of(self, search_path: str) -> str:
        """
        :param search_path: A ``PATH`` string to fall back to.
        :return: *search_path* with this directory first, so its stubs win.
        """
        return os.pathsep.join([str(self.path), search_path])

    def subprocess_environment(
        self, hidden_executables: Sequence[StubbedExecutable] = (), **overrides: str
    ) -> dict[str, str]:
        """
        Build the environment a stubbed subprocess runs in: this directory first on
        ``PATH``, every real credential and personal-notes setting removed, then
        *overrides* applied.

        :param hidden_executables: Executables to make unfindable, so that selecting a
            fallback backend is deterministic whether or not the machine running the
            tests happens to have the preferred one installed.
        :param overrides: Variables the test sets deliberately, such as the stubs' own
            ``STUB_*`` controls or a token to select the ``curl`` fallback.
        :return: The environment to hand to :func:`subprocess.run`.
        """
        environment = {
            name: value
            for name, value in os.environ.items()
            if not name.startswith(SCRUBBED_VARIABLE_PREFIXES)
        }
        search_path = environment.get("PATH", "")
        for executable in hidden_executables:
            search_path = path_hiding_executable(
                executable, self.path.parent, search_path
            )
        environment["PATH"] = self.ahead_of(search_path)
        environment.update(overrides)
        return environment


def path_hiding_executable(
    executable_name: str, mirror_parent: Path, search_path: str | None = None
) -> str:
    """
    Build a ``PATH`` string equivalent to *search_path* but with *executable_name*
    unfindable through it.

    Mirrors (via symlinks) any directory that provides *executable_name* into a copy
    missing just that one file, rather than dropping the whole directory from `PATH` -
    the directory providing it (typically ``/usr/bin``) also provides ``bash``, ``git``
    and ``python3``, which the script under test still needs to run at all. A mirror
    already built under *mirror_parent* is reused, so hiding the same executable twice
    in one test is harmless.

    :param executable_name: The executable to hide, e.g. ``"gh"``.
    :param mirror_parent: Where to create mirror directories.
    :param search_path: The ``PATH`` string to start from, defaulting to this process's.
    :return: The adjusted ``PATH`` string.
    """
    if search_path is None:
        search_path = os.environ.get("PATH", "")
    entries = []
    mirror_index = 0
    for entry in search_path.split(os.pathsep):
        directory = Path(entry)
        if not directory.is_dir() or not (directory / executable_name).exists():
            entries.append(entry)
            continue
        mirror = mirror_parent / f"hide-{executable_name}-{mirror_index}"
        mirror_index += 1
        mirror.mkdir(exist_ok=True)
        for item in directory.iterdir():
            if item.name == executable_name:
                continue
            try:
                (mirror / item.name).symlink_to(item)
            except OSError:
                continue
        entries.append(str(mirror))
    return os.pathsep.join(entries)
