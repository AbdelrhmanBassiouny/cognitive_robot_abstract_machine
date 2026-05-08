from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CrossModuleBaseTaker:
    base_field: str = ""

    def base_method(self) -> str: ...
