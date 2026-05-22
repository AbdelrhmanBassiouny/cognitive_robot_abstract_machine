from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar

from krrood.entity_query_language.verbalization.fragments.roles import ROLE_COLORS, SemanticRole

_log = logging.getLogger(__name__)


class BulletStyle(Enum):
    """
    Bullet character used by
    :class:`~krrood.entity_query_language.verbalization.rendering.renderer.HierarchicalRenderer`
    for list items.

    :cvar DASH: ``"-"``
    :cvar DOT: ``"•"``
    :cvar ASTERISK: ``"*"``
    """

    DASH = "-"
    DOT = "•"
    ASTERISK = "*"


class IndentSize(Enum):
    """
    Indentation string used by
    :class:`~krrood.entity_query_language.verbalization.rendering.renderer.HierarchicalRenderer`
    per nesting level.

    :cvar TWO_SPACES: Two-space indent (default).
    :cvar FOUR_SPACES: Four-space indent.
    :cvar TAB: Hard tab character.
    """

    TWO_SPACES = "  "
    FOUR_SPACES = "    "
    TAB = "\t"


def _detect_osc8_support() -> bool:
    """Return ``True`` when the current terminal is known to support OSC 8 hyperlinks."""
    if os.environ.get("VTE_VERSION"):          # GNOME Terminal, Tilix, …
        return True
    term_prog = os.environ.get("TERM_PROGRAM", "")
    if term_prog in {"vscode", "WezTerm", "iTerm.app"}:
        return True
    if os.environ.get("TERM") == "xterm-kitty":
        return True
    return False


@dataclass
class Formatter(ABC):
    """
    Single source of truth for all format-specific characters and colour markup.

    Concrete subclasses determine how colours, spaces, newlines, and hyperlinks
    are encoded in the output string.

    Subclasses: :class:`PlainFormatter`, :class:`ANSIFormatter`, :class:`HTMLFormatter`.
    """

    @abstractmethod
    def colorize(self, text: str, role: SemanticRole) -> str:
        """
        Wrap *text* in format-specific colour markup for *role*.

        :param text: Plain display text to colourize.
        :type text: str
        :param role: Semantic role determining the colour.
        :type role: ~krrood.entity_query_language.verbalization.fragments.roles.SemanticRole
        :returns: Coloured string (or *text* unchanged when no colour is defined for *role*).
        :rtype: str
        """
        ...

    @property
    @abstractmethod
    def space(self) -> str:
        """
        Inline word separator character(s) (e.g. ``" "`` or ``"&nbsp;"``).

        :rtype: str
        """
        ...

    @property
    @abstractmethod
    def newline(self) -> str:
        """
        Line break character(s) (e.g. ``"\\n"`` or ``"<br>"``).

        :rtype: str
        """
        ...

    def wrap_link(self, text: str, url: str) -> str:
        """
        Wrap already-rendered *text* with a hyperlink to *url*.

        The base implementation is a no-op (hyperlinks not supported for this format).
        Subclasses override when the output format supports clickable links.

        :param text: Already-colourized display text.
        :type text: str
        :param url: Destination URL.
        :type url: str
        :returns: *text* unchanged (base); linked string (subclasses).
        :rtype: str
        """
        return text


@dataclass
class PlainFormatter(Formatter):
    """
    No colour markup; standard ASCII space (``" "``) and newline (``"\\n"``).

    The default formatter used by
    :class:`~krrood.entity_query_language.verbalization.rendering.renderer.ParagraphRenderer`
    and :meth:`~krrood.entity_query_language.verbalization.pipeline.VerbalizationPipeline.plain`.
    """

    def colorize(self, text: str, role: SemanticRole) -> str:
        """Return *text* unchanged (no colour markup in plain mode)."""
        return text

    @property
    def space(self) -> str:
        return " "

    @property
    def newline(self) -> str:
        return "\n"


@dataclass
class ANSIFormatter(Formatter):
    """
    True-color ANSI escape sequences (24-bit, ``\\033[38;2;R;G;Bm``).

    Compatible with VS Code terminal, GNOME Terminal, iTerm2, Windows Terminal,
    and any terminal supporting the ISO-8613-3 direct-color extension.

    OSC 8 hyperlinks are enabled automatically when the terminal is detected as
    capable (``VTE_VERSION``, ``TERM_PROGRAM`` in ``{vscode, WezTerm, iTerm.app}``,
    or ``TERM=xterm-kitty``).  On unsupported terminals :meth:`wrap_link` falls
    back to returning plain coloured text with no link markup.
    """

    _RESET: ClassVar[str] = "\033[0m"
    _NAMED: ClassVar[dict[str, tuple[int, int, int]]] = {
        "cornflowerblue": (100, 149, 237),
    }

    _hyperlinks_enabled: bool = field(default_factory=_detect_osc8_support, init=False)

    def colorize(self, text: str, role: SemanticRole) -> str:
        color = ROLE_COLORS.get(role)
        if color is None:
            return text
        r, g, b = self._hex_to_rgb(color)
        return f"\033[38;2;{r};{g};{b}m{text}{self._RESET}"

    def wrap_link(self, text: str, url: str) -> str:
        if not self._hyperlinks_enabled:
            return text
        # OSC 8 format: ESC ] 8 ; ; URL ST  text  ESC ] 8 ; ; ST
        return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"

    @property
    def space(self) -> str:
        return " "

    @property
    def newline(self) -> str:
        return "\n"

    def _hex_to_rgb(self, color: str) -> tuple[int, int, int]:
        if color.startswith("#"):
            h = color.lstrip("#")
            return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return self._NAMED.get(color.lower(), (255, 255, 255))


@dataclass
class HTMLFormatter(Formatter):
    """
    HTML output with ``<span style="color: …">`` colour tags, ``&nbsp;`` spaces,
    and ``<br>`` newlines.

    Suitable for Jupyter notebooks, GitLab Markdown, and any renderer that
    passes through inline HTML.  Hyperlinks use standard ``<a href="…">`` anchors.

    Used by :meth:`~krrood.entity_query_language.verbalization.pipeline.VerbalizationPipeline.html`.
    """

    def colorize(self, text: str, role: SemanticRole) -> str:
        color = ROLE_COLORS.get(role)
        if color is None:
            return text
        return f'<span style="color:{color}">{text}</span>'

    def wrap_link(self, text: str, url: str) -> str:
        return f'<a href="{url}">{text}</a>'

    @property
    def space(self) -> str:
        return "&nbsp;"

    @property
    def newline(self) -> str:
        return "<br>"
