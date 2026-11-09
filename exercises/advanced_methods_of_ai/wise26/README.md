# Worksheet 3: Querying and Reasoning

Tutorial material for the lecture *Advanced Methods of AI*, WiSe 2026/2027. It continues Worksheet 2
(Knowledge Representation) on the same pizza knowledge base and introduces querying and reasoning with the
Entity Query Language (EQL) of KRROOD.

## Files

| File | Purpose |
|:-----|:--------|
| `03-querying_and_reasoning.pdf` | The worksheet (3 pages). Task 1 is done on paper, Tasks 2 to 4 refer to the notebook. |
| `03-querying_and_reasoning_solution.pdf` | The worksheet with solutions and discussion notes (8 pages). |
| `03-pizza_queries.ipynb` | The student notebook. Cells marked `TODO` are to be filled in; it runs from top to bottom as it is. |
| `03-pizza_queries_solution.ipynb` | The notebook with solutions and a solution note after each task. |
| `src/03-querying_and_reasoning.html` | The source of both PDFs. Solutions are the blocks of class `solution`. |
| `src/render_pdf.js` | Renders the HTML to the two PDFs. |

## Requirements of the notebook

- KRROOD with the `match` semantics for collection-valued attributes
  (branch `fix/eql-match-collection-attributes`). On a KRROOD without it, the descriptions over the list
  `toppings`, such as `a(Pizza)(toppings=a(CheeseTopping)())`, match nothing.
- The bonus section at the end (verbalization and the generative backend) also needs `casadi`.

Both notebooks were executed without errors on Python 3.12 with `random_events`, `probabilistic_model` and
`krrood` installed from that branch.

## Rebuilding the PDFs

```bash
node src/render_pdf.js src/03-querying_and_reasoning.html .
```

This needs Node.js with Playwright and its Chromium, and the fonts Liberation Serif and DejaVu Sans.

## Assumptions to check

- The date and room in the header (Thursday, 12.11.2026, 8:30 to 10:00, room 0.30, ECO 5) continue the weekly
  rhythm of Worksheet 2.
- The dataclasses of the first notebook cells were rebuilt from the text of Worksheet 2 and of `pizza.owl`.
  If the notebook of Worksheet 2 names a class or field differently, adapt those cells.
