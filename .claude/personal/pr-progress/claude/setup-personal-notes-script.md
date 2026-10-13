## Next
- Do not fix semantic_digital_twin or coraplex here — separate root causes,
  other packages; AGENTS.md routes ORM issues via
  `scripts/regenerate_all_orm.py`/the developer.
- Still unverified: label **creation** against a real token. This
  environment's is a fine-grained installation token, so `POST .../labels`
  is exercised only through the stub. Flagged in the PR body.
- Leave as draft until told otherwise.

## Plan
Extract the mechanical half of `/setup-personal-notes` into a script that
needs no session, and shrink SKILL.md to what a script cannot supply.
