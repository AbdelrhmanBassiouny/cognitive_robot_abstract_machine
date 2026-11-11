# Worksheet 3: Asking, Defining, Constraining, Deriving, Generating

Tutorial material for the lecture *Advanced Methods of AI*, WiSe 2026/2027 (90 minutes). It continues Worksheet 2
(Knowledge Representation) on the same pizza knowledge base and introduces the Entity Query Language (EQL) of
KRROOD through one story: a service robot in a pizzeria on a Thursday evening. Every act uses the same kind of
expression, a description, in a different way, and relates it to first-order logic. Asking and constraining *read*
what the robot knows; defining, deriving and generating *write* to it.

## The 90 minutes

| Time | Part | Story | The description is … | Logic |
|:--|:--|:--|:--|:--|
| 0–8 | Slides | what we want today, EQL and first-order logic | – | queries as formulas with free variables |
| 8–12 | Prologue | the pizzeria (Figure 2) | – | an interpretation |
| 12–36 | 1 Asking | “Which pizzas have cheese?” “Bring me the one with olives.” | a question | ∃, ∀, ¬∃; assignments; closed world; definite descriptions (Russell, Strawson) |
| 36–54 | 2 Defining | “Which pizzas may carry the green V?” | a definition | class declarations as necessary conditions; ↔ to check, classify (roles) and conclude; rules with exceptions, non-monotonicity |
| 54–66 | 3 Constraining | “Ben must never get milk.” | a constraint | ¬∀ ≡ ∃¬; integrity constraint versus axiom |
| 66–78 | 4 Deriving | the kitchen writes allergen warnings | the body of a rule that creates objects | ∃ in the head, forward chaining, truth maintenance |
| 78–85 | 5 Generating | Dana orders a new pizza | a specification | constructing a model; one query, several backends |
| 85–90 | Epilogue | the whole picture | – | summary |

Students start the setup cell of the notebook during the slides, so that EQL is installed when the acts begin.
Every task follows the same rhythm: predict on paper, run in the notebook, discuss. The first page of the solution
PDF is the tutor's run sheet, with what to discuss at the end of each act and the sentence that leads to the next.

## Files

| File | Purpose |
|:-----|:--------|
| `03-introduction_slides.pdf` | Nine slides for the first 8 minutes. |
| `03-querying_and_reasoning.pdf` | The worksheet (13 pages; each act starts on a new page). |
| `03-querying_and_reasoning_solution.pdf` | The run sheet for the tutor, and the worksheet with solutions (21 pages). |
| `03-pizza_queries.ipynb` | The student notebook. Cells marked `TODO` are to be filled in; it runs from top to bottom as it is. |
| `03-pizza_queries_solution.ipynb` | The notebook with solutions, solution notes and its outputs. |
| `kitchen_picture.py` | Draws the pizzeria with the answers of a query marked on it. |
| `requirements.txt` | The packages the notebook needs besides KRROOD, `random_events` and `probabilistic_model`. |
| `src/build_notebooks.py` | Writes both notebooks from one source. |
| `src/make_figures.py` | Runs the solution notebook and draws the pictures of the pizzeria into `src/figures`. |
| `src/03-querying_and_reasoning.html` | The source of the worksheet PDFs. Solutions are the blocks of class `solution`. |
| `src/03-introduction_slides.html` | The source of the slides. |
| `src/render_pdf.js` | Renders the HTML sources to PDF. |

## Running the notebook

The first code cell of the notebook installs everything it needs: KRROOD (with EQL) and `random_events` and
`probabilistic_model`, built from source at a fixed commit, and the packages of `requirements.txt`. It takes one to
two minutes the first time and does nothing afterwards. `random_events` contains C++ code, so the machine needs a
C++ compiler. Python 3.12 or newer is required.

### In the browser: Windows, macOS, Linux and tablets alike (recommended)

Nothing is installed on the student's computer.

1. Open the notebook in Google Colab:
   <https://colab.research.google.com/github/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/blob/claude/serene-carson-x3hvx6/exercises/advanced_methods_of_ai/wise26/03-pizza_queries.ipynb>
   (a Google account is needed). A JupyterHub of the university works the same way: upload the notebook.
2. Run the setup cell, then the rest from top to bottom.
3. Save your work with *File → Download → .ipynb* before closing the tab; a Colab session forgets its files.

### On your own computer: the same commands on every system

1. Install a C++ compiler, once:
   - Windows: the “Build Tools for Visual Studio” with the workload “Desktop development with C++”
     (<https://visualstudio.microsoft.com/visual-cpp-build-tools/>).
   - macOS: run `xcode-select --install` in the Terminal.
   - Linux: usually present; otherwise `sudo apt install build-essential` (Debian, Ubuntu).
2. Install uv, which brings its own Python, once. Windows (PowerShell):

   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

   macOS and Linux:

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. Put the notebook, `kitchen_picture.py` and `requirements.txt` in a folder of their own (outside a clone of
   this repository), open a terminal in it and run:

   ```bash
   uv venv --seed --python 3.12
   ```

   ```bash
   uv pip install jupyterlab
   ```

   ```bash
   uv run jupyter lab
   ```

4. In JupyterLab, open `03-pizza_queries.ipynb` and run the setup cell. Next time, only `uv run jupyter lab` is
   needed. In VS Code, open the folder and choose the interpreter in `.venv` instead of step 3's last command.

The setup cell and both routes were tested on Linux with Python 3.12, from an empty environment: the whole student
notebook ran without errors in about a minute, in an environment of 0.9 GB including JupyterLab.

## Requirements of the notebook

- KRROOD with the `match` semantics for collection-valued attributes (pull request #556, branch
  `fix/eql-match-collection-attributes`); the setup cell installs exactly that commit. On a KRROOD without it, the
  descriptions over the list `toppings`, such as `a(Pizza)(toppings=a(CheeseTopping))`, match nothing.
- The fixes of pull requests #566 and #567, carried onto #556 at commit `a4c474b434`.
- Attribute paths through a list, such as `pizza.toppings.spiciness` (pull request #605, stacked on #556). Without
  it, such a path matches nothing.
- Variables over an expression, `a(PizzaTopping).from_(pizza.toppings)` (pull request #541, upstream #922, merged
  into #605). Without it, the topping is bound to the expression object instead of each topping.
- The patterns `every_is(...)` and `none_is(...)`, and a union of classes such as `MeatTopping | FishTopping` in a
  pattern (pull request #606, stacked on #605 at commit `2ec20a0f73`, which the setup cell pins).
  Without #566, `an(Order)(pizzas=hot_pizzas)` returns every order once `hot_pizzas` has been evaluated. Without
  #567, a query evaluated a second time does not see objects created since its first evaluation, so `hot_pizzas`
  asked again in Act 5 misses the kitchen's offers.
- `kitchen_picture.py` must lie next to the notebook; the setup cell downloads it if it is missing.
- Once #556, #566, #567, #541, #605 and #606 are merged and released, the commit in the setup cell can be replaced by the release, and the two URLs
  in the setup cell should point to the default branch.

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

```bash
node src/render_pdf.js src/03-introduction_slides.html . --slides
```

The second command needs KRROOD (see above); the last two need Node.js with Playwright and its Chromium, and the
fonts Liberation Serif, DejaVu Sans and DejaVu Sans Mono. After rebuilding the notebooks, execute the solution
notebook again to store its outputs.

## Assumptions to check

- The date and room in the header (Thursday, 12.11.2026, 8:30 to 10:00, room 0.30, ECO 5) continue the weekly
  rhythm of Worksheet 2.
- The dataclasses of the first notebook cells were rebuilt from the text of Worksheet 2 and of `pizza.owl`.
  If the notebook of Worksheet 2 names a class or field differently, adapt those cells in `src/build_notebooks.py`.
