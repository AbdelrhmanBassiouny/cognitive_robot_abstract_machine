import numpy
from semantic_digital_twin.adapters.robocasa_dataset.loader import RoboCasaDatasetLoader
from semantic_digital_twin.adapters.robocasa_dataset.semantics import RoboCasaObjectCategory
from semantic_digital_twin.part_finding.annotation_part_finder import AnnotationPartFinder
from semantic_digital_twin.part_finding.locating import KnownPartLocator, LocatedPart
from semantic_digital_twin.pipeline.mesh_decomposition.coacd import COACDMeshDecomposer
from semantic_digital_twin.semantic_annotations.semantic_annotations import Mug

for decomposer in (None, COACDMeshDecomposer()):
    world = RoboCasaDatasetLoader().load_object(RoboCasaObjectCategory.MUG)
    mug = world.get_semantic_annotations_by_type(Mug)[0]
    mesh = mug.root.visual.combined_mesh
    centers = mesh.triangles_center
    # stand in for the handle: the faces furthest out along the axis the mug is widest in
    axis = numpy.argmax(mesh.extents[:2])
    faces = numpy.flatnonzero(centers[:, axis] > numpy.percentile(centers[:, axis], 90))
    finder = AnnotationPartFinder(
        locator=KnownPartLocator(parts=[LocatedPart(relationship_name="handle", faces=faces, confidence=1.0)]),
        decomposer=decomposer,
    )
    try:
        parts = finder.find_parts(mug)
        print("decomposer", type(decomposer).__name__, "-> parts", [p.root.name.name for p in parts],
              "handle", mug.handle.root.name.name if mug.handle else None,
              "collision shapes", len(mug.root.collision), len(mug.handle.root.collision))
    except Exception as error:
        print("decomposer", type(decomposer).__name__, "->", type(error).__name__, error)
