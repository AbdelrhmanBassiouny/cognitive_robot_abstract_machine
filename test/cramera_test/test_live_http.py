"""
End-to-end tests of the live bridge's HTTP layer.

Every endpoint is served against an explicitly injected :class:`Bridge`, never the
module-level ``BRIDGE`` singleton — the concrete proof that
:class:`BridgeRequestHandler` and :func:`serve` no longer read a shared global.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import asdict

import pytest

from cramera.live.bridge import Bridge, WorldStateSnapshot
from cramera.live.http import serve

from .test_live_bridge import PublishedBody
from .test_server import get, get_json, post_json


@pytest.fixture()
def bridge():
    return Bridge()


@pytest.fixture()
def server(bridge):
    """
    A real server on an ephemeral port, bound to ``bridge``.
    """
    httpd = serve(bridge, 0)
    yield "http://localhost:%d" % httpd.server_address[1]
    httpd.shutdown()


@pytest.fixture()
def query_bridge(bridge):
    """
    The bridge with a demo's queryable state registered on it.
    """
    krrood = pytest.importorskip("krrood", reason="EQL requires krrood")  # noqa: F841
    from .test_live_query import GrowingRecordSource, make_record

    bridge.register_query_source(
        GrowingRecordSource(
            records=[make_record("first")], stored=[make_record("last week")]
        )
    )
    return bridge


def publish_mesh_object(
    bridge, tmp_path, key="milk.stl", content=b"solid milk endsolid"
):
    """
    Publish one mesh-backed object on ``bridge``, with a real file behind it.
    """
    mesh_file = tmp_path / key
    mesh_file.write_bytes(content)
    bridge.remember_mesh_file(str(mesh_file))
    bridge.publish_bodies({key: PublishedBody(name="world/" + key)})
    return mesh_file


class TestReadOnlyEndpoints:
    def test_state_reflects_a_fresh_bridge(self, server):
        assert get_json(server + "/state") == {
            "sequenceNumber": 0,
            "frames": {},
            "base": None,
            "objects": {},
        }

    def test_plan_reflects_a_fresh_bridge(self, server):
        assert get_json(server + "/plan")["nodes"] == []

    def test_chart_reflects_a_fresh_bridge(self, server):
        chart = get_json(server + "/chart")
        assert chart["nodes"] == []
        assert chart["edges"] == []

    def test_objects_reflects_the_injected_bridges_catalog(
        self, server, bridge, tmp_path
    ):
        publish_mesh_object(bridge, tmp_path)
        payload = get_json(server + "/objects")
        assert [entry["key"] for entry in payload["objects"]] == ["milk.stl"]

    def test_info_reflects_a_fresh_bridge(self, server):
        assert get_json(server + "/info") == {
            "running": False,
            "robot": None,
            "objects": [],
            "movable": True,
            "plan": False,
            "chart": False,
            "query": False,
            "events": False,
            "control": None,
            "sequenceNumber": 0,
            "partAnnotations": [],
        }

    def test_unknown_get_path_is_404(self, server):
        with pytest.raises(urllib.error.HTTPError) as error:
            get(server + "/nope")
        assert error.value.code == 404


class TestMesh:
    def test_a_published_meshs_bytes_are_served(self, server, bridge, tmp_path):
        publish_mesh_object(bridge, tmp_path, content=b"solid milk endsolid")
        status, body = get(server + "/mesh?key=milk.stl")
        assert status == 200
        assert body == b"solid milk endsolid"

    def test_an_unknown_mesh_key_is_404(self, server):
        with pytest.raises(urllib.error.HTTPError) as error:
            get(server + "/mesh?key=nope.stl")
        assert error.value.code == 404


class TestModels:
    def test_models_reflects_a_fresh_bridge(self, server):
        assert get_json(server + "/models") == {"models": []}

    def test_models_reports_a_remembered_source(self, server, bridge, tmp_path):
        urdf = tmp_path / "pr2.urdf"
        urdf.write_text('<robot name="demo">\n  <link name="base_link"/>\n</robot>\n')
        bridge.remember_urdf_source(str(urdf))

        assert get_json(server + "/models") == {
            "models": [{"index": 0, "prefix": "", "robot": False}]
        }

    def test_model_urdf_serves_the_rewritten_text(self, server, bridge, tmp_path):
        urdf = tmp_path / "pr2.urdf"
        urdf.write_text(
            '<robot name="demo">\n'
            '  <link name="base_link">\n'
            "    <visual><geometry>\n"
            '      <mesh filename="meshes/cup.stl"/>\n'
            "    </geometry></visual>\n"
            "  </link>\n"
            "</robot>\n"
        )
        bridge.remember_urdf_source(str(urdf))

        status, body = get(server + "/model_urdf?model=0")

        assert status == 200
        assert b'filename="model_mesh/0/0.stl"' in body

    def test_an_out_of_range_model_urdf_is_404(self, server):
        with pytest.raises(urllib.error.HTTPError) as error:
            get(server + "/model_urdf?model=0")
        assert error.value.code == 404

    def test_model_mesh_serves_the_resolved_file(self, server, bridge, tmp_path):
        (tmp_path / "meshes").mkdir()
        (tmp_path / "meshes" / "cup.stl").write_bytes(b"solid cup endsolid")
        urdf = tmp_path / "pr2.urdf"
        urdf.write_text(
            '<robot name="demo">\n'
            '  <link name="base_link">\n'
            "    <visual><geometry>\n"
            '      <mesh filename="meshes/cup.stl"/>\n'
            "    </geometry></visual>\n"
            "  </link>\n"
            "</robot>\n"
        )
        bridge.remember_urdf_source(str(urdf))

        status, body = get(server + "/model_mesh/0/0.stl")

        assert status == 200
        assert body == b"solid cup endsolid"

    def test_an_out_of_range_model_mesh_is_404(self, server, bridge, tmp_path):
        urdf = tmp_path / "pr2.urdf"
        urdf.write_text('<robot name="demo">\n  <link name="base_link"/>\n</robot>\n')
        bridge.remember_urdf_source(str(urdf))

        with pytest.raises(urllib.error.HTTPError) as error:
            get(server + "/model_mesh/0/9.stl")
        assert error.value.code == 404


class TestMove:
    def test_a_valid_move_is_queued_on_the_injected_bridge(self, server, bridge):
        request = urllib.request.Request(
            server + "/move",
            method="POST",
            data=json.dumps(
                {"object": "milk.stl", "position": [1.0, 2.0, 3.0]}
            ).encode(),
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            assert response.status == 200
            assert json.loads(response.read()) == {"ok": True}
        assert [move.object_key for move in bridge._moves] == ["milk.stl"]

    def test_a_malformed_move_is_rejected_without_touching_the_bridge(
        self, server, bridge
    ):
        request = urllib.request.Request(
            server + "/move",
            method="POST",
            data=json.dumps({"object": "milk.stl"}).encode(),
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                status, body = response.status, response.read()
        except urllib.error.HTTPError as error:
            status, body = error.code, error.read()
        assert status == 400
        assert json.loads(body)["ok"] is False
        assert bridge._moves == []

    def test_unknown_post_path_is_404(self, server):
        request = urllib.request.Request(server + "/nope", method="POST", data=b"{}")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                status = response.status
        except urllib.error.HTTPError as error:
            status = error.code
        assert status == 404


class TestQueryEndpoints:
    """
    The panel asks the running demo itself, over the same bridge it polls for state.
    """

    def test_presets_are_the_registered_sources(self, server, query_bridge):
        # the wording is the bridge's own (see TestWordedLivePresets); the payload has
        # to carry it under the key the panel reads, next to the preset's own fields
        worded = [asdict(preset) for preset in query_bridge.query_presets()]
        assert all(entry["verbalization"] is not None for entry in worded)
        assert get_json(server + "/presets") == {
            "ok": True,
            "title": "record demo",
            "presets": [
                {
                    "text": "all records",
                    "code": "an(entity(record))",
                    "requires_live": False,
                    "scope": "current_state",
                    "verbalization": worded[0]["verbalization"],
                },
                {
                    "text": "everything stored",
                    "code": "an(entity(stored_record))",
                    "requires_live": False,
                    "scope": "episodic_memory",
                    "verbalization": worded[1]["verbalization"],
                },
            ],
            "scopes": [
                {
                    "name": "current_state",
                    "label": "Current State Queries",
                    "variables": ["record"],
                },
                {
                    "name": "episodic_memory",
                    "label": "Episodic Memory Queries",
                    "variables": ["stored_record"],
                },
            ],
            "variables": ["record"],
        }

    def test_a_query_is_answered_from_the_scope_it_names(self, server, query_bridge):
        payload = post_json(
            server + "/eql",
            {"code": "an(entity(stored_record))", "scope": "episodic_memory"},
        )

        assert payload["ok"] is True
        assert [row["__entity__"] for row in payload["rows"]] == ["last week"]

    def test_a_query_naming_no_scope_asks_the_current_state(self, server, query_bridge):
        payload = post_json(server + "/eql", {"code": "an(entity(record))"})

        assert [row["__entity__"] for row in payload["rows"]] == ["first"]

    def test_a_query_of_a_scope_the_demo_does_not_offer_reports_why(
        self, server, query_bridge
    ):
        payload = post_json(
            server + "/eql", {"code": "an(entity(record))", "scope": "yesterday"}
        )

        assert payload["ok"] is False
        assert "yesterday" in payload["error"]

    def test_presets_without_a_source_report_why(self, server):
        payload = get_json(server + "/presets")
        assert payload["ok"] is False
        assert payload["presets"] == []

    def test_a_query_is_answered_from_the_running_demo(self, server, query_bridge):
        payload = post_json(server + "/eql", {"code": "an(entity(record))"})

        assert payload["ok"] is True
        assert [row["__entity__"] for row in payload["rows"]] == ["first"]

    def test_info_announces_that_querying_is_available(self, server, query_bridge):
        assert get_json(server + "/info")["query"] is True

    def test_a_broken_query_is_reported_rather_than_crashing_the_handler(
        self, server, query_bridge
    ):
        payload = post_json(server + "/eql", {"code": "definitely not python ((("})

        assert payload["ok"] is False
        assert "SyntaxError" in payload["error"]

    def test_an_empty_query_is_rejected(self, server, query_bridge):
        assert post_json(server + "/eql", {"code": "   "})["ok"] is False

    def test_a_query_without_a_source_reports_why(self, server):
        payload = post_json(server + "/eql", {"code": "an(entity(record))"})

        assert payload["ok"] is False
        assert "no query source" in payload["error"].lower()


class TestAskedQuestionsOverTheBridge:
    """
    A spoken question about the running demo is matched against the demo's own presets
    and either runs as if clicked or is declined with the sorry reply.
    """

    def test_the_full_voice_flow_runs_the_matched_preset(self, server, query_bridge):
        """
        The whole journey minus the microphone: transcript in, matched preset out, the
        preset's code and scope posted back — exactly what clicking its button runs —
        and answered from the demo.
        """
        match = post_json(server + "/question", {"text": "show me all records"})

        assert match["ok"] is True
        assert match["matched"] is True
        assert match["preset"]["code"] == "an(entity(record))"

        answer = post_json(
            server + "/eql",
            {"code": match["preset"]["code"], "scope": match["preset"]["scope"]},
        )
        assert answer["ok"] is True
        assert [row["__entity__"] for row in answer["rows"]] == ["first"]

    def test_a_question_about_stored_runs_matches_its_own_scope(
        self, server, query_bridge
    ):
        match = post_json(server + "/question", {"text": "everything stored"})

        assert match["matched"] is True
        assert match["preset"]["code"] == "an(entity(stored_record))"
        assert match["preset"]["scope"] == "episodic_memory"

    def test_an_unanswerable_question_gets_the_sorry_reply(self, server, query_bridge):
        from cramera.knowledge.question_matching import UNMATCHED_QUESTION_REPLY

        match = post_json(server + "/question", {"text": "open the pod bay doors"})

        assert match["ok"] is True
        assert match["matched"] is False
        assert match["reply"] == UNMATCHED_QUESTION_REPLY

    def test_an_empty_question_is_rejected(self, server, query_bridge):
        assert post_json(server + "/question", {"text": "   "})["ok"] is False

    def test_a_body_that_is_not_an_object_is_a_400(self, server, query_bridge):
        assert post_json(server + "/question", ["not", "an", "object"])["ok"] is False

    def test_a_question_without_a_source_reports_why(self, server):
        payload = post_json(server + "/question", {"text": "which robot is this"})

        assert payload["ok"] is False
        assert "no query source" in payload["error"].lower()


class TestRunControlEndpoints:
    """
    The viewer drives the demo over the same bridge it polls for state.
    """

    @pytest.fixture()
    def controlled_bridge(self, bridge):
        from .test_live_run_control import RecordingRunControl

        control = RecordingRunControl()
        bridge.register_run_control(control)
        return bridge, control

    def test_the_run_state_is_served(self, server, controlled_bridge):
        payload = get_json(server + "/run")

        assert payload["ok"] is True
        assert payload["title"] == "record demo"
        assert payload["paused"] is False

    def test_the_run_state_without_a_demo_reports_why(self, server):
        payload = get_json(server + "/run")

        assert payload["ok"] is False
        assert "no run control" in payload["error"].lower()

    def test_a_command_reaches_the_demo(self, server, controlled_bridge):
        _, control = controlled_bridge

        payload = post_json(server + "/run", {"command": "pause"})

        assert payload["ok"] is True
        assert payload["paused"] is True
        assert [command.value for command in control.applied] == ["pause"]

    def test_an_unknown_command_is_refused_rather_than_ignored(
        self, server, controlled_bridge
    ):
        _, control = controlled_bridge

        payload = post_json(server + "/run", {"command": "self_destruct"})

        assert payload["ok"] is False
        assert "self_destruct" in payload["error"]
        assert control.applied == []

    def test_a_command_without_a_demo_reports_why(self, server):
        payload = post_json(server + "/run", {"command": "pause"})

        assert payload["ok"] is False
        assert "no run control" in payload["error"].lower()

    def test_info_carries_the_run_state_the_controls_render(
        self, server, controlled_bridge
    ):
        post_json(server + "/run", {"command": "enable_loop"})

        assert get_json(server + "/info")["control"]["looping"] is True


class TestReplay:
    def test_recorded_frames_within_the_window_are_served(self, server, bridge):
        bridge.recording.record(100.0, WorldStateSnapshot(sequence_number=1))

        assert get_json(server + "/replay?start=99&end=101") == {
            "ok": True,
            "start": 99.0,
            "end": 101.0,
            "frames": [{"at": 100.0, "frames": {}, "base": None, "objects": {}}],
        }

    def test_an_unrecorded_window_is_empty_rather_than_an_error(self, server):
        payload = get_json(server + "/replay?start=0&end=1")

        assert payload["ok"] is True
        assert payload["frames"] == []

    def test_a_window_missing_a_bound_is_rejected(self, server):
        with pytest.raises(urllib.error.HTTPError) as error:
            get(server + "/replay?start=5")
        assert error.value.code == 400

    def test_a_backwards_window_is_rejected(self, server):
        with pytest.raises(urllib.error.HTTPError) as error:
            get(server + "/replay?start=5&end=4")
        assert error.value.code == 400


class TestOptions:
    def test_preflight_returns_cors_headers(self, server):
        request = urllib.request.Request(server + "/move", method="OPTIONS")
        with urllib.request.urlopen(request, timeout=10) as response:
            assert response.status == 204
            assert response.headers["Access-Control-Allow-Origin"] == "*"
            assert "POST" in response.headers["Access-Control-Allow-Methods"]


class TestDetectedEvents:
    """
    The timeline polls the same bridge the rest of the viewer does.
    """

    @pytest.fixture()
    def watching_bridge(self, bridge):
        from .test_live_events import ReportingEventSource, event_at

        source = ReportingEventSource(detected=[event_at(1), event_at(2)])
        bridge.register_event_source(source)
        return bridge, source

    def test_the_detections_are_served(self, server, watching_bridge):
        _, source = watching_bridge

        payload = get_json(server + "/events")

        assert payload["ok"] is True
        assert payload["title"] == "record demo"
        assert payload["events"] == [event.to_payload() for event in source.detected]

    def test_the_detections_without_a_demo_report_why(self, server):
        payload = get_json(server + "/events")

        assert payload["ok"] is False
        assert "no event source" in payload["error"].lower()
        assert payload["events"] == []

    def test_info_says_whether_anything_is_detecting(self, server, watching_bridge):
        assert get_json(server + "/info")["events"] is True


class TestTwoIndependentBridges:
    def test_each_server_reflects_only_its_own_bridge(self, tmp_path):
        first_bridge, second_bridge = Bridge(), Bridge()
        publish_mesh_object(first_bridge, tmp_path, key="milk.stl")
        publish_mesh_object(second_bridge, tmp_path, key="cup.stl")
        first_server = serve(first_bridge, 0)
        second_server = serve(second_bridge, 0)
        try:
            first_url = "http://localhost:%d" % first_server.server_address[1]
            second_url = "http://localhost:%d" % second_server.server_address[1]
            first_objects = get_json(first_url + "/objects")["objects"]
            second_objects = get_json(second_url + "/objects")["objects"]
            assert [entry["key"] for entry in first_objects] == ["milk.stl"]
            assert [entry["key"] for entry in second_objects] == ["cup.stl"]
        finally:
            first_server.shutdown()
            second_server.shutdown()


class TestVocabularyEndpoints:
    """
    While a demo is attached, the query box asks the demo what it may name.
    """

    @pytest.fixture()
    def query_bridge(self, bridge):
        pytest.importorskip("krrood", reason="EQL requires krrood")
        from .test_live_query import GrowingRecordSource, make_record

        bridge.register_query_source(
            GrowingRecordSource(
                records=[make_record("first")], stored=[make_record("last week")]
            )
        )
        return bridge

    def test_the_vocabulary_offers_the_demos_own_variables(self, server, query_bridge):
        payload = get_json(server + "/vocabulary")

        assert payload["ok"]
        offered = {entry["name"]: entry for entry in payload["entries"]}
        assert offered["record"]["kind"] == "variable"
        assert offered["record"]["type"] == "NamedRecord"

    def test_the_vocabulary_of_a_scope_offers_that_scopes_variables(
        self, server, query_bridge
    ):
        payload = get_json(server + "/vocabulary?scope=episodic_memory")

        offered = [entry["name"] for entry in payload["entries"]]
        assert "stored_record" in offered and "record" not in offered

    def test_the_members_of_a_variable_are_served_for_its_type(
        self, server, query_bridge
    ):
        payload = get_json(server + "/members?name=record")

        assert payload["ok"] and payload["name"] == "record"
        assert "name" in [member["name"] for member in payload["members"]]

    def test_a_vocabulary_without_a_source_reports_why(self, server):
        payload = get_json(server + "/vocabulary")

        assert payload["ok"] is False
        assert payload["entries"] == []
