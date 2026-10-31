PR #540, plan item eql-planning/call-arguments-normalization. Draft, bug fix off main; merged into #535.

Plan:
- CallArguments binds arguments to the signature; the mapped-variable cache compares builtin containers by contents and other unhashables by identity.

Done:
- 72305bbc5: fix with 4 failing-first tests; then key_by(value_form) so CallTerm in #535 compares by identity.

Next:
- Owner reviews; node creation is 1.7x slower than main (Signature.bind); mark ready only when told.
