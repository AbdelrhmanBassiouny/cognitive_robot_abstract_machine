# cramph-eql-semantics: roadmap

- Analysis and design: https://claude.ai/artifact/Vv5dxWpA1gXJ2GFEGT8mMp (built on cram2#1074).
- eql-planning's planning core comes first; items here start after it.
- EQL gives the meaning; ticks run compiled code or re-evaluate on change, never interpreted EQL on every tick.
- On the real executor's ticks EQL only reads through a state, never puts the world into one; a predicted State for monitoring is built on a frozen base.
- If cram2#1074 lands without lexical binding scope (replacing StatementsGroundedTogether._values_fixed_by_other_statements), add it as an item here.
- cramph imports only krrood and semantic_digital_twin; krrood imports no cramph.
