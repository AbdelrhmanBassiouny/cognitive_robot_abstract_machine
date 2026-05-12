from __future__ import annotations

from dataclasses import dataclass
from krrood.patterns.role import HasRoles


@dataclass
class CrossModuleBaseTaker(HasRoles):
    base_field: str = ""

    def base_method(self) -> str: ...
