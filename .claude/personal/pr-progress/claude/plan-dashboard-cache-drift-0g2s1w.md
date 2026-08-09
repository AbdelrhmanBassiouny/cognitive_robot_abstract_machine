**Item:** `workflow-unification` / `dashboards` / `dashboard-url-cache-integrity`
(placement decided by running `add-plan-item`'s procedure by hand — the skill is
still unlanded on `claude/add-plan-item-skill-e89irj`, so it is not invocable).

**Mechanism found.** Classifying every URL ever written to the cache against the
real artifact listing separates by run kind: bulk refresh 0/23 named a real
artifact, first publish 10/13, hand corrections 15/15 (all made from
`Artifact action: "list"`). `SKILL.md` step 3 asked the session to hand-write the
YAML with "your updated url(s)", but on an in-place update there is no returned
URL to copy — so a UUID got invented, and nothing checked it. The next run passed
that dead URL as `url:`, could not update a missing page, minted a fresh
artifact, and produced the duplicate. Both live pairs arose that way.

**Done**
- `record_dashboard_url.py` + 15 tests (TDD; failing first). Resolves the URL from
  the listing by title, so no UUID passes through the session. Refuses an unlisted
  URL, a title matching nothing, and a title matching several (names both, demands
  `--url`) — the last also blocks silently repointing another plan's entry.
- `SKILL.md` step 3 rewritten; `DASHBOARD_URL_CACHE_PATH` +
  `RECORD_DASHBOARD_URL_SCRIPT` added to `resolve-personal-notes-config.sh`.
- Cache reconciled via the new script, one key at a time (dogfooded). 5 plans +
  `_index` repointed; `dag-facade-hardening` keeps `49053971` by the user's choice;
  `workflow-unification` reported `changed: false`, confirming it was already right.
- 291 tests pass (plan-dashboard + hooks). Branch pushed.

**Next**
- Awaiting the user's call on opening the draft PR. Once opened, run
  `plan_item_bootstrap.py open --pull-request-number` to fill `branch`, `session`
  and `pull_request_number` — currently `branch: null`, since `record` does not set
  them and no PR exists yet.
- Republish the `workflow-unification` dashboard (manifest changed by the `record`).

**Not addressed:** no automated audit of existing cache entries, so a URL that dies
for some other reason still surfaces only when someone opens the page.
