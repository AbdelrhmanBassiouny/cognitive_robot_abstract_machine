## Plan: Cramera verbalization display + voice questions (stack under PR #165)

Two stacked PRs, per the user's request:

1. **PR A — DONE, open as draft #167** (this branch,
   `claude/cramera-verbalization-voice-ttwcza`, base `montessori_event_replay`):
   verbalization display replaces the EQL text box; presets travel worded
   (recorded scene + live bridge, per scope); question shown big; node demo
   test drives the full panel flow. Full cramera suite green (472).
2. **PR B — next** (branch `claude/cramera-voice-questions-ttwcza`, base =
   PR A's branch): 🎤 record button → SpeechRecognition transcript →
   `voice:transcript` bus event; default consumer POSTs to a question-match
   endpoint (rapidfuzz similarity vs preset verbalizations + labels, named
   threshold); match → run preset as if clicked; no match → "Sorry, I cannot
   answer that question." Extensive matcher/endpoint/voice tests + full demo
   round-trips (recorded server + live bridge + panel-level JS).

### Next steps
- Implement PR B backend (`question_matching.py`, `/api/question`, live
  `/question`, rapidfuzz dep in cramera/requirements.txt).
- Frontend voice capture module + panel wiring + CSS states.
- Tests incl. demo round-trips; open draft PR B based on PR A's branch.

### Outstanding
- CI on #167 not yet checked.
