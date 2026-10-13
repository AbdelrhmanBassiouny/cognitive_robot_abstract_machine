# plan-dashboards — standing rules

- Whichever lands second merges. Seven items here edit `build_dashboard.py` and its template with no dependency between them. That is textual overlap, not ownership, and it has been the working arrangement throughout.
- Bug-fix pull requests carry the `bug` label; tooling that never existed does not. An item that *surfaces* bug fixes is not itself a bug fix.
- Wording is not pinned by tests. Twice a round added a test asserting a rendered sentence, and twice the user cut it: nobody parses a drift description or a summary line, so pinning the sentence buys a failing test per reword and catches no defect. What survives asserts that each case renders *something*, and pins rules rather than phrasings.
- Check the neighbours before defending a guard. Three rounds argued about one test, and what ended it was reading how the module already treats the identical pattern - not reasoning about what the test was worth.
- The formatter's non-convergence is positional. An attribute docstring directly before a decorated definition makes `docformatter` drop a blank line, `black` restore it, and `format_docstrings.py` discard the lot - so the whole file is silently declined. Two changes here hit it by placing a new class at exactly that adjacency, and the fix both times was placement.
- The package extraction moves this file wholesale. Every open item here merges main across that move and re-applies its delta.
- Screenshots are binary and regenerated from the committed example, so two branches that both regenerate them conflict. Whoever lands second re-regenerates, which is mechanical since the image is deterministic from the fixture.
