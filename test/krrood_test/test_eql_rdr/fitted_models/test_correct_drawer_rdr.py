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
from test.krrood_test.test_eql_rdr.test_correct_drawer import RDRTestCorrectDrawer

rDRTestCorrectDrawer = variable(RDRTestCorrectDrawer, domain=[])
query = entity(rDRTestCorrectDrawer).where(rDRTestCorrectDrawer.handle.name == 'left_handle')
with query:
    add(rDRTestCorrectDrawer.correct, True)
    with alternative(rDRTestCorrectDrawer.handle.name != 'left_handle'):
        add(rDRTestCorrectDrawer.correct, False)
    with refinement(rDRTestCorrectDrawer.container.name == 'top_drawer'):
        add(rDRTestCorrectDrawer.correct, False)
query.build()

# Stable handles for loading.
RDR_CASE_TYPE = RDRTestCorrectDrawer
RDR_CONCLUSION_ATTRIBUTE = "correct"
RDR_CASE_VARIABLE = rDRTestCorrectDrawer
RDR_QUERY = query