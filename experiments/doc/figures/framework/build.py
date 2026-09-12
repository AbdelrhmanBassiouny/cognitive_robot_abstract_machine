"""
Render the framework figure to PDF, SVG and PNG.

Needs the ``typst`` package (``pip install typst``). The figure reads the camera capture
out of the montessori resources, so it is compiled with the repository root as Typst's
root.
"""

from __future__ import annotations

from pathlib import Path

import typst

FIGURE = Path(__file__).with_name("framework.typ")
REPOSITORY_ROOT = FIGURE.parents[4]
OUTPUTS = (
    (".pdf", {}),
    (".svg", {"format": "svg"}),
    (".png", {"format": "png", "ppi": 300}),
)


def main() -> None:
    """
    Compile the figure once per output format, next to its source.
    """
    for suffix, options in OUTPUTS:
        output = FIGURE.with_suffix(suffix)
        typst.compile(FIGURE, output=output, root=REPOSITORY_ROOT, **options)
        print(output.name)


if __name__ == "__main__":
    main()
