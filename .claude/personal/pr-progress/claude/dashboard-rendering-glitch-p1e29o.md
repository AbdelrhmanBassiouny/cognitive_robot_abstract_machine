Root cause found and fixed - done, no PR needed.

The dashboard glitch (screenshot showed one bullet per character under the
personal-settings-sync item) was a data bug, not a code bug: that item's
`blockers` field in workflow-unification's plan.yaml was a YAML block-scalar
*string* instead of the schema's list of strings. `build_dashboard.py`'s
`list(data.get("blockers") or [])` on a Python string explodes it into one
list element per character, and the template renders one `<div
class="blocker">` per element.

User chose the data-only fix (declined hardening build_dashboard.py against
this class of input). Restructured the prose into a proper 3-item YAML list
(unchanged wording, split at the existing "(1)"/"(2)" boundaries), pushed via
save-plan.sh, verified `list()` now yields a real list of 3 in Python and
`build_dashboard.py`'s output has exactly 3 `.blocker` divs, then republished
the workflow-unification dashboard Artifact (same URL, no drift, no manifest
auto-corrections). Nothing to commit to this branch - the fix lives entirely
on claude/personal-notes.
