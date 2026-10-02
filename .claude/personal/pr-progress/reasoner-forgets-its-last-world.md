# PR #483 — Give each reasoner its own rules so the last world it classified is freed (`bug`)

Branch `reasoner-forgets-its-last-world`, off `main`. Draft. Session_016LRmUnGe5NAuEmCxZy9E6t,
2026-10-02. Found while root-causing #229's sdt CI world-budget failure (also merged there).

## Done

- `49ca5081`: `CaseReasoner.rdr` is a `cached_property` reading its own `GeneralRDR`; the
  class-level `rdrs` / `CaseRDRs` are gone. Test `test_each_reasoner_applies_rules_of_its_own`
  (red without, green with, in the CI image). Session-end worlds for the reasoner tests: 5 -> 0.
- A world-is-freed assertion inside a test does not work: the per-test SymbolGraph (rustworkx,
  invisible to gc) holds annotations until teardown.

## Next

- CI on the PR.
