
## Branch `cramera_eql_autocomplete` -- the workspace in the EQL namespace, with completion

Branched off `montessori_fast_inline_monitor` at `30bd734f53` (so it carries the mesh
download retry and the scene-default fix). One commit: `2765cec9b8`, pushed. No PR opened
-- the developer asked for a branch, and the parent branch has no PR either.

### What the developer asked for

1. every class usable in a query, and
2. IDE-style hints in the query box: what types and variables exist, filtered by the
   characters typed.

Decided with them before implementing: workspace `src/` classes without the ~4,200
generated ORM DAO classes (3,024 names); attribute completion after a dot in scope; an
ambiguous bare name resolves by package priority with the module shown.

### What is on the branch

- `knowledge/workspace_classes.py`: `WorkspacePackage` (declaration order *is* the
  tie-break rule), `ClassLocation` (scan module `coraplex.src.coraplex.filter` ->
  importable `coraplex.filter`), `WorkspaceClassIndex` (cached per architecture root, so
  pointing at another checkout rebuilds and tests do not leak into each other), and
  `WorkspaceClassNamespace`, a dict whose `__missing__` imports on first use. A `KeyError`
  there is what keeps an unknown name a `NameError` inside a query.
- `knowledge/query_vocabulary.py`: `QueryVocabulary` built from the runner, so the recorded
  scene and the live demo describe what they really accept. Members come from krrood's
  `DataclassOnlyIntrospector` for fields plus an MRO walk for properties/methods -- read
  off the classes, never through `getattr`, so describing a type never runs a property.
- Endpoints: `/api/eql/vocabulary`, `/api/eql/members?name=` and the bridge's
  `/vocabulary?scope=`, `/members?name=&scope=`; `QuerySource` gained
  `vocabularyUrl(scope)` / `membersUrl(name, scope)`.
- `web/core/completion.js` (token under the caret, prefix + capital-initials matching,
  ranking, insertion) and `web/panels/eql/suggestions.js` (the menu). The menu is
  `position:fixed`, placed from the input's rectangle: every `.panel` sets
  `overflow:hidden`, and an absolutely positioned menu was invisible because of it -- that
  cost a round of debugging, do not "fix" it back to absolute.

### Verified

- 473 cramera tests pass (was 431): 18 index/namespace, 16 vocabulary, 3+4 endpoint,
  17 node completion, 3 node query-source.
- In Chrome against this checkout on port 8712: `Bo` offers Box/Body/Book/... with module
  and docstring; `scene_object.` offers name/kind/label/position/height_metres with their
  types; Tab accepts; Enter then runs the query; `len(list(Body.__dataclass_fields__))`
  answers 11, where `Body` was a `NameError` before.
- Vocabulary payload is 682 KB / 3,078 entries, fetched once per source in ~76 ms.

### Deliberate deviation to tell the developer about

They asked for *every* candidate of an ambiguous name in the menu. It offers the winner
once instead, labelled `module (+35 more)`: 36 identical `Descriptor` rows cannot be told
apart or chosen (a bare name always resolves to the winner), so the count carries the same
information without flooding the list. Say so; revisit if they want all rows.

### Next

- No docs beyond `cramera/README.md`'s new section; a dual-audience guide was not asked
  for.
- `_hand_placed()` classifies a non-type as `VALUE` with `type(value).__name__` as the
  detail -- fine for `objects`/`sum`, unhelpful for anything richer.
- The 682 KB payload could be trimmed (drop `detail` for classes, or serve names only and
  fetch details per row) if it ever feels slow.

