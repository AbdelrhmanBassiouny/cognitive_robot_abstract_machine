# knowledge-directed-requests — standing rules

- Unmerged is not unusable: an item stacks on the open, reviewed EQL rule-tree stack (#159 -> #210 -> #79 -> #76 -> #80 -> #77) directly rather than waiting for it to land. Only the classic krrood.ripple_down_rules machinery is genuinely unusable.
- State every cost comparison as a ratio to a baseline measured in the same run (e.g. "1.08x the parent"), never as bare seconds: the container's speed varies between runs by more than the differences measured.
- A direction relation (left of, above) is read from where the camera stands, via RgbdFrame.point_of_view, not from the world's axes.
- A relation asserted about the thing sought is an ordinary EQL Match over the relation's own class, not a Match subclass (the developer reversed StatedRelation); value comparison is stated explicitly at the call sites that need it.
