# Fetching live pull request data into pr_data.json

The canonical procedure for gathering the `pr_data.json` shape
`build_dashboard.py`, `sync_manifest_status.py`, and
`check_dependency_readiness.py` all consume - referenced by
`plan-dashboard/SKILL.md` step 2 and `dependency-readiness.md` instead of
each restating it. See any of those three scripts' own `--help` / module
docstring for the exact JSON shape expected.

## The script route, when `gh` or a token is available

The `development_tooling.pr_state` module (repository root) fetches and
serializes this exact shape itself - including the optional chip fields
below - through `gh` when installed, else a `GH_TOKEN`/`GITHUB_TOKEN`.
`build_site.py` (next to this file) is the headless consumer: it builds
every plan's dashboard plus the master index with no session at all. A
session can use the same module instead of the MCP procedure below whenever
one of those routes is available; the MCP procedure remains the fallback
for a session with neither.

## Optional chip fields

Each pull request entry may additionally carry `ci`
(`"success"`/`"failure"`/`"pending"`/null), `additions`, `deletions`,
`mergeable`, and `session_url` - `build_dashboard.py` renders them as the
CI/change-size/conflict chips on the item card and as a session-link
fallback. All optional: entries without them (e.g. gathered by the MCP
procedure below, which cannot see them in bulk) render chipless, never
error.

Source the shared config script first if you haven't already this session -
it defines the tool-name constants referenced below:

```bash
source .claude/hooks/resolve-personal-notes-config.sh
```

For each distinct repository referenced (`items[].repository` if set, else
the plan's `default_repository`), fetch pull request state **once, in
bulk**, rather than one API call per item - with dozens of items per plan
this matters:

1. `${GITHUB_LIST_PULL_REQUESTS_TOOL}` with `state: "all"`, `perPage: 100`,
   paginating (`page`) until a page comes back short of 100.
2. For any pull request number not covered by that result set (older than
   the pagination window), fall back to `${GITHUB_PULL_REQUEST_READ_TOOL}`
   with `method: "get"` for that specific `pullNumber`.

Include `labels` even though most callers never look at it: a pull request
merged out-of-band never gets `merged_at` set, and this repo's convention
is to add a `"merged"` label by hand in that case - see
`build_dashboard.py`'s `PullRequestLabel`/`was_merged`.
