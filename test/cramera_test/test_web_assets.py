"""
Consistency checks of the packaged frontend, plus the node-based JS tests.

The asset checks keep the panel architecture honest: every asset the shell references
must exist, every panel id in config.js must be defined by an included panel script, and
panels must not reach outside their own DOM subtree.
"""

import re
import shutil
import subprocess
from dataclasses import asdict
from pathlib import Path

import pytest
from typing_extensions import List

from cramera.knowledge.eql_session import EqlSession
from cramera.knowledge.presets import Preset
from cramera.knowledge.query_runner import RenderResult
from cramera.knowledge.question_matching import (
    UNMATCHED_QUESTION_REPLY,
    QuestionMatchResult,
)
from cramera.paths import WEB_ROOT

JS_DIR = Path(__file__).parent / "js"

SCRIPT_PATTERN = re.compile(r'<script src="([^"]+)"')
"""
How the shell references the assets that must ship with it.
"""

STYLESHEET_PATTERN = re.compile(r'<link rel="stylesheet" href="([^"]+)"')
IMAGE_PATTERN = re.compile(r'<img[^>]+src="([^"]+)"')
CSS_URL_PATTERN = re.compile(r"url\(['\"]?([^)'\"]+)['\"]?\)")

#: the EQL variables the query panel advertises: the ``vars:`` list in its placeholder,
#: and every bare identifier it marks up as ``<code>``
ADVERTISED_VARIABLES_PATTERN = re.compile(r"vars: ([a-z_, ]+)")
MARKED_UP_IDENTIFIER_PATTERN = re.compile(r"<code>([a-z_]+)</code>")

#: the ready-to-run query the panel shows in its empty input box
PLACEHOLDER_QUERY_PATTERN = re.compile(r'placeholder="(the\(entity.*?\)\))')


def read(relative_path: str) -> str:
    """
    The text of one packaged frontend file.
    """
    return (WEB_ROOT / relative_path).read_text(encoding="utf-8")


def panel_scripts() -> List[Path]:
    """
    Every script belonging to a panel, at any depth under ``panels/``.
    """
    return sorted(WEB_ROOT.glob("panels/**/*.js"))


class TestAssetConsistency:
    def test_every_included_script_exists(self):
        for source in SCRIPT_PATTERN.findall(read("index.html")):
            assert (WEB_ROOT / source).is_file(), source

    def test_stylesheet_and_slots_exist(self):
        html = read("index.html")
        for href in STYLESHEET_PATTERN.findall(html):
            assert (WEB_ROOT / href).is_file(), href
        assert 'data-slot="left"' in html and 'data-slot="right"' in html

    def test_every_referenced_image_exists(self):
        """
        A missing image is invisible at runtime, so it has to fail here.
        """
        for source in IMAGE_PATTERN.findall(read("index.html")):
            assert (WEB_ROOT / source).is_file(), source

    def test_every_css_url_resolves(self):
        """
        Backgrounds and fonts referenced by the stylesheet must ship with it.
        """
        for reference in CSS_URL_PATTERN.findall(read("app.css")):
            if reference.startswith(("data:", "http:", "https:", "//")):
                continue
            assert (WEB_ROOT / reference).is_file(), reference

    def test_no_undefined_css_variables(self):
        """
        A ``var(--x)`` with no declaration silently drops the whole property.
        """
        stylesheet = read("app.css")
        declared = set(re.findall(r"(--[\w-]+)\s*:", stylesheet))
        used = set(re.findall(r"var\((--[\w-]+)", stylesheet))
        assert used <= declared, used - declared

    def test_configured_panels_are_defined(self):
        config = read("config.js")
        configured = set(re.findall(r"'([\w-]+)'", config.split("layout", 1)[1]))
        defined = set()
        for panel_js in WEB_ROOT.glob("panels/*/panel.js"):
            defined |= set(
                re.findall(r"Panels\.define\('([\w-]+)'", panel_js.read_text())
            )
        assert configured <= defined, configured - defined

    def test_panels_only_query_their_own_root(self):
        """
        A panel owns its DOM subtree; a document-level lookup couples it to the shell
        and to whichever other panel happens to use the same id.
        """
        for panel_js in panel_scripts():
            source = panel_js.read_text()
            assert "document.getElementById" not in source, panel_js.name
            assert "document.querySelector" not in source, panel_js.name

    def test_no_stale_static_urls(self):
        # the old repo served under /static/; the packaged app is rooted at /
        for panel_js in panel_scripts():
            assert "'static/" not in panel_js.read_text(), panel_js.name


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
class TestJsUnits:
    def run_node(self, name: str) -> None:
        """
        Run one node test file, failing with its output.
        """
        result = subprocess.run(
            ["node", "--test", str(JS_DIR / name)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_bus_and_registry(self):
        self.run_node("test_bus_registry.js")

    def test_graph_status_rendering(self):
        self.run_node("test_graph_status.js")

    def test_graph_panel(self):
        self.run_node("test_graph_panel.js")

    def test_response_util(self):
        self.run_node("test_response_util.js")

    def test_scene_context(self):
        self.run_node("test_scene_context.js")

    def test_query_source_routing(self):
        self.run_node("test_query_source.js")

    def test_run_control_buttons(self):
        self.run_node("test_run_control.js")

    def test_live_attach_decision(self):
        self.run_node("test_live_attach.js")

    def test_replay(self):
        self.run_node("test_replay.js")

    def test_highlight_arrow(self):
        self.run_node("test_highlight_arrow.js")

    def test_answer_table(self):
        self.run_node("test_answer_table.js")

    def test_preset_groups(self):
        self.run_node("test_preset_groups.js")

    def test_question_display(self):
        self.run_node("test_question_display.js")

    def test_eql_panel(self):
        self.run_node("test_eql_panel.js")

    def test_voice_capture(self):
        self.run_node("test_voice.js")

    def test_scene_picker(self):
        self.run_node("test_scene_picker.js")

    def test_completion(self):
        self.run_node("test_completion.js")

    def test_collada_mesh(self):
        self.run_node("test_collada_mesh.js")

    def test_environment_theme(self):
        self.run_node("test_environment_theme.js")

    def test_split_sizing(self):
        self.run_node("test_split_sizing.js")

    def test_split_resize(self):
        self.run_node("test_split_resize.js")

    def test_graph_gestures(self):
        self.run_node("test_graph_gestures.js")

    def test_joint_routing(self):
        self.run_node("test_joint_routing.js")


class TestSceneHighlightVisibility:
    """
    A highlighted object must be unmissable: the scene panel hangs a bouncing arrow over
    it, driven by the shared pure module so the animation stays testable.
    """

    def test_the_arrow_module_ships_with_the_shell(self):
        assert 'src="core/highlight_arrow.js"' in read("index.html")

    def test_the_panel_places_and_animates_the_arrow_from_the_shared_module(self):
        panel = read("panels/robot_scene/panel.js")
        assert "HighlightArrow.restAltitude" in panel
        assert "HighlightArrow.bobOffset" in panel

    def test_the_ssao_pass_is_sized_by_the_composer_alone(self):
        """
        ``composer.setSize`` already resizes every pass at device resolution; an extra
        CSS-pixel ``ssaoPass.setSize`` would shrink the rendered image back down and
        blur the whole scene on high-density screens.
        """
        assert "ssaoPass.setSize" not in read("panels/robot_scene/panel.js")


class TestQueryPanelReadsTheAnswer:
    """
    The answer payload is produced in Python and consumed in JavaScript, so a renamed
    key drifts silently until someone opens the panel.
    """

    def test_the_panel_reads_the_verbalization_under_the_key_it_is_sent_as(self):
        payload = RenderResult(
            kind="rows", rows=[], count=0, more=False, highlight=[]
        ).to_payload()

        assert "verbalization" in payload
        assert "res.verbalization" in read("panels/eql/panel.js")

    def test_the_replay_windows_are_read_from_where_they_are_sent(self):
        """
        An answer carries its replay windows beside its rows (see
        :attr:`~cramera.knowledge.query_runner.RenderResult.replay`); the table pairs
        each with its row and the panel builds the replay button from it.
        """
        assert "res.replay" in read("panels/eql/panel.js")
        assert "row.replay" in read("panels/eql/panel.js")

    def test_the_preset_verbalization_is_read_under_the_key_it_is_sent_as(self):
        """
        A preset travels as its ``asdict`` shape, so the question display must read the
        wording under the same key the dataclass carries it as.
        """
        payload = asdict(Preset("which robot is this?", "the(entity(robot))"))

        assert "verbalization" in payload
        assert "question.verbalization" in read("core/question_display.js")

    def test_the_question_display_sits_under_the_query_bar(self):
        """
        The query bar keeps its input box; underneath it the asked question is shown big
        as English, and the stylesheet styles both the display and the documentation
        links inside it.
        """
        panel = read("panels/eql/panel.js")
        assert 'class="query-bar"' in panel
        assert "<textarea" in panel
        assert 'class="question"' in panel
        stylesheet = read("app.css")
        assert ".question{" in stylesheet
        assert ".question a{" in stylesheet

    def test_the_question_match_is_read_under_the_keys_it_is_sent_as(self):
        """
        The match outcome is produced in Python and consumed by the panel's voice
        consumer, so its keys are pinned across the boundary.
        """
        matched = QuestionMatchResult(
            preset=Preset("which robot is this?", "the(entity(robot))"),
            similarity=90.0,
        ).to_payload()
        unmatched = QuestionMatchResult(preset=None, similarity=10.0).to_payload()
        panel = read("panels/eql/panel.js")

        assert {"matched", "preset", "similarity"} <= matched.keys()
        assert {"matched", "reply"} <= unmatched.keys()
        assert "res.matched" in panel
        assert "res.preset" in panel
        assert "res.reply" in panel

    def test_the_sorry_reply_has_one_source_and_it_is_not_the_frontend(self):
        """
        The reply travels in the payload, so the panel never carries a second copy that
        could drift from :data:`UNMATCHED_QUESTION_REPLY`.
        """
        assert UNMATCHED_QUESTION_REPLY not in read("panels/eql/panel.js")

    def test_the_voice_button_sits_in_the_query_bar_and_is_styled(self):
        """
        The record button lives inside the text bar, beside Run.
        """
        panel = read("panels/eql/panel.js")
        bar = panel.split('class="query-bar"', 1)[1].split("</div>", 1)[0]
        assert 'id="query-run"' in bar
        assert bar.index('id="query-run"') < bar.index('id="voice-ask"')
        assert "voice:transcript" in panel
        stylesheet = read("app.css")
        assert ".voice-ask{" in stylesheet
        assert ".voice-ask.listening" in stylesheet


class TestQueryPanelHints:
    """
    The EQL panel hard-codes the variable names it tells users to type, so a rename in
    the EQL namespace silently leaves the panel advertising names that no longer
    resolve.
    """

    def advertised_variables(self) -> List[str]:
        """
        Every EQL variable name the query panel offers the user.
        """
        panel = read("panels/eql/panel.js")
        [listed] = ADVERTISED_VARIABLES_PATTERN.findall(panel)
        names = [name.strip() for name in listed.split(",")]
        return sorted(set(names) | set(MARKED_UP_IDENTIFIER_PATTERN.findall(panel)))

    def test_every_advertised_variable_exists_in_the_namespace(self, fixture_scene):
        namespace = EqlSession.of_active_scene().namespace()
        assert self.advertised_variables()
        for name in self.advertised_variables():
            assert name in namespace, name

    def test_the_placeholder_query_runs(self, fixture_scene):
        """
        The query shown in the empty input box must be one a user can actually run.
        """
        placeholder = PLACEHOLDER_QUERY_PATTERN.search(read("panels/eql/panel.js"))
        assert placeholder is not None
        result = EqlSession.of_active_scene().run(
            placeholder.group(1).replace("\\'", "'")
        )
        assert result.ok
