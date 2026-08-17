"""
Tests for reading a query back as coloured English before its answers.

The point is that the answer panel says what was asked, not only what came back, so a
preset button is self-explaining rather than a label over an opaque result.
"""

import pytest

krrood = pytest.importorskip("krrood", reason="EQL requires krrood")

from krrood.entity_query_language.verbalization._example_domain import (  # noqa: E402
    Robot as ExampleRobot,
)
from krrood.entity_query_language.verbalization.exceptions import (  # noqa: E402
    UnverbalizableExpressionError,
)
from krrood.entity_query_language.verbalization.fragments.source_reference import (  # noqa: E402
    SourceReference,
)
from krrood.entity_query_language.verbalization.pipeline import (  # noqa: E402
    VerbalizationPipeline,
)
from krrood.entity_query_language.verbalization.verbalizer import (  # noqa: E402
    EQLVerbalizer,
)

from cramera.knowledge.query_domain import QueryDomain  # noqa: E402
from cramera.knowledge.query_runner import EqlQueryRunner  # noqa: E402
from cramera.knowledge.query_verbalization import (  # noqa: E402
    DEFAULT_DOCUMENTATION_SITE,
    DOCUMENTATION_SITE_VARIABLE,
    PublishedDocumentationResolver,
    QueryVerbalization,
)

from .dataset.queryable_records import NamedRecord  # noqa: E402
from .test_query_runner import make_records, make_runner  # noqa: E402


def verbalize(code: str) -> QueryVerbalization:
    """
    The verbalization of one query over the shared ``record`` domain.

    :param code: The query source to verbalize.
    """
    runner = make_runner()
    namespace = runner.namespace()
    return QueryVerbalization.of_expression(eval(code, namespace))


# %% what a query says in English
class TestReadingAQueryBack:
    def test_a_query_is_read_back_as_a_sentence(self):
        """
        The wording is krrood's to decide, so this pins ours to krrood's own plain
        verbalization of the same expression rather than to a second copy of the string.
        """
        namespace = make_runner().namespace()
        expression = eval("an(entity(record).where(record.score > 1.0))", namespace)

        verbalization = QueryVerbalization.of_expression(expression)

        assert verbalization.text == VerbalizationPipeline.plain().verbalize(expression)

    def test_the_sentence_names_what_is_asked_about(self):
        verbalization = verbalize("an(entity(record).where(record.score > 1.0))")

        assert "NamedRecord" in verbalization.text
        assert "score" in verbalization.text

    def test_the_html_colours_each_part_by_its_role(self):
        """
        The colours are the semantic-role palette krrood already draws query graphs
        with, so the sentence and the graph agree on what a variable looks like.
        """
        verbalization = verbalize("an(entity(record).where(record.score > 1.0))")

        assert '<span style="color:' in verbalization.html
        assert verbalization.html.count("<span") >= 3

    def test_markup_in_a_literal_cannot_escape_into_the_page(self):
        """
        The sentence is inserted as markup, so a literal a user typed must arrive as
        text rather than as tags.
        """
        verbalization = verbalize(
            "an(entity(record).where(record.name == '<b>hi</b>'))"
        )

        assert "&lt;b&gt;hi&lt;/b&gt;" in verbalization.html
        assert "<b>" not in verbalization.html


# %% words linking to their documentation
class TestDocumentationLinks:
    """
    A verbalized word naming a class or attribute of a package with published docs is a
    hyperlink to its AutoAPI page; anything else stays plain text — a link known to lead
    nowhere is worse than no link.
    """

    EXAMPLE_ROBOT_PAGE = (
        DEFAULT_DOCUMENTATION_SITE
        + "/krrood/autoapi/krrood/entity_query_language/verbalization/_example_domain"
        + "/index.html#krrood.entity_query_language.verbalization._example_domain.Robot"
    )

    def documented_runner(self) -> EqlQueryRunner:
        """
        A runner over a class from a package whose documentation is published.
        """
        return EqlQueryRunner(domains=[QueryDomain("bot", ExampleRobot, [])])

    def test_a_documented_class_resolves_to_its_autoapi_page(self):
        url = PublishedDocumentationResolver().resolve(
            SourceReference(owner_type=ExampleRobot)
        )

        assert url == self.EXAMPLE_ROBOT_PAGE

    def test_a_documented_attribute_resolves_to_its_own_anchor(self):
        url = PublishedDocumentationResolver().resolve(
            SourceReference(owner_type=ExampleRobot, attribute="battery")
        )

        assert url == self.EXAMPLE_ROBOT_PAGE + ".battery"

    def test_a_class_of_an_undocumented_package_resolves_to_nothing(self):
        assert (
            PublishedDocumentationResolver().resolve(
                SourceReference(owner_type=NamedRecord)
            )
            is None
        )

    def test_the_environment_overrides_the_documentation_site(self, monkeypatch):
        monkeypatch.setenv(DOCUMENTATION_SITE_VARIABLE, "http://localhost:8000/docs/")

        url = PublishedDocumentationResolver.of_environment().resolve(
            SourceReference(owner_type=ExampleRobot)
        )

        assert url.startswith("http://localhost:8000/docs/krrood/autoapi/")

    def test_the_html_links_documented_words_to_their_pages(self):
        verbalization = self.documented_runner().verbalize(
            "an(entity(bot).where(bot.battery > 50))"
        )

        assert 'href="' + self.EXAMPLE_ROBOT_PAGE + '"' in verbalization.html
        assert 'href="' + self.EXAMPLE_ROBOT_PAGE + '.battery"' in verbalization.html

    def test_the_plain_text_stays_free_of_link_markup(self):
        verbalization = self.documented_runner().verbalize(
            "an(entity(bot).where(bot.battery > 50))"
        )

        assert "href" not in verbalization.text
        assert "<a" not in verbalization.text

    def test_undocumented_words_stay_plain_text(self):
        verbalization = make_runner().verbalize(
            "an(entity(record).where(record.score > 1.0))"
        )

        assert "<a" not in verbalization.html


# %% wording a query from its source code
class TestWordingFromCode:
    """
    Presets are worded before they are run, so the runner reads a query's source back as
    English without evaluating it.
    """

    def test_code_is_worded_the_same_as_the_expression_it_builds(self):
        runner = make_runner()
        code = "an(entity(record).where(record.score > 1.0))"
        expected = QueryVerbalization.of_expression(eval(code, runner.namespace()))

        assert runner.verbalize(code) == expected

    def test_code_that_does_not_build_is_not_worded(self):
        assert make_runner().verbalize("definitely not python (((") is None

    def test_a_name_the_runner_does_not_know_is_not_worded(self):
        assert make_runner().verbalize("an(entity(shape))") is None

    def test_code_that_builds_something_other_than_a_query_is_not_worded(self):
        assert make_runner().verbalize("1 + 1") is None

    def test_wording_leaves_the_code_runnable(self):
        runner = make_runner()
        runner.verbalize("an(entity(record))")

        assert runner.run("an(entity(record))").ok


# %% verbalizing what cannot be verbalized
class TestUnverbalizableQueries:
    """
    An uncovered construct makes krrood raise rather than degrade to a class name, so a
    grammar gap would otherwise turn an answerable query into an error.
    """

    @pytest.fixture()
    def no_grammar_rule_covers_it(self, monkeypatch):
        def raise_unverbalizable(self, expression, *arguments, **keyword_arguments):
            raise UnverbalizableExpressionError(node=expression)

        monkeypatch.setattr(EQLVerbalizer, "build", raise_unverbalizable)

    def test_an_expression_krrood_cannot_word_has_no_verbalization(
        self, no_grammar_rule_covers_it
    ):
        namespace = make_runner().namespace()

        expression = eval("an(entity(record))", namespace)

        assert QueryVerbalization.of_expression(expression) is None

    def test_the_answer_is_still_returned_in_full(self, no_grammar_rule_covers_it):
        """
        A sentence is a nicety; failing to word one must not cost the caller its answer.
        """
        result = make_runner().run("an(entity(record))")

        assert result.count == 3
        assert result.verbalization is None


# %% the runner attaches it to the answer
class TestTheAnswerCarriesTheQuestion:
    def test_a_run_answer_reads_its_own_query_back(self):
        result = make_runner().run("an(entity(record).where(record.score > 1.0))")

        assert result.verbalization is not None
        assert "NamedRecord" in result.verbalization.text

    def test_the_payload_carries_both_renderings(self):
        result = make_runner().run("an(entity(record))")

        payload = result.to_payload()
        assert payload["verbalization"]["text"] == result.verbalization.text
        assert payload["verbalization"]["html"] == result.verbalization.html

    def test_an_answer_that_was_never_a_query_has_none(self):
        """
        A runner can be handed a plain list under ``extra_names``; there is no
        expression to word, and the answer still stands on its own.
        """
        runner = EqlQueryRunner(
            domains=[QueryDomain("record", NamedRecord, make_records())],
            extra_names={"records": make_records()},
        )

        result = runner.run("records")

        assert result.count == 3
        assert result.verbalization is None
        assert result.to_payload()["verbalization"] is None
