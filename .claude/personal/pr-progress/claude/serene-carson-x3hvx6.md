This branch has no code changes. The session's work is in KAOS-repositories/basstler, worktree
C:\Users\Abdel\Projects\basstler-review-triage-url: #265 (review-triage-script-pull-request-url,
on #253) and #266 (review-triage-speed-and-progress, on #265).

Plan
- #265: review-triage.sh takes a PR URL; its clone gets an origin
- #266: triage 10x faster, tqdm progress, batched mark-viewed, --verbose / --summary-only

Done
- #265 and #266 opened as drafts; cram2 PR 1019 triages in 33 s (was 345 s), report identical
- #266: package-map CI failure fixed (ba022f3e); shared parses + parallel judging (9a84269f)
- Batched mutation validated against GitHub with a bogus ID; not yet run live

Next
- CI on #266 at 9a84269f; review; merge order #253, #265, #266
- Ask whether #266 needs api-break (ViewedFile, MARK_FILE_AS_VIEWED removed)
- Open: rename detection per file in workers; mark-viewed --workflow-repository default
