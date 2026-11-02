## Plan
- Resolve #540's fork review and keep cram2 #837 (tomsch420 requested changes) in step.

## Done
- `HasFactoryAndKwargs` reads signatures through `CallArguments.signature_of`; `merge_args_and_kwargs` and `get_function_argument_names` replaced by `CallArguments.named_by_parameter(signature, ...)` and `initializer_signature_of` (no `without_first` flag). Commits d543f35349, 4248146cd9. `test_patterns` + `test_eql`: 1577 passed.
- Replied inline on all three fork threads; all left open for the owner (the rename to `without_self_or_cls_arguments` was answered differently: the flag no longer exists).

## Next
- Owner: resolve the three threads, update the #540 description (new `TypeError` for arguments fitting no parameter).
- Next maintenance pass carries both commits to cram2 #837; tomsch420 re-reviews.
