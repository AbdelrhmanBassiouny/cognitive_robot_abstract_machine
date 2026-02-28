from ..dataset.university_ontology_like_classes_without_descriptors import (
    Person,
    CEOAsFirstRole,
    Company,
)


def test_getting_and_setting_attribute_for_role_and_role_taker():
    person = Person(name="Bass")
    ceo = CEOAsFirstRole(person)
    ceo.head_of = Company(name="BassCo")

    assert ceo.person.name == person.name

    # access attribute of role-taker (Person) directly from a role (CEO)
    assert ceo.name == person.name

    # access attribute of a role (CEO) directly from a role-taker (Person)
    assert ceo.head_of is person.head_of
    assert ceo.person.head_of is ceo.head_of
