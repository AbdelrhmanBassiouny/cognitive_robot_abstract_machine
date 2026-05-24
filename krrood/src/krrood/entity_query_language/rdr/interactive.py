"""
Interactive :class:`ExpertInterface` backed by an embedded IPython shell.

The expert is shown a coloured instruction header and the case rendered as a table, then
authors a **live EQL condition expression** over ``case_variable`` and assigns it to
``conditions`` (and a ``conclusion`` when no ground-truth target is known). On exit the
elicitation loop validates the assignment; an invalid or missing answer re-opens the shell
with an error message, while ``abort()`` cancels the session.

The actual shell launch is injectable (``shell_runner``) so tests can play the expert's
part without a real terminal.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Any, Callable, Dict, List, Optional

from colorama import Fore, Style

from krrood.entity_query_language.rdr.case_table import render_case_table
from krrood.entity_query_language.rdr.interface import (
    ABORT_NAME,
    CASE_INSTANCE_NAME,
    CASE_VARIABLE_NAME,
    AnswerRequest,
    CaseContext,
    ExpertInterface,
)

#: A shell runner takes ``(namespace, header)`` and must leave the expert's assignments
#: (and any ``abort()`` flag) visible in ``namespace`` when it returns.
ShellRunner = Callable[[Dict[str, Any], str], None]


@dataclass
class IPythonInterface(ExpertInterface):
    """Elicits a rule's answers through an embedded IPython shell."""

    shell_runner: Optional[ShellRunner] = None
    """Injectable launcher; defaults to a real embedded IPython shell. Tests pass a stub."""

    def _render_header(
        self,
        context: CaseContext,
        requests: List[AnswerRequest],
        errors: Dict[str, str],
    ) -> str:
        parts: List[str] = []
        for name, message in errors.items():
            parts.append(f"{Fore.RED}[error] {name}: {message}{Style.RESET_ALL}")
        parts.append(
            f"{Fore.CYAN}{Style.BRIGHT}EQL RDR — author a rule for this case."
            f"{Style.RESET_ALL}"
        )
        parts.append(
            f"{Fore.MAGENTA}current conclusion: {Style.RESET_ALL}"
            f"{Fore.WHITE}{context.current_conclusion!r}{Style.RESET_ALL}"
        )
        if context.has_target:
            parts.append(
                f"{Fore.MAGENTA}target conclusion:  {Style.RESET_ALL}"
                f"{Fore.GREEN}{context.target_conclusion!r}{Style.RESET_ALL}"
            )
        parts.append(
            f"{Fore.MAGENTA}case `{CASE_INSTANCE_NAME}` "
            f"(concrete — inspect & experiment):{Style.RESET_ALL}"
        )
        parts.append(render_case_table(context.case_instance))
        parts.append(
            f"{Fore.YELLOW}Build your answer(s) over `{CASE_VARIABLE_NAME}` "
            f"(the EQL variable), e.g.:{Style.RESET_ALL}"
        )
        for request in requests:
            parts.append(f"  {Fore.GREEN}{request.example}{Style.RESET_ALL}")
        parts.append(
            f"{Fore.YELLOW}Then exit the shell (Ctrl-D). "
            f"Call {Fore.CYAN}{ABORT_NAME}(){Fore.YELLOW} to cancel.{Style.RESET_ALL}"
        )
        return "\n".join(parts)

    def _run(self, namespace: Dict[str, Any], header: str) -> None:
        runner = self.shell_runner or self._default_run_shell
        runner(namespace, header)

    @staticmethod
    def _default_run_shell(namespace: Dict[str, Any], header: str) -> None:
        from IPython.terminal.embed import InteractiveShellEmbed

        shell = InteractiveShellEmbed(banner1=header, user_ns=namespace)
        shell.auto_match = True
        # The shell shares ``namespace``, so the expert's assignments are already visible
        # to the caller when it returns.
        shell()
