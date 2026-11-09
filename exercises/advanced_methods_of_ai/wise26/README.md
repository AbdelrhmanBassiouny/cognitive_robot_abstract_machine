# Worksheet 3: Asking, Describing, Constraining, Inferring

Tutorial material for the lecture *Advanced Methods of AI*, WiSe 2026/2027 (90 minutes). It continues Worksheet 2
(Knowledge Representation) on the same pizza knowledge base and introduces the Entity Query Language (EQL) of
KRROOD through one story: a service robot in a pizzeria on a Thursday evening. Every act uses the same kind of
expression, a description, in a different way, and relates it to description logic and first-order logic.

| Act | Time | Story | The description is … | Theory |
|:--|:--|:--|:--|:--|
| Prologue | 5 min | the pizzeria (Figure 1) | – | an interpretation |
| 1 Asking | 25 min | “Which pizzas have cheese?” | a question | ∃, ∀, ¬∃ as queries; free variables and bindings; closed world |
| 2 Describing | 12 min | “Bring me the pizza with olives.” | a reference | definite descriptions; the domain |
| 3 Constraining | 15 min | “Ben must never get milk.” | a constraint | ∀ checked as ∃¬; integrity constraint versus axiom |
| 4 Inferring | 20 min | warnings and menu labels | the body of a rule | forward chaining, exceptions, non-monotonicity |
| 5 Generating | 13 min | Dana orders a new pizza | a specification | model construction; one query, several backends |

Students draw on Figure 1 throughout the session; the solution ends with the completed picture.

## Files

| File | Purpose |
|:-----|:--------|
| `03-querying_and_reasoning.pdf` | The worksheet (7 pages). |
| `03-querying_and_reasoning_solution.pdf` | The worksheet with solutions and discussion notes (10 pages). |
| `03-pizza_queries.ipynb` | The student notebook. Cells marked `TODO` are to be filled in; it runs from top to bottom as it is. |
| `03-pizza_queries_solution.ipynb` | The notebook with solutions, solution notes and its outputs. |
| `kitchen_picture.py` | Draws the pizzeria with the answers of a query marked on it; used by the notebooks and the figures. |
| `src/build_notebooks.py` | Writes both notebooks from one source. |
| `src/make_figures.py` | Runs the solution notebook and draws the pictures of the pizzeria into `src/figures`. |
| `src/03-querying_and_reasoning.html` | The source of both PDFs. Solutions are the blocks of class `solution`. |
| `src/render_pdf.js` | Renders the HTML to the two PDFs. |

## Requirements of the notebook

- KRROOD with the `match` semantics for collection-valued attributes
  (branch `fix/eql-match-collection-attributes`). On a KRROOD without it, the descriptions over the list
  `toppings`, such as `a(Pizza)(toppings=a(CheeseTopping)())`, match nothing.
- `kitchen_picture.py` must lie next to the notebook.

## Rebuilding

From this folder:

```bash
python src/build_notebooks.py
```

```bash
python src/make_figures.py
```

```bash
node src/render_pdf.js src/03-querying_and_reasoning.html .
```

The second command needs KRROOD (see above); the third needs Node.js with Playwright and its Chromium, and the
fonts Liberation Serif and DejaVu Sans.

## Assumptions to check

- The date and room in the header (Thursday, 12.11.2026, 8:30 to 10:00, room 0.30, ECO 5) continue the weekly
  rhythm of Worksheet 2.
- The dataclasses of the first notebook cells were rebuilt from the text of Worksheet 2 and of `pizza.owl`.
  If the notebook of Worksheet 2 names a class or field differently, adapt those cells in `src/build_notebooks.py`.
