## Outstanding
1. **CI is running on the fifth round.** Round four never reported on the long-term
   questions at all: the class-diagram fixture died at setup, so all 282 experiments
   tests errored before any of them ran. So the fourth round's krrood fix -- reading
   a collection's members as the class the query asks for -- is still unconfirmed,
   and this round is the first that can confirm it. Neither
   `test_long_term_questions.py` nor coraplex's suite can run in a session container.
2. **One thread left open**, needing the developer, and it is no longer about the
   recording: the robot's own degree-of-freedom count. No run sets `Episode.world`
   (the runner releases a trial's world before the trial is recorded), and the count
   itself is not one query because `SemanticAnnotation.bodies` is a computed property
   with no mapped path from an annotation to its entities.
3. **Three buckets still have no long-term spelling** and control has none in
   either memory. Support-and-spatial waits on `query-routed-per-predicate`,
   embodiment on a run that keeps its world, control on
   `control-constraints-and-degrees-of-freedom-queried`.
4. **This PR now changes krrood, segmind and experiments.** That breadth is the
   finding the branch was chartered to produce, but splitting the krrood half out
   is reasonable if the developer prefers.
