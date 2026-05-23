"""
Interactive expert backed by an embedded IPython shell.

When the RDR needs a new rule it opens a shell whose namespace is the scope captured
where the RDR was created (see :mod:`krrood.entity_query_language.scope`) plus the EQL
factories and the shared case variable. The expert writes a **live EQL condition
expression** and assigns it to ``conditions``; on exit that object is returned as-is —
never a string.
"""

from __future__ import annotations

from typing_extensions import Any, Callable, Dict, Optional

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.core.mapped_variable import CanBehaveLikeAVariable
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.scope import get_definition_scope

#: The variable name the expert assigns their condition expression to.
ANSWER_NAME = "conditions"

#: A shell runner takes (namespace, header) and is expected to populate
#: ``namespace[ANSWER_NAME]`` with the expert's live EQL condition expression.
ShellRunner = Callable[[Dict[str, Any], str], None]


class NoConditionsProvided(Exception):
    """Raised when the interactive session ended without assigning ``conditions``."""


class IPythonExpert(Expert):
    """An :class:`Expert` that prompts a human through an embedded IPython shell."""

    def __init__(self, shell_runner: Optional[ShellRunner] = None) -> None:
        """
        :param shell_runner: Injectable launcher (namespace, header) -> None that must
            set ``namespace["conditions"]``. Defaults to a real embedded IPython shell;
            tests pass a stub that simulates the expert.
        """
        self._run_shell = shell_runner or self._default_run_shell

    def _variable_name(self, case_variable: CanBehaveLikeAVariable) -> str:
        type_ = case_variable._type_
        name = type_.__name__ if type_ is not None else "case"
        return name[0].lower() + name[1:]

    def _build_namespace(
        self, case: Any, case_variable: CanBehaveLikeAVariable
    ) -> Dict[str, Any]:
        namespace = get_definition_scope(case_variable)
        namespace[self._variable_name(case_variable)] = case_variable
        namespace["case"] = case
        namespace[ANSWER_NAME] = None
        return namespace

    def _build_header(
        self,
        case: Any,
        current_conclusion: Optional[Any],
        target_conclusion: Any,
        variable_name: str,
    ) -> str:
        return (
            "EQL RDR — provide rule conditions.\n"
            f"  case:    {case!r}\n"
            f"  current: {current_conclusion!r}\n"
            f"  target:  {target_conclusion!r}\n"
            f"Write an EQL condition over `{variable_name}` and assign it to "
            f"`{ANSWER_NAME}`,\n"
            f"e.g.  {ANSWER_NAME} = {variable_name}.some_attr == True\n"
            "then exit the shell."
        )

    def ask_for_conditions(
        self,
        case: Any,
        current_conclusion: Optional[Any],
        target_conclusion: Any,
        case_variable: CanBehaveLikeAVariable,
    ) -> SymbolicExpression:
        namespace = self._build_namespace(case, case_variable)
        header = self._build_header(
            case,
            current_conclusion,
            target_conclusion,
            self._variable_name(case_variable),
        )
        self._run_shell(namespace, header)
        conditions = namespace.get(ANSWER_NAME)
        if conditions is None:
            raise NoConditionsProvided(
                "The interactive session did not assign a `conditions` expression."
            )
        return conditions

    @staticmethod
    def _default_run_shell(namespace: Dict[str, Any], header: str) -> None:
        from IPython.terminal.embed import InteractiveShellEmbed

        shell = InteractiveShellEmbed(banner1=header, user_ns=namespace)
        shell()
        # The shell shares ``namespace`` as its user namespace, so the expert's
        # ``conditions = ...`` assignment is already visible to the caller.
