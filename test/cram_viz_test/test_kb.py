"""
Tests for the scene-driven knowledge base and its graph-panel payloads.
"""

import pytest

krrood = pytest.importorskip("krrood", reason="EQL requires krrood")

from cram_viz import kb  # noqa: E402  (importable once krrood is present)


@pytest.fixture()
def fresh_kb(fixture_scene):
    kb.reset_kb()
    return kb.get_kb()


class TestKB:
    def test_scene_entities(self, fresh_kb):
        assert [o.name for o in fresh_kb.objects] == ["milk", "place_area"]
        assert fresh_kb.robot.name == "pr2"
        assert [a.side for a in fresh_kb.arms] == ["left"]
        assert fresh_kb.arms[0].gripper.name == "left_gripper"

    def test_episodes_link_objects(self, fresh_kb):
        transport = next(e for e in fresh_kb.episodes if e.name == "transport_milk")
        assert transport.picks is fresh_kb.objects[0]
        assert transport.places_at.name == "place_area"
        assert transport.performed_by.side == "left"

    def test_joint_motion_ranges(self, fresh_kb):
        torso = next(j for j in fresh_kb.joints if j.name == "torso_lift_joint")
        assert torso.min_rad == 0.0 and torso.max_rad == 0.3

    def test_architecture_scan(self, fresh_kb):
        names = {p.name for p in fresh_kb.packages}
        assert {"coraplex", "krrood"} <= names
        assert any(c.name == "Plan" for c in fresh_kb.classes)


class TestQueries:
    def test_entity_query(self, fixture_scene):
        result = kb.run_query("the(entity(obj).where(obj.name == 'milk'))")
        assert result["ok"] and result["count"] == 1
        assert result["rows"][0]["__entity__"] == "milk"
        assert "milk" in result["highlight"]

    def test_an_unknown_name_raises(self, fixture_scene):
        """
        A query naming something the namespace does not define must raise.

        The server turns this into a JSON error payload; the knowledge base itself
        does not swallow it.
        """
        with pytest.raises(NameError):
            kb.run_query("this is not python")

    def test_a_syntactically_invalid_query_raises(self, fixture_scene):
        with pytest.raises(SyntaxError):
            kb.run_query("definitely not python (((")


class TestRecordedMeasurements:
    def test_an_unrecorded_height_stays_unknown(self, fresh_kb):
        """
        The fixture bundle records no object height, so none may be invented.
        """
        milk = next(entry for entry in fresh_kb.objects if entry.name == "milk")
        assert milk.height_m is None

    def test_an_unrecorded_gripper_opening_stays_unknown(self, fresh_kb):
        assert fresh_kb.arms[0].gripper.opening_m is None

    def test_a_recorded_height_is_used(self, fixture_scene, monkeypatch):
        """
        A bundle that reports a height must be taken at its word.
        """
        scene, trajectory = kb.load_scene()
        scene["objects"][0]["height"] = 0.23
        monkeypatch.setattr(kb, "load_scene", lambda: (scene, trajectory))
        kb.reset_kb()
        milk = next(entry for entry in kb.get_kb().objects if entry.name == "milk")
        assert milk.height_m == 0.23

    def test_unknown_measurements_are_left_out_of_the_graph(self, fixture_scene):
        """
        A tooltip must not show a height the bundle never recorded.
        """
        payload = kb.view_payload("knowledge")
        milk = payload["details"]["milk"]
        assert not any(line.startswith("height:") for line in milk["lines"])


class TestActionLabelShortening:
    def test_action_suffix_is_dropped(self):
        assert kb.shorten_action_label("TransportAction") == "Transport"

    def test_the_word_action_inside_a_label_is_kept(self):
        assert kb.shorten_action_label("ActionNode") == "ActionNode"

    def test_only_the_trailing_occurrence_is_dropped(self):
        assert kb.shorten_action_label("ActionSequenceAction") == "ActionSequence"

    def test_a_label_that_is_only_the_suffix_is_kept(self):
        assert kb.shorten_action_label("Action") == "Action"


class TestViewPayloads:
    def test_knowledge_view(self, fixture_scene):
        payload = kb.view_payload("knowledge")
        assert payload["ok"]
        ids = {n["id"] for n in payload["nodes"]}
        assert {"pr2", "milk", "transport_milk", "plan"} <= ids
        assert payload["presets"]

    def test_kinematics_view(self, fixture_scene):
        payload = kb.view_payload("kinematics")
        assert payload["ok"]
        ids = {n["id"] for n in payload["nodes"]}
        assert "urdf:base_link" in ids and "urdf:l_gripper_link" in ids
        # fixed joints render dashed ('type'), movable solid ('prop')
        kinds = {e["label"].split(" ")[0]: e["kind"] for e in payload["edges"]}
        assert kinds["torso_lift_joint"] == "prop"
        assert kinds["l_gripper_joint"] == "type"

    def test_kinematics_counts_every_movable_joint(self, fixture_scene):
        """
        The movable-joint tally must match the joints drawn as movable.

        The fixture's ``torso_lift_joint`` is prismatic: movable, but not revolute.
        """
        payload = kb.view_payload("kinematics")
        movable_edges = [edge for edge in payload["edges"] if edge["kind"] == "prop"]
        root_lines = payload["details"]["urdf:base_link"]["lines"]
        summary = next(line for line in root_lines if "movable" in line)
        assert summary.endswith("(%d movable)" % len(movable_edges))

    def test_plan_view_carries_status(self, fixture_scene):
        payload = kb.view_payload("plan")
        assert payload["ok"] and payload["layout"] == "hier"
        assert payload["live"] == "plan" and payload["statusLegend"]
        by_label = {n["label"]: n for n in payload["nodes"]}
        assert by_label["SequentialNode"]["status"] == "SUCCEEDED"
        # recorded inner nodes stay CREATED (only the root is performed)
        assert by_label["Transport"]["status"] == "CREATED"
        assert len(payload["edges"]) == len(payload["nodes"]) - 1

    def test_chart_view_is_live_only(self, fixture_scene):
        payload = kb.view_payload("chart")
        assert payload["ok"] and payload["nodes"] == []
        assert payload["live"] == "chart" and payload["empty"]

    def test_unknown_view(self, fixture_scene):
        payload = kb.view_payload("bogus")
        assert not payload["ok"]
