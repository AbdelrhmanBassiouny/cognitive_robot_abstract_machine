### Outstanding
- **CI has not been read yet** for this branch. Both test files run only there.
- An automated integration pass merged the updated base into the remote branch
  mid-session; that merge is in and the tests still pass on top of it.
- Two tables the item's title implies are deliberately absent, each recorded
  with the item that owns it: accuracy per bucket/Bloom level
  (`question-set-answered-from-memory`) and the resource-cost table
  (`resource-cost-measured-per-system`). Neither column exists on an episode
  row yet.
