"""Fixtures: give every door and drawer of RoboCasa's fridges, microwaves, dishwashers and ovens whose handle is
still part of its mesh a handle of its own, with the default part finder.

usage: fixtures.py <style number>...
Builds each style's kitchens until it has seen every fixture category, and claims each fixture model the first
time any worker sees it, so that every model is decomposed once.
"""
import json, os, sys, time, traceback
from datetime import timedelta
from pathlib import Path

import numpy as np
import yaml

from common import OUT, SERVER, write_json
from decompose import split
from semantic_digital_twin.adapters.mjcf import MJCFParser
from semantic_digital_twin.adapters.part_finding.client import RemotePartLocator
from semantic_digital_twin.adapters.robocasa_dataset.loader import RoboCasaDatasetLoader, _category_from_class_name, _parse_robosuite_mjcf
from semantic_digital_twin.adapters.robocasa_dataset.semantics import RoboCasaKitchenApplianceCategory as K
from semantic_digital_twin.part_finding.locating import PartQuery
from semantic_digital_twin.part_finding.relationships import PartRelationshipInspector
from semantic_digital_twin.semantic_annotations.mixins import HasHandle
from robocasa.models.scenes import scene_builder, scene_registry

TARGETS = (K.FRIDGE, K.MICROWAVE, K.DISHWASHER, K.OVEN)
CLAIMS = OUT / "fixture_claims"
CLAIMS.mkdir(parents=True, exist_ok=True)
loader = RoboCasaDatasetLoader()
locator = RemotePartLocator(base_url=SERVER, timeout=timedelta(minutes=30))
classes = {loader.kitchen_appliance_annotator.category_to_annotation_class[c]: c for c in TARGETS}


def claim(name):
    try:
        os.close(os.open(CLAIMS / name, os.O_CREAT | os.O_EXCL))
        return True
    except FileExistsError:
        return False


def decompose_fixture(category, style, fixture):
    model = Path(fixture.file).parent.name
    world = _parse_robosuite_mjcf(MJCFParser.from_xml_string(fixture.get_xml()))
    loader._apply_kitchen_appliance_semantics(world, {fixture.name: fixture})
    wholes = [a for a in world.semantic_annotations if isinstance(a, HasHandle) and a.handle is None and a.root.visual]
    print(category, model, [type(a).__name__ for a in wholes], flush=True)
    for whole in wholes:
        part_name = whole.root.name.name.removeprefix(fixture.name).strip("_") or type(whole).__name__.lower()
        key = f"{category}__{model}__{part_name}"
        meta = {"object": key, "asset": f"fixtures/{Path(fixture.file).parent.parent.name}/{model}", "annotation": type(whole).__name__,
                "category": f"{category} {type(whole).__name__.lower()}", "style": style, "body": whole.root.name.name}
        try:
            mesh = whole.root.visual.combined_mesh
            missing = [r.name for r in PartRelationshipInspector.all_of_type(type(whole)) if not r.is_filled_in(whole)]
            start = time.time()
            answer = locator.answer(PartQuery.from_mesh(mesh, type(whole), missing))
            np.savez_compressed(OUT / "located" / f"{key}.npz", vertices=mesh.vertices, faces=mesh.faces)
            located = dict(meta, asked_for=missing, faces=len(mesh.faces), visual_shapes=len(whole.root.visual),
                           original_collision_shapes=len(whole.root.collision), server_seconds=answer.duration.total_seconds(),
                           round_trip_seconds=time.time() - start, from_cache=answer.from_cache,
                           parts=[{"relationship": p.relationship_name, "faces": np.asarray(p.faces).tolist(), "confidence": float(p.confidence)} for p in answer.parts])
            write_json(OUT / "located" / f"{key}.json", located)
            print(key, len(answer.parts), "parts", [round(p.confidence, 2) for p in answer.parts], f"{answer.duration.total_seconds():.1f}s", flush=True)
            split(key, located, world, whole)
        except Exception as error:
            write_json(OUT / "results" / f"{key}.json", dict(meta, status=f"error: {type(error).__name__}: {str(error)[:300]}", trace=traceback.format_exc()[-3000:]))
            print(key, "ERROR", type(error).__name__, error, flush=True)


def run_style(number):
    style = scene_registry.StyleType(number)
    with open(scene_registry.get_style_path(style)) as style_file:
        style_config = yaml.safe_load(style_file)
    unseen = set(TARGETS)
    for layout in loader._kitchen_layouts():
        if not unseen:
            break
        with open(scene_registry.get_layout_path(layout)) as layout_file:
            layout_config = yaml.safe_load(layout_file)
        for fixture in scene_builder.create_fixtures(layout_config, style_config).values():
            category = classes.get(loader.kitchen_appliance_annotator.resolve(_category_from_class_name(type(fixture).__name__)))
            if category is None or not getattr(fixture, "file", None):
                continue
            unseen.discard(category)
            if claim(f"{category}__{Path(fixture.file).parent.name}"):
                decompose_fixture(str(category), style.name, fixture)
    print("STYLE DONE", style.name, "unseen", sorted(map(str, unseen)), flush=True)


for number in sys.argv[1:]:
    run_style(int(number))
