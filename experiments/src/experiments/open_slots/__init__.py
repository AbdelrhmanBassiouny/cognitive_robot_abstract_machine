"""
Who answers each open slot of a plan.

A plan says what it wants -- the piece to pick up, how to hold it, the hole to put it
through -- and leaves who is to supply it open. Each module here holds one of the
backends that can supply such a slot for the Montessori scene, and :mod:`choice`
assembles them into the
:class:`~krrood.entity_query_language.backends.BackendChoice` a plan is run with.
"""
