Data fix done directly on claude/personal-notes (no PR - see below). Code
hardening now also shipped as draft PR #136 on this branch, per explicit
follow-up request ("I would like a bug fix PR there").

Root cause: the workflow-unification dashboard's rendering glitch (one
bullet per character under personal-settings-sync) was a plan.yaml data bug
- that item's `blockers` field was a YAML block-scalar string instead of a
list, and `build_dashboard.py`'s `list(data.get("blockers") or [])` explodes
a Python string into one list element per character. Fixed the data by
restructuring it into a proper 3-item YAML list (unchanged wording), pushed
via save-plan.sh, and republished the dashboard Artifact (same URL, no
drift).

PR #136 (draft, `bug` label, based on main @ 2f459043, committed as
Abdelrhman Bassiouny <abassiou@uni-bremen.de> not the assistant identity):
adds `InvalidBlockers` to build_dashboard.py's `validate_plan`, mirroring
the existing `InvalidDependsOn` check (which already documented this exact
string-explodes-to-chars footgun for depends_on but had no equivalent for
blockers) - a string `blockers` now fails validation loudly instead of
silently corrupting the render. Added
test_validate_plan_rejects_blockers_that_is_not_a_list first (confirmed it
failed via ImportError before the fix), then implemented; full suite
(.claude/skills/plan-dashboard/tests + .claude/hooks/tests) passes, 223/223.
Subscribed to PR activity.

Next: none - waiting on review/CI. React to webhook events as they arrive;
no scheduled check-ins per this repo's personal-notes rule.
