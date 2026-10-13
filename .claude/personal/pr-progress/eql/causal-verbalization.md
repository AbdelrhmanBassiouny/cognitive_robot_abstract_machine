PR #82 (eql/causal-verbalization -> claude/rdr-why-answer-6fnw2o), draft, RDR
causal-explanation verbalization + rule codes. Working branch:
claude/pr-82-causal-review-t6ppd2.

Status: review round DONE, plus one CI-caught regression fixed. All 22
threads replied-and-resolved (20 resolved, 2 left open pending PR #83 — the
boolean-predicate goldens). Pushed commit f9fa1252 (rebased cleanly onto a
mid-session remote restack, zero file overlap) then commit 2bb7503e (a
CI-caught fix, see below) to eql/causal-verbalization. Author+committer both
set to the human identity throughout. PR description updated to match the
diff, session link kept. PR stayed draft throughout (per personal-notes
default).

CI-caught regression (commit 2bb7503e): the krrood test_each_lib job failed
with `AttributeError: 'WhyAnswer' object has no attribute 'rule_kind'` in
test_why.py — a file I never touched, missed because my earlier "is rule_kind
read anywhere?" grep only covered krrood/src, not test/. Fixed both
assertions to use `answer.rule_code.kind.tree_connector_word` (the field's
replacement) instead of the removed `answer.rule_kind`. Verified: (a) a
comprehensive re-grep of the whole test/ tree for rule_kind/from_kind/
CausalConnectives/.verbalize()/_annotate_rule_comments turned up nothing else
missed; (b) an isolated WhyAnswer dataclass construction confirms the
attribute chain resolves to "if"/"except if" correctly; (c) local end-to-end
verification is blocked by a pre-existing `jpt` import-chain gap in
.why()'s evaluation path (same class of pre-existing local-env gap
documented elsewhere in these notes, not something my fix caused — confirmed
by every test in the class failing identically at setUp(), not just the two
I touched). Real verification is CI, which has the full env.

CI on 2bb7503e (full run, workflow 29698823747): 17/18 green, including
