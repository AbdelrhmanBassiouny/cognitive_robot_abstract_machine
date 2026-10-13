from pathlib import Path

from .dataset.patterns import DirectoryLayout


def test_a_member_is_the_path_it_names():
    assert DirectoryLayout.CONFIGURATION == DirectoryLayout.ROOT.value / "settings.toml"


def test_a_path_derived_from_a_member_is_a_plain_path():
    derived = DirectoryLayout.ROOT / "cache"

    assert type(derived) is type(Path())


def test_a_member_and_its_path_are_one_key():
    lookup = {DirectoryLayout.ROOT: DirectoryLayout.ROOT._name_}

    assert lookup[Path(DirectoryLayout.ROOT.value)] == DirectoryLayout.ROOT._name_
