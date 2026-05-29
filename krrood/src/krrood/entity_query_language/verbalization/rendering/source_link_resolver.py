"""
Source-link resolution — maps Python class/attribute references to documentation URLs.

:class:`SourceLinkResolver` is the protocol; :class:`AutoAPIResolver` resolves
references to Sphinx AutoAPI-generated HTML pages.  ``AutoAPIResolver.for_package``
auto-detects the base URL for a locally installed package whose docs are served
by the JetBrains IDE built-in HTTP server.
"""

from __future__ import annotations

import importlib
import inspect
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol

from krrood.entity_query_language.verbalization.fragments.source_ref import SourceRef

_log = logging.getLogger(__name__)


class SourceLinkResolver(Protocol):
    """
    Protocol: maps a
    :class:`~krrood.entity_query_language.verbalization.fragments.source_ref.SourceRef`
    to a URL string, or ``None`` when the class or attribute cannot be located.

    Implementations are passed to
    :class:`~krrood.entity_query_language.verbalization.rendering.renderer.FragmentRenderer`
    and used to wrap
    :class:`~krrood.entity_query_language.verbalization.fragments.base.RoleFragment`
    text with hyperlinks.

    Built-in implementation: :class:`AutoAPIResolver`.
    """

    def resolve(self, ref: SourceRef) -> Optional[str]:
        """
        Resolve *ref* to a URL string.

        :param ref: Source reference to resolve.
        :type ref: ~krrood.entity_query_language.verbalization.fragments.source_ref.SourceRef
        :returns: URL string, or ``None`` when the reference cannot be resolved.
        :rtype: str or None
        """
        ...


@dataclass
class AutoAPIResolver:
    """
    Resolves source references to Sphinx AutoAPI documentation pages.

    :param base_url: Root URL of the generated docs site, e.g.
        ``"https://myproject.readthedocs.io/en/latest"`` or
        ``"http://localhost:63342/project/doc/_build/html"``.
    :type base_url: str
    :param html_root: Optional local path to the Sphinx HTML output directory.
        When set, :meth:`resolve` verifies that the AutoAPI page exists on disk
        and logs a warning if it does not.
    :type html_root: pathlib.Path or None

    Use :meth:`for_package` to auto-detect the base URL for a locally installed
    package whose docs are served by the JetBrains IDE built-in HTTP server.
    """

    base_url: str
    html_root: Optional[Path] = None

    def resolve(self, ref: SourceRef) -> Optional[str]:
        """
        Resolve *ref* to a Sphinx AutoAPI page URL.

        Constructs the URL as::

            {base_url}/autoapi/{module/path}/index.html#{module.QualName[.attr]}

        When :attr:`html_root` is set and the page does not exist on disk,
        logs a ``WARNING`` suggesting the docs be rebuilt.

        :param ref: Source reference to resolve.
        :type ref: ~krrood.entity_query_language.verbalization.fragments.source_ref.SourceRef
        :returns: AutoAPI page URL, or ``None`` when *ref.cls* has no ``__module__``.
        :rtype: str or None
        """
        try:
            module = ref.cls.__module__
            qualname = ref.cls.__qualname__
        except AttributeError:
            return None
        module_path = module.replace(".", "/")
        anchor = f"{module}.{qualname}"
        if ref.attribute is not None:
            anchor = f"{anchor}.{ref.attribute}"
        base = self.base_url.rstrip("/")
        url = f"{base}/autoapi/{module_path}/index.html#{anchor}"
        if self.html_root is not None:
            page = self.html_root / "autoapi" / module_path / "index.html"
            if not page.exists():
                _log.warning(
                    "AutoAPI page for %s.%s does not exist at %s — "
                    "the class may be missing from the docs; "
                    "try rebuilding: sphinx-build doc doc/_build/html",
                    module,
                    qualname,
                    page,
                )
        return url

    @classmethod
    def for_package(cls, package_name: str, port: int = 63342) -> AutoAPIResolver:
        """Build an :class:`AutoAPIResolver` for *package_name*'s locally built Sphinx docs.

        The base URL targets the JetBrains IDE built-in HTTP server using this algorithm:

        1. Import *package_name* to locate its source tree.
        2. Walk up to the directory containing ``pyproject.toml`` (the package root).
        3. Expect the Sphinx HTML output at ``{package_root}/doc/_build/html``.
        4. Walk up to the git root (directory containing ``.git``).
        5. Construct ``http://localhost:{port}/{git_root_name}/{relative_html_path}``.

        :raises ImportError: if *package_name* cannot be imported.
        :raises FileNotFoundError: if ``doc/_build/html`` does not exist —
            build the docs first with ``sphinx-build doc doc/_build/html``.
        """
        try:
            pkg = importlib.import_module(package_name)
        except ImportError as exc:
            raise ImportError(f"Cannot import package {package_name!r}: {exc}") from exc

        pkg_file = Path(inspect.getfile(pkg)).resolve()

        package_root: Optional[Path] = None
        for parent in pkg_file.parents:
            if (parent / "pyproject.toml").exists():
                package_root = parent
                break
        if package_root is None:
            raise FileNotFoundError(f"No pyproject.toml found in any parent of {pkg_file}")

        html_root = package_root / "doc" / "_build" / "html"
        if not html_root.exists():
            raise FileNotFoundError(
                f"Sphinx HTML output not found at {html_root}. "
                f"Build the docs first: sphinx-build doc doc/_build/html"
            )

        git_root: Optional[Path] = None
        for parent in [package_root, *package_root.parents]:
            if (parent / ".git").exists():
                git_root = parent
                break
        if git_root is None:
            git_root = package_root.parent

        rel_html = html_root.relative_to(git_root)
        return cls(
            base_url=f"http://localhost:{port}/{git_root.name}/{rel_html}",
            html_root=html_root,
        )
