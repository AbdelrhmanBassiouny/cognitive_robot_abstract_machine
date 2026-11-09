"""
Draws the pictures of the pizzeria for the worksheet from the solution notebook.

The code cells of :file:`03-pizza_queries_solution.ipynb` except the installation cell are run in order, so the pictures show exactly what the
notebook computes. Usage: ``python src/make_figures.py`` from the folder of the worksheet; the SVG files are
written to :file:`src/figures`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType

from typing_extensions import Any


# %% running the notebook


def run_solution_notebook(folder: Path) -> dict[str, Any]:
    """
    :return: The variables of the solution notebook after all its code cells have run, without displaying
        anything.
    """
    sys.path.insert(0, str(folder))
    notebook = json.loads((folder / "03-pizza_queries_solution.ipynb").read_text())
    module = ModuleType("worksheet_3")
    sys.modules[module.__name__] = module
    namespace = module.__dict__
    for cell in notebook["cells"]:
        if cell["cell_type"] != "code" or "setup" in cell["metadata"].get("tags", []):
            continue
        exec("".join(cell["source"]), namespace)
        namespace["display"] = lambda *arguments, **keywords: None
    return namespace


# %% the pictures


def write_figures(folder: Path) -> None:
    """
    Write the plain pizzeria, the legend and one picture per act of the solution.
    """
    kb = run_solution_notebook(folder)
    picture = kb["KitchenPicture"]
    pizzas, orders = kb["pizzas"], kb["orders"]
    output = folder / "src" / "figures"
    output.mkdir(exist_ok=True)

    def write(name: str, kitchen: Any) -> None:
        (output / f"{name}.svg").write_text(kitchen.to_svg())

    (output / "legend.svg").write_text(kb["legend_svg"]())
    write("world", picture(pizzas, orders))

    write("act_1", picture(pizzas, orders, marked=kb["cheesy"].tolist()))

    violations = [tuple(row.values()) for row in kb["dangerous"].tolist()]
    write("act_3", picture(pizzas, orders, violations=violations))

    act_4 = picture(pizzas, orders)
    for label in kb["label_pizzas"]():
        act_4.note(label.pizza, type(label).__name__)
    for warning in kb["warnings"]:
        if warning.allergen.value != "gluten":
            act_4.note(warning.pizza, warning.allergen.value, kb["Colour"].WARNING)
    write("act_4", act_4)

    new_pizza = kb["candidates"][0]
    dana_order = kb["Order"](4, kb["Guest"]("Dana"), [new_pizza])
    write("act_5", picture(pizzas, orders + [dana_order], marked=[new_pizza]))

    whole = picture(
        pizzas,
        orders + [dana_order],
        marked=kb["cheesy"].tolist(),
        violations=violations,
    )
    for label in kb["label_pizzas"]():
        whole.note(label.pizza, type(label).__name__)
    write("whole", whole)


if __name__ == "__main__":
    write_figures(Path(__file__).resolve().parent.parent)
