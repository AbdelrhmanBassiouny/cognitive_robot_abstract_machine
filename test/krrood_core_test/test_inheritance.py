from krrood_core.inheritance import inheritance_path_length

from .dataset.patterns import Diamond, LongBranch, Root, Unrelated


def test_the_shortest_branch_decides_the_length():
    assert inheritance_path_length(Diamond, Root) == 2


def test_a_class_is_no_levels_from_itself():
    assert inheritance_path_length(Root, Root) == 0


def test_a_single_branch_counts_every_level():
    assert inheritance_path_length(LongBranch, Root) == 2


def test_an_unrelated_class_has_no_length():
    assert inheritance_path_length(Unrelated, Root) is None
