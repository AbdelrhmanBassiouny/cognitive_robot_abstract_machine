import threading

from krrood.entity_query_language.backends import EntityQueryLanguageBackend
from krrood.entity_query_language.factories import an, entity, variable
from krrood.entity_query_language.query_observation import QueryObservation

from ..dataset.observed_queries import (
    ObservedMoment,
    QueryLog,
    Shelf,
    WideShelvesFoundOnIteration,
)

# %% shelves


def shelves() -> list[Shelf]:
    return [Shelf(0.5), Shelf(1.2), Shelf(2.0)]


def wide_shelves_query(domain):
    shelf = variable(Shelf, domain=domain)
    return an(entity(shelf).where(shelf.width >= 1.0))


# %% a query asked and answered


def test_an_observed_query_is_reported_asked_then_answered_with_its_answers():
    log = QueryLog()
    query = wide_shelves_query(shelves())
    with QueryObservation().observed_by(log):
        answers = query.tolist()
    assert [(event.moment, event.answer_count) for event in log.events] == [
        (ObservedMoment.ASKED, 0),
        (ObservedMoment.ANSWERED, len(answers)),
    ]
    asked = log.events[0].asked
    assert asked.query is query
    assert isinstance(asked.backend, EntityQueryLanguageBackend)
    assert asked.answers == answers
    assert asked.is_answered


def test_a_query_whose_first_answer_is_taken_is_answered_with_that_answer():
    log = QueryLog()
    query = wide_shelves_query(shelves())
    with QueryObservation().observed_by(log):
        first = query.first()
    [asked_event, answered_event] = log.events
    assert answered_event.moment is ObservedMoment.ANSWERED
    assert answered_event.asked.answers == [first]


def test_the_asking_frame_is_the_call_that_asked_the_query():
    log = QueryLog()
    with QueryObservation().observed_by(log):
        wide_shelves_query(shelves()).tolist()
    frame = log.events[0].asked.asking_frame
    assert frame.function_name == (
        test_the_asking_frame_is_the_call_that_asked_the_query.__name__
    )


# %% a query asked while another is answered


def test_a_query_asked_while_another_is_answered_names_it_as_its_asker():
    log = QueryLog()
    outer = wide_shelves_query(WideShelvesFoundOnIteration(shelves()))
    with QueryObservation().observed_by(log):
        outer.tolist()
    moments = [(event.moment, event.asked.query is outer) for event in log.events]
    assert moments == [
        (ObservedMoment.ASKED, True),
        (ObservedMoment.ASKED, False),
        (ObservedMoment.ANSWERED, False),
        (ObservedMoment.ANSWERED, True),
    ]
    inner = log.events[1].asked
    assert inner.asker is log.events[0].asked
    assert (inner.depth, inner.asker.depth) == (1, 0)


# %% where queries are not observed


def test_a_query_asked_outside_the_observed_block_is_not_reported():
    log = QueryLog()
    with QueryObservation().observed_by(log):
        pass
    wide_shelves_query(shelves()).tolist()
    assert log.events == []


def test_a_query_asked_in_another_thread_is_not_reported():
    log = QueryLog()
    with QueryObservation().observed_by(log):
        thread = threading.Thread(target=lambda: wide_shelves_query(shelves()).tolist())
        thread.start()
        thread.join()
    assert log.events == []


def test_queries_asked_by_an_observer_are_not_reported_to_it():
    log = QueryLog()
    with QueryObservation().observed_by(log):
        with QueryObservation().unobserved():
            wide_shelves_query(shelves()).tolist()
    assert log.events == []


def test_an_observer_observing_twice_is_told_once():
    log = QueryLog()
    with QueryObservation().observed_by(log), QueryObservation().observed_by(log):
        wide_shelves_query(shelves()).tolist()
    assert [event.moment for event in log.events] == [
        ObservedMoment.ASKED,
        ObservedMoment.ANSWERED,
    ]
