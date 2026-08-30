"""
IPython line-magic factory for the EQL-RDR interactive expert shell.

:func:`_make_assign_exit_magic` creates action magics (``%conclusion``, ``%conditions``)
that evaluate an expression, assign it to the named answer variable, validate, and exit
the embedded shell on success — all in one step. :func:`_make_knowledge_magic` creates a
read-only magic (``%knows``) that displays backward-inference results.
"""

from __future__ import annotations

from typing_extensions import TYPE_CHECKING, Any, Callable, Dict, List

from krrood.entity_query_language.rdr.answer_vocabulary import AnswerName
from krrood.exceptions import DataclassException

from krrood.entity_query_language.rdr.rule_tree_view import format_condition

if TYPE_CHECKING:
    from krrood.entity_query_language.rdr.interactive import IPythonInterface

#: Magic name for setting the conclusion answer variable.
CONCLUSION_MAGIC = "conclusion"

#: Magic name for setting the conditions answer variable.
CONDITIONS_MAGIC = "conditions"

#: Magic name for backward-inference query.
BACKWARD_MAGIC = "knows"

#: Magic name for on-demand model save.
SAVE_MAGIC = "save"

#: Namespace key holding the RDR for the ``%knows`` magic.
_KNOWLEDGE_KEY = "__backward_knowledge__"


def _make_assign_exit_magic(
    target_name: AnswerName,
    shell: Any,
    namespace: Dict[str, Any],
    validate: Callable[[], List[DataclassException]],
    palette: Any,
) -> Callable[[str], None]:
    """Build a line-magic function that assigns, validates, and exits in one step.

    The returned callable is registered as an IPython line magic. When the expert types
    ``%conclusion Species.mammal``, the shell calls ``magic("Species.mammal")``, which
    evaluates the expression in the live namespace, assigns it, and leaves the shell only
    if the answer validates — an invalid one prints its error and keeps the shell open.

    The plain-assignment path (``conclusion = value`` then Ctrl-D) still works
    unchanged — this magic is an optional shorthand.

    :param target_name: The answer the magic assigns.
    :param shell: The :class:`~IPython.terminal.embed.InteractiveShellEmbed` instance.
    :param namespace: The shared namespace dict (mutated in place).
    :param validate: Zero-arg callable returning the failures of every answer.
    :param palette: A :class:`~krrood.entity_query_language.rdr.interactive.Palette` for
        colouring error messages.
    :return: A line-magic function ``(line: str) -> None``.
    """

    def magic(line: str) -> None:
        """
        :param line: The expression to assign to ``target_name``.
        """
        try:
            value = eval(line.strip(), namespace)
        except Exception as exc:
            print(palette.error(f"[error] {target_name}: {exc}"))
            return
        namespace[target_name] = value
        for error in validate():
            if error.answer_name == target_name:
                print(palette.error(f"[error] {target_name}: {error}"))
                return
        shell._force_exit = True
        shell.ask_exit()

    return magic


def _make_knowledge_magic(
    namespace: Dict[str, Any],
    palette: Any,
) -> Callable[[str], None]:
    """
    Build a line magic (``%knows <value>``) that queries backward inference.

    Reads the RDR reference from the namespace at :data:`_KNOWLEDGE_KEY`,
    evaluates the line argument in the namespace, calls
    ``rdr.what_do_we_know_about(value)``, and prints the result as a
    human-readable list of sufficient condition sets.

    :param namespace: The shell's namespace (mutated in place).
    :param palette: A :class:`~krrood.entity_query_language.rdr.interactive.Palette` for
        colouring output.
    :return: A line-magic function ``(line: str) -> None``.
    """

    def magic(line: str) -> None:
        """
        :param line: The conclusion value to work backwards from.
        """
        rdr = namespace.get(_KNOWLEDGE_KEY)
        if rdr is None:
            print(palette.error("[error] No rule tree available in this session."))
            return

        if not line.strip():
            print(palette.hint("Usage: %knows <conclusion_value>"))
            return

        try:
            value = eval(line.strip(), namespace)
        except Exception as exc:
            print(palette.error(f"[error] Cannot evaluate argument: {exc}"))
            return

        knowledge = rdr.sufficient_conditions_for(value)
        p = palette

        if not knowledge.is_satisfiable():
            print(
                p.label("→ ")
                + p.neutral("No rule path concludes ")
                + p.code(repr(value))
                + p.label(".")
            )
            return

        label = repr(value)
        sets = knowledge.sufficient_condition_sets
        print(
            p.label("→ ")
            + str(len(sets))
            + p.label(" sufficient condition set(s) for ")
            + p.good(label)
            + p.label(":")
        )
        for position, condition_set in enumerate(sets, 1):
            print()
            print(f"  {p.keyword(f'{position}.')}")
            for guard in condition_set.conditions:
                print(f"    {p.code(format_condition(guard.as_expression))}")

    return magic


def _make_save_magic(
    interface: "IPythonInterface",
    palette: Any,
) -> Callable[[str], None]:
    """
    Build a ``%save`` line magic that persists the model through the RDR's own
    :class:`~krrood.entity_query_language.rdr.serialization.ModelSaver`.

    Accepts the *interface* rather than the RDR itself so that an RDR attached after the
    shell was built is visible at call time.

    When the interface has no RDR a hint is printed and no save occurs; no exception is
    raised so the shell stays open.

    :param interface: The
        :class:`~krrood.entity_query_language.rdr.interactive.IPythonInterface` whose
        RDR to persist.
    :param palette: A :class:`~krrood.entity_query_language.rdr.interactive.Palette` for
        colouring feedback messages.
    :return: A line-magic function ``(line: str) -> None``.
    """

    def magic(line: str) -> None:
        """
        :param line: The magic's line argument, unused — the RDR names its own saver.
        """
        rdr = interface.rdr
        if rdr is None:
            print(palette.hint("[hint] No model is attached to this session."))
            return
        rdr.model_saver.save(rdr)
        print(palette.good("[saved] Model saved."))

    return magic
