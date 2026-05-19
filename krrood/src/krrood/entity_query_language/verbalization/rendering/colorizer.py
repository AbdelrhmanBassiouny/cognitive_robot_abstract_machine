from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol

from krrood.entity_query_language.verbalization.fragments.roles import ROLE_COLORS, SemanticRole
from typing_extensions import ClassVar


@dataclass
class Colorizer(ABC):
    """Applies visual styling to a text string based on its semantic role."""

    @abstractmethod
    def colorize(self, text: str, role: SemanticRole) -> str:
        """
        :param text: The text to colorize
        :param role: The semantic role of the text
        :return: The colorized text
        """
        ...


@dataclass
class PlainColorizer(Colorizer):
    """Returns text unchanged — no color markup."""

    def colorize(self, text: str, role: SemanticRole) -> str:
        return text


@dataclass
class ANSIColorizer(Colorizer):
    """
    Wraps text in true-color ANSI escape sequences (24-bit, ``\\033[38;2;R;G;Bm``).

    Works in VS Code terminal, GNOME Terminal, iTerm2, Windows Terminal, and any
    other terminal that supports the ISO-8613-3 direct-color extension.
    """

    _RESET: ClassVar[str] = "\033[0m"
    """
    The ANSI escape sequence to reset the terminal color to the default.
    """
    _NAMED: ClassVar[dict[str, tuple[int, int, int]]] = {
        "cornflowerblue": (100, 149, 237),
    }
    """
    Named colors used in ROLE_COLORS (currently only "cornflowerblue")
    """

    def colorize(self, text: str, role: SemanticRole) -> str:
        color = ROLE_COLORS.get(role)
        if color is None:
            return text
        r, g, b = self._hex_to_rgb(color)
        return f"\033[38;2;{r};{g};{b}m{text}{self._RESET}"

    def _hex_to_rgb(self, color: str) -> tuple[int, int, int]:
        """
        Convert ``"#rrggbb"`` or a CSS named color to an ``(R, G, B)`` tuple.
        """
        if color.startswith("#"):
            h = color.lstrip("#")
            return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return self._NAMED.get(color.lower(), (255, 255, 255))

@dataclass
class MarkdownColorizer(Colorizer):
    """
    Wraps text in an HTML ``<span style="color: …">`` tag.

    The output is valid inside GitHub-flavored Markdown rendered by any renderer
    that passes through inline HTML (Jupyter, GitLab, most static-site generators).
    """

    def colorize(self, text: str, role: SemanticRole) -> str:
        color = ROLE_COLORS.get(role)
        if color is None:
            return text
        return f'<span style="color:{color}">{text}</span>'
