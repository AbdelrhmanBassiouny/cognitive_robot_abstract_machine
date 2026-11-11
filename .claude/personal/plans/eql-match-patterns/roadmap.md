# Extend the EQL match pattern language

- A new pattern form means the same as the first-order formula it abbreviates, with the closed world of selective queries.
- Every pattern form works in a, every_is and none_is, nested or top level, or raises a dedicated exception where it cannot.
- Generation never yields an object the same pattern would not select.
