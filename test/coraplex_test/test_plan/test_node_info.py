from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from krrood.entity_query_language.factories import a, variable

from coraplex.datastructures.enums import NodeDetail, NodeDetailNotation
from coraplex.plans.failures import PlanFailure
from coraplex.plans.node_info import NodeDetailRenderer, NodeInfoSection
from coraplex.robot_plans.actions.core.navigation import NavigateAction
from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction
from semantic_digital_twin.datastructures.definitions import TorsoState
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.semantic_annotations.semantic_annotations import Milk
from semantic_digital_twin.spatial_types import Pose
from semantic_digital_twin.world_description.world_entity import Body

# %% descriptions the tests render


@dataclass
class DescriptionOfATorsoState:
    """
    A description without a description nested in it.
    """

    torso_state: TorsoState
    """
    The torso state it describes.
    """


@dataclass
class DescriptionNestingADescription:
    """
    A description holding another description and a field left empty.
    """

    torso: DescriptionOfATorsoState
    """
    The nested description.
    """

    height: float
    """
    A number it holds.
    """

    unset: TorsoState | None = None
    """
    A field that holds no value.
    """


# %% single values


def test_a_class_is_named_by_its_name():
    """
    A class, such as the type a designator parameter asks for, reads as its name.
    """
    assert NodeDetailRenderer().render(MoveTorsoAction) == MoveTorsoAction.__name__


def test_an_enum_member_is_named_by_its_name():
    """
    An enumeration member reads as its name, without its enumeration.
    """
    assert NodeDetailRenderer().render(TorsoState.HIGH) == TorsoState.HIGH.name


def test_a_body_is_named_by_its_name():
    """
    A body reads as its name instead of its representation.
    """
    body = Body(name=PrefixedName("milk", "kitchen"))

    assert NodeDetailRenderer().render(body) == str(body.name)


def test_a_semantic_annotation_is_named_by_its_name():
    """
    A semantic annotation reads as its name instead of its representation.
    """
    milk = Milk(name=PrefixedName("milk", "kitchen"), root=Body())

    assert NodeDetailRenderer().render(milk) == str(milk.name)


def test_a_pose_is_shown_by_its_position_to_the_millimetre():
    """
    A pose reads as the coordinates of its position, rounded to the millimetre.
    """
    coordinates = [0.12345, -1.5, 2.0]
    pose = Pose.from_xyz_rpy(*coordinates)

    assert NodeDetailRenderer().render(pose) == NodeDetailNotation.PART_SEPARATOR.join(
        NodeDetailNotation.COORDINATE_FORMAT.format(coordinate)
        for coordinate in coordinates
    )


def test_a_boolean_is_shown_as_on_or_off():
    """
    A boolean reads as a switch.
    """
    renderer = NodeDetailRenderer()

    assert [renderer.render(True), renderer.render(False)] == [
        NodeDetailNotation.SWITCHED_ON,
        NodeDetailNotation.SWITCHED_OFF,
    ]


def test_a_number_is_shown_as_short_as_it_reads_back():
    """
    A number drops the digits that carry nothing.
    """
    renderer = NodeDetailRenderer()

    assert [renderer.render(2.0), renderer.render(3)] == [
        NodeDetailNotation.NUMBER_FORMAT.format(2.0),
        NodeDetailNotation.NUMBER_FORMAT.format(3),
    ]


def test_a_text_is_shown_as_it_is():
    """
    A text is shown unchanged.
    """
    assert NodeDetailRenderer().render("handle") == "handle"


def test_a_list_is_shown_by_its_items():
    """
    A list reads as its items, each shown readably.
    """
    assert NodeDetailRenderer().render(
        [TorsoState.HIGH, TorsoState.LOW]
    ) == NodeDetailNotation.PART_SEPARATOR.join(
        [TorsoState.HIGH.name, TorsoState.LOW.name]
    )


def test_a_failure_is_shown_by_its_message():
    """
    A failure reads as its message, not as the fields of the exception.
    """
    failure = PlanFailure()

    assert NodeDetailRenderer().render(failure) == str(failure)


def test_any_other_value_is_shown_as_its_text():
    """
    A value no rule covers is shown as its text.
    """
    started = datetime(2026, 10, 27, 14, 51)

    assert NodeDetailRenderer().render(started) == str(started)


# %% values a designator leaves open


def test_a_match_is_shown_by_its_class_and_the_fields_it_states():
    """
    A match reads as the class it matches followed by what it states about each field.
    """
    renderer = NodeDetailRenderer()
    pose = Pose.from_xyz_rpy(1.0, 2.0, 0.0)

    rendered = renderer.render(a(NavigateAction)(target_location=pose))

    assert rendered == (
        f"{NavigateAction.__name__}{NodeDetailNotation.MATCH_SEPARATOR}"
        f"target_location {renderer.render(pose)}"
    )


def test_a_match_stating_no_field_is_named_by_its_class():
    """
    A match that states nothing reads as the class it matches alone.
    """
    assert NodeDetailRenderer().render(a(NavigateAction)()) == NavigateAction.__name__


def test_a_match_stated_by_a_match_is_named_by_its_class():
    """
    A match a match states about a field reads as the class it matches only.
    """
    match = a(DescriptionNestingADescription)(
        torso=a(DescriptionOfATorsoState)(torso_state=TorsoState.HIGH)
    )

    assert NodeDetailRenderer().render(match) == (
        f"{DescriptionNestingADescription.__name__}"
        f"{NodeDetailNotation.MATCH_SEPARATOR}"
        f"torso {DescriptionOfATorsoState.__name__}"
    )


def test_a_variable_is_shown_as_any_value_of_its_type():
    """
    A value a designator leaves open reads as any value of its type.
    """
    open_pose = variable(Pose, domain=[Pose()])

    assert (
        NodeDetailRenderer().render(open_pose)
        == f"{NodeDetailNotation.OPEN_VALUE} {Pose.__name__}"
    )


# %% nested descriptions


def test_a_description_is_shown_by_the_fields_that_hold_a_value():
    """
    A description reads as its fields that hold a value, a description nested in it as its class.
    """
    renderer = NodeDetailRenderer()
    description = DescriptionNestingADescription(
        torso=DescriptionOfATorsoState(TorsoState.MID), height=0.5
    )

    assert renderer.render(description) == NodeDetailNotation.PART_SEPARATOR.join(
        [
            f"torso {DescriptionOfATorsoState.__name__}",
            f"height {renderer.render(description.height)}",
        ]
    )


# %% node details


def test_a_section_shows_each_detail_readably():
    """
    A section shows each detail as the renderer writes it, not as the value's representation.
    """
    raw = NodeInfoSection(NodeDetail.DESIGNATOR_PARAMETER, {"state": TorsoState.HIGH})
    readable = NodeInfoSection(
        NodeDetail.DESIGNATOR_PARAMETER, {"state": TorsoState.HIGH.name}
    )

    assert raw.to_lines() == readable.to_lines()
