from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from krrood.entity_query_language.verbalization.fragments.base import (
    BlockFragment,
    PhraseFragment,
    RoleFragment,
    VerbFragment,
    WordFragment,
)
from krrood.entity_query_language.verbalization.rendering import MarkdownColorizer
from krrood.entity_query_language.verbalization.rendering.colorizer import Colorizer, PlainColorizer


@dataclass
class FragmentRenderer(ABC):
    """Converts a VerbFragment tree into a string."""

    _colorizer: Colorizer = field(default_factory=PlainColorizer)
    """
    The colorizer to use for rendering semantic roles.
    """

    @abstractmethod
    def render(self, fragment: VerbFragment) -> str:
        """
        Render a VerbFragment tree into a string.

        :param fragment: The root of the fragment tree.
        :return: The rendered string.
        """
        ...


@dataclass
class ParagraphRenderer(FragmentRenderer):
    """
    Flattens the fragment tree into a single prose string.

    BlockFragment headers and items are joined inline; nesting adds no
    visual structure — only content.
    """

    def render(self, fragment: VerbFragment) -> str:
        match fragment:
            case WordFragment(text=text):
                return text
            case RoleFragment(text=text, role=role):
                return self._colorizer.colorize(text, role)
            case PhraseFragment(parts=parts, separator=sep):
                rendered = [self.render(p) for p in parts]
                return sep.join(rendered)
            case BlockFragment(header=header, items=items):
                rendered_items = [self.render(i) for i in items]
                prose = ", ".join(rendered_items)
                if header is None:
                    return prose
                header_str = self.render(header)
                return f"{header_str} {prose}" if prose else header_str
            case _:
                return ""


@dataclass
class HierarchicalRenderer(FragmentRenderer):
    """
    Renders BlockFragments as indented bullet lists.

    Each level of BlockFragment nesting adds one ``indent`` step.
    Non-block fragments are rendered inline using the same colorizer.

    Example output::

        **If:**
          - there's a Handle
          - there's a PrismaticConnection, whose child is …
        **Then:**
          - there's a Drawer
            - whose container is …
    """
    indent: str = field(default="  ")
    """
    The indentation string to use for each level of nesting.
    """
    bullet: str = field(default="-")
    """
    The bullet character to use for the bullet points.
    """
    _add_extra_lines_between_headers: bool = field(init=False, default=False)
    """
    Internal field, that decides whether to add extra lines between headers, useful when rendering in Markdown.
    """

    def __post_init__(self):
        self._add_extra_lines_between_headers = isinstance(self._colorizer, MarkdownColorizer)

    def render(self, fragment: VerbFragment, depth: int = 0) -> str:
        match fragment:
            case BlockFragment(header=header, items=items):
                lines: list[str] = []
                if header is not None:
                    lines.extend(self._get_header_lines(header, depth))
                    depth = depth + 1
                for item in items:
                    lines.append(self._render_item(item, depth))
                return "\n".join(lines)
            case _:
                return self.indent * depth + self._inline(fragment)

    def _get_header_lines(self, header: VerbFragment, depth: int):
        """
        Get the lines that make up the header.

        :param header: The header fragment.
        :param depth: The indentation depth.
        :return: List of header lines.
        """
        header_str = self._inline(header)
        header_line = self.indent * depth + header_str
        lines = ["", header_line, ""] if self._add_extra_lines_between_headers else [header_line]
        return lines

    def _render_item(self, fragment: VerbFragment, depth: int) -> str:
        """Render one item, prepending the bullet at its indentation level."""
        match fragment:
            case BlockFragment():
                return self.render(fragment, depth)
            case _:
                prefix = self.indent * depth + f"{self.bullet} "
                return prefix + self._inline(fragment)

    def _inline(self, fragment: VerbFragment) -> str:
        """Render a non-block fragment as a flat inline string."""
        match fragment:
            case WordFragment(text=text):
                return text
            case RoleFragment(text=text, role=role):
                return self._colorizer.colorize(text, role)
            case PhraseFragment(parts=parts, separator=sep):
                return sep.join(self._inline(p) for p in parts)
            case BlockFragment():
                # Nested block encountered while rendering inline — delegate to render()
                return self.render(fragment, 0)
            case _:
                return ""
