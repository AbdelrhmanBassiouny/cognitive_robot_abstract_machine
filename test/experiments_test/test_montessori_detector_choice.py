"""
Tests for choosing which detector answers a look, from what the world says about the
surface and the piece being looked for.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from krrood.entity_query_language.factories import ConditionType
from krrood.entity_query_language.rdr.rule_tree_view import walk_rules

from experiments.montessori.perception.camera import RgbdFrame
from experiments.montessori.perception.detections import MontessoriShapeDetection
from experiments.montessori.perception.detector_choice import (
    DetectorRules,
    PieceDetector,
    TargetOnSurface,
)
from experiments.montessori.perception.edges import EdgeDistances
from experiments.montessori.perception.exceptions import NoDetectorAnswersTheLook
from experiments.montessori.perception.orthophoto import (
    Orthophoto,
    OrthophotoProjector,
    WorkspaceRegion,
)
from experiments.montessori.perception.look_choice import RectifiedFrame
from experiments.montessori.perception.pipeline import (
    ColorBlobDetector,
    EdgeFitDetector,
    MontessoriPerceptionPipeline,
)
from experiments.montessori.perception.surfaces import SurfaceSearch, WorkspaceSurface
from experiments.montessori.pieces import (
    KNOWN_PIECE_BY_CATEGORY,
    HUE_RANGE,
    color_of_hue,
    HUE_TOLERANCE,
    KNOWN_PIECES,
    KnownPiece,
    hue_distance,
)
from experiments.montessori.semantics import (
    MontessoriShapeCategory,
    ShapeSortingBoard,
)
from experiments.montessori.world import MontessoriWorld
from semantic_digital_twin.semantic_annotations.semantic_annotations import Table
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.world_description.geometry import Color, SurfaceFinish
from semantic_digital_twin.world_description.world_entity import (
    KinematicStructureEntity,
)
from typing_extensions import List, Optional, Sequence

from .dataset import montessori_scene_fixtures
from .dataset.montessori_scene_renderer import (
    LID_COLOR,
    TABLE_COLOR,
    MontessoriSceneRenderer,
)

pytest_plugins = [montessori_scene_fixtures.__name__]

# %% surfaces and targets to choose between


def _surface(
    finish: SurfaceFinish | None = None, color: Color | None = None
) -> WorkspaceSurface:
    """
    A surface stating only what the rules read.

    :param finish: How the world says the surface takes light.
    :param color: The colour the world states for the surface.
    """
    return WorkspaceSurface(
        name=PrefixedName("surface", "test"),
        region=WorkspaceRegion(
            minimum_x=0.0, maximum_x=1.0, minimum_y=0.0, maximum_y=1.0
        ),
        height=0.0,
        finish=finish,
        color=color,
    )


def _piece_of_hue(hue: int) -> KnownPiece:
    """
    A known piece wearing one colour, with the outline of a real one.

    :param hue: The colour it was measured to be, as OpenCV reports hue.
    """
    cube = _piece_of_category(MontessoriShapeCategory.CUBE)
    return KnownPiece(
        category=cube.category,
        outline=cube.outline,
        height=cube.height,
        hue=hue,
        rotation_period=cube.rotation_period,
    )


def _piece_of_category(category: MontessoriShapeCategory) -> KnownPiece:
    """
    The piece this set holds of one shape.

    :param category: The shape to look up.
    """
    [piece] = [piece for piece in KNOWN_PIECES if piece.category is category]
    return piece


def _piece_of_no_outline(hue: int = 30) -> KnownPiece:
    """
    A piece whose shape is not modelled, which is the look the edge fit declares it
    cannot answer.

    :param hue: The colour it was measured to be, as OpenCV reports hue.
    """
    return replace(_piece_of_hue(hue), outline=None)


def _color_of_hue(hue: int) -> Color:
    """
    The colour a hue names, at full saturation and brightness.

    :param hue: The hue, as OpenCV reports it.
    """
    return _piece_of_hue(hue).color


# %% what the rules read


def test_a_look_reads_the_finish_off_the_surface_it_holds():
    """
    A look holds the surface itself rather than a copy of what it happens to say, so
    what a rule reads about a surface is what the world states about it, with nothing in
    between to fall out of step with it.
    """
    surface = _surface(finish=SurfaceFinish.MIRROR)

    look = TargetOnSurface(surface, _piece_of_hue(30))

    assert look.surface is surface
    assert look.surface.finish is SurfaceFinish.MIRROR


def test_a_target_whose_hue_is_far_from_the_surface_separates_from_it():
    surface_hue = 20
    target_hue = surface_hue + HUE_TOLERANCE + 1
    surface = _surface(color=_color_of_hue(surface_hue))

    look = TargetOnSurface(surface, _piece_of_hue(target_hue))

    assert hue_distance(surface_hue, target_hue) > HUE_TOLERANCE
    assert look.target_separates_from_the_surface_by_color


def test_a_target_wearing_the_surfaces_own_hue_does_not_separate_from_it():
    surface_hue = 19
    target_hue = 21
    surface = _surface(color=_color_of_hue(surface_hue))

    look = TargetOnSurface(surface, _piece_of_hue(target_hue))

    assert hue_distance(surface_hue, target_hue) <= HUE_TOLERANCE
    assert not look.target_separates_from_the_surface_by_color


def test_a_target_on_a_surface_of_unstated_color_is_not_claimed_to_separate():
    surface = _surface(color=None)

    look = TargetOnSurface(surface, _piece_of_hue(30))

    assert not look.target_separates_from_the_surface_by_color


def test_the_hue_separation_wraps_around_the_colour_circle():
    surface_hue = 1
    target_hue = HUE_RANGE - 1
    surface = _surface(color=_color_of_hue(surface_hue))

    look = TargetOnSurface(surface, _piece_of_hue(target_hue))

    assert not look.target_separates_from_the_surface_by_color


# %% what each detector declares it can answer


def test_the_edge_fit_answers_a_look_for_a_piece_of_known_outline():
    look = TargetOnSurface(_surface(finish=SurfaceFinish.MIRROR), _piece_of_hue(30))

    assert EdgeFitDetector().asked_about(look).tolist()


def test_the_color_blob_answers_only_where_colour_separates_the_target():
    separating, merging = (
        TargetOnSurface(_surface(color=_color_of_hue(20)), _piece_of_hue(hue))
        for hue in (20 + HUE_TOLERANCE + 1, 21)
    )
    detector = ColorBlobDetector()

    assert detector.asked_about(separating).tolist()
    assert not detector.asked_about(merging).tolist()


def test_a_detector_states_the_looks_it_answers_once_and_is_asked_per_look():
    detector = EdgeFitDetector()
    look = TargetOnSurface(_surface(finish=SurfaceFinish.MIRROR), _piece_of_hue(30))

    assert detector.asked_about(look).tolist()
    stated = detector.answerable_looks
    assert not detector.asked_about(
        replace(look, target=_piece_of_no_outline())
    ).tolist()

    assert detector.answerable_looks is stated


# %% which detector the rules choose


@pytest.fixture
def rules() -> DetectorRules:
    """
    The rules over the two detectors this scene has.
    """
    return DetectorRules(edge_fit=EdgeFitDetector(), color_blob=ColorBlobDetector())


def test_a_mirror_surface_is_looked_at_by_fitting_edges(rules):
    look = TargetOnSurface(
        _surface(finish=SurfaceFinish.MIRROR, color=_color_of_hue(20)),
        _piece_of_hue(60),
    )

    assert isinstance(rules.detector_for(look), EdgeFitDetector)


def test_a_matte_surface_is_looked_at_by_colour_where_colour_separates(rules):
    look = TargetOnSurface(
        _surface(finish=SurfaceFinish.MATTE, color=_color_of_hue(20)),
        _piece_of_hue(60),
    )

    assert isinstance(rules.detector_for(look), ColorBlobDetector)


def test_a_target_wearing_a_matte_surfaces_hue_falls_back_to_fitting_edges(rules):
    look = TargetOnSurface(
        _surface(finish=SurfaceFinish.MATTE, color=_color_of_hue(19)),
        _piece_of_hue(21),
    )

    assert isinstance(rules.detector_for(look), EdgeFitDetector)


def test_a_surface_of_unstated_finish_is_looked_at_by_fitting_edges(rules):
    look = TargetOnSurface(_surface(color=_color_of_hue(20)), _piece_of_hue(60))

    assert isinstance(rules.detector_for(look), EdgeFitDetector)


def test_the_rules_answer_with_a_detector_they_were_given(rules):
    look = TargetOnSurface(
        _surface(finish=SurfaceFinish.MATTE, color=_color_of_hue(20)),
        _piece_of_hue(60),
    )

    assert rules.detector_for(look) is rules.color_blob


def test_a_look_no_detector_answers_is_refused(rules):
    """
    A piece whose outline is not modelled has nothing for the edge fit to lay over what
    the camera saw, and on a surface whose colour it shares nothing for the colour blob
    to cut it out of, so the look is refused rather than answered by a detector that
    declared it could not.
    """
    look = TargetOnSurface(
        _surface(finish=SurfaceFinish.MATTE, color=_color_of_hue(19)),
        _piece_of_no_outline(21),
    )

    with pytest.raises(NoDetectorAnswersTheLook):
        rules.detector_for(look)


def test_every_detector_the_rules_choose_declared_it_could_answer(rules):
    looks = [
        TargetOnSurface(_surface(finish=finish, color=_color_of_hue(19)), piece)
        for finish in (None, SurfaceFinish.MATTE, SurfaceFinish.MIRROR)
        for piece in (_piece_of_hue(21), _piece_of_hue(60))
    ]

    for look in looks:
        assert rules.detector_for(look).asked_about(look).tolist()


def test_the_rules_are_stated_over_the_look_itself(rules):
    """
    What a rule reads is the look being taken, and what the rules work out about it is
    the slot that look leaves open, so neither is named a second time here.
    """
    assert rules.rules.case_type is TargetOnSurface
    assert rules.rules.conclusion_attribute_name in vars(
        TargetOnSurface(_surface(), _piece_of_hue(30))
    )


def test_the_rules_can_be_read_as_a_tree(rules):
    """
    A tree of rules is worth having only if it can be read, so the detector chosen for
    one look is named in the rendering of the rules that chose it.
    """
    look = TargetOnSurface(
        _surface(finish=SurfaceFinish.MATTE, color=_color_of_hue(20)),
        _piece_of_hue(60),
    )

    assert type(rules.color_blob).__name__ in rules.render_tree(look)


# %% growing the rules while they are in use


@dataclass(eq=False)
class DetectorAddedAfterTheRulesWereStated(PieceDetector):
    """
    A detector standing for one reached for after the rules are already in use, so a
    situation nobody foresaw can be given a rule without the rules being rewritten.
    """

    piece_height: float = 0.0

    def capability(self, look: TargetOnSurface) -> ConditionType:
        """
        Answers any look for a piece whose outline is modelled.

        :param look: The look to state the condition over.
        """
        return look.target_outline_is_known

    def detect(
        self,
        orthophoto: Orthophoto,
        top_orthophoto: Orthophoto,
        edges: EdgeDistances,
        frame: RgbdFrame,
        reference_frame: Optional[KinematicStructureEntity],
        search: SurfaceSearch,
        candidates: Sequence[KnownPiece] = KNOWN_PIECES,
    ) -> List[MontessoriShapeDetection]:
        """
        Finds nothing: this detector stands for the choice, not for a way of looking.
        """
        return []


def test_a_situation_the_rules_did_not_cover_is_given_a_rule_while_they_are_in_use(
    rules,
):
    added = DetectorAddedAfterTheRulesWereStated()
    look = TargetOnSurface(
        _surface(finish=SurfaceFinish.GLOSSY, color=_color_of_hue(19)),
        _piece_of_hue(21),
    )
    assert rules.detector_for(look) is rules.edge_fit

    rules.add_rule(look, added)

    assert rules.detector_for(look) is added


def test_a_rule_added_while_the_rules_are_in_use_leaves_the_stated_ones_answering(
    rules,
):
    matte = TargetOnSurface(
        _surface(finish=SurfaceFinish.MATTE, color=_color_of_hue(20)),
        _piece_of_hue(60),
    )
    mirror = TargetOnSurface(
        _surface(finish=SurfaceFinish.MIRROR, color=_color_of_hue(20)),
        _piece_of_hue(60),
    )

    rules.add_rule(
        TargetOnSurface(
            _surface(finish=SurfaceFinish.GLOSSY, color=_color_of_hue(19)),
            _piece_of_hue(21),
        ),
        DetectorAddedAfterTheRulesWereStated(),
    )

    assert rules.detector_for(matte) is rules.color_blob
    assert rules.detector_for(mirror) is rules.edge_fit


# %% the scene as the world describes it, and what that changes


def _annotated(
    surface: WorkspaceSurface, finish: SurfaceFinish, hue: int
) -> WorkspaceSurface:
    """
    The same surface, with what the world says about it filled in.

    :param surface: The surface as the pipeline reads it today.
    :param finish: How the surface takes light.
    :param hue: The colour it was measured to wear.
    """
    return replace(surface, finish=finish, color=color_of_hue(hue))


@pytest.fixture
def annotated_pipeline(
    pipeline: MontessoriPerceptionPipeline,
) -> MontessoriPerceptionPipeline:
    """
    The rendered scene's pipeline, with the table and the lid described the way the real
    ones were measured: a mirror-finished steel table and a matte wooden lid.
    """
    return replace(
        pipeline,
        table=_annotated(pipeline.table, SurfaceFinish.MIRROR, TABLE_COLOR[0]),
        lid=_annotated(pipeline.lid, SurfaceFinish.MATTE, LID_COLOR[0]),
    )


def test_nothing_is_annotated_yet_so_every_look_falls_to_the_edge_fit(
    pipeline: MontessoriPerceptionPipeline,
):
    for surface in (pipeline.table, pipeline.lid):
        [(detector, chosen_for)] = (
            pipeline.look_rules.find_the_pieces.detector_rules.detectors_for(
                surface, KNOWN_PIECES
            )
        )
        assert isinstance(detector, EdgeFitDetector)
        assert chosen_for == KNOWN_PIECES


def test_a_mirror_table_is_searched_by_fitting_edges_whatever_the_piece(
    annotated_pipeline: MontessoriPerceptionPipeline,
):
    [(detector, chosen_for)] = (
        annotated_pipeline.look_rules.find_the_pieces.detector_rules.detectors_for(
            annotated_pipeline.table, KNOWN_PIECES
        )
    )

    assert isinstance(detector, EdgeFitDetector)
    assert chosen_for == KNOWN_PIECES


def test_a_matte_lid_splits_the_pieces_by_whether_colour_separates_them(
    annotated_pipeline: MontessoriPerceptionPipeline,
):
    chosen = {
        type(detector): {piece.hue for piece in pieces}
        for detector, pieces in annotated_pipeline.look_rules.find_the_pieces.detector_rules.detectors_for(
            annotated_pipeline.lid, KNOWN_PIECES
        )
    }

    lid_hue = LID_COLOR[0]
    assert chosen[ColorBlobDetector] == {
        piece.hue
        for piece in KNOWN_PIECES
        if hue_distance(piece.hue, lid_hue) > HUE_TOLERANCE
    }
    assert chosen[EdgeFitDetector] == {
        piece.hue
        for piece in KNOWN_PIECES
        if hue_distance(piece.hue, lid_hue) <= HUE_TOLERANCE
    }


def test_a_piece_on_an_annotated_lid_is_still_found_by_the_detector_chosen_for_it(
    annotated_pipeline: MontessoriPerceptionPipeline,
    renderer: MontessoriSceneRenderer,
    placed_pieces,
    piece_on_the_lid,
):
    scene = annotated_pipeline.detect(
        renderer.render([*placed_pieces, piece_on_the_lid])
    )

    on_the_lid = [
        piece
        for piece in scene.shapes
        if piece.supporting_surface == annotated_pipeline.lid.name
    ]
    assert [piece.category for piece in on_the_lid] == [piece_on_the_lid.category]


def test_the_colour_blob_finds_on_a_matte_lid_what_the_edge_fit_finds(
    annotated_pipeline: MontessoriPerceptionPipeline,
    renderer: MontessoriSceneRenderer,
    piece_on_the_lid,
):
    """
    What makes the cheaper detector worth preferring: on the surface the rules choose it
    for, it reports the same piece the general one does.
    """
    frame = renderer.render([piece_on_the_lid])
    lid = annotated_pipeline.lid
    rectified = RectifiedFrame(
        frame=frame, projector=OrthophotoProjector(region=lid.region)
    )
    search = SurfaceSearch(surface=lid)
    cyan = tuple(
        piece
        for piece in KNOWN_PIECES
        if hue_distance(piece.hue, LID_COLOR[0]) > HUE_TOLERANCE
    )

    found_by = {
        type(detector): detector.detect(
            rectified.at(lid.height),
            rectified.at(lid.height + detector.piece_height),
            rectified.edges_at(lid.height + detector.piece_height),
            frame,
            None,
            search,
            cyan,
        )
        for detector in (EdgeFitDetector(), ColorBlobDetector())
    }

    assert (
        [piece.category for piece in found_by[ColorBlobDetector]]
        == [piece.category for piece in found_by[EdgeFitDetector]]
        == [piece_on_the_lid.category]
    )


# %% the world's own surfaces deciding the look


def test_the_world_states_a_finish_so_a_look_at_its_lid_is_answered_by_colour(rules):
    montessori = MontessoriWorld()
    [board] = montessori.world.get_semantic_annotations_by_type(ShapeSortingBoard)
    lid = WorkspaceSurface.of_body(board.root, montessori.world.root)

    look = TargetOnSurface(lid, KNOWN_PIECE_BY_CATEGORY[MontessoriShapeCategory.CUBE])

    assert rules.detector_for(look) is rules.color_blob


def test_the_worlds_own_table_is_looked_at_by_fitting_edges(rules):
    montessori = MontessoriWorld()
    [table] = montessori.world.get_semantic_annotations_by_type(Table)
    surface = WorkspaceSurface.of_body(table.root, montessori.world.root)

    look = TargetOnSurface(
        surface, KNOWN_PIECE_BY_CATEGORY[MontessoriShapeCategory.CUBE]
    )

    assert rules.detector_for(look) is rules.edge_fit


def test_a_piece_wearing_the_boards_own_wood_falls_back_to_fitting_edges(rules):
    montessori = MontessoriWorld()
    [board] = montessori.world.get_semantic_annotations_by_type(ShapeSortingBoard)
    lid = WorkspaceSurface.of_body(board.root, montessori.world.root)

    look = TargetOnSurface(
        lid, KNOWN_PIECE_BY_CATEGORY[MontessoriShapeCategory.TRIANGULAR_PRISM]
    )

    assert rules.detector_for(look) is rules.edge_fit


# %% the stated rules, put to the surfaces the world really states


def test_the_stated_rules_answer_the_scenes_own_surfaces_without_needing_a_new_rule(
    rules,
):
    """
    A stated rule is not derived from a case, so what says it is right is a real surface
    put to it: fitting the two the modelled scene states -- the brushed steel table and
    the board's painted lid -- with the detector each should get leaves the tree the size
    it was, because both were already answered that way.
    """
    montessori = MontessoriWorld()
    montessori.world.update_forward_kinematics()
    [table] = montessori.world.get_semantic_annotations_by_type(Table)
    pipeline = MontessoriPerceptionPipeline.of_world(montessori.world, table.root)
    target = KNOWN_PIECES[0]
    stated = len(walk_rules(rules.rules.conditions_root))

    for surface, expected in (
        (pipeline.table, rules.edge_fit),
        (pipeline.lid, rules.color_blob),
    ):
        look = TargetOnSurface(surface, target)
        assert rules.detector_for(look) is expected
        rules.add_rule(look, expected)

    assert len(walk_rules(rules.rules.conditions_root)) == stated
