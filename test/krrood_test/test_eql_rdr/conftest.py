"""Shared fixtures for the EQL-RDR tests.

.. note:: The autouse fixture that skips tests needing a real interactive shell
    (``skip_tests_needing_a_real_user``) is reintroduced once
    :mod:`krrood.entity_query_language.rdr.interactive` lands with the D-ui split slice;
    none of the tests present in this slice reach the real shell.
"""

from __future__ import annotations
