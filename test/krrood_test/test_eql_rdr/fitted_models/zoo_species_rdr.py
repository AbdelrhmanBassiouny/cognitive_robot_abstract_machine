"""Auto-generated EQL-RDR rule tree. Do not edit by hand."""
from krrood.entity_query_language.factories import (
    variable,
    entity,
    add,
    refinement,
    alternative,
    next_rule,
    and_,
    or_,
    not_,
)
from test.krrood_test.test_eql_rdr.animal import Animal, Species

animal = variable(Animal, domain=[])
query = entity(animal).where(animal.eggs == False)
with query:
    add(animal.species, Species.mammal)
    with alternative(and_(animal.aquative == True, animal.fins == True)):
        add(animal.species, Species.fish)
    with alternative(and_(animal.aquatic, animal.fins)):
        add(animal.species, Species.fish)
    with alternative(and_(animal.feathers, animal.eggs)):
        add(animal.species, Species.bird)
    with alternative(and_(animal.aquatic, not_(animal.fins))):
        add(animal.species, Species.molusc)
        with refinement(animal.legs > 0):
            add(animal.species, Species.amphibian)
            with refinement(animal.legs > 0):
                add(animal.species, Species.molusc)
                with refinement(animal.toothed):
                    add(animal.species, Species.amphibian)
                with refinement(animal.milk):
                    add(animal.species, Species.mammal)
    with alternative(and_(not_(animal.aquatic), not_(animal.backbone))):
        add(animal.species, Species.insect)
        with refinement(not_(animal.backbone)):
            add(animal.species, Species.molusc)
            with refinement(animal.legs > 0):
                add(animal.species, Species.insect)
    with alternative(animal.eggs):
        add(animal.species, Species.reptile)
    with refinement(not_(animal.milk)):
        add(animal.species, Species.molusc)
        with refinement(animal.venomous):
            add(animal.species, Species.reptile)
            with refinement(not_(animal.backbone)):
                add(animal.species, Species.molusc)
query.build()

# Stable handles for loading.
RDR_CASE_TYPE = Animal
RDR_CONCLUSION_ATTRIBUTE = "species"
RDR_CASE_VARIABLE = animal
RDR_QUERY = query