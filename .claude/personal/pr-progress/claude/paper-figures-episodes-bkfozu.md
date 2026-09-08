## `claude/paper-figures-episodes-bkfozu` — PR #297 (draft)

Plan item `icra-evidence` / `paper-figures-from-episodes`, track `release`,
kicked off in `auto` mode. Based on #278 (`episodes-queried-by-eql`). The full
plan and what building it found are in the plan's `roadmap.md`, under "as
planned" and "as built" 2026-09-08.

### Done — the item is built and pushed

- `experiments/src/experiments/paper/`: `figure.py` (`FigureName`, `FigureFile`,
  `WrittenFigure`, `PaperFigure`), `measurement.py` (`MeasuredQuantity`,
  `RunConditions`), `outcomes.py` (four tables), `queries.py` (two tables),
  `figure_set.py` (`FigureSet.for_the_paper`).
- `experiments/scripts/generate_paper_figures.py`, the one script; the new
  package added to `generate_orm.py`'s ignore list.
- `LongTermMemory.recall_every_trial`, the question the script asks.
- `test_paper_figures.py` (23 tests, run here outside the ORM conftest, all
  passing) and `test_paper_figures_from_the_database.py` (CI-only round trip).
- PR description, `plan.yaml` and `roadmap.md` all match what the branch does.

### Outstanding

- **CI has not been read yet** for this branch. Both test files run only there.
- An automated integration pass merged the updated base into the remote branch
  mid-session; that merge is in and the tests still pass on top of it.
- Two tables the item's title implies are deliberately absent, each recorded
  with the item that owns it: accuracy per bucket/Bloom level
  (`question-set-answered-from-memory`) and the resource-cost table
  (`resource-cost-measured-per-system`). Neither column exists on an episode
  row yet.

### For the developer

- **`plan_item_bootstrap.py` `open`/`record` are broken for this plan.** They
  write an item's fields indented under a folded (`>-`) `title`, producing
  invalid YAML that `save-plan.sh` rejects. Every item here has such a title.
  Worked around by editing `plan.yaml` by hand; not fixed on this branch.
- Local verification needed a `geometry_msgs` stand-in inside a throwaway venv,
  because `segmind.datastructures.events` imports ROS messages that are not on
  PyPI. Nothing of that is in the repository.

