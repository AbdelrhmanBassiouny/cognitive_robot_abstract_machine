"""
Reading an entity query language expression back as English, coloured by role.

The answer panel shows this above the rows, so a preset button says what it asked rather
than only what came back.
"""

from __future__ import annotations

import html
from dataclasses import dataclass

from krrood.entity_query_language.verbalization.exceptions import (
    UnverbalizableExpressionError,
)
from krrood.entity_query_language.verbalization.fragments.roles import SemanticRole
from krrood.entity_query_language.verbalization.rendering.formatter import HTMLFormatter
from krrood.entity_query_language.verbalization.rendering.renderer import (
    ParagraphRenderer,
)
from krrood.entity_query_language.verbalization.verbalizer import EQLVerbalizer
from typing_extensions import Any, Dict, Optional


class EscapedHtmlFormatter(HTMLFormatter):
    """
    Krrood's HTML colour markup, with the display text escaped.

    The rendered sentence is inserted into the page as markup, and a query's literals
    are whatever a viewer typed, so they arrive as text rather than as tags.
    """

    def colorize(self, text: str, role: SemanticRole) -> str:
        """
        Colour one already-escaped span of display text.

        :param text: Plain display text to escape and colour.
        :param role: The semantic role deciding the colour.
        """
        return super().colorize(html.escape(text), role)


@dataclass(frozen=True)
class QueryVerbalization:
    """
    One query read back as English, in both the renderings the viewer needs.
    """

    text: str
    """
    The sentence as plain prose, for logs and for anything that cannot show markup.
    """

    html: str
    """
    The same sentence as ``<span>`` markup, coloured by semantic role.
    """

    @classmethod
    def of_expression(cls, expression: Any) -> Optional[QueryVerbalization]:
        """
        Read one entity query language expression back as English.

        Building the sentence leaves the expression evaluable, so the caller can word a
        query and then answer it.

        :param expression: The expression to word.
        :return: Both renderings, or None for anything krrood cannot word — a sentence
            is a nicety, and failing to build one must not cost the caller its answer.
        """
        try:
            fragment = EQLVerbalizer().build(expression)
        except UnverbalizableExpressionError:
            return None
        return cls(
            text=ParagraphRenderer().render(fragment),
            html=ParagraphRenderer(EscapedHtmlFormatter()).render(fragment),
        )

    def to_payload(self) -> Dict[str, Any]:
        """
        The JSON-serializable shape the answer panel reads.
        """
        return {"text": self.text, "html": self.html}
