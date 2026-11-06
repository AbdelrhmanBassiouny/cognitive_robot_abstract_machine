Follow-up to cram2#888 (tomsch420:better-exceptions); answers Abdelrhman's two open review threads there.

Plan
- Descriptor installed after the class, shared base with PropertyDescriptor, DataclassFieldDescriptorOwner keeps it on redeclaration/narrowing, ormatic allocation in field order.

Done
- 98f5d6cf4 pushed; all krrood test dirs pass except env-only (mypy, graphviz dot missing; same on 502cce962).

Next
- User opens the draft PR into tomsch420:better-exceptions via the compare link (session cannot attach tomsch420's fork: same repo name as the fork); description in the session scratchpad.
- Reply on the two cram2#888 threads once the PR exists, if the user allows commenting upstream.
