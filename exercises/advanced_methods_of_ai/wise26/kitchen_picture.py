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

    CHEESE = "#f2c12e"
    VEGETABLE = "#43a047"
    MEAT = "#c0392b"
    FISH = "#1e88e5"
    OTHER_TOPPING = "#9e9e9e"
    HOT = "#ff6d00"
    CRUST = "#e8c38a"
    CRUST_EDGE = "#b07c3c"
    DOUGH = "#fbeccb"
    TABLE = "#eef2f7"
    TABLE_EDGE = "#7b8ba1"
    ORDER_LINE = "#9aa7b5"
    ANSWER = "#c2185b"
    VIOLATION = "#d50000"
    NOTE = "#37474f"
    WARNING = "#e65100"
    TEXT = "#212121"
    MUTED = "#757575"


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

    pizza_spacing: int = 100
    """
    The horizontal distance between two pizzas, in pixels.
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
        new = [pizza for order in self.orders for pizza in order.pizzas] + [
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
        top = 26 if self.title else 6
        pizza_y = top + 132
        note_rows = max((len(notes) for notes in self.notes.values()), default=0)
        height = pizza_y + 64 + 17 * note_rows
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" '
            f'height="{height}" font-family="DejaVu Sans, Liberation Sans, Arial, sans-serif">',
            f'<rect width="{width}" height="{height}" fill="white"/>',
        ]
        if self.title:
            parts.append(
                f'<text x="{width / 2}" y="17" text-anchor="middle" font-size="14" font-weight="bold" '
                f'fill="{Colour.TEXT.value}">{escape(self.title)}</text>'
            )
        parts.extend(self.order_lines(x_of, top, pizza_y))
        parts.extend(self.tables(x_of, top))
        on_counter = [pizza for pizza in counter if self.is_on_counter(pizza)]
        if on_counter:
            first, last = x_of[id(on_counter[0])], x_of[id(on_counter[-1])]
            parts.append(
                f'<rect x="{first - 46}" y="{pizza_y - 44}" width="{last - first + 92}" height="88" rx="10" '
                f'fill="#faf6ef" stroke="#e3d6c0"/>'
                f'<text x="{first - 40}" y="{pizza_y - 33}" font-size="9" '
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
        self, x_of: dict[int, float], top: int, pizza_y: int
    ) -> Iterable[str]:
        """
        :return: The SVG elements of the lines from each table to its pizzas.
        """
        for order in self.orders:
            table_x = self.table_x(order, x_of)
            for pizza in order.pizzas:
                violated = any(o is order and p is pizza for o, p in self.violations)
                colour = Colour.VIOLATION if violated else Colour.ORDER_LINE
                stroke = 4 if violated else 1.5
                dash = "" if violated else ' stroke-dasharray="4 3"'
                yield (
                    f'<line x1="{table_x}" y1="{top + 62}" x2="{x_of[id(pizza)]}" y2="{pizza_y - 46}" '
                    f'stroke="{colour.value}" stroke-width="{stroke}"{dash}/>'
                )
                if violated:
                    middle_x = (table_x + x_of[id(pizza)]) / 2
                    middle_y = (top + 62 + pizza_y - 46) / 2
                    yield (
                        f'<circle cx="{middle_x}" cy="{middle_y}" r="10" fill="{Colour.VIOLATION.value}"/>'
                        f'<text x="{middle_x}" y="{middle_y + 5}" text-anchor="middle" font-size="14" '
                        f'font-weight="bold" fill="white">!</text>'
                    )

    @staticmethod
    def table_x(order: Any, x_of: dict[int, float]) -> float:
        """
        :return: The horizontal centre of the table of an order, above the middle of its pizzas.
        """
        positions = [x_of[id(pizza)] for pizza in order.pizzas]
        return sum(positions) / len(positions)

    def tables(self, x_of: dict[int, float], top: int) -> Iterable[str]:
        """
        :return: The SVG elements of the tables, with the guest and what the guest avoids.
        """
        for order in self.orders:
            centre = self.table_x(order, x_of)
            box_width = max(100, (len(order.pizzas) - 1) * self.pizza_spacing + 70)
            marked = self.is_marked(order) or self.is_marked(order.guest)
            stroke = (
                f'stroke="{Colour.ANSWER.value}" stroke-width="4"'
                if marked
                else (f'stroke="{Colour.TABLE_EDGE.value}" stroke-width="1.2"')
            )
            yield (
                f'<rect x="{centre - box_width / 2}" y="{top + 8}" width="{box_width}" height="54" rx="8" '
                f'fill="{Colour.TABLE.value}" {stroke}/>'
                f'<text x="{centre}" y="{top + 26}" text-anchor="middle" font-size="12" font-weight="bold" '
                f'fill="{Colour.TEXT.value}">Table {order.table} · {escape(str(order.guest))}</text>'
            )
            avoided = sorted(allergen.value for allergen in order.guest.avoids)
            text = "avoids " + ", ".join(avoided) if avoided else "eats everything"
            colour = Colour.VIOLATION if avoided else Colour.MUTED
            yield (
                f'<text x="{centre}" y="{top + 44}" text-anchor="middle" font-size="10" '
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
            f'<text x="{x}" y="{y + 54}" text-anchor="middle" font-size="11" fill="{Colour.TEXT.value}" '
            f'font-weight="{"bold" if self.is_marked(pizza) else "normal"}">{escape(str(pizza))}</text>'
        )
        for row, (text, colour) in enumerate(self.notes.get(id(pizza), [])):
            text_width = 6.2 * len(text) + 10
            note_y = y + 62 + row * 17
            yield (
                f'<rect x="{x - text_width / 2}" y="{note_y}" width="{text_width}" height="14" rx="7" '
                f'fill="{colour.value}"/>'
                f'<text x="{x}" y="{note_y + 10.5}" text-anchor="middle" font-size="9.5" '
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
                dot_x, dot_y = x + 15 * math.cos(angle), y + 15 * math.sin(angle)
            hot = topping.spiciness.name == "HOT"
            outline = (
                f'stroke="{Colour.HOT.value}" stroke-width="2.5"'
                if hot
                else 'stroke="white" stroke-width="1"'
            )
            if self.is_marked(topping):
                yield (
                    f'<circle cx="{dot_x:.1f}" cy="{dot_y:.1f}" r="12" fill="{Colour.ANSWER.value}"/>'
                )
            yield (
                f'<circle cx="{dot_x:.1f}" cy="{dot_y:.1f}" r="9" fill="{self.category_colour(topping).value}" '
                f"{outline}/>"
                f'<text x="{dot_x:.1f}" y="{dot_y + 3:.1f}" text-anchor="middle" font-size="8" font-weight="bold" '
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
        y = 14 + row * 18
        rows.append(
            f'<circle cx="12" cy="{y}" r="6" fill="{colour.value}"/>'
            f'<text x="24" y="{y + 4}" font-size="10.5" font-weight="bold" fill="{Colour.TEXT.value}">{category}</text>'
            f'<text x="92" y="{y + 4}" font-size="10" fill="{Colour.TEXT.value}">{escape(kinds)}</text>'
        )
    y = 14 + 4 * 18
    rows.append(
        f'<circle cx="12" cy="{y}" r="6" fill="white" stroke="{Colour.HOT.value}" stroke-width="2.5"/>'
        f'<text x="24" y="{y + 4}" font-size="10.5" font-weight="bold" fill="{Colour.TEXT.value}">hot</text>'
        f'<text x="92" y="{y + 4}" font-size="10" fill="{Colour.TEXT.value}">an orange ring: the spiciness of the topping is HOT</text>'
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 520 96" width="520" height="96" '
        'font-family="DejaVu Sans, Liberation Sans, Arial, sans-serif">'
        + "".join(rows)
        + "</svg>"
    )
