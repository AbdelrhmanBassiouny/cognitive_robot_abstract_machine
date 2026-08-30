# perception-backend (#222, branch `perception_eql_backend`, base #221)

Plan item `perception-backend` of `knowledge-directed-perception`. Kicked off and
built 2026-08-30 in `auto` mode. The reasoning is in that plan's `roadmap.md`
section of the same name and in #222's description; this is the working state.

## Done — the whole plan, built and pushed as `71730494`

- **krrood**: `Directive.LOOK_FOR`; `BackendCannotResolveCondition` beside
  `SelectiveBackendCannotResolveEllipsisMatch`; `AttributeEquality.read_from`, which
  reads `<selection>.<attribute> == <value>` off a condition; and
  `SymbolicExpression._constrained_variables_`. krrood's own tests use the mimic
  `BackendThatLooksAtTheWorld` in `test/krrood_test/dataset/`, never the perception
  backend (self-containment rule).
- **`SceneRequest`** in `perception/scene_request.py` — the detection type asked for
  and the surface asked about. `MontessoriSceneSource.scene(request)` takes it;
  `PerceivedObjects` is deleted.
- **Pipeline** honours it: `searched_surfaces(board, request)` drops the surface not
  asked about, `detect(frame, request)` skips the piece passes when no piece was
  asked for.
- **`PerceptionBackend`** in `perception/backend.py`.
- **Node** unchanged in behaviour, deliberately: it serves its newest look and the
  narrowing is ignored there. Recorded in its docstring, the roadmap and #222.
- **Manifest**: `status: in_progress`, branch/session/PR recorded; `depends_on` gained
  `detect-per-supporting-surface`. Roadmap section written. Structural change recorded
  on tracking issue #201. Dashboard republished.
- **Tests**: 17 added. `test/experiments_test/` 304 passed against 291 on the parent;
  `test/krrood_test/test_eql/` 1059 against 1050. Both failing-and-erroring sets are
  identical to the parent's.

## Next

- Nothing outstanding from this session. #222 is a draft awaiting review.

## Watch out for

- Base is #221, not #205. Do not restack onto #205.
- Correctness must never depend on the pushdown being honoured: pushed-down conditions
  stay in the `where` clause so native evaluation re-checks them. The *selected type* is
  the exception — the backend filters the domain by it, because a variable's declared
  type is not a condition the query re-checks.
- The container: Python 3.12 venv at `/tmp/venv312`, workspace on `PYTHONPATH`,
  `--noconftest`. `scripts/regenerate_all_orm.py` fails on `CouldNotResolveType: Usd`
  here, with or without this branch — the ORM path is unexercised.
