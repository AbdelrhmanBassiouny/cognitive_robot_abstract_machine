"""Load RoboCasa tasks with the decomposed-object store as preprocessing and report each cookware object's handle."""
import sys, time
from krrood.ormatic.utils import create_engine
from sqlalchemy.orm import Session
from semantic_digital_twin.adapters.robocasa_dataset.loader import RoboCasaDatasetLoader
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
from semantic_digital_twin.part_finding.decomposed_objects import DecomposedObjectStore
from semantic_digital_twin.pipeline.part_finding import UseDecomposedObjects
from semantic_digital_twin.pipeline.pipeline import Pipeline
from semantic_digital_twin.semantic_annotations.semantic_annotations import Kettle, Mug, Pan, Pot

store = DecomposedObjectStore(session=Session(create_engine("sqlite:////root/work/part_decomposition/decomposed_objects.sqlite")), mesh_directory=__import__("pathlib").Path("/root/work/part_decomposition/decomposed_meshes"))
loader = RoboCasaDatasetLoader(preprocessing=Pipeline(steps=[UseDecomposedObjects(store=store)]))
for task_name, seed in [(t.split(":")[0], int(t.split(":")[1])) for t in sys.argv[1:]]:
    environment = loader.build_task_environment(task_name, LayoutType.LAYOUT001, StyleType.STYLE001, seed=seed)
    paths = {model.root_body: (model.mjcf_path, getattr(model, "_scale", None)) for model in environment.objects.values()}
    t = time.time()
    task = loader.load_task_from_environment(environment)
    print(f"== {task_name} seed {seed}: parsed+preprocessed in {time.time() - t:.1f} s")
    for annotation in task.world.semantic_annotations:
        if type(annotation) not in (Mug, Pot, Pan, Kettle):
            continue
        handles = annotation.handles if hasattr(annotation, "handles") else [annotation.handle] if annotation.handle else []
        source = next((v for k, v in paths.items() if str(annotation.root.name).startswith(k) or k.startswith(str(annotation.root.name))), ("?", None))
        print(f"  {type(annotation).__name__:6} {annotation.root.name} handles={len(handles)} "
              f"hulls={len(annotation.root.collision)}+{sum(len(h.root.collision) for h in handles)} "
              f"in_manipulated={annotation.root in task.manipulated_objects} src={source[0].split('objects/')[-1]} scale={source[1]}")
