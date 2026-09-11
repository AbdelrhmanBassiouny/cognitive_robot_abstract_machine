## ICRA paper re-cut (planning session 2026-09-11, no code, no PR)

Deliverable: the "KRROOD ICRA Re-cut" artifact
https://claude.ai/code/artifact/71c63b27-e7d1-495d-a1ab-9f53aeb645c1 - a four-day
paper plan reframing the paper as the single-language realisation of the KnowRob 2.0
vision, evaluated the KnowRob 2.0 way (query answering) made rigorous.

Done: read the KnowRob 2.0 paper; read icra-foundation/mechanism/evidence and the
related plans; surveyed krrood, semdt, coraplex, segmind, giskardpy and PR #265;
wrote the capability matrix, abstract, hypotheses H1-H4, paper structure, twelve
query cards, figure list, item-by-item plan modifications, six new items with
designs, the schedule and the risks.

Findings that limit claims: segmind composite events are imperative, no provenance
(new item event-rules-as-eql); no router or cross-backend disagreement check yet
(new item cross-backend-check); no question performatives or temporal operators
(new item question-performatives).

Next (developer's call): accept/amend the re-cut, then apply it to the three
plan.yaml files on claude/personal-notes and republish the dashboards; start
event-rules-as-eql and question-performatives in parallel sessions off #265.

Update 2026-09-11 (later): the segmind EQL event rules exist on the fork branch
sorinar329/cognitive_robot_abstract_machine:safety_ai_ws (forked 2026-05-06, main 2610
commits ahead, tracks a generated ormatic_interface.py, old event class names). Verdict:
port ~60 lines (rule body of _find_interaction_events, event_time_difference,
not_(exists(...)) dedup) onto #265; do not merge. Its krrood half already landed on main
as InferenceExplanation's meta-query methods. Artifact item 1 rewritten accordingly.

Update 2026-09-11 (later still): developer reports an existing VLM comparison on ~100
simulated episodes with table and statistics. Not found in the repo, the fork branch, or
Drive (the SegMind IJCAI-W paper is single-episode, no VLM arm). Plan updated: VLM items
become vlm-comparison-imported (existing results as ExperimentResult rows beside #304's
accuracy rows); asked the developer where the data lives and which question set it used.
