**Task:** assess the #106/#110 overlap, then apply the agreed #106-side fix.
No PR of its own — the assessment is chat-only, the code change went onto
#106's branch (`claude/stack-tooling-on-main`) with your explicit go-ahead.

**Assessment conclusions (delivered in chat):**
- The #106/#110 split is *correct*; #110 stands alone (2,645 lines vs 187).
  Do not fold it — that would be over-applying the #133→#117→#106 precedent.
- `POINTER.md` beats #110's `routine-prompt.md`, but on the *test-pinning*
  argument, not the "not on main yet" one, which expires when #106 lands.
- Three artifacts were built twice, not one: the pointer prompt, the
  pre-board config subcommand, and `ROUTINE.md` SETUP step 0.
- Verified: #110's step-0 rewrite fails 2 of #106's 14 contract tests;
  merging #110 into #106 conflicts in all five `.claude/stack/` files.

**Done on #106 (`36eda87a`, pushed):** replaced `stack.py remotes` with
`configuration`, printing one `field<TAB>value` line per `Configuration`
field. `upstream_setup_command` moved onto `Configuration`, omitted when
absent. Updated `ROUTINE.md` step 0b, `README.md`, module header; 3 new
tests. 286 CI tests pass. This makes #110's `config` and #106's `remotes`
one surface, so #110's rebase deletes internals only.

**Also done:** #106's description updated (new "One surface for configuration"
section, `272 passed` → `286`, `13 tests` → `14`, this session appended to the
Sessions line). The GitHub MCP read returns the body HTML-escaped with `<...>`
placeholders *stripped*, so it cannot be round-tripped — fetched the raw body
from `api.github.com` unauthenticated instead, edited that, and PATCHed it back
with `$GH_TOKEN`; verified byte-identical afterwards. Use that route for any
future description edit on this repo. Plan manifest + roadmap updated
(`289b8167` on personal-notes) and the dashboard republished to its existing
URL (36572776); zero drift, zero auto-corrections.

**Next / open:**
- Two review threads on #106 still unresolved. `stack.toml:23` asks a direct
  question ("strip the inference here?") — my answer is **no**, keep it,
  delete it in #110. `stack.py:84` is the parser-not-validator note.
- Confirm whether the 2026-07-31 native-stacks re-scope's `stack.py` half
  (cutting `next` / `restack-plan`) is still outstanding. If so, sequence it
  *before* #110's rebase, or that rebase pays the same conflict twice.
- #110 side (not mine to push): delete `routine-prompt.md`, render
  `POINTER.md`, drop the dead `<TOOLING_BRANCH>` fallback, update the two
  step-0 contract tests, adapt `check-stack-setup.sh`/`setup-stacked-prs.sh`
  from `stack.py config` to `stack.py configuration`.
