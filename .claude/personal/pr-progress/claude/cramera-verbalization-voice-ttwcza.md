## PR A — verbalization under the bar + doc links (draft #167, branch `claude/cramera-verbalization-voice-ttwcza`)

Stacked on PR #165 (`montessori_event_replay`). Status: **the reported defects
fixed and pushed** (`06a5297b3`, `c045c9f5b`), description rewritten to match.
The query text bar stays (textarea + Run inside one bar); the asked query's
verbalization shows big *under* the bar; presets travel worded as before.
579 passed.

Two fixes on 2026-08-18, both reported from running the demo:

- **The console scrolls.** The verbalization plus a few rows of presets pushed
  the answer out of a panel that clips its overflow. Question + presets + answer
  now share one scrolling `.console-body` under a bar that stays put (the
  suggestion menu is placed once from the input's rectangle, so a scrolling bar
  would strand it). An answered query is scrolled to; descriptions are not —
  the graph emits `entity:select` as it loads and the episode replaces its own
  step, and revealing those showed an unasked answer on load.
- **The links exist now.** `PublishedDocumentationResolver` only covers the six
  packages the docs site publishes, and a scene is queried through none of them
  (`cramera`, `experiments`), so no word was ever a link outside the tests.
  `RepositorySourceResolver` links a word to the line its class is declared on,
  `WordLinkResolver` asks documentation first. The file is read at the commit
  the checkout is on (`main` 404s — `cramera` is on no main), overridable with
  `CRAMERA_SOURCE_SITE`, and the checkout is `paths.repository_root()` rather
  than the `CRAMERA_ARCHITECTURE`-configurable `architecture_root()`.

PR B (#168, `claude/cramera-voice-questions-ttwcza`) is stacked on this and
adds the 🎤 inside the bar beside Run.

### Outstanding
- CI not checked on #167 after this push.
- The branch is still based on #165's pre-fold tip, so it has yet to take the
  timeline work the #175-into-#169 fold brought into the stack.
