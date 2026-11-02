## Plan
- Resolve #540's fork review and keep cram2 #837 (tomsch420 requested changes) in step.

## Done
- 088d061d1f: `CallSignature.of(callee)` (new `call_signature.py`) owns `bind`, `keyword_arguments` (raises `ArgumentsPassableOnlyByPosition`), `accepts_keyword`; `CallArguments` is only the call's value; `initializer_signature_of`, `HasFactoryAndKwargs._factory_takes_keyword_` gone. `test_patterns` + `test_eql`: 1589 passed. Replied on `predicate.py:234`, left open.

## Next
- Owner: resolve the four open threads; update the #540 description (`CallSignature`, new exceptions, the factory test now patches `inspect` directly).
- Next maintenance pass carries d543f35349, 4248146cd9, 088d061d1f to cram2 #837; tomsch420 re-reviews.
