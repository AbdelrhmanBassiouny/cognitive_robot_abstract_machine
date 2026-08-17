## PR B — voice questions (draft #168, branch `claude/cramera-voice-questions-ttwcza`)

Stacked on PR A (#167, `claude/cramera-verbalization-voice-ttwcza`) which sits on
PR #165. Status: **reworked per feedback, rebased onto reworked PR A, pushed**.

Layout now: the text bar stays; 🎤 sits inside the bar to the right of Run; a
recognized preset fills the bar with its code and its verbalization shows big
under the bar (from PR A). Matching unchanged: `/api/question` + `/question`,
rapidfuzz token_set_ratio vs label + verbalization text, MINIMUM_SIMILARITY=70,
server-supplied "Sorry, I cannot answer that question." reply.

Tests: 513 passed (full cramera suite) after rebase; panel demo tests assert
the bar-fill and button-in-bar placement.

### Outstanding
- CI not checked on #167/#168 after the force-pushes.
- experiments suite not runnable here (rclpy/ROS missing — pre-existing).
