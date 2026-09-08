"""
The branch the reproductions in this dataset are recorded against.

Defined once here rather than in each reproduction and again in the tests that run them:
which branch a reproduction names is what its marker carries, so a second copy would let
the assertion agree with itself while the marker said something else.
"""

BREAKING_BRANCH = "removes-the-module"
"""
The branch whose break these reproductions reproduce.
"""
