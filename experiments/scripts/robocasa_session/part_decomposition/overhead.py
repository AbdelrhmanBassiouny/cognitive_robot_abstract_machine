"""Time load_task_from_environment with and without the decomposed-object step on the same environment."""
import sys, time
from pathlib import Path
from krrood.ormatic.utils import create_engine
from sqlalchemy.orm import Session
from semantic_digital_twin.adapters.robocasa_dataset.loader import RoboCasaDatasetLoader
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
from semantic_digital_twin.part_finding.decomposed_objects import DecomposedObjectStore
from semantic_digital_twin.pipeline.part_finding import UseDecomposedObjects
from semantic_digital_twin.pipeline.pipeline import Pipeline
from semantic_digital_twin.semantic_annotations.semantic_annotations import Kettle, Mug, Pan, Pot

OUT = Path("/root/work/part_decomposition")
store = DecomposedObjectStore(session=Session(create_engine(f"sqlite:///{OUT / 'decomposed_objects.sqlite'}")), mesh_directory=OUT / "decomposed_meshes")
t = time.time(); store.whole_types(); print(f"first query {time.time() - t:.1f} s", flush=True)
plain, with_step = RoboCasaDatasetLoader(), RoboCasaDatasetLoader(preprocessing=Pipeline(steps=[UseDecomposedObjects(store=store)]))
for spec in sys.argv[1:]:
    name, seed = spec.split(":")
    environment = plain.build_task_environment(name, LayoutType.LAYOUT001, StyleType.STYLE001, seed=int(seed))
    scales = {m.root_body: getattr(m, "_scale", None) for m in environment.objects.values()}
    for label, loader in (("plain", plain), ("step", with_step)):
        t = time.time()
        task = loader.load_task_from_environment(environment)
        found = [f"{type(a).__name__}:{len(a.handles) if hasattr(a, 'handles') else int(a.handle is not None)}"
                 for a in task.world.semantic_annotations if type(a) in (Mug, Pot, Pan, Kettle)]
        print(f"{name}:{seed} {label:5} {time.time() - t:5.1f} s  {found}  scales={[list(s) for s in scales.values() if s is not None]}", flush=True)
