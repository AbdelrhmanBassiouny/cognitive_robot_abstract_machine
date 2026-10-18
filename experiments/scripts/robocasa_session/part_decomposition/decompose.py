"""Stage 2: split the located parts off one object with the default part finder (V-HACD, 32 hulls),
measure the fit and export the result.

usage: decompose.py <object>
Writes results/<object>.json, hulls/<object>.npz and assets/<asset>/parts.glb.
"""
import json, sys, time, traceback

import numpy as np
import trimesh
from scipy.spatial import cKDTree

from common import OUT, load, write_json
from semantic_digital_twin.part_finding.annotation_part_finder import AnnotationPartFinder
from semantic_digital_twin.part_finding.locating import KnownPartLocator, LocatedPart

SURFACE_SAMPLES = 40000


def placed(shapes, root_T_body):
    meshes = []
    for shape in shapes:
        mesh = shape.mesh.copy()
        mesh.apply_transform(root_T_body @ shape.origin.to_np())
        meshes.append(mesh)
    return meshes


def fidelity(visual, hulls):
    """Symmetric surface distances between the visual mesh and the collision hulls, in mm."""
    visual_points, _ = trimesh.sample.sample_surface(visual, SURFACE_SAMPLES, seed=1)
    hull_points, _ = trimesh.sample.sample_surface(trimesh.util.concatenate(hulls), SURFACE_SAMPLES, seed=2)
    gap = cKDTree(hull_points).query(visual_points)[0] * 1000
    bloat = cKDTree(visual_points).query(hull_points)[0] * 1000
    return {"gap_p95_mm": float(np.percentile(gap, 95)), "gap_mean_mm": float(gap.mean()),
            "bloat_p95_mm": float(np.percentile(bloat, 95)), "bloat_mean_mm": float(bloat.mean())}


def save_hulls(path, groups):
    vertices, faces, hull_id, is_part, offset, index = [], [], [], [], 0, 0
    for part_flag, meshes in groups:
        for mesh in meshes:
            vertices.append(mesh.vertices); faces.append(mesh.faces + offset)
            hull_id += [index] * len(mesh.faces); is_part += [part_flag] * len(mesh.faces)
            offset += len(mesh.vertices); index += 1
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, vertices=np.concatenate(vertices), faces=np.concatenate(faces),
                        hull=np.array(hull_id), is_part=np.array(is_part, dtype=bool))


def main(key):
    located = json.loads((OUT / "located" / f"{key}.json").read_text())
    world, whole = load(key)
    split(key, located, world, whole)


def split(key, located, world, whole):
    """Split the located parts off ``whole`` with the default part finder, measure and export the result."""
    result = {"object": key, "asset": located["asset"], "annotation": located["annotation"]}
    visual = whole.root.visual.combined_mesh
    finder = AnnotationPartFinder(locator=KnownPartLocator(parts=[
        LocatedPart(relationship_name=p["relationship"], faces=np.array(p["faces"]), confidence=p["confidence"]) for p in located["parts"]]))
    result["decomposer"] = repr(finder.decomposer)[:200]
    result["located_pieces"] = len(located["parts"])
    result["kept_pieces"] = sum(p["confidence"] >= finder.minimum_confidence for p in located["parts"])
    start = time.time()
    parts = finder.find_parts(whole)
    result["seconds"] = time.time() - start
    if not parts:
        return write_json(OUT / "results" / f"{key}.json", dict(result, status="no part split off"))
    transforms = [world.compute_forward_kinematics_np(whole.root, part.root) for part in parts]
    part_hulls = [h for part, T in zip(parts, transforms) for h in placed(part.root.collision, T)]
    rest_hulls = placed(whole.root.collision, np.eye(4))
    result.update(status="ok", parts=[part.root.name.name for part in parts], part_hulls=len(part_hulls), rest_hulls=len(rest_hulls),
                  part_faces=sum(len(part.root.visual.combined_mesh.faces) for part in parts), **fidelity(visual, part_hulls + rest_hulls))
    save_hulls(OUT / "hulls" / f"{key}.npz", [(True, part_hulls), (False, rest_hulls)])
    scene = trimesh.Scene()
    for i, (part, T) in enumerate(zip(parts, transforms)):
        for j, mesh in enumerate(placed(part.root.visual, T)):
            scene.add_geometry(mesh, node_name=f"{part.root.name.name}_visual_{j}")
    for j, mesh in enumerate(placed(whole.root.visual, np.eye(4))):
        scene.add_geometry(mesh, node_name=f"rest_visual_{j}")
    for j, mesh in enumerate(part_hulls):
        scene.add_geometry(mesh, node_name=f"part_collision_{j}")
    for j, mesh in enumerate(rest_hulls):
        scene.add_geometry(mesh, node_name=f"rest_collision_{j}")
    target = OUT / "assets" / located["asset"] / "parts.glb"
    target.parent.mkdir(parents=True, exist_ok=True)
    scene.export(target)
    write_json(OUT / "results" / f"{key}.json", result)


if __name__ == "__main__":
    key = sys.argv[1]
    try:
        main(key)
    except Exception as error:
        write_json(OUT / "results" / f"{key}.json", {"object": key, "status": f"error: {type(error).__name__}: {str(error)[:300]}", "trace": traceback.format_exc()[-3000:]})
        raise
