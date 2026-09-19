## `/add-plan-item`: downstream propagation from `/plan-item-resolve`

**This branch carries no work and must not become a pull request.** It descends from
`integration`, which `check-setup.sh` refuses as a pull request base, and the session that
used it only ran `/add-plan-item` — a skill that writes no code and cuts no branch.

### Done

- Ran the scope check against nineteen unlanded tooling branches. Outcome: **new item**, not a
  fold and not a duplicate.
- Recorded `resolve-propagates-downstream` on `plan-tracking-skills` (track `skills`,
  `not_started`), with its `roadmap.md` section and `notes`.
- Republished the dashboard: https://claude.ai/artifact/DJpqWMCgNiGv5QFGr7xGHz
- Posted the structural record on tracking issue #102.

### Next

`/plan-item-kickoff plan-tracking-skills resolve-propagates-downstream`, which must cut the
item's branch from `origin/claude/plan-item-kickoff-workflow-cuare2` (#185, the basstler
relocation) rather than from `main` — the new code is Python and #185 is where `basstler/`
and `test/basstler_test/` exist.

### Carried forward

- **`.claude/skills/plan-item-resolve/SKILL.md` is contended** by thirteen unlanded branches,
  most inserting #151's "Record what you found" block in the same region. Keep this item's
  footprint there to a reference line pointing at a document of its own.
- **`depends_on` is empty on purpose.** The real dependency is `basstler-package`'s own item,
  in another plan; cross-plan `depends_on` is #253, still in flight. Make it a named
  `depends_on` once #253 lands.
