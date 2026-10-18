"""Render the views the part finding server sees for a few objects, as one sheet."""
import sys
import numpy as np, trimesh
from PIL import Image
from common import OUT
from semantic_digital_twin.spatial_computations.mesh_rendering import CameraRing
ring = CameraRing(); rows = []
for key in sys.argv[1:]:
    d = np.load(OUT / "located" / f"{key}.npz")
    views = ring.render(trimesh.Trimesh(d["vertices"], d["faces"], process=False))
    rows.append(np.concatenate([Image.fromarray(v).resize((160, 160)) for v in map(np.asarray, views.images[:8])], 1))
Image.fromarray(np.concatenate(rows, 0)).save(OUT / "peek.png")
