Resolve of Nov 4: the stall was a merge conflict with `main` (bee57056c2) in the imports of `krrood/src/krrood/patterns/factory_and_kwargs.py`: `main` replaced `list_like_classes` with `CollectionKind`, this branch adds `get_type_hints_of_object`. Merged `main` into the branch (9bd5951e46), keeping both imports; merge probe afterwards: clean.

Read on 9b073d07f3: 18/18 fork checks passed. Not read on 9bd5951e46: its CI was still running. Upstream cram2/cognitive_robot_abstract_machine#862: two approvals, 29/29 checks, no unresolved threads. Three fork threads stay open for the owner, the "why not `_type_`" questions on `plan_transformations.py:334`, `task_conditions.py:477` and `planner.py:118`.

No tests were run locally: the scratch environment cannot install pyjpt. Nothing is stacked on this branch.
