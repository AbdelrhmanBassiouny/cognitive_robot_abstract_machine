"""
Reading an entity query language expression back as English, coloured by role.

The panel shows this as the asked question, so a query says what it asks rather than
only what came back — with class and attribute words linking to their documentation.
"""

from __future__ import annotations

import html
import os
from dataclasses import dataclass

from krrood.entity_query_language.verbalization.exceptions import (
    UnverbalizableExpressionError,
)
from krrood.entity_query_language.verbalization.fragments.roles import SemanticRole
from krrood.entity_query_language.verbalization.fragments.source_reference import (
    SourceReference,
)
from krrood.entity_query_language.verbalization.rendering.formatter import HTMLFormatter
from krrood.entity_query_language.verbalization.rendering.renderer import (
    ParagraphRenderer,
)
from krrood.entity_query_language.verbalization.rendering.source_link_resolver import (
    AutoAPIResolver,
)
from krrood.entity_query_language.verbalization.verbalizer import EQLVerbalizer
from typing_extensions import Any, Dict, FrozenSet, Optional

DOCUMENTED_PACKAGES: FrozenSet[str] = frozenset(
    {
        "coraplex",
        "giskardpy",
        "krrood",
        "probabilistic_model",
        "random_events",
        "semantic_digital_twin",
    }
)
"""
The workspace packages whose AutoAPI documentation the docs site publishes.

Words naming classes of any other package stay plain text: a link that is known to
lead nowhere is worse than no link.
"""

DOCUMENTATION_SITE_VARIABLE = "CRAMERA_DOCUMENTATION_SITE"
"""
Environment variable overriding the documentation site the verbalized words link to.
"""

DEFAULT_DOCUMENTATION_SITE = "https://cram2.github.io/cognitive_robot_abstract_machine"
"""
The published aggregate docs site, hosting each package's docs under its own name.
"""


@dataclass(frozen=True)
class PublishedDocumentationResolver:
    """
    Resolves a verbalized word's source reference to its published AutoAPI page.

    The docs site hosts one Sphinx build per package (``{site}/{package}/autoapi/…``),
    so the reference's own top-level package picks the build its link points into.
    """

    site: str = DEFAULT_DOCUMENTATION_SITE
    """
    Root URL of the aggregate documentation site.
    """

    def resolve(self, reference: SourceReference) -> Optional[str]:
        """
        The AutoAPI page URL a reference documents itself at, or None when its package
        publishes no documentation.

        :param reference: Source reference of the class or attribute a word names.
        """
        if not isinstance(reference.owner_type, type):
            return None
        package = reference.owner_type.__module__.split(".", 1)[0]
        if package not in DOCUMENTED_PACKAGES:
            return None
        return AutoAPIResolver(
            base_url="%s/%s" % (self.site.rstrip("/"), package)
        ).resolve(reference)

    @classmethod
    def of_environment(cls) -> PublishedDocumentationResolver:
        """
        A resolver against the configured docs site (:data:`DOCUMENTATION_SITE_VARIABLE`),
        or the published one.
        """
        return cls(
            site=os.environ.get(DOCUMENTATION_SITE_VARIABLE)
            or DEFAULT_DOCUMENTATION_SITE
        )


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
            html=ParagraphRenderer(
                EscapedHtmlFormatter(),
                link_resolver=PublishedDocumentationResolver.of_environment(),
            ).render(fragment),
        )

    def to_payload(self) -> Dict[str, Any]:
        """
        The JSON-serializable shape the answer panel reads.
        """
        return {"text": self.text, "html": self.html}
