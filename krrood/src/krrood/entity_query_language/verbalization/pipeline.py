from __future__ import annotations

from krrood.entity_query_language.verbalization.fragments import VerbFragment
from krrood.entity_query_language.verbalization.rendering.colorizer import (
    ANSIColorizer,
    MarkdownColorizer,
    PlainColorizer,
)
from krrood.entity_query_language.verbalization.rendering.renderer import (
    FragmentRenderer,
    HierarchicalRenderer,
    ParagraphRenderer,
)
from krrood.entity_query_language.verbalization.verbalizer import EQLVerbalizer
from krrood.entity_query_language.query.query import Query


class VerbalizationPipeline:
    """
    Combines an :class:`EQLVerbalizer` (fragment builder) with a
    :class:`FragmentRenderer` (format + colour) to produce a final string.

    Usage::

        pipeline = VerbalizationPipeline(HierarchicalRenderer(MarkdownColorizer()))
        text = pipeline.verbalize(query)

    Factory helpers cover the most common configurations:

    * :meth:`plain`      — no colour, paragraph prose (default for :func:`verbalize_expression`)
    * :meth:`ansi`       — ANSI true-colour terminal output, paragraph prose
    * :meth:`markdown`   — HTML ``<span>`` colours, paragraph prose or hierarchical
    """

    def __init__(self, renderer: FragmentRenderer = ParagraphRenderer()):
        self._verbalizer = EQLVerbalizer()
        self._renderer = renderer

    def verbalize(self, expr) -> str:
        if isinstance(expr, Query):
            expr.build()
        fragment = self._verbalizer.build(expr)
        return self.verbalize_fragment(fragment)

    def verbalize_fragment(self, fragment: VerbFragment) -> str:
        return self._renderer.render(fragment)

    # ── Factories ──────────────────────────────────────────────────────────────

    @classmethod
    def plain(cls) -> "VerbalizationPipeline":
        """Plain text, paragraph prose — no colour."""
        return cls(ParagraphRenderer(PlainColorizer()))

    @classmethod
    def ansi(cls, hierarchical: bool = False) -> "VerbalizationPipeline":
        """ANSI true-colour output for terminal display."""
        colorizer = ANSIColorizer()
        renderer = HierarchicalRenderer(colorizer) if hierarchical else ParagraphRenderer(colorizer)
        return cls(renderer)

    @classmethod
    def markdown(cls, hierarchical: bool = False) -> "VerbalizationPipeline":
        """HTML ``<span>`` colour output for Markdown / Jupyter rendering."""
        colorizer = MarkdownColorizer()
        renderer = HierarchicalRenderer(colorizer) if hierarchical else ParagraphRenderer(colorizer)
        return cls(renderer)
