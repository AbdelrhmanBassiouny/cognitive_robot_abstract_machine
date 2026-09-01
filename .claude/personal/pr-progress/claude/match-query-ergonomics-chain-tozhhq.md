# chain-signature-reads-attribute-only-names (PR #248, draft, `bug`)

Plan `match-query-ergonomics`, item `chain-signature-reads-attribute-only-names`,
branch `claude/match-query-ergonomics-chain-tozhhq` off `main` at 2318e206.

## Plan
1. Discharge the recorded blocker: #182 merged 2026-08-24, dependency `is_ready: true`. [done]
2. Re-measure the collision on today's `main`. [done - the paths differ and still compare
   equal, because the bogus reads build a truthy `Comparator`]
3. Failing tests first at the level the fix changes. [done - 4 assembler-level tests fail
   on `main`; the core `_structural_key_` tests cannot fail first, since the missing name
   is itself a symbolic attribute]
4. `_structural_key_` abstract on `MappedVariable`, stated by each of the five kinds;
   assembler reads it per step. [done]
5. Record manifest + roadmap section 25, open the draft PR, republish the dashboard. [done]

## Verification
- `test/krrood_test/test_eql`: 1276 passed, 3 skipped.
- Full `test/krrood_test`: 2258 passed, 5 skipped; the two `test_object_diagram`
  failures are this container's missing Graphviz `dot` binary (`/usr/bin/dot: not
  found`), the same pair every earlier session on this plan recorded.
- The recorded repro script prints `equal : False` on this branch and `equal : True`
  on `main`.

## Records written
- `plan.yaml`: status `in_progress`, blockers cleared, branch/PR/session recorded.
- `roadmap.md` §25; dashboard republished; tracking issue #181 and #196 commented.

## Next / outstanding
- Landing order with #196: adjacent lines of `_expression_signature`; second lander
  resolves one hunk. Recorded on both pull requests.
- The user-visible ranking repro over two aggregates of one kind needs #196 *and* this
  one; neither alone closes it.
