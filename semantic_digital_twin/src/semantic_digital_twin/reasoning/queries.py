import math
from typing import List, Union, Optional
from krrood.entity_query_language.factories import variable_from, entity, flat_variable, in_, the, contains, variable, \
    an
from krrood.entity_query_language.query.query import Entity
from krrood.entity_query_language.predicate import symbolic_function
from krrood.utils import inheritance_path_length, recursive_subclasses

from semantic_digital_twin.reasoning.predicates import (
    is_supported_by,
    compute_euclidean_distance_2d,
    is_supporting,
)
from semantic_digital_twin.semantic_annotations.mixins import HasSupportingSurface, IsPerceivable, HasRootBody
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.geometry import Color

from semantic_digital_twin.world_description.world_entity import (
    Body,
    SemanticAnnotation,
)



def query_semantic_annotations_on_surfaces(
    supporting_surfaces: List[HasRootBody], world: World
) -> Union[Entity[SemanticAnnotation], SemanticAnnotation]:
    """
    Queries a list of Semantic annotations that are on top of a given list of other annotations (ex. Tables).
    param: supporting_surfaces: List of SemanticAnnotations that are supporting other annotations.
    :param world: World object that contains the supporting_surfaces.
    return: List of SemanticAnnotations that are supported by the given supporting_surfaces.
    """
    supporting_surfaces_var = variable_from(supporting_surfaces)
    bodies = variable_from(world.bodies_with_collision)
    body = entity(bodies).where(
        is_supported_by(
            supported_body=bodies,
            supporting_body=supporting_surfaces_var.root,
        )
    )
    return entity(
            semantic_annotation := variable(HasRootBody, domain=world.semantic_annotations)
        ).where(semantic_annotation.root == body)

def query_get_next_object_euclidean_x_y(
    main_body: Body,
    supporting_surface,
) -> Entity[SemanticAnnotation]:
    """
    Queries the next object based on Euclidean distance in x and y coordinates
    relative to the given main body and supporting surface. This function utilizes
    semantic annotations of objects and orders them by their Euclidean distances
    to the main body.

    :param main_body: The main body to which the Euclidean distance is computed.
    :param supporting_surface: The surface on which the semantic annotations
        of interest are queried.
    :return: A `QueryObjectDescriptor` containing semantic annotations ordered
        by Euclidean distance to the main body.
    """
    supported_semantic_annotations = query_semantic_annotations_on_surfaces(
        [supporting_surface], main_body._world
    )
    return supported_semantic_annotations.ordered_by(
        compute_euclidean_distance_2d(
            body1=supported_semantic_annotations.selected_variable.bodies[0],
            body2=main_body,
        )
    )


def query_surface_of_most_similar_obj(
    object_of_interest: SemanticAnnotation,
    supporting_surfaces: List[HasSupportingSurface],
    threshold: int = 1,
) -> Optional[HasSupportingSurface]:
    """
    Finds the most similar object to a given semantic annotation among a list of tables
    based on the inheritance path length. If the similarity does not meet the provided
    threshold, the method attempts to return the table that is not supporting any object.
    The similarity metric leverages the class hierarchy to compute distances.

    :param object_of_interest: The semantic annotation to compare.
    :param supporting_surfaces: A list of supporting surfaces semantic annotations to search on top of them for similar objects to the object_of_interest.
    :param threshold: The maximum acceptable inheritance path length to classify objects
                      as similar. Defaults to 1.
    :return: The semantic annotation of the most appropriate surface based on similarity
             metrics or the non-supporting table when no viable candidate is found, or None if there are no supporting surfaces.
    """
    if not supporting_surfaces:
        return None

    # Find the surface that is not supporting anything
    non_supporting_table = None
    for supporting_surface in supporting_surfaces:
        if not is_supporting(supporting_surface.bodies[0]):
            non_supporting_table = supporting_surface
            break

    # Query annotations on the surfaces of the tables
    objects = query_semantic_annotations_on_surfaces(
        supporting_surfaces, object_of_interest._world
    ).tolist()

    best_distance = math.inf
    most_similar = None

    # Iterate over each object to find the most similar based on inheritance path length
    for obj in objects:
        for cls in type(obj).__mro__:
            dist = inheritance_path_length(type(object_of_interest), cls)
            if dist is None:
                continue
            if dist < best_distance:
                best_distance = dist
                most_similar = obj
            break  # Once a match is found, no need to check further classes for this object

    # Apply threshold to determine if the match is acceptable
    if best_distance > threshold or most_similar is None:
        return non_supporting_table

    # Find the table supporting the most similar object
    for supporting_surface in supporting_surfaces:
        if is_supported_by(most_similar.bodies[0], supporting_surface.bodies[0]):
            return supporting_surface

def query_annotations_by_color(color: Color, objects: list[SemanticAnnotation]) -> List[SemanticAnnotation]:
    """
    Queries and retrieves a list of annotations from another one that match
    the specified color based on their visual properties.

    :param color: The color to filter annotations by.
    :param objects: The list of the unfiltered annotations.

    :return: List[SemanticAnnotation]: A list of annotations from the world whose primary shape's
    visual color matches the specified color.
    """
    all_bodies = []
    for obj in objects:
        all_bodies.append(obj.bodies[0])

    filtered_bodies = []

    for body in all_bodies:
        if body.visual and body.collision is None:
            continue
        shapes = body.visual.shapes or body.collision.shapes
        if shapes[0].color == color:
            filtered_bodies.append(body)
    filtered_annotations = []
    for body in filtered_bodies:
        world = body._world
        filtered_annotations.extend(an(entity(
            semantic_annotation := variable(HasRootBody, domain=world.semantic_annotations)
        ).where(semantic_annotation.root == body)).tolist())
    return filtered_annotations


@symbolic_function
def class_name_in_label(cls: type, label: str) -> bool:
    """Check if the class name is contained in the label."""
    return cls.__name__.lower() in label.lower()


def query_class_by_label(label: str) -> Optional[type]:
    """
    Finds the class whose name is contained within the given label.
    It searches through all subclasses of IsPerceivable.

    :param label: The string input from perception (e.g., "bowl_collapsable_yellowgrey").
    :return: The matching class (e.g., Bowl) or None if no match is found.
    """
    semantic_class = variable_from(recursive_subclasses(IsPerceivable))
    matching_class = entity(semantic_class).where(
        class_name_in_label(semantic_class, label)
    )
    return None if matching_class.tolist() == [] else matching_class.first()


def query_sort_by_size(annotations: List[HasRootBody], order: Optional[bool]=True) -> List[SemanticAnnotation]:
    """
    Sorts a list of SemanticAnnotations by volume in descending order (largest to smallest).
    Volume is calculated by multiplying the scale dimensions (x * y * z) of the object's shape.

    :param annotations: List of annotations of type HasRootBody to sort.
    :param order: Whether to sort in ascending or descending order (default is True).
    :return: List of SemanticAnnotation objects sorted by volume (largest to smallest).
    """
    newList = []
    for annotation in annotations:
        if annotation.bodies:
            newList.append(annotation)

    def get_volume(annotation: SemanticAnnotation) -> float:
        """Calculate volume from the annotation's body scale."""
        body = annotation.bodies[0]

        # Get shapes from collision if available, otherwise from visual
        if body.collision is not None:
            return body.collision.scale.x * body.collision.scale.y * body.collision.scale.z
        else:
            return 0.0
    return sorted(newList, key=get_volume, reverse=order)