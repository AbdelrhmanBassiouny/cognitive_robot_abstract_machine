## Plan
- Keep the item's pull request in step with upstream main and answer review.

## Done
- All five core crossings removed; core boundary test added.
- Merged upstream main (8ed27b107b) into the branch (pushed 1107f1c700). It conflicted in the module docstrings of control_loop_experiments/scenarios.py and semantic_annotations/mixins.py; upstream's docstrings were kept. Their classproperty imports, and the new spatial_type_marker_renderer.py's, now come from krrood.patterns.classproperty.
- Upstream pull request 978, read at its head: checks 30/30 passed, approved by ichumuh and LucaKro, no unresolved threads.
- Locally: the core boundary test (no_core_module_imports_outside_core) passes on the merged tree and no old import path of a moved module is left in the repository.

## Next
- Read CI on the new head 1107f1c700 and the merge probe against upstream main; the needs-resolution label clears on the next maintenance pass.
- Not run locally: the rest of the krrood tests and krrood check (no development environment here).
