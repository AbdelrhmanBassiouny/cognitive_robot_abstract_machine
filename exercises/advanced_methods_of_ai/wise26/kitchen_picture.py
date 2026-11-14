"""
Draws the pizzeria of Worksheet 3 as a picture: the tables with their guests above, the pizzas on the counter
below, and a line from every table to each pizza it ordered.

The picture marks the answers of a query on it, so that a query can be *seen* and not only read. It is used by
the notebook :file:`03-pizza_queries.ipynb` and by :file:`src/make_figures.py` for the figures of the worksheet.
Objects are recognised by the names of their classes, so any classes shaped like those of the notebook work.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from html import escape

from typing_extensions import Any, Iterable


# %% colours and abbreviations


class Colour(str, Enum):
    """
    The colours of the picture, one per kind of thing drawn.
    """

    CHEESE = "#e0b048"
    VEGETABLE = "#5f8f62"
    MEAT = "#a8483e"
    FISH = "#3f6e9a"
    OTHER_TOPPING = "#9a9a9a"
    HOT = "#c8742e"
    CRUST = "#e3c79a"
    CRUST_EDGE = "#a9844f"
    DOUGH = "#f6ebd3"
    TABLE = "#eef1f5"
    TABLE_EDGE = "#7d8a9b"
    ORDER_LINE = "#a3aebb"
    ANSWER = "#1f3a5f"
    VIOLATION = "#b03a2e"
    NOTE = "#33414d"
    WARNING = "#9c6b1f"
    TEXT = "#1a1a1a"
    MUTED = "#6b6b6b"


TOPPING_CATEGORIES = (
    ("CheeseTopping", Colour.CHEESE),
    ("VegetableTopping", Colour.VEGETABLE),
    ("MeatTopping", Colour.MEAT),
    ("FishTopping", Colour.FISH),
)
"""
The topping classes of pizza.owl that the picture distinguishes by colour, and their colours.
"""

ABBREVIATIONS = {
    "MozzarellaTopping": "Mo",
    "ParmesanTopping": "Pa",
    "TomatoTopping": "To",
    "OliveTopping": "Ol",
    "CaperTopping": "Ca",
    "MushroomTopping": "Mu",
    "JalapenoPepperTopping": "Ja",
    "HotGreenPepperTopping": "Gp",
    "HamTopping": "Ha",
    "PeperoniSausageTopping": "Pe",
    "AnchoviesTopping": "An",
}
"""
The two letters written on the dot of each kind of topping.
"""


# %% the picture


@dataclass
class KitchenPicture:
    """
    The pizzeria with the answers of one query marked on it, rendered as SVG.
    """

    pizzas: list[Any]
    """
    The pizzas on the counter, drawn in a row below the tables.
    """

    orders: list[Any]
    """
    The orders; each is drawn as a table above the pizzas it contains.
    """

    marked: list[Any] = field(default_factory=list)
    """
    Pizzas, orders and guests to ring as answers of a query. Pizzas not on the counter are drawn as new ones.
    """

    new_pizzas: list[Any] = field(default_factory=list)
    """
    Pizzas that are not on the counter, drawn after it as new ones even if no order or answer contains them.
    """

    violations: list[tuple[Any, Any]] = field(default_factory=list)
    """
    Pairs of an order and one of its pizzas whose line is drawn as a violated constraint.
    """

    notes: dict[int, list[tuple[str, Colour]]] = field(default_factory=dict)
    """
    Short notes written below a pizza with their background colours, keyed by the identity of the pizza.
    """

    title: str = ""
    """
    A caption written above the picture.
    """

    pizza_spacing: int = 116
    """
    The horizontal distance between two pizzas, in pixels.
    """

    largest_display_width: int = 820
    """
    The widest the picture is shown, in pixels; a wider picture is scaled down as a whole so that it fits a notebook.
    """

    def note(self, pizza: Any, text: str, colour: Colour = Colour.NOTE) -> None:
        """
        Write a note below a pizza.
        """
        self.notes.setdefault(id(pizza), []).append((text, colour))

    # %% layout

    def counter(self) -> list[Any]:
        """
        :return: The pizzas in drawing order: those on the counter that were ordered, order by order, then the
            other pizzas on the counter, then new pizzas, which are not on the counter.
        """
        arranged = []
        for order in self.orders:
            arranged.extend(
                pizza
                for pizza in order.pizzas
                if self.is_on_counter(pizza) and not self.contains(arranged, pizza)
            )
        arranged.extend(
            pizza for pizza in self.pizzas if not self.contains(arranged, pizza)
        )
        new = [pizza for order in self.orders for pizza in order.pizzas] + self.new_pizzas + [
            thing
            for thing in self.marked
            if type(thing).__name__ not in ("Order", "Guest")
            and hasattr(thing, "toppings")
        ]
        arranged.extend(pizza for pizza in new if not self.contains(arranged, pizza))
        return arranged

    @staticmethod
    def contains(things: list[Any], thing: Any) -> bool:
        """
        :return: Whether the very object is in the list, regardless of equality.
        """
        return any(thing is other for other in things)

    def is_on_counter(self, pizza: Any) -> bool:
        """
        :return: Whether the pizza is one of :attr:`pizzas`.
        """
        return self.contains(self.pizzas, pizza)

    def to_svg(self) -> str:
        """
        :return: The picture as a standalone SVG document.
        """
        counter = self.counter()
        x_of = {
            id(pizza): 60 + index * self.pizza_spacing
            for index, pizza in enumerate(counter)
        }
        width = 60 + (len(counter) - 1) * self.pizza_spacing + 60
        top = 36 if self.title else 10
        pizza_y = top + 140
        note_rows = max((len(notes) for notes in self.notes.values()), default=0)
        height = pizza_y + 74 + 22 * note_rows
        scale = min(1.0, self.largest_display_width / width)
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width * scale:.0f}" '
            f'height="{height * scale:.0f}" style="max-width: 100%; height: auto" '
            'font-family="DejaVu Sans, Liberation Sans, Arial, sans-serif">',
            f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="12" fill="white" '
            f'stroke="#d5dbe3"/>',
        ]
        if self.title:
            parts.append(
                f'<text x="{width / 2}" y="25" text-anchor="middle" font-size="17" font-weight="bold" '
                f'fill="{Colour.TEXT.value}">{escape(self.title)}</text>'
            )
        parts.extend(self.order_lines(x_of, width, top, pizza_y))
        parts.extend(self.tables(x_of, width, top))
        on_counter = [pizza for pizza in counter if self.is_on_counter(pizza)]
        if on_counter:
            first, last = x_of[id(on_counter[0])], x_of[id(on_counter[-1])]
            parts.append(
                f'<rect x="{first - 50}" y="{pizza_y - 46}" width="{last - first + 100}" height="92" rx="12" '
                f'fill="#faf6ef" stroke="#e3d6c0"/>'
                f'<text x="{last + 48}" y="{pizza_y - 52}" text-anchor="end" font-size="12" font-style="italic" '
                f'fill="{Colour.MUTED.value}">counter</text>'
            )
        for pizza in counter:
            parts.extend(self.pizza(pizza, x_of[id(pizza)], pizza_y))
        parts.append("</svg>")
        return "\n".join(parts)

    def is_marked(self, thing: Any) -> bool:
        """
        :return: Whether the thing is one of :attr:`marked`.
        """
        return self.contains(self.marked, thing)

    # %% tables and order lines

    def order_lines(
        self, x_of: dict[int, float], width: float, top: int, pizza_y: int
    ) -> Iterable[str]:
        """
        :return: The SVG elements of the lines from each table to its pizzas.
        """
        for order in self.orders:
            table_x = self.table_x(order, x_of, width)
            for pizza in order.pizzas:
                violated = any(o is order and p is pizza for o, p in self.violations)
                colour = Colour.VIOLATION if violated else Colour.ORDER_LINE
                stroke = 4 if violated else 1.5
                dash = "" if violated else ' stroke-dasharray="4 3"'
                yield (
                    f'<line x1="{table_x}" y1="{top + 70}" x2="{x_of[id(pizza)]}" y2="{pizza_y - 46}" '
                    f'stroke="{colour.value}" stroke-width="{stroke}"{dash}/>'
                )
                if violated:
                    middle_x = (table_x + x_of[id(pizza)]) / 2
                    middle_y = (top + 70 + pizza_y - 46) / 2
                    yield (
                        f'<circle cx="{middle_x}" cy="{middle_y}" r="10" fill="{Colour.VIOLATION.value}"/>'
                        f'<text x="{middle_x}" y="{middle_y + 5}" text-anchor="middle" font-size="14" '
                        f'font-weight="bold" fill="white">!</text>'
                    )

    def table_x(self, order: Any, x_of: dict[int, float], width: float) -> float:
        """
        :return: The horizontal centre of the table of an order: above the middle of its pizzas, but no closer to
            an edge of the picture than half the table.
        """
        positions = [x_of[id(pizza)] for pizza in order.pizzas]
        margin = self.table_width(order) / 2 + 8
        return min(max(sum(positions) / len(positions), margin), width - margin)

    @staticmethod
    def table_lines(order: Any) -> tuple[str, str]:
        """
        :return: The two lines written on the table of an order: the table and its guest, and what the guest avoids.
        """
        avoided = sorted(allergen.value for allergen in order.guest.avoids)
        return (
            f"Table {order.table} · {order.guest}",
            "avoids " + ", ".join(avoided) if avoided else "eats everything",
        )

    def table_width(self, order: Any) -> float:
        """
        :return: The width of the table of an order: wide enough for its text and to span its pizzas.
        """
        heading, text = self.table_lines(order)
        return max(
            9.2 * len(heading) + 24,
            7.4 * len(text) + 24,
            (len(order.pizzas) - 1) * self.pizza_spacing + 50,
        )

    def tables(self, x_of: dict[int, float], width: float, top: int) -> Iterable[str]:
        """
        :return: The SVG elements of the tables, with the guest and what the guest avoids.
        """
        for order in self.orders:
            centre = self.table_x(order, x_of, width)
            heading, text = self.table_lines(order)
            box_width = self.table_width(order)
            marked = self.is_marked(order) or self.is_marked(order.guest)
            stroke = (
                f'stroke="{Colour.ANSWER.value}" stroke-width="4"'
                if marked
                else (f'stroke="{Colour.TABLE_EDGE.value}" stroke-width="1.2"')
            )
            yield (
                f'<rect x="{centre - box_width / 2}" y="{top + 6}" width="{box_width}" height="64" rx="10" '
                f'fill="{Colour.TABLE.value}" {stroke}/>'
                f'<text x="{centre}" y="{top + 30}" text-anchor="middle" font-size="15" font-weight="bold" '
                f'fill="{Colour.TEXT.value}">{escape(heading)}</text>'
            )
            colour = Colour.VIOLATION if order.guest.avoids else Colour.MUTED
            yield (
                f'<text x="{centre}" y="{top + 54}" text-anchor="middle" font-size="13" '
                f'fill="{colour.value}">{escape(text)}</text>'
            )

    # %% pizzas

    def pizza(self, pizza: Any, x: float, y: float) -> Iterable[str]:
        """
        :return: The SVG elements of one pizza: crust, toppings, name, ring and notes.
        """
        new = not self.is_on_counter(pizza)
        crust_dash = ' stroke-dasharray="5 3"' if new else ""
        yield (
            f'<circle cx="{x}" cy="{y}" r="34" fill="{Colour.CRUST.value}" '
            f'stroke="{Colour.CRUST_EDGE.value}" stroke-width="1.5"{crust_dash}/>'
            f'<circle cx="{x}" cy="{y}" r="27" fill="{Colour.DOUGH.value}"/>'
        )
        yield from self.toppings(pizza.toppings, x, y)
        if self.is_marked(pizza):
            yield (
                f'<circle cx="{x}" cy="{y}" r="41" fill="none" stroke="{Colour.ANSWER.value}" stroke-width="4"/>'
            )
        yield (
            f'<text x="{x}" y="{y + 62}" text-anchor="middle" font-size="13.5" fill="{Colour.TEXT.value}" '
            f'font-weight="{"bold" if self.is_marked(pizza) else "normal"}">{escape(str(pizza))}</text>'
        )
        for row, (text, colour) in enumerate(self.notes.get(id(pizza), [])):
            text_width = 7.6 * len(text) + 16
            note_y = y + 72 + row * 22
            yield (
                f'<rect x="{x - text_width / 2}" y="{note_y}" width="{text_width}" height="19" rx="9.5" '
                f'fill="{colour.value}"/>'
                f'<text x="{x}" y="{note_y + 14}" text-anchor="middle" font-size="12" font-weight="bold" '
                f'fill="white">{escape(text)}</text>'
            )

    def toppings(self, toppings: list[Any], x: float, y: float) -> Iterable[str]:
        """
        :return: One coloured dot per topping, arranged in a ring on the pizza.
        """
        count = len(toppings)
        for index, topping in enumerate(toppings):
            if count == 1:
                dot_x, dot_y = x, y
            else:
                angle = -math.pi / 2 + 2 * math.pi * index / count
                dot_x, dot_y = x + 16 * math.cos(angle), y + 16 * math.sin(angle)
            hot = topping.spiciness.name == "HOT"
            outline = (
                f'stroke="{Colour.HOT.value}" stroke-width="2.5"'
                if hot
                else 'stroke="white" stroke-width="1"'
            )
            if self.is_marked(topping):
                yield (
                    f'<circle cx="{dot_x:.1f}" cy="{dot_y:.1f}" r="13" fill="{Colour.ANSWER.value}"/>'
                )
            yield (
                f'<circle cx="{dot_x:.1f}" cy="{dot_y:.1f}" r="10" fill="{self.category_colour(topping).value}" '
                f"{outline}/>"
                f'<text x="{dot_x:.1f}" y="{dot_y + 3.5:.1f}" text-anchor="middle" font-size="9.5" font-weight="bold" '
                f'fill="white">{ABBREVIATIONS.get(type(topping).__name__, "?")}</text>'
            )

    @staticmethod
    def category_colour(topping: Any) -> Colour:
        """
        :return: The colour of the topping's category in pizza.owl.
        """
        ancestors = [cls.__name__ for cls in type(topping).__mro__]
        for category, colour in TOPPING_CATEGORIES:
            if category in ancestors:
                return colour
        return Colour.OTHER_TOPPING

    def _repr_svg_(self) -> str:
        return self.to_svg()


# %% legend


def legend_svg() -> str:
    """
    :return: An SVG strip that explains the colours and the letters of the toppings.
    """
    entries = [
        (Colour.CHEESE, "cheese", "Mo mozzarella · Pa parmesan"),
        (
            Colour.VEGETABLE,
            "vegetable",
            "To tomato · Ol olive · Ca caper · Mu mushroom · Ja jalapeño · Gp green pepper",
        ),
        (Colour.MEAT, "meat", "Ha ham · Pe peperoni"),
        (Colour.FISH, "fish", "An anchovies"),
    ]
    rows = []
    for row, (colour, category, kinds) in enumerate(entries):
        y = 26 + row * 26
        rows.append(
            f'<circle cx="26" cy="{y}" r="8" fill="{colour.value}"/>'
            f'<text x="42" y="{y + 5}" font-size="14" font-weight="bold" fill="{Colour.TEXT.value}">{category}</text>'
            f'<text x="138" y="{y + 5}" font-size="13.5" fill="{Colour.TEXT.value}">{escape(kinds)}</text>'
        )
    y = 26 + 4 * 26
    rows.append(
        f'<circle cx="26" cy="{y}" r="8" fill="white" stroke="{Colour.HOT.value}" stroke-width="3"/>'
        f'<text x="42" y="{y + 5}" font-size="14" font-weight="bold" fill="{Colour.TEXT.value}">hot</text>'
        f'<text x="138" y="{y + 5}" font-size="13.5" fill="{Colour.TEXT.value}">an orange ring: the spiciness of the topping is HOT</text>'
    )
    width, height = 760, y + 22
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        'style="max-width: 100%; height: auto" font-family="DejaVu Sans, Liberation Sans, Arial, sans-serif">'
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="12" fill="white" stroke="#d5dbe3"/>'
        + "".join(rows)
        + "</svg>"
    )
