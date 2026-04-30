from krrood.class_diagrams.class_diagram import ClassDiagram
from krrood.class_diagrams.utils import classes_of_module
from pycram import exceptions

# from pycram.robot_plans.actions.base import ActionDescription


def test_parsing_exceptions_file():
    classes = classes_of_module(exceptions)
    class_diagram = ClassDiagram(list(classes))
    condition_exception = class_diagram.get_wrapped_class(
        exceptions.ConditionNotSatisfied
    )
    found_type = [wf for wf in condition_exception.fields if wf.name == "action"][
        0
    ].type_endpoint
    assert found_type.__name__ == "ActionDescription"
    assert found_type.__module__ == "pycram.robot_plans.actions.base"
    assert any(base.__name__ == "Designator" for base in found_type.__bases__)
