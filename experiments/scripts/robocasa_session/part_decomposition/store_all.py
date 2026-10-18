"""Split every located RoboCasa object again and keep it, decomposed, in the store."""
import json, sys, time
import numpy as np
from pathlib import Path
sys.path.insert(0, "/root/work/part_decomposition/code")
from common import load, OUT
from krrood.ormatic.utils import create_engine
from sqlalchemy.orm import Session
from semantic_digital_twin.orm.ormatic_interface import Base
from semantic_digital_twin.part_finding.annotation_part_finder import AnnotationPartFinder
from semantic_digital_twin.part_finding.decomposed_objects import DecomposedObject, DecomposedObjectStore, ShapeFingerprint
from semantic_digital_twin.part_finding.locating import KnownPartLocator, LocatedPart

DATABASE = OUT / "decomposed_objects.sqlite"
engine = create_engine(f"sqlite:///{DATABASE}")
Base.metadata.create_all(engine)
MESHES = OUT / "decomposed_meshes"
MESHES.mkdir(exist_ok=True)
store = DecomposedObjectStore(session=Session(engine), mesh_directory=MESHES)
done = OUT / "stored.json"
stored = json.loads(done.read_text()) if done.exists() else {}
for path in sorted((OUT / "located").glob("*.json")):
    key = path.stem
    located = json.loads(path.read_text())
    if key in stored or "__" in key or not located["parts"]:
        continue
    t = time.time()
    world, whole = load(key)
    fingerprint = ShapeFingerprint.of_body(whole.root)
    parts = [LocatedPart(p["relationship"], np.array(p["faces"]), p["confidence"]) for p in located["parts"]]
    added = AnnotationPartFinder(locator=KnownPartLocator(parts=parts)).find_parts(whole)
    store.add(DecomposedObject.of(whole, fingerprint))
    stored[key] = {"asset": located["asset"], "parts": len(added), "key": fingerprint.key, "seconds": round(time.time() - t, 1)}
    done.write_text(json.dumps(stored, indent=1))
    print(key, stored[key], flush=True)
print("DONE", len(stored), DATABASE.stat().st_size // 2**20, "MiB", flush=True)
