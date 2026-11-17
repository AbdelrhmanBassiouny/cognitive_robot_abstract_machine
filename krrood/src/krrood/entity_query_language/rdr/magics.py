"""
The IPython line magics of the EQL-RDR interactive expert shell.

Each magic is a :class:`Magic` — one class holding the name the expert invokes it by, the
collaborators it needs, and the behaviour it runs — so registering one into a shell takes
nothing but the object itself. The names and the private namespace keys the magics read
their collaborators from are enumerated rather than spelled out at each use site.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum

from typing_extensions import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from krrood.entity_query_language.rdr.answer_vocabulary import AnswerName
from krrood.entity_query_language.rdr.rule_tree_view import format_condition
from krrood.exceptions import DataclassException

if TYPE_CHECKING:
    from krrood.entity_query_language.rdr.interactive import (
        IPythonInterface,
        Palette,
    )


# %% The vocabulary the shell and its magics share


class MagicName(StrEnum):
    """
    The names the expert types after ``%`` to invoke a magic.
    """

    CONCLUSION = "conclusion"
    """
    Assigns the conclusion answer and submits it.
    """

    CONDITIONS = "conditions"
    """
    Assigns the conditions answer and submits it.
    """

    SUFFICIENT_CONDITIONS_FOR = "sufficient_conditions_for"
    """
    Lists the rule paths that are sufficient to reach a conclusion value.
    """

    SAVE = "save"
    """
    Persists the attached model through its own saver.
    """

    HELP = "help"
    """
    Re-displays the how-to-answer guidance.
    """

    SHOW_TREE = "show_tree"
    """
    Re-displays the rule tree for the case being labelled.
    """

    HELPER = "helper"
    """
    Re-displays the task-specific supporting material.
    """


class MagicKind(StrEnum):
    """
    The IPython magic kinds this shell registers.
    """

    LINE = "line"
    """
    A magic taking the rest of its line as a single argument.
    """


class NamespaceKey(StrEnum):
    """
    The private shell-namespace keys the magics read their collaborators from.

    Private so the expert never sees them among the names they author answers over; the
    answers and the case bindings themselves are named in
    :mod:`~krrood.entity_query_language.rdr.answer_vocabulary`.
    """

    SUFFICIENT_CONDITIONS = "__sufficient_conditions__"
    """
    Holds the RDR that :class:`SufficientConditionsMagic` queries.
    """

    RULE_TREE_TEXT = "__rule_tree_render__"
    """
    Holds the zero-argument renderer behind :class:`RuleTreeMagic`.
    """

    HELP_TEXT = "__expert_help__"
    """
    Holds the zero-argument builder behind :class:`HelpMagic`.
    """

    HELPER_TEXT = "__expert_helper__"
    """
    Holds the zero-argument renderer behind :class:`HelperMagic`.
    """


#: The magic that assigns each answer, which is named after the answer it assigns.
ANSWER_MAGIC_NAMES: Dict[AnswerName, MagicName] = {
    AnswerName.CONCLUSION: MagicName.CONCLUSION,
    AnswerName.CONDITIONS: MagicName.CONDITIONS,
}


# %% The magics themselves


@dataclass
class Magic(ABC):
    """
    One line magic the expert can invoke in the embedded shell.
    """

    palette: Palette
    """
    Colours every message the magic prints.
    """

    @property
    @abstractmethod
    def name(self) -> MagicName:
        """
        :return: The name the expert invokes this magic by.
        """

    @abstractmethod
    def run(self, line: str) -> None:
        """
        Carry the magic out.

        :param line: Everything the expert typed after the magic's name.
        """

    def register(self, shell: Any) -> None:
        """
        Make this magic invokable in *shell* under its own name.

        :param shell: The embedded IPython shell to register into.
        """
        shell.register_magic_function(
            self.run, magic_kind=MagicKind.LINE, magic_name=self.name
        )


@dataclass
class AssignAndExitMagic(Magic):
    """
    Assigns an expression to one answer variable, validates it, and leaves the shell —
    all in one step.

    When the expert types ``%conclusion Species.mammal`` the expression is evaluated in
    the live namespace and assigned; the shell is left only if the answer validates, and
    an invalid one prints its error and keeps the shell open. The plain-assignment path
    (``conclusion = value`` then Ctrl-D) still works unchanged; this is a shorthand.
    """

    answer_name: AnswerName
    """
    The answer this magic assigns.
    """

    shell: Any
    """
    The :class:`~IPython.terminal.embed.InteractiveShellEmbed` to leave on success.
    """

    namespace: Dict[str, Any]
    """
    The shared shell namespace, mutated in place with the assigned answer.
    """

    validate: Callable[[], List[DataclassException]]
    """
    Re-runs every answer's validators and returns their failures.
    """

    @property
    def name(self) -> MagicName:
        """
        :return: The magic name paired with the answer this magic assigns.
        """
        return ANSWER_MAGIC_NAMES[self.answer_name]

    def run(self, line: str) -> None:
        """
        :param line: The expression to assign to the answer.
        """
        try:
            value = eval(line.strip(), self.namespace)
        except Exception as evaluation_error:
            print(self.palette.error(f"[error] {self.answer_name}: {evaluation_error}"))
            return
        self.namespace[self.answer_name] = value
        for error in self.validate():
            if error.answer_name == self.answer_name:
                print(self.palette.error(f"[error] {self.answer_name}: {error}"))
                return
        self.shell._force_exit = True
        self.shell.ask_exit()


@dataclass
class SufficientConditionsMagic(Magic):
    """
    Lists the sufficient condition sets that reach a conclusion value.

    Reads the RDR from the namespace, evaluates the line argument there, and prints each
    rule path that is on its own enough to conclude that value.
    """

    namespace: Dict[str, Any]
    """
    The shared shell namespace, holding the RDR to query and the names to evaluate in.
    """

    @property
    def name(self) -> MagicName:
        """
        :return: The name this magic is invoked by.
        """
        return MagicName.SUFFICIENT_CONDITIONS_FOR

    def run(self, line: str) -> None:
        """
        :param line: The conclusion value to work backwards from.
        """
        rdr = self.namespace.get(NamespaceKey.SUFFICIENT_CONDITIONS)
        if rdr is None:
            print(self.palette.error("[error] No rule tree available in this session."))
            return

        if not line.strip():
            print(self.palette.hint(f"Usage: %{self.name} <conclusion_value>"))
            return

        try:
            value = eval(line.strip(), self.namespace)
        except Exception as evaluation_error:
            print(
                self.palette.error(
                    f"[error] Cannot evaluate argument: {evaluation_error}"
                )
            )
            return

        sufficient_conditions = rdr.sufficient_conditions_for(value)
        if not sufficient_conditions.is_satisfiable():
            print(
                self.palette.label("→ ")
                + self.palette.neutral("No rule path concludes ")
                + self.palette.code(repr(value))
                + self.palette.label(".")
            )
            return

        condition_sets = sufficient_conditions.sufficient_condition_sets
        print(
            self.palette.label("→ ")
            + str(len(condition_sets))
            + self.palette.label(" sufficient condition set(s) for ")
            + self.palette.good(repr(value))
            + self.palette.label(":")
        )
        for position, condition_set in enumerate(condition_sets, 1):
            print()
            print(f"  {self.palette.keyword(f'{position}.')}")
            for guard in condition_set.conditions:
                print(f"    {self.palette.code(format_condition(guard.as_expression))}")


@dataclass
class SaveModelMagic(Magic):
    """
    Persists the model through the RDR's own
    :class:`~krrood.entity_query_language.rdr.serialization.ModelSaver`.

    Holds the interface rather than the RDR itself so that an RDR attached after the
    shell was built is still visible at call time. With no RDR attached a hint is
    printed and nothing is saved, so the shell stays open.
    """

    interface: IPythonInterface
    """
    The interface whose RDR to persist.
    """

    @property
    def name(self) -> MagicName:
        """
        :return: The name this magic is invoked by.
        """
        return MagicName.SAVE

    def run(self, line: str) -> None:
        """
        :param line: The magic's line argument, unused — the RDR names its own saver.
        """
        rdr = self.interface.rdr
        if rdr is None:
            print(self.palette.hint("[hint] No model is attached to this session."))
            return
        rdr.model_saver.save(rdr)
        print(self.palette.good("[saved] Model saved."))


@dataclass
class RenderedTextMagic(Magic, ABC):
    """
    Prints whatever a zero-argument renderer returns, or a placeholder when it returns
    nothing.
    """

    render: Callable[[], Optional[str]]
    """
    Produces the text to print, re-run on each invocation.
    """

    def run(self, line: str) -> None:
        """
        :param line: The magic's line argument, unused — the renderer takes none.
        """
        text = self.render()
        print(text if text else self.palette.absent("(nothing to show)"))


@dataclass
class HelpMagic(RenderedTextMagic):
    """
    Re-displays the how-to-answer guidance.
    """

    @property
    def name(self) -> MagicName:
        """
        :return: The name this magic is invoked by.
        """
        return MagicName.HELP


@dataclass
class RuleTreeMagic(RenderedTextMagic):
    """
    Re-displays the rule tree for the case being labelled.
    """

    @property
    def name(self) -> MagicName:
        """
        :return: The name this magic is invoked by.
        """
        return MagicName.SHOW_TREE


@dataclass
class HelperMagic(RenderedTextMagic):
    """
    Re-displays the task-specific supporting material.
    """

    @property
    def name(self) -> MagicName:
        """
        :return: The name this magic is invoked by.
        """
        return MagicName.HELPER
