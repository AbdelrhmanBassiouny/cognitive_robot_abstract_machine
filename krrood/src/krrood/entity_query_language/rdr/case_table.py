"""
Render a concrete case object as a readable terminal table for the interactive expert.

The case's ``(attribute, value)`` pairs are laid out across as many columns as the
terminal is wide enough for: the number of pairs per row is derived from the available
width and :data:`DEFAULT_MIN_COLUMN_WIDTH` (the smallest a pair column may be), and the
value columns are then stretched so the table spans the full width rather than hugging
its content. Values that overflow their budget are wrapped across multiple lines so the
full content is visible rather than truncated.

Kept deliberately small and dependency-light (just ``tabulate``);
"""

from __future__ import annotations

import dataclasses
import enum
import shutil
import textwrap

from dataclasses import dataclass

from typing_extensions import Any, Dict, List, Optional, Tuple

import tabulate as _tabulate

from colorama import Fore, Style

# %% the column labels of the side-by-side comparison table


class CaseColumnLabel(enum.StrEnum):
    """
    The headers of the two value columns in a side-by-side case comparison.
    """

    NEW = "New case"
    """
    Heads the column holding the case currently being fitted.
    """

    CORNER = "Corner case"
    """
    Heads the column holding the corner case of the firing rule.
    """


#: Smallest total width (key + value + borders) a single pair column may occupy. The
#: number of pairs laid side by side is ``terminal_width // min_column_width``.
DEFAULT_MIN_COLUMN_WIDTH = 24

#: Ellipsis appended to a clipped cell.
_ELLIPSIS = "..."

#: Longest attribute name rendered before clipping.
_MAX_KEY_WIDTH = 30

#: Per-pair horizontal padding ``simple_grid`` adds around the key and value cells.
_PAIR_BORDER = 7

#: Width assumed when the terminal size cannot be detected.
_FALLBACK_WIDTH = 100

#: Maximum triplets per row in :func:`render_cases_side_by_side`.  Capped to keep the
#: table narrow enough for the IPython embedded shell display area.
_MAX_TRIPLETS_PER_ROW = 3


def case_items(case: Any) -> List[Tuple[str, Any]]:
    """
    Return ``(public_attribute_name, value)`` pairs describing a case object.

    Handles dataclasses (via :func:`dataclasses.fields`) and plain objects (via
    ``__dict__``), filtering out any name that starts with ``_``.  Falls back to a
    single ``("value", case)`` pair when neither introspection path applies.

    :param case: The case object to inspect.
    :return: An ordered list of ``(name, value)`` tuples for every public field.
    """
    if dataclasses.is_dataclass(case) and not isinstance(case, type):
        return [
            (f.name, getattr(case, f.name))
            for f in dataclasses.fields(case)
            if not f.name.startswith("_")
        ]
    if hasattr(case, "__dict__"):
        return [(k, v) for k, v in vars(case).items() if not k.startswith("_")]
    return [("value", case)]


def _format_value(value: Any) -> str:
    """
    Render a field value as display text, lower-casing a boolean's ``True``/``False``.

    :param value: The field value to format; ``None`` becomes an empty string.
    :return: The value's display text.
    """
    text = "" if value is None else str(value)
    if text in ("True", "False"):
        text = text.lower()
    return text


def _clip(text: str, width: int) -> str:
    """
    :param text: The text to fit into ``width`` characters.
    :param width: The maximum number of characters ``text`` may occupy.
    :return: ``text`` truncated to ``width`` characters, ending in an ellipsis if cut.
    """
    if len(text) <= width:
        return text
    if width <= len(_ELLIPSIS):
        return text[:width]
    return text[: width - len(_ELLIPSIS)] + _ELLIPSIS


def _terminal_width() -> int:
    """
    :return: The current terminal width in columns, or :data:`_FALLBACK_WIDTH` when it
        cannot be detected.
    """
    return shutil.get_terminal_size((_FALLBACK_WIDTH, 24)).columns


@dataclass
class CaseTableRenderer:
    """
    Renders a case as a full-width, multi-column ``(attribute, value)`` table.
    """

    min_column_width: int = DEFAULT_MIN_COLUMN_WIDTH
    """
    Smallest total width a pair column may take; sets how many pairs fit per row.
    """

    max_width: Optional[int] = None
    """
    Total table width budget; defaults to the current terminal width.
    """

    use_color: bool = True
    """
    Render field names in a distinct accent so they stand apart from their values.
    """

    def render(self, case: Any) -> str:
        """
        :param case: The case object to render.
        :return: A multi-column table of the case's public attributes that spans the full
            available width. Falls back to ``repr(case)`` when the case has no inspectable
            attributes.
        """
        items = [(name, _format_value(value)) for name, value in case_items(case)]
        if not items:
            return repr(case)
        width = self.max_width or _terminal_width()
        key_width = min(_MAX_KEY_WIDTH, max(len(name) for name, _ in items))
        pairs_per_row = self._pairs_per_row(len(items), width, key_width)
        value_width = self._value_width(width, pairs_per_row, key_width)
        rows = self._rows(items, pairs_per_row, key_width, value_width)
        return self._tabulate_full_width(rows)

    def _style_key(self, text: str) -> str:
        """
        Wrap a (already width-padded) field name in the accent style, if colour is on.

        :param text: The already width-padded field name.
        :return: ``text`` wrapped in the accent style, or unchanged if colour is off.
        """
        if not self.use_color:
            return text
        return f"{Style.BRIGHT}{Fore.CYAN}{text}{Style.RESET_ALL}"

    @staticmethod
    def _tabulate_full_width(rows: List[List[str]]) -> str:
        """
        Tabulate without trimming the padding that stretches columns to full width.

        :param rows: The table rows, each a flat list of already width-padded cells.
        :return: The rendered ``simple_grid`` table.
        """
        preserve = _tabulate.PRESERVE_WHITESPACE
        _tabulate.PRESERVE_WHITESPACE = True
        try:
            return _tabulate.tabulate(rows, tablefmt="simple_grid")
        finally:
            _tabulate.PRESERVE_WHITESPACE = preserve

    def _pairs_per_row(self, item_count: int, width: int, key_width: int) -> int:
        """
        :param item_count: How many ``(attribute, value)`` pairs need to be laid out.
        :param width: The total table width budget.
        :param key_width: The width reserved for a pair's key column.
        :return: How many pairs fit side by side within ``width``.
        """
        budget = max(self.min_column_width, key_width + _PAIR_BORDER + 1)
        return max(1, min(item_count, width // budget))

    @staticmethod
    def _value_width(width: int, pairs_per_row: int, key_width: int) -> int:
        """
        Stretch the value column so ``pairs_per_row`` pairs span the full width.

        :param width: The total table width budget.
        :param pairs_per_row: How many pairs are laid out side by side.
        :param key_width: The width reserved for a pair's key column.
        :return: The width available to a pair's value column.
        """
        pair_width = width // pairs_per_row
        return max(1, pair_width - key_width - _PAIR_BORDER)

    def _rows(
        self,
        items: List[Tuple[str, str]],
        pairs_per_row: int,
        key_width: int,
        value_width: int,
    ) -> List[List[str]]:
        """
        Lay ``items`` out into table rows, ``pairs_per_row`` pairs wide.

        :param items: The ``(name, formatted value)`` pairs to lay out.
        :param pairs_per_row: How many pairs are laid out side by side.
        :param key_width: The width reserved for a pair's key column.
        :param value_width: The width reserved for a pair's value column.
        :return: The table rows, each a flat list of already width-padded cells; the
            trailing row is padded with empty pairs when short of a full row.
        """
        cells = [
            (
                self._style_key(_clip(name, key_width).ljust(key_width)),
                textwrap.fill(value, width=value_width) if value else "",
            )
            for name, value in items
        ]
        empty_pair = ["".ljust(key_width), ""]
        rows: List[List[str]] = []
        for start in range(0, len(cells), pairs_per_row):
            chunk = cells[start : start + pairs_per_row]
            row: List[str] = [field for pair in chunk for field in pair]
            for _ in range(pairs_per_row - len(chunk)):
                row += empty_pair
            rows.append(row)
        return rows


def render_case_table(
    case: Any,
    min_column_width: int = DEFAULT_MIN_COLUMN_WIDTH,
    max_width: Optional[int] = None,
    use_color: bool = True,
) -> str:
    """
    Convenience wrapper around :class:`CaseTableRenderer`.

    :param case: The case object to render.
    :param min_column_width: Smallest total width a pair column may take.
    :param max_width: Total table width budget; defaults to the current terminal width.
    :param use_color: Whether to emit ANSI colour in the table.
    :return: The rendered table, as returned by :meth:`CaseTableRenderer.render`.
    """
    return CaseTableRenderer(
        min_column_width=min_column_width, max_width=max_width, use_color=use_color
    ).render(case)


def render_cases_side_by_side(
    new_case: Any,
    corner_case: Any,
    *,
    new_label: str = CaseColumnLabel.NEW,
    corner_label: str = CaseColumnLabel.CORNER,
    min_column_width: int = DEFAULT_MIN_COLUMN_WIDTH,
    use_color: bool = True,
) -> str:
    """
    Render two cases as a single 3-column comparison table.

    Columns are: **Attribute** | **corner_label** (corner-case values) |
    **new_label** (new-case values).  Multiple attribute triplets are laid
    side by side per row to make full use of the terminal width, following
    the same approach as :class:`CaseTableRenderer`.

    :param new_case: The case currently being fitted.
    :param corner_case: The corner case of the firing rule.
    :param new_label: Column header for the new-case values.
    :param corner_label: Column header for the corner-case values.
    :param min_column_width: Minimum total width per triplet; controls how many triplets
        fit side by side.
    :param use_color: Whether to emit ANSI colour in the table.
    :return: Multiple independent 3-column comparison tables stitched side by side.
    """
    new_items_list = case_items(new_case)
    corner_items_list = case_items(corner_case)
    new_items = dict(new_items_list)
    corner_items = dict(corner_items_list)

    # Preserve new-case field order, then corner-only fields appended.
    all_attributes: List[str] = []
    seen: set = set()
    for attribute, _ in new_items_list:
        all_attributes.append(attribute)
        seen.add(attribute)
    for attribute, _ in corner_items_list:
        if attribute not in seen:
            all_attributes.append(attribute)
            seen.add(attribute)

    if not all_attributes:
        return f"{new_label}: {new_case!r}  {corner_label}: {corner_case!r}"

    width = _terminal_width()
    key_width = min(_MAX_KEY_WIDTH, max(len(attribute) for attribute in all_attributes))

    # Triplet overhead: │ attribute │ corner │ new │  (3 cells × 4 padding/border)
    triplet_border = 12
    # A value column is always at least as wide as its header, so wrapping a value narrower than
    # that only splits it pointlessly (e.g. "eagle" -> "ea"/"gl"/"e"). Reserve the header widths
    # both when deciding how many triplets fit and when wrapping values.
    min_value_width = max(len(corner_label), len(new_label))
    triplet_budget = max(
        min_column_width, key_width + triplet_border + 2 * min_value_width
    )
    triplets_per_row = max(
        1, min(len(all_attributes), width // triplet_budget, _MAX_TRIPLETS_PER_ROW)
    )
    value_width = max(
        min_value_width,
        (width // triplets_per_row - key_width - triplet_border) // 2,
    )

    # %% style helpers

    def _style_key(text: str) -> str:
        """
        :param text: The already width-padded field name.
        :return: ``text`` wrapped in the accent style, or unchanged if colour is off.
        """
        if not use_color:
            return text
        return f"{Style.BRIGHT}{Fore.CYAN}{text}{Style.RESET_ALL}"

    def _style_new_value(text: str) -> str:
        """
        :param text: The new-case cell text to style.
        :return: ``text`` styled to stand out as the new case's value, or unchanged if
            colour is off or ``text`` is empty.
        """
        if not use_color or not text:
            return text
        return f"{Fore.GREEN}{text}{Style.RESET_ALL}"

    def _style_header(text: str) -> str:
        """
        :param text: The column header text.
        :return: ``text`` wrapped in the header style, or unchanged if colour is off.
        """
        if not use_color:
            return text
        return f"{Style.BRIGHT}{Fore.MAGENTA}{text}{Style.RESET_ALL}"

    sentinel = object()

    def _value_for(items: Dict[str, str], attribute: str) -> str:
        """
        :param items: The case's ``(attribute name, formatted value)`` mapping.
        :param attribute: The attribute to look up.
        :return: The wrapped display text for ``attribute``, or an empty string when the
            case has no such attribute.
        """
        value = items.get(attribute, sentinel)
        if value is sentinel:
            return ""
        text = _format_value(value)
        if not text:
            return ""
        return textwrap.fill(text, width=value_width)

    # %% partition attributes round-robin into groups

    groups: List[List[str]] = [[] for _ in range(triplets_per_row)]
    for index, attribute in enumerate(all_attributes):
        groups[index % triplets_per_row].append(attribute)

    # %% render each group as an independent 3-column table

    space_between = "  "
    table_strings: List[str] = []
    for group in groups:
        if not group:
            continue
        table_rows: List[List[str]] = [
            [
                _style_header("Attribute"),
                _style_header(corner_label),
                _style_header(new_label),
            ],
        ]
        for attribute in group:
            table_rows.append(
                [
                    _style_key(_clip(attribute, key_width).ljust(key_width)),
                    _value_for(corner_items, attribute),
                    _style_new_value(_value_for(new_items, attribute)),
                ]
            )
        table_strings.append(_tabulate.tabulate(table_rows, tablefmt="simple_grid"))

    # %% stitch horizontally

    table_lines = [table_string.splitlines() for table_string in table_strings]
    max_height = max(len(lines) for lines in table_lines)
    padded = []
    for lines in table_lines:
        width = len(lines[0]) if lines else 0
        padded.append(lines + [" " * width] * (max_height - len(lines)))
    return "\n".join(
        space_between.join(row[i] for row in padded) for i in range(max_height)
    )
