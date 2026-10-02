# network-limits-on-main (montessori-perception-split) - draft PR #487

Plan: check out experiments/src/experiments/network_limits.py and
test/experiments_test/test_network_limits.py verbatim from #202's tip 4653fe32e
onto a branch cut from main. Make no code edits. Run the tests with --noconftest,
then confirm both files are byte-identical to 4653fe32e.

Done: branch re-cut from main (236b295a2), draft PR #487 opened, manifest set to
in_progress, roadmap section recorded. Commit 0a405d103 adds the two files
verbatim; 12/12 tests pass locally (pip venv with krrood, random_events and
probabilistic_model; experiments/src on PYTHONPATH). PR description updated.
Next: CI on #487. Once it is green the item is waiting on review. After it merges,
#202's diff stops showing these two files.
