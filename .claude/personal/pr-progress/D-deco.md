# PR plan: D-deco — @rdr decorator + file store (Wave 0, S2)

Not started. See `.claude/personal/rdr-roadmap.md` §3 Wave 0. Base: `D-ui`
(cut after D-ui exists; final slice — after this, umbrella #38 must diff
empty against the split tip and be closed).

## Goal

The zero-boilerplate `@rdr` decorator path: function → generated
`FunctionCase` dataclass module → auto-persisted rule tree.

## Scope (copy from `abdel/rdr-engine`)

- Source: `rdr/decorator.py` (rdr() factory + RDRWrapper),
  `rdr/file_store.py` (RDRFileStore), `rdr/templates/rdr_empty.py.jinja`,
  `code_generation` additions it needs (`function_to_dataclass_source`
  home per the split: check `krrood/src/krrood/code_generation/`).
- Tests: test_rdr_decorator, test_rdr_file_store (+ any stragglers punted
  from D-ui).
- Docs: `doc/eql/developer/rdr_decorator.md`, `doc/eql/user/rdr_decorator.md`.

## SOLID anchors (from the design doc — keep this exact split)

- `rdr()` = factory (argument validation only), `RDRWrapper` =
  interception, `RDRFileStore` = file lifecycle, `FunctionCase` = shared
  contract, `function_to_dataclass_source` = code generation,
  `EQLSingleClassRDR` untouched. No circular deps between the three new
  classes.

## Procedure

1. `git checkout -B D-deco abdel/D-ui` (or D-core-engine if D-ui not yet
   pushed — rebase later), pull files from `abdel/rdr-engine`.
2. Verify invariants: `case_type.function` rewired on load;
   `rdr.save_path` set after both branches of load-or-generate.
3. Full suite, docformatter, draft PR `D-deco -> D-ui`.
4. Then: confirm `git diff abdel/rdr-engine D-deco` shows only
   intentionally-dropped legacy files; close umbrella #38 with a comment
   pointing at the split chain.
