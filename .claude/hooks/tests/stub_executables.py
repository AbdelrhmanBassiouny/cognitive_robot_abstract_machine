"""
The stubbed ``PATH`` the hook tests run their subprocesses against.

``github-api.sh`` reaches GitHub through ``gh`` or ``curl``, and
``setup-personal-notes.sh`` installs dependencies through ``pip``. Tests replace all
three with the scripts in ``stubs/``, placed earlier on ``PATH`` than any real one, so
the suite runs in CI with no network access and no credentials.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

STUB_SOURCE_DIRECTORY = Path(__file__).parent / "stubs"
"""
The directory holding the stub scripts, each named ``<executable>.sh``.
"""

CREDENTIAL_VARIABLE_NAMES = ("GH_TOKEN", "GITHUB_TOKEN", "GH_HOST")
"""
The GitHub credential variables stripped from every stubbed subprocess.

Whoever runs the tests may well have real ones set - this environment does - and a test
that reached GitHub with them would be neither reproducible nor safe.
"""

PERSONAL_NOTES_VARIABLE_PREFIX = "CLAUDE_PERSONAL_NOTES_"
"""
The prefix of the settings the hooks resolve from the environment, stripped for the same
reason: a value set in the caller's shell must never change what a test asserts.
"""


@dataclass
class StubExecutableDirectory:
    """
    A directory of stub executables, and the subprocess environment that selects them.
    """

    path: Path
    """
    The directory the stubs are installed into, prepended to ``PATH``.
    """

    mirrored_path_entries: dict[str, str] = field(default_factory=dict)
    """
    Mirror directory built for each ``PATH`` entry that had to hide an executable, keyed
    by the original entry so repeated calls reuse one mirror instead of rebuilding it.
    """

    @classmethod
    def create(cls, parent_directory: Path) -> StubExecutableDirectory:
        """
        Create an empty stub directory.

        :param parent_directory: Where to create it, typically pytest's per-test
            temporary directory.
        :return: The new stub directory, with nothing installed yet.
        """
        path = parent_directory / "stub-executables"
        path.mkdir()
        return cls(path)

    def install(self, *executable_names: str) -> None:
        """
        Install stubs, each taking over the name it is asked for.

        :param executable_names: Names to install, each backed by ``<name>.sh`` in
            ``stubs/`` - for example ``"gh"``, ``"curl"``, ``"pip"``.
        :raises FileNotFoundError: If no stub script backs one of the names.
        """
        for executable_name in executable_names:
            source = STUB_SOURCE_DIRECTORY / f"{executable_name}.sh"
            if not source.is_file():
                raise FileNotFoundError(
                    f"no stub script for '{executable_name}': {source}"
                )
            destination = self.path / executable_name
            shutil.copy(source, destination)
            destination.chmod(0o755)

    def subprocess_environment(
        self, hidden_executables: Sequence[str] = (), **overrides: str
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
            if name not in CREDENTIAL_VARIABLE_NAMES
            and not name.startswith(PERSONAL_NOTES_VARIABLE_PREFIX)
        }
        path_entries = [
            self.path_entry_hiding(entry, hidden_executables)
            for entry in environment.get("PATH", "").split(os.pathsep)
            if entry
        ]
        environment["PATH"] = os.pathsep.join([str(self.path), *path_entries])
        environment.update(overrides)
        return environment

    def path_entry_hiding(
        self, directory: str, hidden_executables: Sequence[str]
    ) -> str:
        """
        Return *directory*, or a mirror of it that omits *hidden_executables*.

        Mirrored by symlinking every other entry, rather than dropping the whole
        ``PATH`` entry: the directory providing the executable to hide is typically
        ``/usr/bin``, which also provides ``bash``, ``git`` and everything else a hook
        script runs, so removing it outright leaves nothing to run the test with.

        :param directory: One ``PATH`` entry.
        :param hidden_executables: Names that must not be findable through the result.
        :return: The same directory when it provides none of them, otherwise the path to
            a mirror directory that hides exactly those names.
        """
        source = Path(directory)
        if not source.is_dir():
            return directory
        shadowed = [name for name in hidden_executables if (source / name).exists()]
        if not shadowed:
            return directory

        mirror = self.path.parent / f"path-{len(self.mirrored_path_entries)}-hiding"
        if directory not in self.mirrored_path_entries:
            mirror.mkdir()
            for entry in source.iterdir():
                if entry.name not in shadowed:
                    (mirror / entry.name).symlink_to(entry)
            self.mirrored_path_entries[directory] = str(mirror)
        return self.mirrored_path_entries[directory]
