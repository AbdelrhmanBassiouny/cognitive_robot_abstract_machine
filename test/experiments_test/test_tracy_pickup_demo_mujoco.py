"""
Tests for :mod:`experiments.tracy_experiments.pickup.pickup_demo_mujoco`: the simulated
lab is laid out as the tape measured the real one, its camera stands where the real
camera's captures say it stood, and the run -- perceiving the board and the pieces into a
belief holding Tracy alone, then sorting every piece by driving the simulation -- puts
each piece through its hole and leaves its films behind.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from typing_extensions import Dict

from segmind.datastructures.events import (
    PickUpEvent,
    StopTranslationEvent,
    TranslationEvent,
)

from experiments.episodes.artifacts import ArtifactDirectory
from experiments.montessori.perception.captures import SceneCapture
from experiments.montessori.pieces import SMALLER_PIECES, KnownPieceSet
from experiments.montessori.same_piece import SamePiece
from experiments.montessori.semantics import MontessoriShapeCategory
from experiments.montessori.world import BOARD_SCALE
from experiments.paper.run_plan import RunPlan
from experiments.questions.working_memory import PickedUpRecently
from experiments.scenarios.trial import TrialOutcome
from experiments.tracy_experiments.pick_and_place_action import (
    PickUpActionMujoco,
    PlaceActionMujoco,
)
from experiments.tracy_experiments.pickup.pickup_demo_mujoco import (
    LAB_BOARD_CENTRE,
    LAB_PIECE_PLACES,
    RunArtifact,
    TRACE_PERIOD,
    Shove,
    SimulatedLab,
    SimulatedPickupDemo,
)

from .dataset.montessori_capture_truths import CAPTURE_TRUTHS

MEASURED_CAPTURE = "scaled_pieces_in_a_row"
"""
The capture of the real table laid out the way the simulated one is.
"""

CAMERA_POSE_TOLERANCE = 1e-3
"""
How far, in metres and in the entries of a rotation matrix, the simulated camera may
stand from where the capture's camera stood.
"""

PERCEPTION_TOLERANCE = 0.005
"""
How far, in metres, the belief may stand a piece or the board from where the reality
has it: a rendered look carries no sensor noise, so the look is held to the size of a
pixel on the table rather than to the tape's tolerance.
"""

IN_ITS_HOLE = 0.9
"""
How much of a piece must stand in the space under its hole for it to count as sorted.
"""


@pytest.fixture(scope="module")
def performed() -> SimulatedPickupDemo:
    """
    The whole run, performed once headless and as fast as the machine allows.
    """
    demo = SimulatedPickupDemo(lab=SimulatedLab.build())
    demo.perform()
    return demo


# %% the lab as the tape measured it


def test_the_pieces_and_the_board_stand_where_the_tape_put_them() -> None:
    lab = SimulatedLab.build()
    truth = CAPTURE_TRUTHS[MEASURED_CAPTURE]

    for measured in truth.tape_measured:
        stands_at = lab.real_position_of(measured.category)
        assert stands_at[:2] == pytest.approx(
            [measured.place.x, measured.place.y], abs=1e-9
        )
        assert LAB_PIECE_PLACES[measured.category].x == measured.place.x
    board_at = lab.reality.compute_forward_kinematics_np(
        lab.reality.root, lab.scene.board.root
    )[:3, 3]
    assert board_at[:2] == pytest.approx([LAB_BOARD_CENTRE.x, LAB_BOARD_CENTRE.y])
    assert LAB_BOARD_CENTRE.x - BOARD_SCALE.x / 2 == pytest.approx(
        truth.board_front_left_corner.x
    )
    assert LAB_BOARD_CENTRE.y + BOARD_SCALE.y / 2 == pytest.approx(
        truth.board_front_left_corner.y
    )


def test_the_camera_stands_where_the_captures_camera_stood() -> None:
    """
    The camera on Tracy's ``camera_link`` reports the same optical pose, in the robot's
    frame, as the frame the real camera captured, and takes a picture of the same size
    through the same lens.
    """
    lab = SimulatedLab.build()
    captured = SceneCapture.load(MEASURED_CAPTURE).to_frame()

    assert lab.camera.reference_frame_T_camera == pytest.approx(
        captured.reference_frame_T_camera, abs=CAMERA_POSE_TOLERANCE
    )
    assert lab.camera.width == captured.color.shape[1]
    assert lab.camera.height == captured.color.shape[0]
    assert lab.camera.intrinsics.focal_length_y == pytest.approx(
        captured.intrinsics.focal_length_y, abs=0.5
    )


# %% the run


def test_the_belief_stands_every_piece_where_the_reality_has_it(
    performed: SimulatedPickupDemo,
) -> None:
    """
    The belief held no piece before the look; afterwards it holds one per kind, within
    a pixel's worth of where the reality stands the real one.
    """
    lab = performed.lab
    assert sorted(piece.shape_category for piece in performed.sorting.pieces) == sorted(
        LAB_PIECE_PLACES
    )
    for piece in performed.sorting.pieces:
        believed = lab.believed_position_of(piece)
        real = LAB_PIECE_PLACES[piece.shape_category]
        assert float(np.hypot(believed[0] - real.x, believed[1] - real.y)) <= (
            PERCEPTION_TOLERANCE
        ), (piece.shape_category, believed)


def test_the_belief_stands_the_board_where_the_reality_has_it(
    performed: SimulatedPickupDemo,
) -> None:
    lab = performed.lab
    believed = performed.sorting.board.root.global_transform
    believed_xy = believed.to_position().to_np()[:2]

    assert believed_xy == pytest.approx(
        [LAB_BOARD_CENTRE.x, LAB_BOARD_CENTRE.y], abs=PERCEPTION_TOLERANCE
    )
    assert float(believed.to_rotation_matrix().to_rpy()[2]) == pytest.approx(
        0.0, abs=np.radians(1.0)
    )
    assert float(
        lab.scene.board.root.global_transform.to_rotation_matrix().to_rpy()[2]
    ) == pytest.approx(0.0)


HELD_FLAT_BETWEEN_THE_PADS = (
    MontessoriShapeCategory.CUBE,
    MontessoriShapeCategory.CYLINDER,
    MontessoriShapeCategory.RECTANGULAR_PRISM,
)
"""
The pieces two parallel pads hold by a face each.
"""


def test_every_piece_the_pads_hold_flat_ends_up_through_its_hole(
    performed: SimulatedPickupDemo,
) -> None:
    """
    Sorting from the belief moves the reality's pieces: each stands in the space under
    the hole of its own kind once the run is over.
    """
    containment: Dict[MontessoriShapeCategory, float] = {
        category: performed.lab.containment_in_its_hole(category)
        for category in HELD_FLAT_BETWEEN_THE_PADS
    }

    assert all(value >= IN_ITS_HOLE for value in containment.values()), containment


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Two parallel pads hold the triangular prism by one face and the opposite "
        "edge, and in MuJoCo that grasp does not last the carry to its hole: the prism "
        "works its way out of the pads on the way and lands on the table in front of "
        "the board. A firmer squeeze only pushes it out sooner. The real pads are "
        "compliant and hold it; the simulated ones need a grasp of their own for it."
    ),
)
def test_the_triangular_prism_ends_up_through_its_hole(
    performed: SimulatedPickupDemo,
) -> None:
    assert (
        performed.lab.containment_in_its_hole(MontessoriShapeCategory.TRIANGULAR_PRISM)
        >= IN_ITS_HOLE
    )


def test_the_run_leaves_its_films_and_the_picture_of_the_look(
    performed: SimulatedPickupDemo, tmp_path: Path
) -> None:
    written = performed.write_artifacts(tmp_path / "run")

    assert [path.name for path in written] == [
        RunArtifact.OVERVIEW_VIDEO,
        RunArtifact.CAMERA_VIDEO,
        RunArtifact.DETECTIONS,
    ]
    assert all(path.stat().st_size > 0 for path in written)
    assert performed.overview.frames
    assert len(performed.camera_film.frames) == len(performed.overview.frames)


# %% what the run records of itself


def test_the_run_records_one_trial_of_its_own_episode(
    performed: SimulatedPickupDemo,
) -> None:
    trial = performed.trial

    assert trial.episode is performed.episode
    assert trial.episode.world is performed.lab.reality
    assert trial.outcome is TrialOutcome.SUCCEEDED
    assert trial.duration > 0.0


def test_the_monitor_saw_the_asked_piece_picked_up(
    performed: SimulatedPickupDemo,
) -> None:
    """
    The event monitor watched the piece the run is asked about, so among what it
    reported is that piece being picked up.
    """
    watched = performed.lab.real_piece_of(performed.piece_asked_about).root

    picked_up = [
        event
        for tick in performed.trial.ticks
        for event in tick.events
        if isinstance(event, PickUpEvent) and event.tracked_object is watched
    ]

    assert picked_up
    assert all(
        0.0 <= tick.moment <= performed.trial.duration for tick in performed.trial.ticks
    )


def test_every_plan_the_rig_performed_is_recorded_with_when_its_actions_ran(
    performed: SimulatedPickupDemo,
) -> None:
    """
    One plan is performed per piece the look found, each of a pick-up and a place, and
    each action ran over a stretch of the trial the record places it in.
    """
    trial = performed.trial
    assert len(trial.plans) == len(performed.sorting.pieces)

    items = RunPlan.of(trial).items
    assert {type(item.action) for item in items} == {
        PickUpActionMujoco,
        PlaceActionMujoco,
    }
    assert all(0.0 <= item.start and item.duration > 0.0 for item in items)
    assert all(item.start + item.duration <= trial.duration for item in items)


def test_the_plan_accounts_for_the_pick_up_the_monitor_saw(
    performed: SimulatedPickupDemo,
) -> None:
    """
    The pick-up was reported while the item that picks that very piece up -- named as
    the belief holds it, matched as the kind of piece it is -- was running.
    """
    watched = performed.lab.real_piece_of(performed.piece_asked_about).root
    [picked_up] = [
        event
        for tick in performed.trial.ticks
        for event in tick.events
        if isinstance(event, PickUpEvent) and event.tracked_object is watched
    ][:1]

    accounting = RunPlan.of(performed.trial, identity=SamePiece()).accounts_for(
        picked_up
    )

    assert accounting is not None
    assert isinstance(accounting.action, PickUpActionMujoco)


def test_the_question_set_was_asked_as_the_piece_came_to_rest_and_answered_correctly(
    performed: SimulatedPickupDemo,
) -> None:
    """
    The set is asked the moment the monitor reports the piece asked about has stopped
    moving, so the query stands right after the carry it is about rather than at the
    end of the run.
    """
    queries = performed.trial.queries
    piece = performed.lab.real_piece_of(performed.piece_asked_about).root
    came_to_rest = [
        tick
        for tick in performed.trial.ticks
        if any(
            isinstance(event, StopTranslationEvent) and event.tracked_object is piece
            for event in tick.events
        )
    ][0]

    assert queries
    [picked_up_recently] = [
        query for query in queries if isinstance(query.question, PickedUpRecently)
    ]
    assert picked_up_recently.answered_correctly is True
    assert came_to_rest.moment <= picked_up_recently.moment
    assert picked_up_recently.moment - came_to_rest.moment < TRACE_PERIOD * 2


def test_the_joints_and_the_camera_are_traced_along_the_trial(
    performed: SimulatedPickupDemo,
) -> None:
    joints = performed.tracing.joints
    camera = performed.camera_film.timed_frames()

    assert not joints.is_empty
    assert joints.moments == sorted(joints.moments)
    assert (
        len(camera.frames) == len(camera.moments) == len(performed.camera_film.frames)
    )
    assert camera.moments == sorted(camera.moments)


def test_the_run_keeps_everything_as_the_artifacts_of_its_episode(
    performed: SimulatedPickupDemo, tmp_path: Path
) -> None:
    artifacts = performed.keep(
        ArtifactDirectory(path=tmp_path).open_for(performed.episode)
    )

    kept = artifacts.trial(performed.trial.number)
    assert artifacts.video.is_file()
    assert artifacts.transcript.is_file()
    assert kept.kept_a_joint_trace and kept.kept_a_camera
    assert kept.camera.moments == performed.camera_film.moments


# %% someone shoving the piece while the robot is idle


@pytest.fixture(scope="module")
def shoved() -> SimulatedPickupDemo:
    """
    The run with the cube alone on the table and someone shoving it across the table
    after the look and before the sorting, performed once headless.
    """
    demo = SimulatedPickupDemo(
        lab=SimulatedLab.build(
            pieces=KnownPieceSet(
                pieces=(SMALLER_PIECES.by_category[MontessoriShapeCategory.CUBE],)
            )
        ),
        piece_asked_about=MontessoriShapeCategory.CUBE,
        shove=Shove(category=MontessoriShapeCategory.CUBE, along_y=SHOVED_ALONG_Y),
    )
    demo.perform()
    return demo


SHOVED_ALONG_Y = 0.08
"""
How far the cube is shoved, in metres: further than the pads reach, so the plan made
before the shove closes on nothing.
"""


def test_the_shoved_piece_was_seen_moving_while_nothing_in_the_plan_was_running(
    shoved: SimulatedPickupDemo,
) -> None:
    """
    The answer of no is a translation the monitor reported at a moment no item of the
    plan that acts on that piece was running.
    """
    cube = shoved.lab.real_piece_of(MontessoriShapeCategory.CUBE).root
    plan = RunPlan.of(shoved.trial, identity=SamePiece())
    moved = [
        event
        for tick in shoved.trial.ticks
        for event in tick.events
        if isinstance(event, TranslationEvent) and event.tracked_object is cube
    ]

    assert moved
    assert plan.accounts_for(moved[0]) is None
    assert plan.moment_of(moved[0]) < min(item.start for item in plan.items)


def test_the_plan_made_before_the_shove_still_reaches_for_the_piece(
    shoved: SimulatedPickupDemo,
) -> None:
    """
    The robot did not see the shove, so the plan it made goes on to pick the piece up
    where it was seen -- which is what makes this the same plan as the other run's,
    told apart only by when the piece moved.
    """
    [item] = [
        item
        for item in RunPlan.of(shoved.trial).items
        if isinstance(item.action, PickUpActionMujoco)
    ]
    assert item.acts_on(
        shoved.lab.real_piece_of(MontessoriShapeCategory.CUBE).root, SamePiece()
    )


def test_the_shoved_piece_was_not_picked_up(shoved: SimulatedPickupDemo) -> None:
    [picked_up_recently] = [
        query
        for query in shoved.trial.queries
        if isinstance(query.question, PickedUpRecently)
    ]
    assert picked_up_recently.answered_correctly is True
    assert shoved.trial.outcome is TrialOutcome.FAILED
