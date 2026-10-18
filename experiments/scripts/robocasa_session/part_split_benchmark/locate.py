"""Stage 1: ask the part finding server for the handle faces of every benchmark object, once."""
import sys, time, traceback
from datetime import timedelta

import numpy as np

from common import OUT, SERVER, load, objects, write_json
from semantic_digital_twin.adapters.part_finding.client import RemotePartLocator
from semantic_digital_twin.part_finding.locating import PartQuery
from semantic_digital_twin.part_finding.relationships import PartRelationshipInspector

locator = RemotePartLocator(base_url=SERVER, timeout=timedelta(minutes=10))
for key in sys.argv[1:] or objects():
    target = OUT / "located" / f"{key}.json"
    if target.exists():
        continue
    try:
        world, whole = load(key)
        shapes = whole.root.visual or whole.root.collision
        mesh = shapes.combined_mesh
        names = [r.name for r in PartRelationshipInspector.all_of_type(type(whole))]
        query = PartQuery.from_mesh(mesh, type(whole), names)
        start = time.time()
        answer = locator.answer(query)
        np.savez_compressed(OUT / "located" / f"{key}.npz", vertices=mesh.vertices, faces=mesh.faces)
        write_json(target, {
            "object": key, "faces": len(mesh.faces), "extent_m": float(np.linalg.norm(mesh.extents)),
            "original_collision_shapes": len(whole.root.collision), "visual_differs": len(whole.root.visual) > 0,
            "server_seconds": answer.duration.total_seconds(), "round_trip_seconds": time.time() - start, "from_cache": answer.from_cache,
            "parts": [{"relationship": p.relationship_name, "faces": np.asarray(p.faces).tolist(), "confidence": float(p.confidence)} for p in answer.parts],
        })
        print(key, len(answer.parts), "parts", [round(p.confidence, 2) for p in answer.parts], f"{answer.duration.total_seconds():.1f}s", flush=True)
    except Exception as error:
        write_json(OUT / "located" / f"{key}.error.json", {"object": key, "error": f"{type(error).__name__}: {error}", "trace": traceback.format_exc()})
        print(key, "ERROR", type(error).__name__, error, flush=True)
