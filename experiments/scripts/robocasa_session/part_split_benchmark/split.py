"""Stage 2: split the located handle off one object with one splitting setting, and measure the result.

usage: split.py <object> <config|original>
Writes results/<object>/<config>.json and hulls/<object>/<config>.npz.
"""
import json, sys, time, traceback

import numpy as np
import trimesh
from scipy.spatial import cKDTree

from common import CONFIGS, OUT, load, write_json
from semantic_digital_twin.part_finding.annotation_part_finder import AnnotationPartFinder
from semantic_digital_twin.part_finding.locating import KnownPartLocator, LocatedPart

SURFACE_SAMPLES = 40000


def hull_meshes(body, root_T_body):
    meshes = []
    for shape in body.collision:
        mesh = shape.mesh.copy()
        mesh.apply_transform(root_T_body @ shape.origin.to_np())
        meshes.append(mesh)
    return meshes


def surface_points(meshes, count, seed):
    combined = trimesh.util.concatenate(meshes)
    points, _ = trimesh.sample.sample_surface(combined, count, seed=seed)
    return points


def fidelity(visual, hulls):
    """Symmetric surface distances between the visual mesh and the collision hulls, in mm."""
    visual_points = surface_points([visual], SURFACE_SAMPLES, 1)
    hull_points = surface_points(hulls, SURFACE_SAMPLES, 2)
    missed = cKDTree(hull_points).query(visual_points)[0] * 1000  # visual surface not traced by the hulls
    bloat = cKDTree(visual_points).query(hull_points)[0] * 1000  # hull surface away from the visual surface
    return {
        "visual_to_hull_mean_mm": float(missed.mean()), "visual_to_hull_p95_mm": float(np.percentile(missed, 95)),
        "hull_to_visual_mean_mm": float(bloat.mean()), "hull_to_visual_p95_mm": float(np.percentile(bloat, 95)),
        "hull_volume_l": float(sum(abs(h.volume) for h in hulls) * 1000),
    }


def save_hulls(path, groups):
    """groups: list of (is_part, meshes)."""
    vertices, faces, hull_id, is_part, offset = [], [], [], [], 0
    for part_flag, meshes in groups:
        for mesh in meshes:
            index = len(set(hull_id)) if hull_id else 0
            vertices.append(mesh.vertices); faces.append(mesh.faces + offset)
            hull_id += [index] * len(mesh.faces); is_part += [part_flag] * len(mesh.faces)
            offset += len(mesh.vertices)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, vertices=np.concatenate(vertices), faces=np.concatenate(faces),
                        hull=np.array(hull_id), is_part=np.array(is_part, dtype=bool))


def main(key, config):
    target = OUT / "results" / key / f"{config}.json"
    located = json.loads((OUT / "located" / f"{key}.json").read_text())
    result = {"object": key, "config": config}
    world, whole = load(key)
    visual = whole.root.visual.combined_mesh
    if config == "original":
        hulls = hull_meshes(whole.root, np.eye(4))
        result.update(status="ok", seconds=0.0, part_hulls=0, rest_hulls=len(hulls), **fidelity(visual, hulls))
        save_hulls(OUT / "hulls" / key / f"{config}.npz", [(False, hulls)])
        return write_json(target, result)
    if not located["parts"]:
        return write_json(target, dict(result, status="no part located"))
    family, parameters, factory = CONFIGS[config]
    finder = AnnotationPartFinder(
        locator=KnownPartLocator(parts=[LocatedPart(relationship_name=p["relationship"], faces=np.array(p["faces"]), confidence=p["confidence"]) for p in located["parts"]]),
        decomposer=factory(),
    )
    result["located_pieces"] = len(located["parts"])
    result["kept_pieces"] = sum(p["confidence"] >= finder.minimum_confidence for p in located["parts"])
    start = time.time()
    parts = finder.find_parts(whole)
    seconds = time.time() - start
    if not parts:
        return write_json(target, dict(result, status="nothing split off", seconds=seconds))
    part_hulls = [h for part in parts for h in hull_meshes(part.root, world.compute_forward_kinematics_np(whole.root, part.root))]
    rest_hulls = hull_meshes(whole.root, np.eye(4))
    result.update(status="ok", family=family, parameters=parameters, seconds=seconds, parts=len(parts),
                  part_hulls=len(part_hulls), rest_hulls=len(rest_hulls), **fidelity(visual, part_hulls + rest_hulls))
    save_hulls(OUT / "hulls" / key / f"{config}.npz", [(True, part_hulls), (False, rest_hulls)])
    write_json(target, result)


if __name__ == "__main__":
    key, config = sys.argv[1], sys.argv[2]
    try:
        main(key, config)
    except Exception as error:
        write_json(OUT / "results" / key / f"{config}.json",
                   {"object": key, "config": config, "status": f"error: {type(error).__name__}: {str(error)[:300]}", "trace": traceback.format_exc()[-3000:]})
        raise
