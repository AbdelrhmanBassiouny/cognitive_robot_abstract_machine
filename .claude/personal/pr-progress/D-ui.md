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
