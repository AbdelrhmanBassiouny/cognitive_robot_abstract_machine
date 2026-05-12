"""
ActionPlan (composite action) and ActionExecutor with rollback support.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import libcst

from krrood.patterns.code_generation.actions.base import Action


@dataclass
class ActionPlan(Action):
    """A composite action: an ordered, reversible sequence of sub-actions.

    :meth:`apply` applies each sub-action in order, threading the module
    through the sequence.  :meth:`reverse` applies each sub-action's
    :meth:`~Action.reverse` in reverse order.

    An :class:`ActionPlan` can itself be a sub-action of another
    :class:`ActionPlan`, enabling hierarchical composition::

        class_transform = ActionPlan([
            AddBaseClass("Professor", BaseClassSpec("HasRoles")),
            AddMethod("Professor", some_method_node),
        ], description="Transform Professor class")

        module_transform = ActionPlan([
            class_transform,
            AddImport("typing", ["List"]),
        ], description="Transform university module")
    """

    actions: list[Action] = field(default_factory=list)
    """The ordered sequence of sub-actions."""

    description: str = ""
    """Human-readable description for the audit trail."""

    def apply(self, module: libcst.Module) -> libcst.Module:
        """Apply each sub-action in order, threading *module* through."""
        for action in self.actions:
            module = action.apply(module)
        return module

    def reverse(self, module: libcst.Module) -> libcst.Module:
        """Reverse each sub-action in reverse order."""
        for action in reversed(self.actions):
            module = action.reverse(module)
        return module

    def __len__(self) -> int:
        return len(self.actions)

    def __bool__(self) -> bool:
        return bool(self.actions)


@dataclass
class ActionResult:
    """The result of executing an :class:`ActionPlan`.

    Attributes:
        module: The transformed module, or ``None`` on failure.
        plan: The plan that was executed.
        actions_applied: Actions that completed before failure (for audit).
        success: ``True`` if all actions completed without error.
        error: The exception that caused failure, or ``None``.
    """

    module: libcst.Module | None = None
    plan: ActionPlan | None = None
    actions_applied: list[Action] = field(default_factory=list)
    success: bool = False
    error: Exception | None = None


@dataclass
class ActionExecutor:
    """Executes an :class:`ActionPlan` with full-rollback on failure.

    When :meth:`execute` is called and an action raises an exception, all
    previously-applied actions are reversed in LIFO order (best-effort).
    This guarantees that on failure the module is returned to its original
    state::

        executor = ActionExecutor()
        result = executor.execute(plan, module)
        if result.success:
            return result.module
        else:
            raise result.error
    """

    def execute(
        self, plan: ActionPlan, module: libcst.Module
    ) -> ActionResult:
        """Execute *plan* against *module*, rolling back on failure.

        :param plan: The action plan to execute.
        :param module: The starting module to transform.
        :return: An :class:`ActionResult` with the final module or error.
        """
        applied: list[Action] = []
        try:
            for action in plan.actions:
                module = action.apply(module)
                applied.append(action)
        except Exception as exc:
            # Best-effort rollback in reverse order
            for action in reversed(applied):
                try:
                    module = action.reverse(module)
                except Exception:
                    pass
            return ActionResult(
                module=None,
                plan=plan,
                actions_applied=applied,
                success=False,
                error=exc,
            )
        return ActionResult(
            module=module,
            plan=plan,
            actions_applied=applied,
            success=True,
            error=None,
        )
