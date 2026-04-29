from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CrossModuleBase:
    cross_field: str = ""

    def cross_method(self) -> int: ...
