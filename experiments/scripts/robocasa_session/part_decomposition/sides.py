"""For every stored pot: on which sides of it do its two handles sit?"""
import json
import numpy as np
from pathlib import Path
from krrood.ormatic.utils import create_engine
from sqlalchemy import select
from sqlalchemy.orm import Session
from semantic_digital_twin.orm.ormatic_interface import DecomposedObjectDAO
from semantic_digital_twin.semantic_annotations.semantic_annotations import Pot

OUT = Path("/root/work/part_decomposition")
stored = json.loads((OUT / "stored.json").read_text())
names = {v["key"]: k for k, v in stored.items()}
session = Session(create_engine(f"sqlite:///{OUT / 'decomposed_objects.sqlite'}"))
for dao in session.scalars(select(DecomposedObjectDAO).where(DecomposedObjectDAO.whole_type == Pot)):
    decomposed = dao.from_dao()
    pot = decomposed.whole
    center = pot.root.visual.combined_mesh.bounds.mean(axis=0)
    angles = []
    for handle in pot.handles:
        offset = handle.root.visual.combined_mesh.centroid - center
        angles.append(np.degrees(np.arctan2(offset[1], offset[0])))
    apart = abs((angles[0] - angles[1] + 180) % 360 - 180) if len(angles) == 2 else None
    print(f"{names.get(decomposed.fingerprint.key, '?'):7} handles at {[round(a) for a in angles]} deg, {apart and round(apart)} deg apart")
