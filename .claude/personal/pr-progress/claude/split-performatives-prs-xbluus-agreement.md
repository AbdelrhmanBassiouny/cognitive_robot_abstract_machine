## Next
- Await rest of run 31393956085 on b6769dd73; rerun failed sdt job when the run
  completes (event wake or user ping — no timed polling).
- Once a head goes fully green: PR ready for user review/mark-ready. The restack
  routine handles #54/#14/#15.
- Candidate separate bug-fix PR (needs user approval to open): guard the coraplex
  conftest ORM regen from xdist workers (skip when `config.workerinput` is set),
  matching sdt's guarded pattern. One root cause, off main, `bug` label.
- Once green: PR is ready for the user to review/mark ready; the restack routine
  picks up #54/#14/#15 behind the new tip on its own.
