## Next
- Nothing outstanding. Two review threads exist; both replied to, one deliberately left
  open for the user to close.

## Plan
1. Prove the bug: a scratch checkout carrying the tooling, a second branch carrying a
   version whose command set differs, and the in-tree invocation failing after the switch.
2. `stack.py pin-tooling`: copy the tool outside every checkout, print the copy's
   `stack.py`.
3. `SKILL.md` step 0c pins right after `configuration`; every later command names the
   pinned copy; a test asserts nothing else runs from the working tree.
