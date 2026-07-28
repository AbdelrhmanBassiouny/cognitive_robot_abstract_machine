"""Consistency checks of the packaged frontend, plus the node-based JS tests.

The asset checks keep the panel architecture honest: every script index.html
includes must exist, every panel id in config.js must be defined by an included
panel script, and panels must not reach into each other's DOM.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from cram_viz.paths import WEB_ROOT

JS_DIR = Path(__file__).parent / "js"


def read(rel):
    return (WEB_ROOT / rel).read_text(encoding="utf-8")


class TestAssetConsistency:
    def test_every_included_script_exists(self):
        for src in re.findall(r'<script src="([^"]+)"', read("index.html")):
            assert (WEB_ROOT / src).is_file(), src

    def test_stylesheet_and_slots_exist(self):
        html = read("index.html")
        for href in re.findall(r'<link rel="stylesheet" href="([^"]+)"', html):
            assert (WEB_ROOT / href).is_file(), href
        assert 'data-slot="left"' in html and 'data-slot="right"' in html

    def test_configured_panels_are_defined(self):
        config = read("config.js")
        configured = set(re.findall(r"'([\w-]+)'", config.split("layout", 1)[1]))
        defined = set()
        for panel_js in WEB_ROOT.glob("panels/*/panel.js"):
            defined |= set(re.findall(r"Panels\.define\('([\w-]+)'", panel_js.read_text()))
        assert configured <= defined, configured - defined

    def test_panels_do_not_reach_into_each_other(self):
        # a panel may only query its own root; document.getElementById on
        # another panel's elements would silently couple them again
        for panel_js in WEB_ROOT.glob("panels/*/panel.js"):
            assert "document.getElementById" not in panel_js.read_text(), panel_js.name

    def test_no_stale_static_urls(self):
        # the old repo served under /static/; the packaged app is rooted at /
        for panel_js in WEB_ROOT.glob("panels/*/panel.js"):
            assert "'static/" not in panel_js.read_text(), panel_js.name


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
class TestJsUnits:
    def run_node(self, name):
        result = subprocess.run(
            ["node", "--test", str(JS_DIR / name)],
            capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_bus_and_registry(self):
        self.run_node("test_bus_registry.js")

    def test_graph_status_rendering(self):
        self.run_node("test_graph_status.js")
