"""
Interactive :class:`ExpertInterface` backed by an embedded IPython shell.

The expert is shown the case rendered as a table with the instructions printed *below* it
(nearest the prompt), then authors a **live EQL condition expression** over ``case_variable``
and assigns it to ``conditions`` (and a ``conclusion`` when no ground-truth target is known).

Pressing Ctrl-D *submits*: the assignment is validated and, if it is invalid or missing, the
error is printed inline and the **same shell stays open** rather than bailing out. Calling
``exit()`` (or ``quit()``) cancels the session unconditionally, raising
:class:`~krrood.entity_query_language.rdr.interface.ExpertAbort`.

The actual shell launch is injectable (``shell_runner``) so tests can play the expert's
part without a real terminal.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Any, Callable, Dict, List, Optional

from colorama import Fore, Style

from krrood.entity_query_language.rdr.case_table import (
    DEFAULT_COLUMNS,
    render_case_table,
)
from krrood.entity_query_language.rdr.interface import (
    CASE_INSTANCE_NAME,
    CASE_VARIABLE_NAME,
    EXIT_NAME,
    _ABORT_FLAG,
    AnswerRequest,
    CaseContext,
    ExpertInterface,
)
from krrood.entity_query_language.rdr.rule_tree_view import render_rule_tree, format_condition

#: A shell runner takes ``(namespace, header)`` and must leave the expert's assignments
#: (and any ``exit()`` flag) visible in ``namespace`` when it returns.
ShellRunner = Callable[[Dict[str, Any], str], None]

#: The IPython line magic the expert types to redisplay the rule tree.
SHOW_TREE_MAGIC = "show_tree"

#: Private namespace key holding the zero-arg rule-tree renderer for the ``%show_tree`` magic.
_TREE_RENDER_KEY = "__rule_tree_render__"


@dataclass
class IPythonInterface(ExpertInterface):
    """Elicits a rule's answers through an embedded IPython shell."""

    shell_runner: Optional[ShellRunner] = None
    """Injectable launcher; defaults to a real embedded IPython shell. Tests pass a stub."""

    case_table_columns: int = DEFAULT_COLUMNS
    """Number of ``(attribute, value)`` pairs the case table lays out per row."""

    def _render_header(
        self,
        context: CaseContext,
        requests: List[AnswerRequest],
        errors: Dict[str, str],
    ) -> str:
        parts: List[str] = [
            "", render_case_table(context.case_instance, self.case_table_columns), ""
        ]
        parts.extend(self._conclusion_framing(context))
        error_block = self._format_errors(errors)
        if error_block:
            parts.append(error_block)
        parts.append("")
        return "\n".join(parts)

    def _help_inspect_case(self) -> str:
        """
        :return: The help text for inspecting the concrete case.
        """
        return (
            f"{Fore.MAGENTA}Inspect the concrete case with "
            f"`{CASE_INSTANCE_NAME}` (e.g. {CASE_INSTANCE_NAME}.some_attr).{Style.RESET_ALL}"
        )

    def _help_build_answer(self, requests: List[AnswerRequest]) -> str:
        """
        :param requests: The answer requests for which to provide help.
        :return: The help text for building answers.
        """
        parts: List[str] = []
        parts.append(
            f"{Fore.YELLOW}Build your answer(s) over `{CASE_VARIABLE_NAME}` "
            f"(the EQL variable), e.g.:{Style.RESET_ALL}"
        )
        for request in requests:
            parts.append(f"  {Fore.GREEN}{request.example}{Style.RESET_ALL}")
        return '\n'.join(parts)

    def _help_submit_cancel(self) -> str:
        """
        :return: The help text for submitting or canceling the answer.
        """
        return (
            f"{Fore.YELLOW}Press Ctrl-D to submit. "
            f"Call {Fore.CYAN}{EXIT_NAME}(){Fore.YELLOW} to cancel.{Style.RESET_ALL}"
        )

    def _render_tree(self, context: CaseContext) -> Optional[str]:
        """:return: The coloured rule-tree text for this case, or ``None`` if unavailable."""
        trace = context.trace
        if trace is None or trace.rule_tree_root is None:
            return None
        return render_rule_tree(trace)

    def _tree_block(self, context: CaseContext) -> List[str]:
        """The rule-tree visualization, shown above the instructions when a rule fired."""
        if context.current_conclusion is None:
            return []
        tree = self._render_tree(context)
        if not tree:
            return []
        return [
            f"{Fore.CYAN}Current rule tree "
            f"({Fore.GREEN}fired{Fore.CYAN} / {Fore.RED}evaluated{Fore.CYAN} / "
            f"{Fore.LIGHTBLACK_EX}skipped{Fore.CYAN}):{Style.RESET_ALL}",
            tree,
        ]

    def _conclusion_framing(self, context: CaseContext) -> List[str]:
        """Instruction lines that state the (wrong) conclusion and what to do about it."""
        lines: List[str] = []
        current_color = Fore.WHITE
        condition_repr = f"{Fore.CYAN}{Style.BRIGHT}condition{Style.NORMAL}{Fore.MAGENTA}"
        if context.has_target:
            lines.append(
                f"{Fore.MAGENTA}Ground-truth conclusion: "
                f"{Fore.GREEN}{context.target_conclusion!r}{Style.RESET_ALL}")
            current_color = Fore.GREEN if context.current_conclusion == context.target_conclusion else Fore.RED
        lines.append(
            f"{Fore.MAGENTA}Current conclusion: "
            f"{current_color}{context.current_conclusion!r}{Style.RESET_ALL}"
        )
        if context.current_conclusion is None:
            lines.append(
                f"{Fore.MAGENTA}No rule fired for this case.{Style.RESET_ALL}"
            )
            if context.has_target:
                lines.append(
                    f"{Fore.MAGENTA}Write a {condition_repr} that fires for it. {Style.RESET_ALL}"
                )
        elif context.has_target and context.current_conclusion != context.target_conclusion:
            if context.trace is not None:
                lines.append(f"{Fore.MAGENTA}Apparently, the condition {Fore.CYAN}{format_condition(context.trace.firing_anchor)}{Fore.MAGENTA} "
                             f"satisfies both {Fore.GREEN}{context.target_conclusion!r}{Fore.MAGENTA} and {Fore.RED}{Style.BRIGHT}{context.current_conclusion!r}{Style.RESET_ALL}.")
            lines.append(
                f"{Fore.MAGENTA}Write a {condition_repr} that satisfies "
                f"{Fore.GREEN}{context.target_conclusion!r}{Fore.MAGENTA} "
                f"and does not satisfy {Fore.RED}{Style.BRIGHT}{context.current_conclusion!r}{Style.RESET_ALL}"
            )
        if self._render_tree(context):
            lines.append(self._help_show_tree())
        return lines

    def _help_show_tree(self) -> str:
        """:return: The help text for the ``%show_tree`` magic."""
        return (
            f"{Fore.YELLOW}Type {Fore.CYAN}%{SHOW_TREE_MAGIC}{Fore.YELLOW} to "
            f"display the current rule tree state.{Style.RESET_ALL}"
        )

    def _build_namespace(
        self, context: CaseContext, requests: List[AnswerRequest]
    ) -> Dict[str, Any]:
        namespace = super()._build_namespace(context, requests)
        namespace[_TREE_RENDER_KEY] = lambda: self._render_tree(context)
        return namespace

    @staticmethod
    def _format_errors(errors: Dict[str, str]) -> str:
        """:return: A red, one-line-per-error block, or ``""`` when there are no errors."""
        return "\n".join(
            f"{Fore.RED}[error] {name}: {message}{Style.RESET_ALL}"
            for name, message in errors.items()
        )

    def _run(
        self,
        namespace: Dict[str, Any],
        header: str,
        validate: Callable[[], Dict[str, str]],
    ) -> None:
        if self.shell_runner is not None:
            self.shell_runner(namespace, header)
        else:
            self._default_run_shell(namespace, header, validate)

    def _default_run_shell(
        self,
        namespace: Dict[str, Any],
        header: str,
        validate: Callable[[], Dict[str, str]],
    ) -> None:
        from IPython.terminal.embed import InteractiveShellEmbed

        class _ValidatingEmbeddedShell(InteractiveShellEmbed):
            """Vetoes a Ctrl-D exit while the answer is invalid; ``exit()`` forces the leave."""

            def ask_exit(self) -> None:
                if getattr(self, "_force_exit", False):
                    super().ask_exit()
                    return
                errors = validate()
                if errors:
                    print(IPythonInterface._format_errors(errors))
                    return
                super().ask_exit()

        shell = _ValidatingEmbeddedShell(banner1=header, user_ns=namespace)
        shell.auto_match = True
        shell.confirm_exit = False
        shell._force_exit = False

        self._register_show_tree_magic(shell, namespace)

        def _cancel() -> None:
            shell._force_exit = True
            namespace[_ABORT_FLAG] = True
            shell.ask_exit()

        namespace[EXIT_NAME] = _cancel
        namespace["quit"] = _cancel
        # The shell shares ``namespace``, so the expert's assignments are already visible
        # to the caller when it returns.
        shell()

    @staticmethod
    def _register_show_tree_magic(shell: Any, namespace: Dict[str, Any]) -> None:
        """Register ``%show_tree`` so the expert can redisplay the rule tree on demand."""
        render = namespace.get(_TREE_RENDER_KEY)
        if render is None:
            return

        def show_tree(line: str) -> None:
            text = render()
            print(text if text else f"{Fore.LIGHTBLACK_EX}(no rule tree){Style.RESET_ALL}")

        shell.register_magic_function(
            show_tree, magic_kind="line", magic_name=SHOW_TREE_MAGIC
        )
