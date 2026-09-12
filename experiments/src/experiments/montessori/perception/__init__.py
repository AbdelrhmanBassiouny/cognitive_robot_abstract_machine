"""
Continuous perception of the Montessori shape-sorting scene from a registered RGB-D
camera: where every loose shape lies on the table, and where every hole sits on the
board.

The detectors work on a metric, top-down rectification of the colour image rather than
on the raw camera view, so a footprint's measured size and orientation are in metres and
radians of the world frame directly (see
:mod:`~experiments.montessori.perception.orthophoto`). Results are answered as an
:mod:`entity query language <krrood.entity_query_language>` domain, so asking for a pose
is what triggers perception (see
:mod:`~experiments.montessori.perception.scene_source`).
"""
