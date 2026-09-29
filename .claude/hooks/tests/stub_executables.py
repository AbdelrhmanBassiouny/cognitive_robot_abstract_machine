"""
The stubbed ``PATH`` the hook tests run their subprocesses against.

``github-api.sh`` reaches GitHub through ``gh`` or ``curl``, and ``setup-personal-
notes.sh`` installs dependencies through ``pip``. Tests replace all three with the
scripts in ``stubs/``, placed earlier on ``PATH`` than any real one, so the suite runs
in CI with no network access and no credentials.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

STUB_SOURCE_DIRECTORY = Path(__file__).parent / "stubs"
"""
The directory holding the stub scripts, each named ``<executable>.sh``.
"""


class GitHubCredentialVariable(StrEnum):
    """
    The GitHub credential variables stripped from every stubbed subprocess.

    Whoever runs the tests may well have real ones set - this environment does - and a
    test that reached GitHub with them would be neither reproducible nor safe.
    """

    GH_TOKEN = "GH_TOKEN"
    """
    The token ``gh`` reads first, and the fallback backend's own preference.
    """

    GITHUB_TOKEN = "GITHUB_TOKEN"
    """
    The token both fall back to.
    """

    GH_HOST = "GH_HOST"
    """
    The host ``gh`` would talk to, which a real value could redirect.
    """


class StubbedExecutable(StrEnum):
    """
    The executables the hook tests replace, each backed by ``<name>.sh`` in ``stubs/``.

    ``git`` has no stub of its own - the scratch repositories run it for real - and is
    named here because tests hide it to exercise what a script does without it.
    """

    GH = "gh"
    """
    The GitHub CLI, ``github-api.sh``'s preferred backend.
    """

    CURL = "curl"
    """
    The fallback backend, used with a token when ``gh`` is absent.
    """

    PIP = "pip"
    """
    How setup-personal-notes.sh installs the plan-dashboard dependencies.
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
        return STUB_SOURCE_DIRECTORY / f"{self.value}.sh"


SCRUBBED_VARIABLE_PREFIXES = (
    "CLAUDE_PERSONAL_NOTES_",
    "GIT_AUTHOR_",
    "GIT_COMMITTER_",
    *GitHubCredentialVariable,
)
"""
Everything stripped from a subprocess's environment before a test runs it.

A whole variable name is its own prefix, so the credentials above belong in the same
tuple as the families. The personal-notes settings redirect where a hook looks; the git
identity variables outrank every config file, so a clone whose recorded identity is
exactly right still commits as whatever they say - which is precisely what
``check-setup.sh``'s ``git_identity`` check reports on.
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

    def install(self, *executables: StubbedExecutable) -> None:
        """
        Install stubs, each taking over the name it is asked for.

        :param executables: The executables to stub.
        :raises FileNotFoundError: If no stub script backs one of them.
        """
        for executable in executables:
            if not executable.stub_script.is_file():
                raise FileNotFoundError(
                    f"no stub script for '{executable}': {executable.stub_script}"
                )
            destination = self.path / executable.value
            shutil.copy(executable.stub_script, destination)
            destination.chmod(0o755)

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
        path_entries = [
            self.path_entry_hiding(entry, hidden_executables)
            for entry in environment.get("PATH", "").split(os.pathsep)
            if entry
        ]
        environment["PATH"] = os.pathsep.join([str(self.path), *path_entries])
        environment.update(overrides)
        return environment

    def path_entry_hiding(
        self, directory: str, hidden_executables: Sequence[StubbedExecutable]
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
        shadowed = [
            executable.value
            for executable in hidden_executables
            if (source / executable.value).exists()
        ]
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
