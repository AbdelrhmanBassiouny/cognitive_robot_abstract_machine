## PR A — verbalization under the bar + doc links (draft #167, branch `claude/cramera-verbalization-voice-ttwcza`)

Stacked on PR #165 (`montessori_event_replay`). Status: **reworked per
feedback, amended commit force-pushed**. The query text bar stays (textarea +
Run inside one bar); the asked query's verbalization shows big *under* the
bar, and its class/attribute words hyperlink to Sphinx AutoAPI pages via
`PublishedDocumentationResolver` (site default cram2.github.io aggregate,
`CRAMERA_DOCUMENTATION_SITE` overrides; only packages with published docs get
links). Presets travel worded as before. 481 passed.

PR B (#168, `claude/cramera-voice-questions-ttwcza`) is stacked on this and
adds the 🎤 inside the bar beside Run.

### Outstanding
- CI not checked on #167 after the force-push.
