# montessori-perception-split — standing rules

- `network_limits` is its own pull request off `main`, not the bottom of the stack.
- The ~3,560-line detection layer is cut in two (5a/5b).
- #202 is kept and becomes the top layer. It is not closed and replaced.
- Layers 4 and 6 need only `main` and layer 4 respectively, but are still stacked in a line. That gives every branch a single parent, so no base is a merge of two branches.
