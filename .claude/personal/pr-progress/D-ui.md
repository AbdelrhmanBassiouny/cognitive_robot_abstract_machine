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

- Header thread: the developer chose "push it, and regenerate #76's copies".
  #66 (`D-core-serialization`) carries the new wording plus the first test of
  that header (`bb01256df`); #76's three `fitted_models/` modules follow
  (`1045c6d5a`). Both threads replied to and resolved — #76 has none open.

## Next

- **Nothing is owed on #76 by this session.** Its review round is fully worked.
- Known inconsistency, stated on the PR and in the roadmap: every branch between
  #66 and #76 carries the template with the old header while #76's three
  generated modules carry the new one. A steward cascade fixes it; regenerating
  a model on #76 before then puts the old header back.
- Not verifiable here: CI has never run on #76 or #79, and this container has no
  project interpreter, so the suite ran `--noconftest` (415 passed / 119 skipped
  of 534 on `D-ui`, identical before and after). `test_serialization.py` — where
  the new header test lives — could not be run at all: its import chain reaches
  `random_events_lib`, an unbuilt compiled extension. Its logic was checked
  standalone against the real template; it still needs a real run.
- Left ready-for-review rather than re-drafted — nothing in the record says a
  session marked #76 or #79 ready, so the flip reads as the developer's.
