## PR B — voice questions (draft #168, branch `claude/cramera-voice-questions-ttwcza`)

Stacked on PR A (#167, `claude/cramera-verbalization-voice-ttwcza`) which sits on
PR #165. Status: **implemented, tested, pushed, draft PR open**.

What it contains: `core/voice.js` capture (injectable recognizer) → 🎤 button →
`voice:transcript` bus event; default consumer POSTs to `/api/question`
(recorded) or `/question` (live bridge); `question_matching.py` scores with
rapidfuzz token_set_ratio vs preset label + verbalization text,
MINIMUM_SIMILARITY=70; match runs preset as if clicked, else server-supplied
"Sorry, I cannot answer that question." rapidfuzz added to
cramera/requirements.txt.

Tests: matcher unit tests, endpoint + full demo round-trips on both servers,
voice state-machine node tests, panel-level demo tests (scripted recognizer),
Python↔JS payload-key contract tests. Full cramera suite: 504 passed.

### Outstanding
- CI not checked on #167/#168 (session ends before CI ran).
- experiments suite not runnable here (rclpy/ROS missing — same pre-existing
  env-only failures PR #165 documented); montessori's only contact point is
  `bridge.query_presets()` label comparison, unaffected by wording.
