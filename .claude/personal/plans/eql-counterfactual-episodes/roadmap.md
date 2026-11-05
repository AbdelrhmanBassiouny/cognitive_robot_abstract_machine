# Counterfactual EQL queries over stored episodes: roadmap

- A counterfactual is a State of facts over the objects of a stored moment; it never writes back to the database or changes live objects.
- A ground term's owner is compared by identity, never by value; across reloads, identity is the object's persistent identity where it has one.
- A backend that cannot honour a state raises BackendCannotReadState; it reads a state only once tests show its answers equal the EQL backend's on the same objects.
- A derived ground term follows a state only through EQL, as in eql-planning: an EQL body, or inputs passed as EQL arguments.
