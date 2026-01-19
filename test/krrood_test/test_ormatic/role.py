from ..dataset.example_classes import Torso
from krrood.ormatic.dao import to_dao

from ..dataset.university_ontology_like_classes import (
    PersonOnto,
    CEO,
    Employee,
    CompanyWithEmployees,
    Company,
)
from ..dataset.ormatic_interface import *


def test_role_persistence(session, database):
    person2 = PersonOnto(name="p2")
    employee = Employee(person2)
    company = Company(name="c1")

    company.members.add(employee)

    dao = to_dao(company)
    session.add(dao)
    session.commit()


def test_role_persistence_one_to_one(session, database):
    person2 = PersonOnto(name="p2")
    employee = Employee(person2)
    ceo = CEO(employee)

    dao = to_dao(ceo)
    session.add(dao)
    session.commit()
