## Plan
- State objects, default domains through TermReader.instances_of, expression domains as FlatVariable / InstanceFilteredFlatVariable; removed objects filtered from list/tuple/set values
- Resolve the conflict with main (#535 landed): adopt value_of_term/TermValue and EvaluationContext.current_term_reader

## Done
- First review addressed in fa1dc1af6e; 7 of 8 threads resolved
- Conflicts resolved locally in variable.py, evaluation_context.py, ground_term.py, state.py

## Next
- Run krrood tests, commit the merge, push, run maintenance restack
- Check whether correlated-quantifiers (now on main) lets the binding test use match syntax and close the last thread
- Owner: fold the filtering rule into the roadmap (12-entry limit)
