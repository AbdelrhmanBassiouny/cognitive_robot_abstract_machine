# D-ui (#76) — resolving the 2026-08-30 review round's remainder

Tracked as `rdr-interface-and-decorator` / `D-ui`. Entered by `/plan-item-resolve`
in `auto` mode.

## What was actually stalling it

Not CI and not a conflict — the round was simply not finished. The reviewer had
answered two of the five open threads at 21:55Z/21:56Z, half an hour after the
previous session posted its completion note and stopped, and neither answer was
recorded anywhere. A third problem was self-inflicted: `rdr/__init__.py` was
still in the diff even though the thread about it had been resolved on the claim
that it was not.

## Done

- Recorded all of it in `plan.yaml`/`roadmap.md` *before* touching code, and
  republished the dashboard — the staleness rule.
- `CaseColumnLabel` in `case_table.py` on `D-ui-rendering` (`5a84033eb`, #79),
  where the reviewer directed the labels ask. Both readers use the members.
- Merged that tip into `D-ui` and put `test_ipython_side_by_side.py` on the enum;
  restored `rdr/__init__.py` to the base so it leaves #76's diff (`783546029`).
- Replied on both threads; resolved the labels one.
- Both PR descriptions rewritten to match; manifest, roadmap and dashboard updated.

## Next

- **Waiting on the developer**: whether this session pushes the generated-model
  header wording to #66 (`D-core-serialization`) — its template owns the text,
  it is unmerged, and it sits five branches down in another plan. The thread is
  replied to, left open, and carries the proposed wording.
- Not verifiable here: CI has still never run on either branch, and this
  container has no project interpreter, so the suite ran `--noconftest`
  (415 passed / 119 skipped of 534 on `D-ui`, identical before and after).
- Left ready-for-review rather than re-drafted — nothing in the record says a
  session marked either PR ready, so the flip reads as the developer's.
