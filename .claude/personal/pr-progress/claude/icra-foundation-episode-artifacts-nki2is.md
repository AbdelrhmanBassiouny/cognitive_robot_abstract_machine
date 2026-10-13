## Next
Nothing outstanding on this branch. Waiting on CI, and on the developer's review.


## Outstanding / flagged
- **Tooling bug, not fixed here**: `.claude/hooks/plan_item_bootstrap.py`'s
  `ITEM_FIELD_INDENT` is 4 spaces, but every `plan.yaml` indents item fields by 2.
  `open`/`record` therefore write `branch`/`pull_request_number`/`status`/`session`
  one level too deep - inside the preceding folded scalar or list - and
  `save-plan.sh` rejects the result as unparseable YAML. Worked around by writing
  the manifest directly. Blocks every kickoff/resolve bootstrap until fixed;
  out of scope for this PR.
- Tests are CI-only (nothing in this workspace installs in a session container),
  so this branch is not verified until CI runs. The module's logic WAS executed
  locally against stand-ins - 12 behaviours, all passing - but not as pytest.
- `generate_orm.py` is also appended to by #278: a textual meeting, not a design one.
