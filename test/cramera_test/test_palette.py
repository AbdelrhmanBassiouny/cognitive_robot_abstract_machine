"""
Recorded and live object colours must come from one cycle.

The onboarder bakes colours into a scene bundle while the bridge assigns them on the
fly. When the two hold separate lists, an object beyond the shorter list's length
changes colour the moment the viewer attaches to a running demo.
"""

import inspect

from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.world_description.geometry import Box, Color, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body, Region

from cramera.live import bridge
from cramera.onboard import demo
from cramera.palette import OBJECT_COLORS, ObjectPalette


class TestObjectPalette:
    def test_colors_are_assigned_in_order(self):
        palette = ObjectPalette()
        assert palette.color_for(0) == OBJECT_COLORS[0]
        assert palette.color_for(2) == OBJECT_COLORS[2]

    def test_the_cycle_wraps_around(self):
        palette = ObjectPalette()
        assert palette.color_for(len(OBJECT_COLORS)) == OBJECT_COLORS[0]

    def test_colors_are_distinct(self):
        assert len(set(OBJECT_COLORS)) == len(OBJECT_COLORS)

    def test_colors_are_stored_as_the_shared_color_type(self):
        """
        The cycle is kept internally as :class:`Color`, converting to ``#rrggbb`` only
        at :meth:`~cramera.palette.ObjectPalette.color_for`'s boundary.
        """
        assert all(isinstance(color, Color) for color in ObjectPalette().colors)


class TestAuthoredColours:
    """
    A world that colours its own shapes is shown in those colours; the cycle only fills
    in for entities whose shapes never declared one.
    """

    def test_a_declared_shape_colour_wins_over_the_cycle(self):
        cube = Body(
            name=PrefixedName("cube"),
            visual=ShapeCollection(
                shapes=[Box(scale=Scale(0.1, 0.1, 0.1), color=Color.RED())]
            ),
        )

        assert ObjectPalette().color_of(cube, 0) == "#ff0000"

    def test_a_regions_area_colour_is_read_too(self):
        hole = Region(
            name=PrefixedName("square_hole"),
            area=ShapeCollection(
                shapes=[Box(scale=Scale(0.05, 0.05, 0.001), color=Color.BLUE())]
            ),
        )

        assert ObjectPalette().color_of(hole, 0) == "#0000ff"

    def test_the_default_colour_counts_as_undeclared(self):
        """
        Every shape carries the default white unless its author chose otherwise, so
        white-by-default must not shadow the cycle.
        """
        plain = Body(
            name=PrefixedName("crate"),
            visual=ShapeCollection(shapes=[Box(scale=Scale(0.1, 0.1, 0.1))]),
        )

        assert ObjectPalette().color_of(plain, 1) == OBJECT_COLORS[1]

    def test_an_entity_without_shapes_takes_its_cycle_colour(self):
        assert (
            ObjectPalette().color_of(Body(name=PrefixedName("ghost")), 2)
            == OBJECT_COLORS[2]
        )

    def test_the_first_declared_colour_of_many_shapes_wins(self):
        striped = Body(
            name=PrefixedName("striped"),
            visual=ShapeCollection(
                shapes=[
                    Box(scale=Scale(0.1, 0.1, 0.1)),
                    Box(scale=Scale(0.1, 0.1, 0.1), color=Color.GREEN()),
                    Box(scale=Scale(0.1, 0.1, 0.1), color=Color.RED()),
                ]
            ),
        )

        assert ObjectPalette().color_of(striped, 0) == "#00ff00"


class TestOnlyOnePaletteExists:
    def test_neither_producer_defines_its_own_cycle(self):
        """
        Both colour producers must reference the shared cycle, not a private copy.
        """
        for module in (bridge, demo):
            source = inspect.getsource(module)
            assert "ObjectPalette" in source, module.__name__
            assert "#f3f0ea" not in source, module.__name__

    def test_both_producers_prefer_the_authored_colour(self):
        """
        Recorded bundles and the live catalog must colour a body the same way, so both
        go through :meth:`~cramera.palette.ObjectPalette.color_of` rather than reading
        the cycle directly.
        """
        for module in (bridge, demo):
            source = inspect.getsource(module)
            assert ".color_of(" in source, module.__name__

    def test_both_producers_agree_beyond_the_shortest_former_list(self):
        """
        Index 6 is where the bridge's old ten-colour list and the onboarder's old six-
        colour list disagreed.
        """
        palette = ObjectPalette()
        assert palette.color_for(6) == OBJECT_COLORS[6]
