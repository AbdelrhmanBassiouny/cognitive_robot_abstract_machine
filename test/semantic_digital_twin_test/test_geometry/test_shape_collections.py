import numpy as np

from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.spatial_types.numeric import NumericTransform
from semantic_digital_twin.world_description.geometry import (
    BoundingBox,
    Bounds,
    Sphere,
)
from semantic_digital_twin.world_description.shape_collection import (
    BoundingBoxCollection,
    ShapeCollection,
)
from semantic_digital_twin.world_description.world_entity import Body


def test_post_init_transformation():
    w = World()
    root = Body(name=PrefixedName("root"))
    b1 = Body(name=PrefixedName("b1"))

    with w.modify_world():
        w.add_connection(
            FixedConnection(
                parent=root,
                child=b1,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=1, reference_frame=root
                ),
            )
        )

    shape = Sphere(
        radius=1,
        origin=HomogeneousTransformationMatrix.from_xyz_rpy(x=3, reference_frame=root),
    )
    shape_collection = ShapeCollection(
        shapes=[shape],
        reference_frame=b1,
    )
    shape_collection.transform_all_shapes_to_own_frame()
    assert shape.origin.reference_frame == b1
    assert shape.origin.to_position().x == 2.0

    shape = Sphere(
        radius=1,
        origin=HomogeneousTransformationMatrix.from_xyz_rpy(x=3, reference_frame=root),
    )

    shape_collection = ShapeCollection(reference_frame=b1)
    shape_collection.append(shape)
    shape_collection.transform_all_shapes_to_own_frame()
    assert shape.origin.reference_frame == b1
    assert shape.origin.to_position().x == 2.0


# %% the region a collection of boxes encloses
def test_enclosing_bounds_span_every_box_in_the_collection():
    frame = Body(name=PrefixedName("frame"))
    world = World()
    with world.modify_world():
        world.add_body(frame)
    collection = BoundingBoxCollection(
        [
            BoundingBox(
                -1.0, -1.0, -1.0, 0.0, 0.0, 0.0, NumericTransform(reference_frame=frame)
            ),
            BoundingBox(
                0.5, 0.5, 0.5, 2.0, 3.0, 4.0, NumericTransform(reference_frame=frame)
            ),
        ],
        frame,
    )

    bounds = collection.enclosing_bounds

    assert bounds.lower.tolist() == [-1.0, -1.0, -1.0]
    assert bounds.upper.tolist() == [2.0, 3.0, 4.0]


def test_an_empty_collection_encloses_a_region_nothing_overlaps():
    """
    A body whose shapes name no reference frame contributes no box, and must read as
    enclosing nothing rather than as enclosing everything.
    """
    frame = Body(name=PrefixedName("frame"))
    world = World()
    with world.modify_world():
        world.add_body(frame)
    anywhere = Bounds(np.array([-1e6] * 3), np.array([1e6] * 3))

    bounds = BoundingBoxCollection([], frame).enclosing_bounds

    assert not bounds.overlaps(anywhere)
    assert not anywhere.overlaps(bounds)
