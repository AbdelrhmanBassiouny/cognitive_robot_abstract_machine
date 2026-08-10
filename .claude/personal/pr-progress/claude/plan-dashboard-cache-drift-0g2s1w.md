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

- Manifest carries `branch` + `session`; branch reverse-index regenerated via
  `save-plan.sh`. Dashboard republished to `07123af6` — **same URL, and the artifact
  count stayed at 11**, which is the end-to-end proof the duplicate-minting loop is
  closed.

- Draft PR **#150** opened, `bug` label, subscribed to its activity. Manifest carries
  `pull_request_number: 150` and the item's notes; `save-plan.sh` run.
- Dashboard **and** master index both republished to their existing URLs (`07123af6`,
  `094b785f`). Artifact count still 11 — no duplicate minted by either.
- The index republish is itself evidence for this item: the live one linked
  `dag-facade-hardening` to `572b350a`, the orphaned duplicate, and showed
  workflow-unification at a stale 12/37. All six links now resolve.
- Ran `record_dashboard_url.py` for `workflow-unification` and `_index` afterwards, per
  the new step 3. Both `changed: false` — cache already right, nothing pushed.

**CI on #150 — red, and proven base-side.** A merge of `origin/main` landed on the branch
from outside any session (`358b373d`), bringing main's own breakage with it. Four
`test_each_lib` jobs failed (3x coraplex, 1x experiments), all identically:

    error: Distribution `greenlet==3.5.5` ... doesn't have a source distribution or
    wheel for the current platform (Linux manylinux_2_39_x86_64; greenlet 3.5.5 has
    wheels only for macosx_11_0_universal2, win_amd64, win_arm64)

Every one dies at step 4 *Install dependencies*; steps 5-7 (Restore cache, Build ORM,
Run Script) are **skipped**, so no test ran. Three independent proofs it is not ours:
the branch diff vs main is still the same six `.claude/` files and touches no lockfile
or dependency manifest; main's own run at `7df3ce503` (the commit merged in) failed
**11 of 13** jobs, repo-wide, not coraplex-specific; and `ci.yml` on our own commit
`2e2dba47`, before that merge, was **success** — that is the workflow carrying
`test_claude_dev_tooling`, the only job reaching a `.claude/`-only diff.

Replied once on the PR with the evidence and why the fix (a `greenlet` pin, or the
`tool.uv.required-environments` entry uv suggests) belongs to whoever owns the repo's
Python dependency set rather than to a URL-cache PR. Offered to open a separate
`bug` PR for the pin. The later `experiments` event was the same error byte for byte,
so it was skipped rather than answered twice.

**Review round 1 (7 comments / 5 threads), applied in `74adb826`, pushed as `9f4c1ee6`.**
- Docstring: incident history out, what-it-does in (50 lines to 30).
- Every refusal is a dataclass with typed context fields and abstract
  `error_message()`/`suggest_correction()` composed at construction — `DataclassException`
  mirrored, not imported (stdlib-only tier). 4 protocol tests.
- `apply_url_record` returns `PatchedCache`; body is two guard clauses over
  `find_cache_entry_line` (returns `CacheEntryLine`) and `append_position`. No tuple
  returns left in the module.
- **Behaviour change on the user's instruction:** a duplicated title no longer asks.
  `ArtifactListingEntry` gains `updated`; most-recently-updated wins, ties keep listing
  order. `AmbiguousArtifactTitleError` deleted; `--url` demoted to an override.
  Validated against the two real pairs — recency reproduces both choices made by hand
  (`49053971`, and `07123af6` via the tie-break). Cost, stated on the thread: a newly
  minted duplicate no longer announces itself here.
- `AskUserQuestion` kept in `allowed-tools` — step 0's `prerequisite-check.md` still
  uses it. Checked before removing rather than assuming.
- 393 tests pass (was 291; difference is main's own plus 10 new here). Re-ran the whole
  suite *after* merging main, per the #110 lesson that a clean merge says nothing about
  whether the result still works.
- 4 of 5 threads replied-then-resolved. One left open deliberately: `suggest_correction()`
  is abstract here (as in `DataclassException`) but has a concrete `""` default in the
  sibling `ValidationProblem` on main — asked which the directory should follow.
- Description rewritten; PR still a draft.

**CI after the review round — `greenlet` cleared, one different failure left.** On
`9f4c1ee6` every job installed dependencies fine, so the repo-wide `greenlet` break has
resolved itself (no action taken here; it fixed upstream). **10 of 13 green, including
`test_claude_dev_tooling`** — the only job reaching a `.claude/`-only diff.

The one red is genuinely a different kind, which is why it earned the second comment I
said I'd only spend on a new kind: `test_gazebo.py::TestSmallWarehouseWorld::test_world_is_valid`,
an xdist **worker crash** (`gw0 crashed`), not a failed assertion — 1172 other
semantic_digital_twin tests passed. Base-side and provable: the file is absent from this
branch's diff, has been on main since 2026-08-02 (`062d6843b`, `e5a8cf980`, LucaKro), and
its own docstring says it needs the `aws_robomaker_small_warehouse_world` ROS package
*built in the workspace*. Same family as the Gazebo-adapter failure recorded on #124.
Replied once; not fixing it here.

Worth carrying: a *worker crash* rather than an assertion is the signature of a native/ROS
dependency missing from the CI image, and is worth separating from a real test failure
before spending time on it.

**Next**
- Nothing to push. React to further events; another crash in this same Gazebo test would
  not be worth a third comment.
- Nothing armed. The subscription notice asked for an hourly `send_later` check-in; not
  armed, per the no-scheduled-checks rule, which explicitly overrides that guidance.
- One concurrent-write note: another session republished the dashboard mid-run and the
  publish 409'd. Re-read, confirmed my render was strictly newer (same manifest plus
  #150's live state), republished. Worth knowing the guard fires for generated pages too.

**Not addressed:** no automated audit of existing cache entries, so a URL that dies
for some other reason still surfaces only when someone opens the page.
