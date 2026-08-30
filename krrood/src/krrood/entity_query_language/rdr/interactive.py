"""
Interactive :class:`ExpertInterface` backed by an embedded IPython shell.

The expert is shown the case rendered as a table with the instructions printed *below* it
(nearest the prompt), then authors a **live EQL condition expression** over ``case_variable``
and assigns it to ``conditions`` (and a ``conclusion`` when no ground-truth target is known).

Pressing Ctrl-D *submits*: the assignment is validated and, if it is invalid or missing, the
error is printed inline and the **same shell stays open** rather than bailing out. Calling
``exit()`` (or ``quit()``) cancels the session unconditionally, raising
:class:`~krrood.entity_query_language.rdr.interface.ExpertAbort`.

All on-screen text is composed as plain prose and coloured through a single
:class:`Palette`, and the header is assembled from small section builders so styling lives
in one place. The line magics of
:mod:`~krrood.entity_query_language.rdr.magics` keep the standing header short while
staying discoverable.

The actual shell launch is injectable (``shell_runner``) so tests can play the expert's
part without a real terminal.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from colorama import Fore, Style
from IPython.terminal.embed import InteractiveShellEmbed

from krrood.exceptions import DataclassException
from krrood.entity_query_language.rdr.answer_vocabulary import (
    AnswerName,
    NamespaceName,
)
from krrood.entity_query_language.rdr.case_table import (
    DEFAULT_MIN_COLUMN_WIDTH,
    render_case_table,
    render_cases_side_by_side,
)
from krrood.entity_query_language.rdr.interface import (
    AnswerRequest,
    CaseContext,
    ExpertInterface,
)
from krrood.entity_query_language.rdr.magics import (
    ANSWER_MAGIC_NAMES,
    AssignAndExitMagic,
    HelpMagic,
    HelperMagic,
    Magic,
    MagicName,
    NamespaceKey,
    RuleTreeMagic,
    SaveModelMagic,
    SufficientConditionsMagic,
)
from krrood.entity_query_language.rdr.progress import (
    IPythonProgressBar,
    NullProgressReporter,
)
from krrood.entity_query_language.rdr.prompt_sections import (
    PROMPT_SECTIONS,
    RenderContext,
    supporting_material_presenters,
)
from krrood.entity_query_language.rdr.rule_tree_view import render_rule_tree

if TYPE_CHECKING:
    from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR

#: A shell runner takes ``(namespace, header)`` and must leave the expert's assignments
#: (and any ``exit()`` flag) visible in ``namespace`` when it returns.
ShellRunner = Callable[[Dict[str, Any], str], None]

#: ANSI escape sequence: erase display and return cursor to top-left.
#: Emitted before each new embedded shell so each case starts on a clean screen.
CLEAR_SCREEN = "\033[2J\033[H"


@dataclass
class Palette:
    """
    Maps semantic roles to ANSI styling behind a single ``use_color`` switch.

    Keeps colour out of the message text: callers write plain prose and wrap each fragment
    in the role that fits it, so one line can mix roles without leaking or losing codes.
    """

    use_color: bool = True
    """
    Whether the roles emit ANSI colour or plain text.
    """

    def _paint(self, text: str, *codes: str) -> str:
        """
        :param text: The text to style.
        :param codes: The ANSI codes to wrap it in.
        :return: ``text`` wrapped in ``codes`` and reset, or unchanged without colour.
        """
        if not self.use_color:
            return text
        return f"{''.join(codes)}{text}{Style.RESET_ALL}"

    def label(self, text: str) -> str:
        """
        Ordinary instruction prose.
        """
        return self._paint(text, Fore.MAGENTA)

    def good(self, text: str) -> str:
        """
        A correct / target value.
        """
        return self._paint(text, Fore.GREEN)

    def wrong(self, text: str) -> str:
        """
        A value that is currently wrong (no emphasis).
        """
        return self._paint(text, Fore.RED)

    def strong_wrong(self, text: str) -> str:
        """
        A wrong value the expert must steer away from (emphasised).
        """
        return self._paint(text, Fore.RED, Style.BRIGHT)

    def neutral(self, text: str) -> str:
        """
        A value with no good/bad judgement attached.
        """
        return self._paint(text, Fore.WHITE)

    def code(self, text: str) -> str:
        """
        A name or expression the expert can type.
        """
        return self._paint(text, Fore.CYAN)

    def keyword(self, text: str) -> str:
        """
        An emphasised term within prose (e.g. the word ``condition``).
        """
        return self._paint(text, Fore.CYAN, Style.BRIGHT)

    def hint(self, text: str) -> str:
        """
        A low-key pointer to a command.
        """
        return self._paint(text, Fore.YELLOW)

    def suggestion(self, text: str) -> str:
        """
        A suggested condition offered by the resolver.
        """
        return self._paint(text, Fore.BLUE, Style.BRIGHT)

    def error(self, text: str) -> str:
        """
        A validation error.
        """
        return self._paint(text, Fore.RED)

    def absent(self, text: str) -> str:
        """
        A stand-in for content there is none of.
        """
        return self._paint(text, Fore.LIGHTBLACK_EX)


class ValidatingEmbeddedShell(InteractiveShellEmbed):
    """
    An embedded IPython shell that vetoes a Ctrl-D exit while an answer is still
    invalid; ``exit()`` forces the leave.

    The collaborators below are assigned after construction because the base class takes
    only its own traits as constructor arguments.
    """

    validate: Callable[[], List[DataclassException]]
    """
    Re-runs the request validators and returns their failures.
    """

    format_errors: Callable[[List[DataclassException]], str]
    """
    Renders the failures for the expert to read.
    """

    _force_exit: bool = False
    """
    Whether ``exit()`` has demanded the shell leave regardless of the answers.
    """

    def ask_exit(self) -> None:
        """
        Leave only once every answer validates, or when ``exit()`` forced it.
        """
        if self._force_exit:
            super().ask_exit()
            return
        errors = self.validate()
        if errors:
            print(self.format_errors(errors))
            return
        super().ask_exit()


@dataclass
class IPythonInterface(ExpertInterface):
    """
    An :class:`~krrood.entity_query_language.rdr.interface.ExpertInterface` backed by an
    embedded IPython shell.

    Assembles a namespace from the case definition scope, renders a colour-coded header
    via :data:`~krrood.entity_query_language.rdr.prompt_sections.PROMPT_SECTIONS`, and
    drives the validate-re-prompt loop.  The actual shell launch is injectable via
    :attr:`shell_runner` so tests can run without a real terminal.
    """

    shell_runner: Optional[ShellRunner] = None
    """
    Injectable launcher; defaults to a real embedded IPython shell.

    Tests pass a stub.
    """

    min_column_width: int = DEFAULT_MIN_COLUMN_WIDTH
    """
    Smallest width a case-table pair column may take; sets how many fit per row.
    """

    use_color: bool = True
    """
    Whether the header, framing and magics emit ANSI colour.
    """

    rdr: Optional["EQLSingleClassRDR"] = None
    """
    The
    :class:`~krrood.entity_query_language.rdr.single_class.EQLSingleClassRDR`
    being fit, exposed for the ``%sufficient_conditions_for`` backward-inference magic.

    ``None`` when the interface is used without an RDR (no magic is
    registered).
    """

    _helper_cache: Optional[str] = field(init=False, default=None)
    """
    Memoized helper ``present()`` output for the current ``interact()`` call (set once
    per question in :meth:`_build_namespace`, reused by the header and the ``%helper``
    magic).
    """

    _interact_count: int = field(init=False, default=0)
    """
    Number of :meth:`interact` calls so far; used to show the help hint only once.
    """

    @property
    def palette(self) -> Palette:
        """
        The styling used for every piece of on-screen text.
        """
        return Palette(self.use_color)

    def interact(
        self,
        context: CaseContext,
        requests: List[AnswerRequest],
        initial_errors: Optional[List[DataclassException]] = None,
    ) -> Dict[AnswerName, Any]:
        """
        Count the interaction, so one-time hints show only on the first prompt.

        :param context: The case being labelled.
        :param requests: The answers the expert must supply.
        :param initial_errors: Errors to show on the first render.
        :return: ``{request.name: value}`` for every request, all validated.
        """
        self._interact_count += 1
        return super().interact(context, requests, initial_errors=initial_errors)

    def __post_init__(self) -> None:
        """
        Draw fitting progress into this shell, unless the RDR was given a reporter of
        its own.

        The engine defaults to
        :class:`~krrood.entity_query_language.rdr.progress.NullProgressReporter`, the
        only default correct for a caller it knows nothing about. This layer is the one
        that knows there is a shell to draw on, so an RDR attached here gets a bar
        matching the shell's colour instead.
        """
        if self.rdr is None:
            return
        if isinstance(self.rdr.progress_reporter, NullProgressReporter):
            self.rdr.progress_reporter = IPythonProgressBar(use_color=self.use_color)

    # %% header

    def _render_header(
        self,
        context: CaseContext,
        requests: List[AnswerRequest],
        errors: List[DataclassException],
    ) -> str:
        """
        Assemble the whole header: the case table, any supporting material, every
        applicable prompt section, and the errors from the previous cycle.

        :param context: The case being labelled.
        :param requests: The answers the expert must supply.
        :param errors: Validation errors from the previous cycle.
        :return: The rendered header text.
        """
        ctx = RenderContext(
            case=context,
            requests=requests,
            palette=self.palette,
            is_first_prompt=self._interact_count == 0,
        )
        parts: List[str] = ["", self._case_table(context), ""]
        if self._helper_cache:
            parts.extend([self._helper_cache, ""])
        for section in PROMPT_SECTIONS:
            if section.applicable(ctx):
                parts.extend(section.lines(ctx))
        if errors:
            parts.append(self._format_errors(errors))
        parts.append("")
        return "\n".join(parts)

    def _case_table(self, context: CaseContext) -> str:
        """
        Render the case, beside the corner case of the rule that fired when there is one
        — what makes the two differ is the condition being asked for.

        :param context: The case being labelled.
        :return: The rendered table.
        """
        if context.corner_case is not None:
            return render_cases_side_by_side(
                context.case_instance,
                context.corner_case,
                min_column_width=self.min_column_width,
                use_color=self.use_color,
            )
        return render_case_table(
            context.case_instance, self.min_column_width, use_color=self.use_color
        )

    def _format_errors(self, errors: List[DataclassException]) -> str:
        """:return: A red, one-line-per-error block (empty list -> empty string)."""
        return "\n".join(
            self.palette.error(f"[error] {error.answer_name}: {error}")
            for error in errors
        )

    # %% guidance

    def _render_tree(self, context: CaseContext) -> Optional[str]:
        """:return: The coloured rule-tree text for this case, or ``None`` if unavailable."""
        trace = context.trace
        if trace is None or trace.rule_tree_root is None:
            return None
        return render_rule_tree(trace, use_color=self.use_color)

    def _helper_text(self, context: CaseContext) -> Optional[str]:
        """:return: The combined ``present()`` output of every helper, or ``None`` if none speak.

        Called once per question (memoized in :meth:`_build_namespace`) so a heavy helper does not
        re-run on each re-prompt cycle.
        """
        fragments = [
            text
            for helper in supporting_material_presenters(context)
            if (text := helper.present(context))
        ]
        return "\n".join(fragments) if fragments else None

    def _help_text(self, context: CaseContext, requests: List[AnswerRequest]) -> str:
        """
        The how-to-answer guidance printed by ``%help`` — plain prose, one accent
        colour.
        """
        lines = [
            self.palette.label("How to answer:"),
            (
                f"  Inspect the case with "
                f"{self.palette.code(NamespaceName.CASE_INSTANCE)} "
                f"(e.g. {self.palette.code(f'{NamespaceName.CASE_INSTANCE}.milk')})."
            ),
            (
                f"  Build your answer over "
                f"{self.palette.code(NamespaceName.CASE_VARIABLE)} and assign it:"
            ),
        ]
        lines.extend(
            f"      {self.palette.code(request.example)}" for request in requests
        )
        lines.append("  Or use the shorthand magic (assigns and submits in one step):")
        for request in requests:
            magic_name = ANSWER_MAGIC_NAMES[request.name]
            lines.append(
                f"      {self.palette.code(f'%{magic_name} <value-or-expression>')}"
            )
        lines.append(
            f"  Submit with {self.palette.code('Ctrl-D')}; cancel with "
            f"{self.palette.code(f'{NamespaceName.EXIT}()')}."
        )
        lines.append(
            f"  Show the rule tree with {self.palette.code(f'%{MagicName.SHOW_TREE}')}."
        )
        if supporting_material_presenters(context):
            lines.append(
                f"  Show the task helper with "
                f"{self.palette.code(f'%{MagicName.HELPER}')}."
            )
        if self.rdr is not None:
            lines.append(
                f"  Query backward inference with "
                f"{self.palette.code(f'%{MagicName.SUFFICIENT_CONDITIONS_FOR} <value>')}."
            )
            lines.append(
                f"  Save the model now with {self.palette.code(f'%{MagicName.SAVE}')}."
            )
        lines.append(
            f"  Show this help again with {self.palette.code(f'%{MagicName.HELP}')}."
        )
        return "\n".join(lines)

    def _build_namespace(
        self, context: CaseContext, requests: List[AnswerRequest]
    ) -> Dict[str, Any]:
        """
        Add the shell's own bindings to the base namespace: the zero-arg renderers the
        magics call, the RDR the backward-inference magic queries, and the conclusion
        domain's own names so the expert can type them.

        :param context: The case being labelled.
        :param requests: The answers the expert must supply.
        :return: The namespace the expert authors their answer in.
        """
        namespace = super()._build_namespace(context, requests)
        namespace[NamespaceKey.RULE_TREE_TEXT] = lambda: self._render_tree(context)
        namespace[NamespaceKey.HELP_TEXT] = lambda: self._help_text(context, requests)
        # Run each helper's present() once for this question; reuse the result in the header and
        # the %helper magic so a heavy helper does not re-run on every re-prompt cycle.
        self._helper_cache = self._helper_text(context)
        if supporting_material_presenters(context):
            namespace[NamespaceKey.HELPER_TEXT] = lambda: self._helper_cache
        if self.rdr is not None:
            namespace[NamespaceKey.SUFFICIENT_CONDITIONS] = self.rdr
        if context.conclusion_domain is not None:
            for name, value in context.conclusion_domain.namespace_bindings().items():
                namespace.setdefault(name, value)
        return namespace

    # %% shell

    def _run(
        self,
        namespace: Dict[str, Any],
        header: str,
        validate: Callable[[], List[DataclassException]],
    ) -> None:
        """
        Hand the namespace to the injected runner when there is one, else open the real
        embedded shell.

        :param namespace: The interaction namespace to populate with answers.
        :param header: The rendered header text to present.
        :param validate: Re-runs the request validators against ``namespace``.
        :return: None; assignments are communicated back via ``namespace``.
        """
        if self.shell_runner is not None:
            self.shell_runner(namespace, header)
        else:
            self._default_run_shell(namespace, header, validate)

    def _default_run_shell(
        self,
        namespace: Dict[str, Any],
        header: str,
        validate: Callable[[], List[DataclassException]],
    ) -> None:
        """
        Open an embedded IPython shell over ``namespace``, with the magics registered
        and a Ctrl-D that is vetoed while the answer is still invalid.

        :param namespace: The interaction namespace to populate with answers.
        :param header: The rendered header text to present.
        :param validate: Re-runs the request validators against ``namespace``.
        :return: None; assignments are communicated back via ``namespace``.
        """
        if self.use_color:
            print(CLEAR_SCREEN, end="", flush=True)

        shell = ValidatingEmbeddedShell(banner1=header, user_ns=namespace)
        shell.auto_match = True
        shell.confirm_exit = False
        shell._force_exit = False
        shell.validate = validate
        shell.format_errors = self._format_errors

        for magic in self._magics(shell, namespace, validate):
            magic.register(shell)

        def _cancel() -> None:
            """
            Abandon the session: force the shell out and flag the abort.
            """
            shell._force_exit = True
            namespace[NamespaceName.ABORT_FLAG] = True
            shell.ask_exit()

        namespace[NamespaceName.EXIT] = _cancel
        namespace["quit"] = _cancel
        # The shell shares ``namespace``, so the expert's assignments are already visible
        # to the caller when it returns.
        shell()

    def _magics(
        self,
        shell: ValidatingEmbeddedShell,
        namespace: Dict[str, Any],
        validate: Callable[[], List[DataclassException]],
    ) -> List[Magic]:
        """
        Build every magic this session offers the expert.

        The answers in flight and the renderers this question has are both pre-seeded
        into ``namespace`` by :meth:`_build_namespace`, so what it holds decides which
        magics there are anything to offer. ``%save`` is unconditional because it prints
        a hint of its own when no model is attached.

        :param shell: The shell the answer magics leave on a valid answer.
        :param namespace: The interaction namespace the magics read and assign in.
        :param validate: Re-runs the request validators against ``namespace``.
        :return: The magics to register, in the order they were built.
        """
        magics: List[Magic] = [SaveModelMagic(palette=self.palette, interface=self)]
        for rendered_text_magic, render_key in (
            (RuleTreeMagic, NamespaceKey.RULE_TREE_TEXT),
            (HelpMagic, NamespaceKey.HELP_TEXT),
            (HelperMagic, NamespaceKey.HELPER_TEXT),
        ):
            render = namespace.get(render_key)
            if render is not None:
                magics.append(rendered_text_magic(palette=self.palette, render=render))
        for answer_name in ANSWER_MAGIC_NAMES:
            if answer_name in namespace:
                magics.append(
                    AssignAndExitMagic(
                        palette=self.palette,
                        answer_name=answer_name,
                        shell=shell,
                        namespace=namespace,
                        validate=validate,
                    )
                )
        if NamespaceKey.SUFFICIENT_CONDITIONS in namespace:
            magics.append(
                SufficientConditionsMagic(palette=self.palette, namespace=namespace)
            )
        return magics
