"""
End-to-end tests of the HTTP server: static frontend, scenes and JSON API.
"""

import importlib
import json
import threading
import urllib.error
import urllib.request

import pytest

from cramera import paths

from .conftest import reset_knowledge_base_cache


@pytest.fixture()
def server(fixture_scene):
    """
    The real server on an ephemeral port, bound to the fixture scene.
    """
    from cramera import server as server_module

    importlib.reload(server_module)  # rebind knowledge_module under the fixture env
    httpd = server_module.make_server(0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield "http://localhost:%d" % httpd.server_address[1]
    httpd.shutdown()


def get(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.status, response.read()


def get_json(url):
    status, body = get(url)
    assert status == 200
    return json.loads(body)


def post_json(url, payload):
    """
    POST ``payload`` as JSON and return the decoded answer, error responses included.

    :param url: The endpoint to post to.
    :param payload: The JSON-serializable request body.
    """
    request = urllib.request.Request(
        url,
        method="POST",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        return json.loads(error.read())


class TestStatic:
    def test_index_is_served(self, server):
        status, body = get(server + "/")
        assert status == 200
        assert b"CRAM Visualization" in body
        assert b'data-slot="left"' in body

    def test_panel_scripts_are_served(self, server):
        for path in (
            "/core/bus.js",
            "/core/registry.js",
            "/config.js",
            "/panels/robot_scene/panel.js",
            "/panels/eql/panel.js",
            "/panels/graph/panel.js",
            "/panels/graph/graph.js",
        ):
            status, _ = get(server + path)
            assert status == 200, path

    def test_scene_bundle_is_served_from_data_dir(self, server):
        scene = get_json(server + "/scenes/fixture/scene.json")
        assert scene["name"] == "fixture"
        index = get_json(server + "/scenes/index.json")
        assert index["default"] == "fixture"

    def test_a_static_asset_may_not_be_stored_by_the_browser(self, server):
        """
        The frontend is edited while a browser holds it open, and the only cache
        validator this server offers is the file's modification time — so a stored copy
        outlives every edit that leaves that time behind the date the copy carries.

        Forbidding the store is what keeps an edited frontend from being served from an
        old page load.
        """
        with urllib.request.urlopen(server + "/config.js", timeout=10) as response:
            assert response.headers["Cache-Control"] == "no-store"

    def test_scene_path_traversal_is_blocked(self, server):
        request = urllib.request.Request(server + "/scenes/../../etc/passwd")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                status = response.status
        except urllib.error.HTTPError as err:
            status = err.code
        assert status in (403, 404)


class TestApi:
    def test_knowledge_overview(self, server):
        pytest.importorskip("krrood")
        payload = get_json(server + "/api/knowledge")
        assert payload["ok"]
        assert any(n["id"] == "milk" for n in payload["nodes"])

    def test_knowledge_overview_presets_are_worded(self, server):
        """
        The overview's presets carry their questions read back as English, so the
        panel's question display has words to show before a query has run.
        """
        pytest.importorskip("krrood")
        payload = get_json(server + "/api/knowledge")
        preset = next(
            entry
            for entry in payload["presets"]
            if entry["text"] == "which robot is this?"
        )
        assert preset["verbalization"]["text"]
        assert "<span" in preset["verbalization"]["html"]

    def test_knowledge_views(self, server):
        pytest.importorskip("krrood")
        for name, expect_live in (
            ("kinematics", None),
            ("plan", None),  # the plan panel knows its own live source
            ("chart", "chart"),
        ):
            payload = get_json(server + "/api/knowledge/view?name=" + name)
            assert payload["ok"], name
            assert payload.get("live") == expect_live

    def test_eql_query_roundtrip(self, server):
        pytest.importorskip("krrood")
        request = urllib.request.Request(
            server + "/api/eql",
            data=json.dumps(
                {"code": "the(entity(scene_object).where(scene_object.name == 'milk'))"}
            ).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read())
        assert payload["ok"] and payload["count"] == 1

    def test_broken_query_returns_json_error(self, server):
        pytest.importorskip("krrood")
        request = urllib.request.Request(
            server + "/api/eql",
            data=json.dumps({"code": "definitely not python ((("}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read())
        assert payload["ok"] is False and "error" in payload

    def test_unknown_post_endpoint_is_json_404(self, server):
        request = urllib.request.Request(server + "/api/nope", data=b"{}")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                status, body = response.status, response.read()
        except urllib.error.HTTPError as err:
            status, body = err.code, err.read()
        assert status == 404
        assert json.loads(body)["ok"] is False


class TestVocabularyApi:
    """
    What the query box is told it may name, served from the recorded scene.
    """

    def test_the_vocabulary_offers_the_scene_variables_and_workspace_classes(
        self, server
    ):
        pytest.importorskip("krrood")
        payload = get_json(server + "/api/eql/vocabulary")

        assert payload["ok"]
        offered = {entry["name"]: entry for entry in payload["entries"]}
        assert offered["scene_object"]["kind"] == "variable"
        assert offered["scene_object"]["type"] == "BenchObject"
        assert offered["entity"]["kind"] == "factory"
        # a class of the scanned architecture, which the fixture keeps miniature
        assert offered["Plan"]["kind"] == "class"
        assert offered["Plan"]["module"] == "coraplex.plans.plan"

    def test_the_members_of_a_variable_are_served_for_its_type(self, server):
        pytest.importorskip("krrood")
        payload = get_json(server + "/api/eql/members?name=scene_object")

        assert payload["ok"] and payload["name"] == "scene_object"
        assert "name" in [member["name"] for member in payload["members"]]

    def test_the_members_of_an_unknown_name_are_refused(self, server):
        pytest.importorskip("krrood")
        payload = get_json(server + "/api/eql/members?name=NoSuchType")

        assert payload["ok"] is False
        assert "NoSuchType" in payload["error"]


class TestAskedQuestions:
    """
    A natural-language question — spoken or typed — is matched to the presets the
    recorded scene can answer, and either runs as if its button had been clicked or is
    declined with the sorry reply.
    """

    def test_a_question_is_recognized_and_its_query_runs(self, server):
        """
        The full voice flow, minus the microphone: transcript in, matched preset out,
        the preset's own code answered — exactly what clicking its button runs.
        """
        pytest.importorskip("krrood")
        match = post_json(server + "/api/question", {"text": "which robot is this"})

        assert match["ok"] is True
        assert match["matched"] is True
        assert match["preset"]["code"] == "the(entity(robot))"

        answer = post_json(server + "/api/eql", {"code": match["preset"]["code"]})
        assert answer["ok"] is True
        assert answer["count"] == 1

    def test_a_paraphrase_is_recognized_too(self, server):
        pytest.importorskip("krrood")
        match = post_json(
            server + "/api/question", {"text": "can you tell me what is in the scene"}
        )

        assert match["matched"] is True
        assert match["preset"]["code"] == "an(entity(scene_object))"

    def test_an_unanswerable_question_gets_the_sorry_reply(self, server):
        pytest.importorskip("krrood")
        from cramera.knowledge.question_matching import UNMATCHED_QUESTION_REPLY

        match = post_json(
            server + "/api/question", {"text": "what's the weather like today"}
        )

        assert match["ok"] is True
        assert match["matched"] is False
        assert match["reply"] == UNMATCHED_QUESTION_REPLY

    def test_an_empty_question_is_an_error(self, server):
        pytest.importorskip("krrood")
        assert post_json(server + "/api/question", {"text": "   "})["ok"] is False

    def test_a_preset_needing_a_running_demo_is_not_offered(self, server):
        """
        A bundle-declared preset ranges over a demo the recording does not have;
        matching it here would hand the panel a query it cannot run.
        """
        pytest.importorskip("krrood")
        bundle_directory = paths.scenes_directory() / "fixture"
        (bundle_directory / "presets.json").write_text(
            json.dumps(
                {
                    "presets": [
                        {
                            "text": "which shapes are inserted?",
                            "code": "an(entity(shape))",
                        }
                    ]
                }
            )
        )
        reset_knowledge_base_cache()

        match = post_json(
            server + "/api/question", {"text": "which shapes are inserted"}
        )

        assert match["matched"] is False
