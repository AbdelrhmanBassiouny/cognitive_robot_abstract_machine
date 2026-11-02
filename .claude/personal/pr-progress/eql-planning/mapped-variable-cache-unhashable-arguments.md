## Resolve, Nov 2

- Upstream cram2 PR #837: tomsch420 requested changes; checks pending.
- Done: `HasFactoryAndKwargs` reads signatures through `CallArguments.signature_of` and drops its own `lru_cache` (owner chose this over storing `_kwargs_` as `CallArguments`, which would change a field `Match` reads). `test_patterns` and `test_eql/test_core`: 471 passed.
- Open for reviewers: LucaKro's two threads (frozen cache item, purpose of the mimic) are answered by the owner.
- Fork checks on 1616d8d: `random_events` failed on `No space left on device` while installing `pyarrow`; `segmind` failed in the same run (log not conclusive). Neither touches this change.
- The pull request stays ready: its upstream review is still open.

## Fork review, Nov 2 (later)

- Owner's question on `factory_and_kwargs.py:106` (is the signature cache the only share?): no. `merge_args_and_kwargs` and `get_function_argument_names` are replaced by `CallArguments.named_by_parameter` (defaults still left out, so symbolic calls are unchanged; arguments that fit no parameter now raise `TypeError` at build time). Commit d543f35349, 4 new tests, `test_patterns` + `test_eql` 1573 passed. Answered in the thread; the thread is left open for the owner to resolve.
- The upstream PR (#837) now needs the same two commits pulled in by the next maintenance pass.
