import numpy as np

from semantic_digital_twin.world_description.geometry import Bounds


# %% reading bounds off a point cloud
def test_bounds_enclose_every_point_they_were_read_from():
    points = np.array([[1.0, -2.0, 3.0], [-1.0, 2.0, 0.5], [0.0, 0.0, 4.0]])

    bounds = Bounds.from_points(points)

    assert bounds.lower.tolist() == [-1.0, -2.0, 0.5]
    assert bounds.upper.tolist() == [1.0, 2.0, 4.0]


# %% overlap
def test_bounds_that_share_a_region_overlap():
    left = Bounds(np.array([0.0, 0.0, 0.0]), np.array([2.0, 2.0, 2.0]))
    right = Bounds(np.array([1.0, 1.0, 1.0]), np.array([3.0, 3.0, 3.0]))

    assert left.overlaps(right)
    assert right.overlaps(left)


def test_bounds_separated_along_one_axis_do_not_overlap():
    """
    A single axis is enough to rule an overlap out, which is what makes this worth
    checking before an exact intersection.
    """
    left = Bounds(np.array([0.0, 0.0, 0.0]), np.array([2.0, 2.0, 2.0]))
    right = Bounds(np.array([0.0, 0.0, 5.0]), np.array([2.0, 2.0, 7.0]))

    assert not left.overlaps(right)
    assert not right.overlaps(left)


def test_bounds_meeting_at_a_face_overlap():
    """
    Touching counts as overlapping, so that a cheap rejection never rules out a pair an
    exact check would still have something to say about.
    """
    left = Bounds(np.array([0.0, 0.0, 0.0]), np.array([1.0, 1.0, 1.0]))
    right = Bounds(np.array([1.0, 0.0, 0.0]), np.array([2.0, 1.0, 1.0]))

    assert left.overlaps(right)


# %% containment of points
def test_bounds_contain_the_points_inside_them():
    bounds = Bounds(np.array([0.0, 0.0, 0.0]), np.array([1.0, 1.0, 1.0]))
    points = np.array([[0.5, 0.5, 0.5], [2.0, 0.5, 0.5], [0.5, 0.5, -0.1]])

    assert bounds.contains(points).tolist() == [True, False, False]


def test_bounds_contain_a_point_on_their_boundary():
    bounds = Bounds(np.array([0.0, 0.0, 0.0]), np.array([1.0, 1.0, 1.0]))

    assert bounds.contains(np.array([[0.5, 0.5, 1.0]])).tolist() == [True]


def test_bounds_with_no_volume_contain_nothing():
    """
    A region flattened onto a plane encloses no volume, so nothing is inside it -- not
    even a point lying on it.
    """
    bounds = Bounds(np.array([0.0, 0.0, 1.0]), np.array([1.0, 1.0, 1.0]))

    assert bounds.contains(np.array([[0.5, 0.5, 1.0]])).tolist() == [False]
