## Next
- Nothing on the branch. CI on the new head (1e93c138) unread; what the previous heads'
  unread CI was hiding is the crash above, so read it this time rather than assuming.
- Put to the developer and not decided: segmind's interface now maps Match_RelationDAO and
  Variable_RelationDAO. One ignored_classes entry in segmind/scripts/generate_orm.py is
  where it goes if the query graph should stay out of the schema.
- Two threads answered and left open for the developer, both krrood questions:
  whether `Match.stating` earns its place (it has one production caller, and the fold into
  that caller was offered), and whether subclassing `Match` was worth it (no -- the
  equality override contradicted `Match`'s identity equality silently, which is the
  argument, and the honest cost of dropping it is that reading an operand is now a call).
- One thread open for the developer: he proposed making `InsideOf` answer for regions to
  fold the containment check onto the statechart's detectors. It already answers for them
  -- 1.000 sunk, 0.500 standing over the hole, 0.000 clear, 23x cheaper than
  `InsideRegion` -- but it counts vertices in a bounding box, so its own 0.5 default reads
  the over-the-hole case as *in* while the detectors' 0.9 reads it right. His to settle,
  with `InsideRegion` being a `PlacementRelation` the second thing to weigh.
- The lid marks stay four; a history reaches two of them, and the rest is
  `competing-explanations`'.
- A look cannot tell a sunk piece from one standing over the hole; the success case is
  checked against a stated sighting only until the icra item runs it in simulation.


## Watch out
- A red check on a job whose sources the diff does not touch is not automatically someone
  else's: the ORM build runs in every job, so one broken generator fails nine of them.
- The full ORM generation needs rclpy for giskardpy and everything after it, which this
