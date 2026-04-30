import sys

from krrood.class_diagrams import ClassDiagram
from krrood.class_diagrams.class_diagram import WrappedSpecializedGeneric
from krrood.patterns.role import Role
from krrood.patterns.role.role_transformer import RoleTransformer


def transform_roles_in_class_diagram(class_diagram: ClassDiagram) -> None:
    """
    Transform role classes that are in the given class diagram.

    :param class_diagram: Class diagram to transform.
    """
    modules_with_roles = []
    for wrapped_class in class_diagram.wrapped_classes:
        if (
            not isinstance(wrapped_class, WrappedSpecializedGeneric)
            and Role in wrapped_class.clazz.__bases__
        ):
            new_module = sys.modules[wrapped_class.clazz.__module__]
            if new_module not in modules_with_roles:
                modules_with_roles.append(new_module)
    for module in modules_with_roles:
        transformer = RoleTransformer(module)
        transformer.transform(write=True)
