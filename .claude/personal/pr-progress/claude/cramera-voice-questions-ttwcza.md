## PR B — voice questions (draft #168, branch `claude/cramera-voice-questions-ttwcza`)

Stacked on PR A (#167, `claude/cramera-verbalization-voice-ttwcza`) which sits on
PR #165. Status: **PR A merged in as `abcb6ee7a`, pushed; still a draft**.

Layout now: the text bar stays; 🎤 sits inside the bar to the right of Run; a
recognized preset fills the bar with its code and its verbalization shows big
under the bar (from PR A). Matching unchanged: `/api/question` + `/question`,
rapidfuzz token_set_ratio vs label + verbalization text, MINIMUM_SIMILARITY=70,
server-supplied "Sorry, I cannot answer that question." reply.

### Merging PR A (2026-08-18)

Brought down PR A's two fixes: the scrolling console and the source-link
fallback. One textual conflict — both branches had appended a test section to
the end of `test/cramera_test/js/test_eql_panel.js`, so both were kept. The
harness merged additively on its own (A's `scrolledIntoView` counter beside this
branch's `recognizerClass()` / `speak()` / `mountPanel(overrides, recognizer)`),
as did `app.css` and `test_web_assets.py`.

The conflict that mattered was invisible to git. PR A added `showAnswer()` —
write the answer, then scroll to it — and routed `renderAnswer`'s three writes
through it, deliberately leaving the four unasked ones (load failure, hint,
entity description) alone. This branch had meanwhile added three answer writes
on the voice path (sorry reply, matcher error, capture failure) on different
lines, so they merged silently and kept writing straight to the element: a
spoken question's reply would have landed below the fold of a console that now
scrolls. All three now go through `showAnswer`, since a question asked aloud is
still asked; the comment's "Only a query" became "Only what was asked". The
matched path already went through `runQuery` → `renderAnswer`.

Worth remembering: this is the third silent conflict on this stack, after
`giskardpy/executor.py`'s dropped `Optional` twice. Same shape every time — one
side centralises something, the other adds a new use of the old way, no shared
line. After a merge, grep the call sites of whatever the base just centralised
and check the incoming side didn't add one that should have been converted.

Tests: 611 passed (full cramera suite, was 598); 221 node tests across 23 files.
The new test (`a spoken question nothing answers is scrolled to like any other`)
was run against the unfixed panel first and fails there.

### Outstanding
- CI not checked on #167/#168.
- experiments suite not runnable here (rclpy/ROS missing — pre-existing).
