"""
Checks the answers of the tasks in the notebook of Worksheet 3 against the solution and shows the verdict as a box:
green when the answer is right, red with a hint when it is not, grey while the task is still ``TODO``.

The solution is stored as fingerprints of the answers, not as the answers, so reading this file does not solve a task.
An answer is the text the notebook prints for it, such as ``napoletana_1`` or ``Order(table 2), napoletana_1``.
Every wrong answer costs the pizzeria a fine; the fines are kept in a file, so they add up across kernel restarts.

Predictions are not fined: a student writes a guess before running a cell, and the cell then shows what surprised
them and why.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum, StrEnum
from html import escape
from pathlib import Path

from krrood.adapters.json_serializer import from_json, to_json
from typing_extensions import Any

# %% verdicts


class VerdictKind(Enum):
    """The outcomes of a check or a prediction, each with the border colour of
    its box and a translucent tint of it, so that the box reads on light and
    dark notebook themes alike."""

    CORRECT = ("#4f9a6b", "rgba(79, 154, 107, 0.13)")
    WRONG = ("#c0504d", "rgba(192, 80, 77, 0.15)")
    UNANSWERED = ("#8a97a8", "rgba(138, 151, 168, 0.13)")
    SURPRISE = ("#c38d2c", "rgba(195, 141, 44, 0.14)")


@dataclass
class Verdict:
    """The result of checking one answer, shown by the notebook as a coloured
    box."""

    kind: VerdictKind
    """Whether the answer is right, wrong, or not given yet; decides the colour
    of the box."""

    headline: str
    """The first line of the box, in bold."""

    story: str = ""
    """What happened in the pizzeria because of the answer, with a hint where
    the answer is wrong."""

    fine: int = 0
    """The fine in euros that the answer costs the pizzeria."""

    fine_note: str = ""
    """The line about the fine and the total so far, written once the fine is
    booked."""

    def _repr_html_(self) -> str:
        border, fill = self.kind.value
        style = (
            f"border-left: 5px solid {border}; background-color: {fill}; border-radius: 0 8px 8px 0; "
            "padding: 8px 20px; margin: 8px 0; line-height: 1.6"
        )
        lines = [f"<b>{escape(self.headline)}</b>"] + [
            escape(line) for line in (self.story, self.fine_note) if line
        ]
        return f'<div style="{style}">{"<br>".join(lines)}</div>'

    def __repr__(self) -> str:
        return " ".join(
            line for line in (self.headline, self.story, self.fine_note) if line
        )


# %% expected answers


@dataclass(frozen=True)
class Expectation:
    """The solution of one task and what the pizzeria makes of a wrong
    answer."""

    fingerprints: tuple[str, ...]
    """The :meth:`fingerprint` of every answer of the solution, once per time
    it is an answer."""

    singular: str
    """The noun for one answer, as in *you missed 1 pizza*."""

    plural: str
    """The noun for several answers, as in *you missed 2 pizzas*."""

    success_story: str
    """What happens when the answer is right."""

    missing_story: str
    """What happens when answers of the solution are missing."""

    extra_story: str
    """What happens when there are answers the solution does not have, or more
    than one object fits a reference."""

    missing_fine: int
    """The fine in euros for an answer with missing answers."""

    extra_fine: int
    """The fine in euros for an answer with answers that do not belong."""

    starter_fingerprints: tuple[str, ...] = ()
    """The :attr:`fingerprints` of what the starting code of the task gives,
    which is not yet an attempt."""

    @staticmethod
    def fingerprint(answer: str) -> str:
        """
        :return: A short hash of the answer, from which the answer cannot be read back.
        """
        return hashlib.sha256(answer.encode()).hexdigest()[:16]

    def noun(self, count: int) -> str:
        """
        :return: The count with the noun in the right number, such as *1 pizza* or *2 pizzas*.
        """
        return f"{count} {self.singular if count == 1 else self.plural}"

    def verdict(self, answers: list[str] | None) -> Verdict:
        """
        :param answers: The answers the student's code gives, or ``None`` while the task is still ``TODO``.
        :return: The verdict on the answers, compared with the solution as a multiset.
        """
        if answers is None:
            return Verdict(
                VerdictKind.UNANSWERED,
                "Still TODO: write your answer, then run the cell again.",
            )
        given = Counter(self.fingerprint(answer) for answer in answers)
        expected = Counter(self.fingerprints)
        if self.starter_fingerprints and given == Counter(self.starter_fingerprints):
            return Verdict(
                VerdictKind.UNANSWERED,
                "Still the starting code: complete the TODO, then run the cell again.",
            )
        if given == expected:
            return Verdict(VerdictKind.CORRECT, "Correct!", self.success_story)
        missing = sum((expected - given).values())
        extra = sum((given - expected).values())
        if set(given) == set(expected):
            return Verdict(
                VerdictKind.WRONG,
                "Not yet: every answer is right, but some appear more than once.",
                "An object either satisfies the formula or it does not; it is never an answer twice.",
                self.extra_fine,
            )
        if not extra:
            return Verdict(
                VerdictKind.WRONG,
                f"Not yet: it looks like you missed {self.noun(missing)}.",
                self.missing_story,
                self.missing_fine,
            )
        if not missing:
            return Verdict(
                VerdictKind.WRONG,
                f"Not yet: it looks like you have {self.noun(extra)} too many.",
                self.extra_story,
                self.extra_fine,
            )
        return Verdict(
            VerdictKind.WRONG,
            f"Not yet: you missed {self.noun(missing)}, and {self.noun(extra)} {'does' if extra == 1 else 'do'} not belong.",
            f"{self.missing_story} {self.extra_story}",
            self.missing_fine + self.extra_fine,
        )

    def ambiguity_verdict(self) -> Verdict:
        """
        :return: The verdict on a reference that more than one object fits.
        """
        return Verdict(
            VerdictKind.WRONG,
            f"Not yet: more than one {self.singular} fits, so the robot has to ask back.",
            self.extra_story,
            self.extra_fine,
        )


class Task(Enum):
    """The tasks of the notebook whose answer can be checked, each with its
    solution."""

    VEGETARIAN_PIZZAS = Expectation(
        fingerprints=(
            "96142b90f77b5ec3",
            "1f69b3bf57366f68",
            "16bfb7fcde99a0d0",
            "f43d6696c6d1430e",
            "ef6c16479a9e8fbe",
        ),
        singular="pizza",
        plural="pizzas",
        success_story="The green V is on exactly the right pizzas. The vegetarians at the bar order seconds.",
        missing_story=(
            "A vegetarian found too little on the menu and went to the falafel stand across the street. "
            "Fewer than five? Look at plain_1 and unclosed_1."
        ),
        extra_story=(
            "A vegetarian trusted the green V, bit into a slice of ham and is now writing a very long review."
        ),
        missing_fine=50,
        extra_fine=200,
    )
    HOT_PIZZAS = Expectation(
        fingerprints=("15dc829e56cf51b5",),
        singular="pizza",
        plural="pizzas",
        success_story="The robot warns Ada in time; she orders something mild and keeps her tongue.",
        missing_story=(
            "A hot pizza slipped through: Ada bit into a jalapeño and has emptied the kitchen's milk supply."
        ),
        extra_story="The robot warned Ada about a pizza as mild as a cloud; she ordered a salad and the chef wept.",
        missing_fine=150,
        extra_fine=30,
    )
    HOT_ORDERS = Expectation(
        fingerprints=("56270cd3463d7701",),
        singular="order",
        plural="orders",
        success_story="The right table is warned; nobody breathes fire tonight.",
        missing_story="The robot overlooked a table with a hot pizza; somebody there is breathing fire.",
        extra_story="The robot fanned a table whose pizzas are not hot at all; those guests are now cold.",
        missing_fine=150,
        extra_fine=30,
    )
    OLIVES_WITHOUT_FISH = Expectation(
        fingerprints=("16bfb7fcde99a0d0",),
        singular="pizza",
        plural="pizzas",
        success_story="Ben gets his olives and not a single anchovy. He tips the robot.",
        missing_story="The pizza Ben asked for is not the one the robot brings: Ben stares at his plate.",
        extra_story=(
            "Your condition still lets a pizza with fish through; Ben is asked back once more and eyes the "
            "burger place."
        ),
        missing_fine=80,
        extra_fine=40,
    )
    ALLERGENS = Expectation(
        fingerprints=(
            "e26c47cce825e8cd",
            "51bcd32d49060d07",
            "6b4fce31ca55052e",
            "a98b80f929257cfa",
            "113ea9073ccac86a",
            "7ecf025c9eaeea20",
            "acbb9104e861ca62",
            "52dee9e577263983",
            "e7cd6869c794b9b7",
            "81cf5dcab9e8d0fb",
            "38b9c436be1d4982",
            "826e9ceb5ab84f33",
            "ba558e6b0c1323f9",
        ),
        singular="allergen",
        plural="allergens",
        success_story="Every allergen is on the menu. The health inspector nods, which never happens.",
        missing_story=(
            "An allergen went unlisted: a guest ate what nobody warned them about and spent the night in hospital."
        ),
        extra_story="The menu lists allergens that are not there; the health inspector is confused.",
        missing_fine=500,
        extra_fine=50,
        starter_fingerprints=(
            "e26c47cce825e8cd",
            "a98b80f929257cfa",
            "7ecf025c9eaeea20",
            "52dee9e577263983",
            "81cf5dcab9e8d0fb",
            "38b9c436be1d4982",
            "826e9ceb5ab84f33",
        ),
    )
    SAFE_FOR_BEN = Expectation(
        fingerprints=(
            "16bfb7fcde99a0d0",
            "f43d6696c6d1430e",
        ),
        singular="pizza",
        plural="pizzas",
        success_story="Ben eats well and stays out of hospital.",
        missing_story="Ben went home hungry, although the kitchen had pizzas he could eat.",
        extra_story=(
            "The robot called a pizza with cheese safe. Ben believed it and is in hospital; the pizzeria's "
            "lawyer is on the phone. Does your __call__ still return True for every pizza?"
        ),
        missing_fine=40,
        extra_fine=1000,
        starter_fingerprints=(
            "96142b90f77b5ec3",
            "bbcf7aea3feeb629",
            "15dc829e56cf51b5",
            "1f69b3bf57366f68",
            "16bfb7fcde99a0d0",
            "f43d6696c6d1430e",
            "ef6c16479a9e8fbe",
        ),
    )
    DANGEROUS_PLATES = Expectation(
        fingerprints=("c44d8125b632acbd",),
        singular="pair of an order and a pizza",
        plural="pairs of an order and a pizza",
        success_story="The robot stops exactly the one dangerous plate. Nobody goes to hospital tonight.",
        missing_story=(
            "The robot found nothing wrong and served the plate. An ambulance is now parked in front of the "
            "pizzeria."
        ),
        extra_story="The robot took a safe pizza off a table; it went cold while the cook checked it three times.",
        missing_fine=2000,
        extra_fine=60,
    )
    ALLERGEN_WARNINGS = Expectation(
        fingerprints=(
            "a849d948f0e14f47",
            "7462327016b4b808",
            "481eca66cd6698a3",
            "3115b076b0a6de2b",
            "aa69b172caa4a9c3",
            "601f65b605d65f66",
            "05f6ffa685eee3a0",
            "123ed3778558fb62",
            "56836a9bb25749da",
            "d24f29ea46fecffb",
            "3932bc1a6085eecb",
            "4672e34407c72e9b",
            "ff1d4928da6b6ce9",
        ),
        singular="warning",
        plural="warnings",
        success_story="Every slip of paper is right. The pizzeria's insurance lowers its rate.",
        missing_story="A pizza left the kitchen without its warning; the ambulance driver knows the way by now.",
        extra_story="Warnings about allergens a pizza does not have: the guests now believe the dough contains fish.",
        missing_fine=800,
        extra_fine=100,
        starter_fingerprints=(
            "a849d948f0e14f47",
            "7462327016b4b808",
            "481eca66cd6698a3",
            "3115b076b0a6de2b",
            "aa69b172caa4a9c3",
        ),
    )


# %% predictions


class HowManyFit(StrEnum):
    """How many objects fit a description that demands exactly one, and what
    the robot does then."""

    NONE = "none fits: the robot reports that there is no such pizza"
    ONE = "one fits: the robot brings it"
    SEVERAL = "several fit: the robot asks back"


@dataclass(frozen=True)
class AnswerShape(ABC):
    """What a prediction is about, which decides how a guess is compared with
    what the robot found."""

    @abstractmethod
    def normalized(self, value: Any) -> Any:
        """
        :return: The value in the form in which a guess and the robot's answer are compared.
        """

    @abstractmethod
    def surprise(self, guess: Any, found: Any) -> str:
        """
        :param guess: The normalized guess.
        :param found: The normalized answer of the robot, different from the guess.
        :return: What the robot found that the guess did not expect.
        """

    @staticmethod
    def spelled(value: Any) -> str:
        """
        :return: The value as the notebook prints it: a set as its sorted elements, a truth value as yes or no,
            ``None`` as *none* and ``...`` as *no guess*.
        """
        if isinstance(value, (set, frozenset)):
            return ", ".join(sorted(value)) if value else "nothing"
        if isinstance(value, bool):
            return "yes" if value else "no"
        if value is None:
            return "none"
        if value is ...:
            return "no guess"
        return str(value)


@dataclass(frozen=True)
class Names(AnswerShape):
    """The objects a query returns, compared as a set of their names."""

    def normalized(self, value: Any) -> frozenset[str]:
        if isinstance(value, str):
            return frozenset({value})
        return frozenset(str(element) for element in value)

    def surprise(self, guess: frozenset[str], found: frozenset[str]) -> str:
        lines = []
        if found - guess:
            lines.append(f"The robot also found {self.spelled(found - guess)}.")
        if guess - found:
            pronoun = "it" if len(guess - found) == 1 else "them"
            lines.append(
                f"You expected {self.spelled(guess - found)}, but the robot did not return {pronoun}."
            )
        return " ".join(lines)


@dataclass(frozen=True)
class Count(AnswerShape):
    """The number of answers of a query."""

    def normalized(self, value: Any) -> int:
        return value if isinstance(value, int) else len(value)

    def surprise(self, guess: int, found: int) -> str:
        return f"You guessed {guess}, the robot found {found}."


@dataclass(frozen=True)
class Value(AnswerShape):
    """One value, such as yes or no, or the name of a label; a label is
    compared without its suffix *Pizza*, and *none* or *no label* is no label
    at all."""

    def normalized(self, value: Any) -> Any:
        if isinstance(value, Enum) or not isinstance(value, str):
            return value
        text = value.strip().lower().removesuffix("pizza")
        return None if text in ("", "none", "no label") else text

    def surprise(self, guess: Any, found: Any) -> str:
        return f"Your guess: {self.spelled(guess)}. The robot: {self.spelled(found)}."


@dataclass(frozen=True)
class Labels(AnswerShape):
    """The label of every pizza, compared pizza by pizza; ``None`` is a pizza
    without a label."""

    def normalized(self, value: dict[str, Any]) -> dict[str, Any]:
        return {name: Value().normalized(label) for name, label in value.items()}

    def surprise(self, guess: dict[str, Any], found: dict[str, Any]) -> str:
        differences = [
            f"{name} (you: {self.spelled(guess[name])}; the robot: {self.spelled(label)})"
            for name, label in found.items()
            if guess.get(name, ...) is not ... and guess[name] != label
        ]
        unguessed = [name for name in found if guess.get(name, ...) is ...]
        lines = []
        if differences:
            lines.append("Different from your guess: " + ", ".join(differences) + ".")
        if unguessed:
            lines.append("No guess for " + ", ".join(unguessed) + ".")
        return " ".join(lines)


@dataclass(frozen=True)
class Question:
    """One prediction the notebook asks for: what is predicted, and why the
    answer is what it is."""

    topic: str
    """What the student predicts, completing the sentence *You predicted
    ...*."""

    shape: AnswerShape
    """How the guess is compared with what the robot found."""

    explanation: str
    """Why the robot's answer is what it is, shown once the answer is
    revealed."""


class Prediction(Enum):
    """The predictions of the notebook, each made in a cell before the cell
    that reveals the answer."""

    EVERY_TOPPING_A_VEGETABLE = Question(
        "the pizzas Q1 returns",
        Names(),
        "plain_1 has no toppings at all, so none of its toppings is a counterexample: every topping it has is a "
        "vegetable (vacuous truth).",
    )
    EXACTLY_MOZZARELLA_AND_TOMATO = Question(
        "the pizzas Q2 returns",
        Names(),
        "A list of patterns describes the whole list: a mozzarella, then a tomato, and nothing else. mushroom_1 "
        "has a third topping, unclosed_1 only one.",
    )
    NO_CHEESE = Question(
        "the pizzas Q3 returns",
        Names(),
        "Nobody ever wrote down that veggie_1 has no cheese. The robot reads the list of toppings as complete: "
        "what is not listed is not there (closed world).",
    )
    SOME_TOPPING_NOT_HOT = Question(
        "the pizzas of the second query",
        Names(),
        "not_ negates the condition on one topping: the query asks for a pizza with some topping that is not hot. "
        "Every pizza with a mild topping has one, the American Hot too; and on plain_1 the condition on a topping "
        "it does not have is false, so its negation is true. No hot topping at all is none_is.",
    )
    HOT_TOPPING_BINDINGS = Question(
        "the number of answers",
        Count(),
        "An answer is a binding of every selected variable. The American Hot has two hot toppings, so there are "
        "two bindings; hot_orders hid the pizza and the topping under ∃ and had one answer.",
    )
    THE_PIZZA_WITH_HAM = Question(
        "what happens for the pizza with ham",
        Value(),
        "No pizza has ham: there is nothing that the pizza with ham could refer to.",
    )
    THE_PIZZA_WITH_FISH = Question(
        "what happens for the pizza with fish",
        Value(),
        "Exactly one pizza has fish, napoletana_1: the description refers, and the robot brings it.",
    )
    THE_PIZZA_WITH_OLIVES = Question(
        "what happens for the pizza with olives",
        Value(),
        "napoletana_1 and veggie_1 both have olives. Picking one of them at random would be a guess, not "
        "obedience, so the robot asks back.",
    )
    ACCEPTED_FROZEN_PIZZAS = Question(
        "the frozen pizzas that get the green V",
        Names(),
        "frozen_1 has ham, frozen_2 only tomato and capers. Checking one candidate binds the variable of the "
        "definition: a question whose answer is yes or no.",
    )
    ONLY_IN_THE_REGISTRY = Question(
        "the pizzas the registry adds to the counter's answer",
        Names(),
        "Creating the frozen pizzas to check them entered them in the registry. Without .from_, the robot asks "
        "about everything it has ever created, so frozen_2 is vegetarian there, although it is not on tonight's "
        "menu.",
    )
    MENU_LABELS = Question(
        "the label of every pizza",
        Labels(),
        "napoletana_1 has fish, so it is not vegetarian by the first rule, and no meat, so the alternative fails "
        "as well: the rules are silent about it. Silence is not no: they never said it is not vegetarian.",
    )
    VIOLATIONS_AFTER_THE_PARMESAN = Question(
        "the number of violations of the constraint",
        Count(),
        "The constraint is a query, evaluated against the world as it is now: Ben's veggie_1 has cheese since a "
        "minute ago, and is a second violation.",
    )
    MILK_WARNING_ON_VEGGIE = Question(
        "whether veggie_1 has a milk warning",
        Value(),
        "The warnings were written down in 4(a), before the parmesan, and nobody ran the rule again. A stored "
        "conclusion goes stale when its reasons change; keeping it up to date is called truth maintenance.",
    )
    LABEL_OF_VEGGIE = Question(
        "the label of veggie_1",
        Value(),
        "Vegan needs a pizza without cheese. A fact was added and a conclusion was withdrawn: reasoning in which "
        "more knowledge can remove a conclusion is non-monotonic.",
    )
    FROM_THE_COUNTER = Question(
        "what the counter answers",
        Names(),
        "The counter selects among the pizzas that exist: margherita_1 is exactly a mozzarella and a tomato. The "
        "kitchen answers the same description by making a new pizza.",
    )
    OFFERS_FOR_THE_OPEN_WISH = Question(
        "the number of pizzas the kitchen offers",
        Count(),
        "Dana left the spiciness open, so the kitchen fills the open slot in every possible way: one pizza for "
        "each value of Spiciness.",
    )
    HOT_PIZZAS_NOW = Question(
        "the number of hot pizzas now",
        Count(),
        "hot_pizzas has no .from_: it asks the registry as it is now, and the kitchen's offer with a hot green "
        "pepper is in it, a pizza nobody ordered. A question with .from_(pizzas) keeps its answer.",
    )


@dataclass
class Predictions:
    """The guesses of one student, kept while the notebook runs, and the
    comparison with what the robot finds."""

    guesses: dict[Prediction, Any] = field(default_factory=dict)
    """The guess for every prediction made so far, as the student wrote it."""

    def record(self, prediction: Prediction, guess: Any) -> Verdict:
        """Keep the guess, unless it is still ``...``, or a set of labels that
        are all still ``...``.

        :return: A box that confirms the guess.
        """
        if guess is ... or (
            isinstance(guess, dict) and all(label is ... for label in guess.values())
        ):
            return Verdict(
                VerdictKind.UNANSWERED,
                "Still TODO: type your guess in place of ..., then run the cell.",
            )
        self.guesses[prediction] = guess
        return Verdict(
            VerdictKind.SURPRISE,
            "Your guess is noted. Now run the next cell.",
            f"You predicted {prediction.value.topic}: {AnswerShape.spelled(guess)}.",
        )

    def reveal(self, prediction: Prediction, found: Any) -> Verdict:
        """
        :param found: What the robot found, in the shape of the prediction.
        :return: A box that compares the guess with what the robot found and explains the answer.
        """
        if prediction not in self.guesses:
            return Verdict(
                VerdictKind.UNANSWERED,
                "You did not guess. Make your guess in the cell above, then run both cells again.",
                "A wrong guess is where you learn the most, and nobody fines a guess.",
            )
        question = prediction.value
        guess = question.shape.normalized(self.guesses[prediction])
        answer = question.shape.normalized(found)
        if guess == answer:
            return Verdict(
                VerdictKind.CORRECT,
                f"Spot on! You predicted {question.topic}.",
                question.explanation,
            )
        return Verdict(
            VerdictKind.SURPRISE,
            f"Surprise! {question.shape.surprise(guess, answer)}",
            question.explanation,
        )


# %% fines


@dataclass
class Fine:
    """A fine the pizzeria paid for one wrong answer to a task."""

    task: Task
    """The task that was answered wrongly."""

    attempt: str
    """The fingerprint of all answers of the attempt together, so that running
    the same wrong answer again costs nothing."""

    amount: int
    """The fine in euros."""


@dataclass
class FineBook:
    """Every fine of one student, kept in a JSON file next to the notebook so
    that it survives kernel restarts."""

    fines: list[Fine] = field(default_factory=list)
    """The fines, in the order they were booked."""

    @property
    def total(self) -> int:
        """
        :return: The sum of all fines in euros.
        """
        return sum(fine.amount for fine in self.fines)


@dataclass
class AnswerChecker:
    """Checks the answers of the notebook's tasks and books a fine for every
    new wrong answer."""

    fines_file: Path = Path("fines.json")
    """The file the fines are kept in."""

    book: FineBook = field(init=False)
    """The fines booked so far, read from :attr:`fines_file`."""

    def __post_init__(self) -> None:
        self.book = (
            from_json(json.loads(self.fines_file.read_text()))
            if self.fines_file.exists()
            else FineBook()
        )

    def check(self, task: Task, answers: list[str] | None) -> Verdict:
        """
        :param answers: The answers the student's code gives, or ``None`` while the task is still ``TODO``.
        :return: The verdict on the answers, with its fine booked.
        """
        verdict = task.value.verdict(answers)
        attempt = Expectation.fingerprint("\n".join(sorted(answers or [])))
        return self.book_fine(task, attempt, verdict)

    def check_ambiguous(self, task: Task) -> Verdict:
        """
        :return: The verdict on a reference that more than one object fits, with its fine booked.
        """
        return self.book_fine(task, "ambiguous", task.value.ambiguity_verdict())

    def book_fine(self, task: Task, attempt: str, verdict: Verdict) -> Verdict:
        """Book the fine of the verdict, unless the same attempt at the task
        was already fined.

        :return: The verdict with a note on the fine and the total so
            far.
        """
        if verdict.kind is not VerdictKind.WRONG:
            return verdict
        if any(
            fine.task is task and fine.attempt == attempt for fine in self.book.fines
        ):
            verdict.fine_note = f"You already paid for this answer. Your fines so far: €{self.book.total}."
            return verdict
        self.book.fines.append(Fine(task, attempt, verdict.fine))
        self.fines_file.write_text(json.dumps(to_json(self.book)))
        verdict.fine_note = (
            f"Fine: €{verdict.fine}. Your fines so far: €{self.book.total}."
        )
        return verdict

    def bill(self) -> Bill:
        """
        :return: The bill of the evening: every fine booked so far and their total.
        """
        return Bill(self.book)


@dataclass
class Bill:
    """The bill of the evening, shown at the end of the notebook: every fine,
    and the guests' decision to waive them."""

    book: FineBook
    """The fines on the bill."""

    def _repr_html_(self) -> str:
        border, fill = VerdictKind.CORRECT.value
        style = (
            f"border-left: 5px solid {border}; background-color: {fill}; border-radius: 0 8px 8px 0; "
            "padding: 8px 20px; margin: 8px 0; line-height: 1.6"
        )
        rows = "".join(
            f"<tr><td>{escape(fine.task.name.lower().replace('_', ' '))}</td>"
            f"<td style='text-align: right'><s>€{fine.amount}</s></td></tr>"
            for fine in self.book.fines
        )
        table = f"<table>{rows}</table>" if rows else ""
        return f'<div style="{style}"><b>{escape(self.total_line)}</b>{table}{escape(self.verdict_line)}</div>'

    def __repr__(self) -> str:
        return f"{self.total_line} {self.verdict_line}"

    @property
    def total_line(self) -> str:
        """
        :return: The first line of the bill: the total of the fines.
        """
        if not self.book.fines:
            return "The bill of the evening: €0."
        return f"The bill of the evening: €{self.book.total} in {len(self.book.fines)} fine(s)."

    @property
    def verdict_line(self) -> str:
        """
        :return: The last line of the bill: what the guests decided.
        """
        if not self.book.fines:
            return "Not a single fine. The guests send their compliments to the robot."
        return (
            "But the guests talked it over and waived every euro: you are still learning, "
            "and they are on your side. You owe nothing."
        )
