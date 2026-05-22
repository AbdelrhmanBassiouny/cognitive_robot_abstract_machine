from __future__ import annotations

import logging
import tempfile
import webbrowser
from typing import Optional, TYPE_CHECKING

from krrood.entity_query_language.verbalization.fragments import VerbFragment
from krrood.entity_query_language.verbalization.rendering.formatter import (
    ANSIFormatter,
    HTMLFormatter,
    PlainFormatter,
    _detect_osc8_support,
)
from krrood.entity_query_language.verbalization.rendering.renderer import (
    FragmentRenderer,
    HierarchicalRenderer,
    ParagraphRenderer,
)
from krrood.entity_query_language.verbalization.verbalizer import EQLVerbalizer
from krrood.entity_query_language.query.query import Query

if TYPE_CHECKING:
    from krrood.entity_query_language.verbalization.rendering.source_link_resolver import SourceLinkResolver

_log = logging.getLogger(__name__)

_HTML_PAGE_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{
    background: #1e1e1e;
    color: #d4d4d4;
    font-family: monospace;
    font-size: 14px;
    padding: 1.5em;
    line-height: 1.8;
  }}
  a {{ color: inherit; }}
</style>
</head>
<body>{body}</body>
</html>
"""

# Inline dark wrapper for HTML cell output (Jupyter / built docs). Mirrors
# _HTML_PAGE_TEMPLATE so the colors read correctly in both environments.
_HTML_CELL_WRAPPER = (
    '<div style="background:#1e1e1e;color:#d4d4d4;font-family:monospace;'
    'font-size:14px;padding:0.75em;border-radius:0.4em;line-height:1.8;">'
    "{body}"
    "</div>"
)


def _is_ipython() -> bool:
    """Return ``True`` when running inside an IPython / Jupyter session."""
    try:
        from IPython import get_ipython
        return get_ipython() is not None
    except ImportError:
        return False


class VerbalizationPipeline:
    """
    Combines an :class:`EQLVerbalizer` (fragment builder) with a
    :class:`FragmentRenderer` (format + colour) to produce a final string.

    Usage::

        pipeline = VerbalizationPipeline(HierarchicalRenderer(HTMLFormatter()))
        text = pipeline.verbalize(query)

    Factory helpers cover the most common configurations:

    * :meth:`plain`  — no colour, paragraph prose (default for :func:`verbalize_expression`)
    * :meth:`ansi`   — ANSI true-colour terminal output, paragraph prose
    * :meth:`html`   — HTML ``<span>`` colours, paragraph prose or hierarchical

    All factory methods accept an optional *link_resolver* that maps class and
    attribute names to hyperlinks.  Built-in resolver:

    * :class:`~krrood.entity_query_language.verbalization.rendering.source_link_resolver.AutoAPIResolver` — Sphinx AutoAPI documentation pages (local build or GitHub Pages)
    """

    def __init__(self, renderer: FragmentRenderer = ParagraphRenderer()):
        self._verbalizer = EQLVerbalizer()
        self._renderer = renderer

    def verbalize(self, expr) -> str:
        if isinstance(expr, Query):
            expr.build()
        fragment = self._verbalizer.build(expr)
        return self.verbalize_fragment(fragment)

    def _is_html_renderer(self) -> bool:
        return isinstance(getattr(self._renderer, "_formatter", None), HTMLFormatter)

    def verbalize_fragment(self, fragment: VerbFragment) -> str:
        result = self._renderer.render(fragment)
        if self._is_html_renderer():
            return _HTML_CELL_WRAPPER.format(body=result)
        return result

    def display(self, expr) -> None:
        """Render *expr* and display it in the current environment.

        * **Jupyter / IPython** — renders inline via ``IPython.display.HTML``.
        * **Elsewhere** — writes a temporary ``.html`` file and opens it in the
          default system browser.

        This method is designed for use with :meth:`html` pipelines.  Calling it
        on a plain-text or ANSI pipeline will open a browser tab with raw text.
        """
        self.display_fragment(self._verbalizer.build(expr))

    def display_fragment(self, fragment: VerbFragment) -> None:
        """Display a pre-built :class:`VerbFragment` — same routing as :meth:`display`."""
        raw_html = self._renderer.render(fragment)
        if _is_ipython():
            from IPython.display import display as _ipython_display, HTML
            wrapped = _HTML_CELL_WRAPPER.format(body=raw_html) if self._is_html_renderer() else raw_html
            _ipython_display(HTML(wrapped))
            return
        full_page = _HTML_PAGE_TEMPLATE.format(body=raw_html)
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".html",
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(full_page)
            tmp_path = f.name
        webbrowser.open(f"file://{tmp_path}")

    # ── Factories ──────────────────────────────────────────────────────────────

    @classmethod
    def plain(cls) -> "VerbalizationPipeline":
        """Plain text, paragraph prose — no colour, no links."""
        return cls(ParagraphRenderer(PlainFormatter()))

    @classmethod
    def ansi(
        cls,
        hierarchical: bool = False,
        link_resolver: Optional["SourceLinkResolver"] = None,
    ) -> "VerbalizationPipeline":
        """ANSI true-colour output for terminal display.

        When *link_resolver* is provided and the terminal supports OSC 8
        hyperlinks, class and attribute names become clickable.  On unsupported
        terminals a warning is logged and the resolver is silently disabled.
        """
        formatter = ANSIFormatter()
        if link_resolver is not None and not _detect_osc8_support():
            _log.warning(
                "The current terminal does not appear to support OSC 8 hyperlinks "
                "(VTE_VERSION / TERM_PROGRAM / TERM not recognised). "
                "link_resolver will be ignored for ANSI output."
            )
            link_resolver = None
        renderer: FragmentRenderer = (
            HierarchicalRenderer(formatter, link_resolver)
            if hierarchical
            else ParagraphRenderer(formatter, link_resolver)
        )
        return cls(renderer)

    @classmethod
    def html(
        cls,
        hierarchical: bool = False,
        link_resolver: Optional["SourceLinkResolver"] = None,
    ) -> "VerbalizationPipeline":
        """HTML ``<span>`` colour output for Jupyter / inline-HTML rendering.

        When *link_resolver* is provided, class and attribute names are wrapped
        in ``<a href="…">`` anchors.
        """
        formatter = HTMLFormatter()
        renderer = (
            HierarchicalRenderer(formatter, link_resolver)
            if hierarchical
            else ParagraphRenderer(formatter, link_resolver)
        )
        return cls(renderer)
