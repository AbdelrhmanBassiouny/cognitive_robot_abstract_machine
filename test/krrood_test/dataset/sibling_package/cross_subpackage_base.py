from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CrossSubpackageBase:
    sub_field: str = ""

    def sub_method(self) -> int: ...
