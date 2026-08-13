"""
Tests for the launcher that runs the cramera viewer and the Montessori demo together.

The script names ports and demo flags that live in Python, so what it checks is that
none of them has drifted out from under it; actually running two processes is not
something a test suite should do.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

krrood = pytest.importorskip("krrood", reason="the viewer's EQL panel requires krrood")

from cramera.live.http import DEFAULT_PORT as BRIDGE_PORT  # noqa: E402
from cramera.server import DEFAULT_PORT as VIEWER_PORT  # noqa: E402

from experiments.montessori.franka_montessori_demo import (  # noqa: E402
    _parse_arguments,
)

SCRIPT_PATH = Path(__file__).parents[2] / "run_montessori_demo.sh"
"""
The launcher, at the repository root beside ``run_cramera.sh``.
"""

SCRIPT_TEXT = SCRIPT_PATH.read_text()
"""
The launcher's source, which every assertion here reads.
"""


def documented_demo_flags() -> list:
    """
    Every demo flag the script's help text advertises, ready to be parsed.

    A flag documented with an upper-case metavar after it (``--only-shape KEY``) takes a
    value, so it is returned with one.
    """
    help_text = SCRIPT_TEXT.split("cat <<USAGE", 1)[1].split("\nUSAGE", 1)[0]
    documented = []
    for line in help_text.splitlines():
        words = line.strip().split()
        if not words or not words[0].startswith("--") or words[0] == "--no-browser":
            continue
        takes_a_value = len(words) > 1 and words[1].isupper()
        documented.append([words[0], "value"] if takes_a_value else [words[0]])
    return documented


# %% the script itself
class TestTheLauncherIsRunnable:
    def test_it_is_executable(self):
        assert os.access(SCRIPT_PATH, os.X_OK)

    def test_it_is_valid_bash(self):
        assert subprocess.run(["bash", "-n", str(SCRIPT_PATH)]).returncode == 0

    def test_its_help_needs_no_running_services(self):
        finished = subprocess.run(
            [str(SCRIPT_PATH), "--help"], capture_output=True, text=True, timeout=60
        )

        assert finished.returncode == 0
        assert "--no-browser" in finished.stdout


# %% what it launches
class TestItLaunchesTheQueryablePair:
    def test_it_starts_the_viewer_server(self):
        assert "-m cramera.server" in SCRIPT_TEXT

    def test_it_starts_the_demo_with_queries_enabled(self):
        """
        Without ``--cramera`` the demo runs perfectly well and answers nothing, which is
        the one failure this script exists to prevent.
        """
        assert (
            "-m experiments.montessori.franka_montessori_demo --cramera" in SCRIPT_TEXT
        )

    def test_every_flag_it_advertises_is_one_the_demo_accepts(self):
        advertised = documented_demo_flags()
        assert advertised
        for arguments in advertised:
            assert _parse_arguments(arguments), arguments

    def test_it_passes_further_arguments_through_to_the_demo(self):
        assert '${demo_arguments[@]+"${demo_arguments[@]}"}' in SCRIPT_TEXT

    def test_it_checks_the_results_database_before_starting_anything(self):
        """
        The demo will not start without its database, and finding that out only after
        the CRAM stack has imported costs a minute for an answer worth a fraction of a
        second.
        """
        preflight = SCRIPT_TEXT.index("-m experiments.montessori.results_database")
        assert preflight < SCRIPT_TEXT.index("-m cramera.server")
        assert preflight < SCRIPT_TEXT.index(
            "-m experiments.montessori.franka_montessori_demo"
        )

    def test_an_unreachable_database_stops_it_before_it_opens_a_port(self, tmp_path):
        unreachable = "postgresql+psycopg://nobody:wrong@127.0.0.1:1/montessori"
        finished = subprocess.run(
            [str(SCRIPT_PATH), "--no-browser", "--database-uri", unreachable],
            capture_output=True,
            text=True,
            timeout=120,
        )

        assert finished.returncode == 1
        assert "Cannot reach the results database" in finished.stderr
        assert "Starting the cramera server" not in finished.stdout


# %% what it runs the demo with by default
class TestItChoosesTheDemosDefaults:
    """
    The demo module itself stays headless and single-table, since the headless batch
    runners invoke it directly; the launcher exists to watch a run, so it chooses
    otherwise and says how to override it.
    """

    def test_it_turns_on_the_window_and_the_second_layout(self):
        assert "default_demo_arguments=(--world2 --viewer)" in SCRIPT_TEXT

    def test_each_default_is_one_the_demo_accepts(self):
        arguments = SCRIPT_TEXT.split("default_demo_arguments=(", 1)[1]
        arguments = arguments.split(")", 1)[0].split()

        assert arguments
        assert _parse_arguments(arguments)

    def test_each_default_can_be_turned_back_off(self):
        """
        A default is only a default if the caller can still say no to it.
        """
        arguments = SCRIPT_TEXT.split("default_demo_arguments=(", 1)[1]
        for flag in arguments.split(")", 1)[0].split():
            negation = flag.replace("--", "--no-", 1)
            assert _parse_arguments([flag, negation]), negation
            assert negation in SCRIPT_TEXT


# %% the ports it names
class TestItNamesThePortsInUse:
    def test_it_waits_on_the_port_the_viewer_serves(self):
        assert "cramera_port=%d" % VIEWER_PORT in SCRIPT_TEXT

    def test_it_names_the_port_the_demos_bridge_serves(self):
        assert "bridge_port=%d" % BRIDGE_PORT in SCRIPT_TEXT

    def test_it_opens_the_viewer_without_naming_a_recorded_scene(self):
        """
        The viewer only attaches to a running demo on its own when the page names no
        recorded scene, so a ``?scene=`` in the opened URL would leave the buttons
        unanswered until someone clicked *Live*.
        """
        assert 'viewer_url="http://localhost:${cramera_port}/"' in SCRIPT_TEXT
