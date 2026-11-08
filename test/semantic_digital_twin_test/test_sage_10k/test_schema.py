"""
Reading Sage10k layouts into :class:`Sage10kScene`, offline.

The layout is an excerpt of the GYM scene's ``layout_26384448.json`` from NVIDIA's
SAGE-10k dataset (Apache-2.0), trimmed to one room with two objects, two walls, a door
and a window.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from krrood.adapters.json_serializer import from_json, to_json
from semantic_digital_twin.adapters.sage_10k_dataset.loader import (
    Sage10kDatasetLoader,
)
from semantic_digital_twin.adapters.sage_10k_dataset.schema import (
    Sage10kObject,
    Sage10kPosition,
    Sage10kScene,
)
from semantic_digital_twin.adapters.sage_10k_dataset.utils import (
    Sage10kActionableScenes,
)


# %% fixtures


@pytest.fixture
def layout_file() -> Path:
    """
    The layout excerpt the tests read.
    """
    return Path(__file__).parent / "dataset" / "layout_excerpt.json"


@pytest.fixture
def layout(layout_file: Path) -> dict:
    """
    The layout excerpt as the dataset's JSON object.
    """
    return json.loads(layout_file.read_text())


@pytest.fixture
def scene(layout_file: Path, tmp_path: Path) -> Sage10kScene:
    """
    The excerpt read by :meth:`Sage10kDatasetLoader.create_scene` from a download
    directory that already holds the scene, so nothing is downloaded.
    """
    scene_url = str(Sage10kActionableScenes.GYM)
    scene_directory = tmp_path / Path(scene_url).stem
    scene_directory.mkdir()
    shutil.copy(layout_file, scene_directory / "layout_26384448.json")
    return Sage10kDatasetLoader(directory=tmp_path).create_scene(scene_url=scene_url)


# %% reading a layout


def test_scene_holds_every_room_object_wall_and_door_of_the_layout(
    scene: Sage10kScene, layout: dict
):
    """
    Every room, object, wall and door of the layout is read, in the layout's order.
    """
    room_layout = layout["rooms"][0]
    room = scene.rooms[0]

    assert (scene.id, [room.id for room in scene.rooms]) == (
        layout["id"],
        [room_layout["id"]],
    )
    assert [sage_object.id for sage_object in room.objects] == [
        object_layout["id"] for object_layout in room_layout["objects"]
    ]
    assert [wall.id for wall in room.walls] == [
        wall_layout["id"] for wall_layout in room_layout["walls"]
    ]
    assert [door.id for door in room.doors] == [
        door_layout["id"] for door_layout in room_layout["doors"]
    ]


def test_nested_objects_are_read_into_their_classes(scene: Sage10kScene, layout: dict):
    """
    A nested JSON object, such as an object's position, is read into its own class.
    """
    position_layout = layout["rooms"][0]["objects"][0]["position"]

    assert scene.rooms[0].objects[0].position == Sage10kPosition(**position_layout)


def test_scene_remembers_the_directory_it_was_read_from(
    scene: Sage10kScene, tmp_path: Path
):
    """
    The scene's directory is the one its layout file was found in.
    """
    assert scene.directory == tmp_path / Path(str(Sage10kActionableScenes.GYM)).stem


def test_place_guidance_given_as_an_object_is_kept_as_json_text(layout: dict):
    """
    A place guidance given as a JSON object is kept as that object's JSON text.
    """
    place_guidance = {"near": "wall"}
    object_layout = {**layout["rooms"][0]["objects"][0], "place_guidance": place_guidance}

    sage_object = Sage10kObject._from_json(object_layout)

    assert sage_object.place_guidance == json.dumps(place_guidance)


# %% invalid layouts


def test_a_value_of_the_wrong_type_is_rejected(layout: dict):
    """
    A layout whose object mass is not a number is rejected instead of read.
    """
    layout["rooms"][0]["objects"][0]["mass"] = "heavy"

    with pytest.raises(ValidationError):
        Sage10kScene._from_json(layout)


# %% serialization


def test_scene_round_trips_through_krrood_json(scene: Sage10kScene):
    """
    A scene written with krrood's :func:`to_json` reads back equal.
    """
    assert from_json(to_json(scene)) == scene
