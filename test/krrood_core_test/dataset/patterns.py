from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from krrood_core.class_property import classproperty
from krrood_core.field_metadata import JSONMetadata
from krrood_core.path_enumeration import PathEnumeration

# %% class properties


class HasAbstractClassConstant(ABC):
    """
    Declares a constant every concrete subclass has to supply.
    """

    @classproperty
    @abstractmethod
    def unit(cls) -> str:
        """
        The unit the subclass measures in.
        """


class SuppliesClassConstant(HasAbstractClassConstant):
    """
    Supplies the constant its base declares.
    """

    @classproperty
    def unit(cls) -> str:
        return cls.__name__.lower()


class OmitsClassConstant(HasAbstractClassConstant):
    """
    Supplies nothing, so stays abstract.
    """


# %% path enumerations


class DirectoryLayout(PathEnumeration):
    """
    Paths named by an enumeration.
    """

    ROOT = Path("/srv/data")
    CONFIGURATION = ROOT / "settings.toml"


# %% inheritance


class Root:
    """
    The top of a diamond.
    """


class ShortBranch(Root):
    """
    One level below the top.
    """


class Middle(Root):
    """
    One level below the top, on the long branch.
    """


class LongBranch(Middle):
    """
    Two levels below the top.
    """


class Diamond(ShortBranch, LongBranch):
    """
    Reaches the top through a short and a long branch.
    """


class Unrelated:
    """
    Shares no ancestor with the diamond other than ``object``.
    """


# %% JSON round trips


class Shade(enum.StrEnum):
    """
    A value stored as an enumeration member.
    """

    LIGHT = "light"
    DARK = "dark"


@dataclass
class LabelledShape:
    """
    A dataclass whose fields span the kinds of value the serializer restores.
    """

    label: str
    corners: list[int] = field(default_factory=list)
    shade: Shade = Shade.LIGHT
    location: Path = Path("/tmp")
    weights: dict[str, float] = field(default_factory=dict)
    cached_area: float = field(
        default=0.0, metadata=JSONMetadata(serialize=False).as_dict()
    )
