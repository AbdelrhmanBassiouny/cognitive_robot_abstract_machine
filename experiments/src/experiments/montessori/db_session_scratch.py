"""
Scratch: open a SQLAlchemy session against the Montessori sorting-results database for
ad hoc querying, without pulling in the simulation stack (mujoco, rclpy, ...) that
importing franka_montessori_demo would.

Run with ``python -i db_session_scratch.py`` to drop into a REPL with ``session`` and
``ormatic_interface`` (holding every DAO class, e.g. ``ShapeInsertionResultDAO``,
``InsertMontessoriShapeActionDAO``) already bound, or just edit the query below and run
it directly.

Points at the same default database (and env var override) as
franka_montessori_demo.py's own --database-uri; see its DEFAULT_DATABASE_URI.
"""

import os

from sqlalchemy import select

import experiments.orm.ormatic_interface as ormatic_interface
from krrood.ormatic.utils import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URI = "sqlite:////tmp/claude-1000/-home-sony-workspace-cognitive-robot-abstract-machine-experiments-src-experiments-montessori/a265e19c-bbf7-4d7e-81ab-0c7879559d20/scratchpad/franka_montessori_2_iterations.db"
#"/tmp/claude-1000/-home-sony-workspace-cognitive-robot-abstract-machine-experiments-src-experiments-montessori/cc5baf39-2a05-4cf1-9872-0d1fea6f34fb/scratchpad/"

engine = create_engine(DATABASE_URI)
ormatic_interface.Base.metadata.create_all(engine)
session = sessionmaker(engine)()

if __name__ == "__main__":
    #iteration_count = session.scalars(select(ormatic_interface.InsertMontessoriShapeActionDAO).limit(10)).all()
    #print(*iteration_count, sep="\n")

    result = session.scalars(
        select(ormatic_interface.ActionNodeDAO).join(ormatic_interface.InsertMontessoriShapeActionDAO, ormatic_interface.ActionNodeDAO.designator)
    ).all()
    print(*result, sep="\n")

# Statt SQLLite PostgressQL in semDT scripts gibts ein script dass die db anlegt.