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

testCorrectDrawer = variable(RDRTestCorrectDrawer, domain=[])
query = entity(testCorrectDrawer).where(testCorrectDrawer.handle.name == 'left_handle')
with query:
    add(testCorrectDrawer.correct, True)
    with alternative(testCorrectDrawer.handle.name != 'left_handle'):
        add(testCorrectDrawer.correct, False)
    with refinement(testCorrectDrawer.container.name != 'bottom_drawer'):
        add(testCorrectDrawer.correct, False)
query.build()

# Stable handles for loading.
RDR_CASE_TYPE = RDRTestCorrectDrawer
RDR_CONCLUSION_ATTRIBUTE = "correct"
RDR_CASE_VARIABLE = testCorrectDrawer
RDR_QUERY = query