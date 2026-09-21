"""
Unit tests for serving a live world's own model geometry with no on-disk bundle.
"""

from __future__ import annotations

from pathlib import Path

from cramera.live import model_source
from cramera.live.model_source import LiveModelCatalog

ONE_MESH_URDF_TEXT = (
    '<robot name="demo">\n'
    '  <link name="base_link"/>\n'
    '  <link name="cup_link">\n'
    "    <visual><geometry>\n"
    '      <mesh filename="meshes/cup.dae"/>\n'
    "    </geometry></visual>\n"
    "  </link>\n"
    '  <joint name="cup_joint" type="fixed">\n'
    '    <parent link="base_link"/><child link="cup_link"/>\n'
    "  </joint>\n"
    "</robot>\n"
)
"""
A URDF referencing exactly one mesh, relative to the URDF's own directory.

``.dae``, not ``.stl``: the vendored URDFLoader dispatches to a mesh loader by regex-
matching the *trailing characters* of the URL, so a rewritten reference must keep the
real extension right at the end — a bug this exact fixture caught once already.
"""

PLUGIN_REFERENCE_URDF_TEXT = (
    '<robot name="demo">\n'
    '  <link name="base_link"/>\n'
    '  <gazebo>\n'
    '    <plugin filename="libgazebo_ros_control.so" name="control"/>\n'
    "  </gazebo>\n"
    "</robot>\n"
)
"""
A URDF whose only ``filename="..."`` attribute is a plugin, not a mesh.
"""


def _written(path: Path, text: str) -> Path:
    """
    Write a source file and return its path.

    :param path: Where the file goes.
    :param text: Its content.
    """
    path.write_text(text)
    return path


class TestRemember:
    def test_a_source_is_remembered_once(self):
        catalog = LiveModelCatalog()

        catalog.remember("/robots/pr2.urdf")
        catalog.remember("/robots/pr2.urdf")

        assert catalog.sources == ["/robots/pr2.urdf"]

    def test_sources_are_kept_in_load_order(self):
        catalog = LiveModelCatalog()

        catalog.remember("/worlds/kitchen.urdf")
        catalog.remember("/robots/pr2.urdf")

        assert catalog.sources == ["/worlds/kitchen.urdf", "/robots/pr2.urdf"]


class TestModels:
    def test_the_robot_source_is_flagged_and_prefixed(self, tmp_path):
        catalog = LiveModelCatalog()
        catalog.remember(str(_written(tmp_path / "pr2.urdf", ONE_MESH_URDF_TEXT)))

        [model] = catalog.models(
            world_body_names=["pr2_1/base_link", "pr2_1/cup_link"],
            base_body="base_link",
        )

        assert model.robot is True
        assert model.prefix == "pr2_1"

    def test_an_environment_source_is_not_the_robot(self, tmp_path):
        catalog = LiveModelCatalog()
        catalog.remember(str(_written(tmp_path / "kitchen.urdf", ONE_MESH_URDF_TEXT)))

        [model] = catalog.models(
            world_body_names=["kitchen_1/base_link", "kitchen_1/cup_link"],
            base_body="other_robot_base",
        )

        assert model.robot is False

    def test_no_bound_robot_means_nothing_is_the_robot(self, tmp_path):
        catalog = LiveModelCatalog()
        catalog.remember(str(_written(tmp_path / "pr2.urdf", ONE_MESH_URDF_TEXT)))

        [model] = catalog.models(world_body_names=["base_link"], base_body=None)

        assert model.robot is False


class TestUrdfText:
    def test_the_mesh_reference_is_rewritten_to_a_servable_url_with_its_extension(
        self, tmp_path
    ):
        catalog = LiveModelCatalog()
        catalog.remember(str(_written(tmp_path / "pr2.urdf", ONE_MESH_URDF_TEXT)))

        text = catalog.urdf_text(0)

        assert 'filename="model_mesh/0/0.dae"' in text
        assert "meshes/cup.dae" not in text

    def test_an_out_of_range_index_returns_none(self):
        catalog = LiveModelCatalog()

        assert catalog.urdf_text(0) is None

    def test_a_plugin_filename_is_not_mistaken_for_a_mesh_reference(self, tmp_path):
        catalog = LiveModelCatalog()
        catalog.remember(
            str(_written(tmp_path / "pr2.urdf", PLUGIN_REFERENCE_URDF_TEXT))
        )

        text = catalog.urdf_text(0)

        assert "libgazebo_ros_control.so" in text
        assert "model_mesh" not in text


class TestMeshPath:
    def test_a_reference_resolves_relative_to_its_source_directory(self, tmp_path):
        catalog = LiveModelCatalog()
        (tmp_path / "meshes").mkdir()
        mesh = _written(tmp_path / "meshes" / "cup.dae", "<COLLADA/>")
        catalog.remember(str(_written(tmp_path / "pr2.urdf", ONE_MESH_URDF_TEXT)))

        resolved = catalog.mesh_path(0, 0)

        assert resolved == str(mesh)

    def test_an_out_of_range_model_index_returns_none(self, tmp_path):
        catalog = LiveModelCatalog()
        catalog.remember(str(_written(tmp_path / "pr2.urdf", ONE_MESH_URDF_TEXT)))

        assert catalog.mesh_path(1, 0) is None

    def test_an_out_of_range_reference_index_returns_none(self, tmp_path):
        catalog = LiveModelCatalog()
        catalog.remember(str(_written(tmp_path / "pr2.urdf", ONE_MESH_URDF_TEXT)))

        assert catalog.mesh_path(0, 1) is None


class TestReadCaching:
    """
    A source's text is parsed at most once — expanding a xacro file (the PR2
    description, in practice) is slow enough that re-expanding it per request makes live
    model serving unusable.
    """

    def test_a_xacro_source_is_expanded_at_most_once(self, monkeypatch):
        call_count = {"n": 0}

        class CountingURDFParser:
            @classmethod
            def from_xacro(cls, path):
                call_count["n"] += 1
                parsed = type("Parsed", (), {})()
                parsed.urdf = ONE_MESH_URDF_TEXT
                return parsed

        monkeypatch.setattr(model_source, "URDFParser", CountingURDFParser)
        catalog = LiveModelCatalog()
        catalog.remember("/robots/pr2.xacro")

        catalog.models(world_body_names=["base_link"], base_body="base_link")
        catalog.urdf_text(0)
        catalog.mesh_path(0, 0)

        assert call_count["n"] == 1


class TestXacroSource:
    def test_a_xacro_source_is_read_like_a_urdf_source(self, tmp_path):
        """
        The same URDF content, saved with a ``.xacro`` extension, is expanded through
        :meth:`URDFParser.from_xacro` rather than read as plain text.
        """
        catalog = LiveModelCatalog()
        catalog.remember(str(_written(tmp_path / "pr2.xacro", ONE_MESH_URDF_TEXT)))

        [model] = catalog.models(world_body_names=["base_link"], base_body="base_link")

        assert model.robot is True
        assert 'filename="model_mesh/0/0.dae"' in catalog.urdf_text(0)
