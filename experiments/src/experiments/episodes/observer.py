"""
What a trial's runner cannot see, collected as it happens: the event monitor's ticks,
the questions asked, the insertions attempted and the motions run.

The runner knows when a trial starts and ends and what it measured; everything that
happened inside a step reaches the episode through here, and is written onto the trial
once the runner has recorded it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime

from coraplex.plans.plan import Plan
from giskardpy.motion_statechart.motion_statechart import MotionStatechart
from segmind.datastructures.events import DetectionEvent
from typing_extensions import Any, List, Sequence

from experiments.episodes.episode import (
    InsertionAttempt,
    PerformedPlan,
    RecordedMotion,
    RecordedQuery,
    RecordedTrial,
    Tick,
)
from experiments.questions.question_set import QuestionSet

# %% the observer


@dataclass
class EpisodeObserver:
    """
    Collects what happens inside one trial, and hands it over when the trial is
    recorded.

    Moments are measured from the last :meth:`restart`, which a run calls as each trial
    begins so that a tick is stamped against the same start the trial's own log uses.
    """

    ticks: List[Tick] = field(default_factory=list)
    """
    The event monitor's ticks of the trial being observed, in the order they happened.
    """

    queries: List[RecordedQuery] = field(default_factory=list)
    """
    Every query asked of the trial being observed, in the order they were asked.
    """

    plans: List[PerformedPlan] = field(default_factory=list)
    """
    Every plan performed in the trial being observed, in the order they were performed.
    """

    insertion_attempts: List[InsertionAttempt] = field(default_factory=list)
    """
    Every insertion attempted in the trial being observed, in the order they were made.
    """

    motions: List[RecordedMotion] = field(default_factory=list)
    """
    Every motion run in the trial being observed, in the order they ran.
    """

    started_at: float = field(default_factory=time.monotonic)
    """
    Reading of the monotonic clock the trial being observed began at.
    """

    began_at: datetime = field(default_factory=datetime.now)
    """
    When the trial being observed began, on the clock a plan's nodes and a monitor's
    events are stamped with.
    """

    @property
    def elapsed_seconds(self) -> float:
        """
        Seconds between the start of the trial being observed and now.
        """
        return time.monotonic() - self.started_at

    def restart(self) -> None:
        """
        Start observing a new trial, measuring its moments from now.
        """
        self.started_at = time.monotonic()
        self.began_at = datetime.now()

    def tick(self, moment: float, events: Sequence[DetectionEvent]) -> Tick:
        """
        Keep one tick of the event monitor.

        :param moment: Seconds between the start of the trial and the tick.
        :param events: What the tick detected.
        :return: The tick that was kept.
        """
        tick = Tick(moment=moment, events=list(events))
        self.ticks.append(tick)
        return tick

    def ask(
        self, question_set: QuestionSet, source: Any, moment: float
    ) -> List[RecordedQuery]:
        """
        Ask every question of a set, score the answers, and keep the rows.

        :param question_set: The questions to ask.
        :param source: The memory the questions are asked of.
        :param moment: Seconds between the start of the trial and the asking.
        :return: The scored rows, stamped with that moment.
        """
        rows = question_set.answer_and_record(source)
        for row in rows:
            row.moment = moment
        self.queries.extend(rows)
        return rows

    def performed(self, plan: Plan) -> PerformedPlan:
        """
        Keep one plan the robot performed.

        :param plan: The plan, once it has been performed.
        :return: The record that was kept.
        """
        performed = PerformedPlan(plan=plan)
        self.plans.append(performed)
        return performed
    def ran_the_motion(
        self,
        motion_statechart: MotionStatechart,
        start_moment: float,
        end_moment: float,
    ) -> RecordedMotion:
        """
        Keep one motion the trial ran.

        The chart itself is kept rather than a copy of it, so what a question about the
        control program reaches is the history the controller wrote.

        :param motion_statechart: The chart that ran.
        :param start_moment: Seconds between the start of the trial and the moment it
            began.
        :param end_moment: Seconds between the start of the trial and the moment it
            ended.
        :return: The motion that was kept.
        """
        motion = RecordedMotion(
            motion_statechart=motion_statechart,
            start_moment=start_moment,
            end_moment=end_moment,
        )
        self.motions.append(motion)
        return motion

    def attempted(self, insertion_attempt: InsertionAttempt) -> None:
        """
        Keep one insertion attempt.

        :param insertion_attempt: The attempt that was made.
        """
        self.insertion_attempts.append(insertion_attempt)

    def into(self, trial: RecordedTrial) -> RecordedTrial:
        """
        Write everything observed onto a recorded trial, and start afresh for the next.

        :param trial: The trial the runner recorded.
        :return: The same trial, now carrying when it began, its ticks, queries, plans,
            attempts and motions.
        """
        trial.began_at = self.began_at
        trial.ticks = self.ticks
        trial.queries = self.queries
        trial.plans = self.plans
        trial.insertion_attempts = self.insertion_attempts
        trial.motions = self.motions
        self.ticks = []
        self.queries = []
        self.plans = []
        self.insertion_attempts = []
        self.motions = []
        self.restart()
        return trial


# %% the hook an event monitor is given


@dataclass
class ObserverListener:
    """
    What an event monitor tells its detections to, so each becomes a tick of the
    observer stamped with the moment it arrived.
    """

    observer: EpisodeObserver
    """
    The observer the ticks go to.
    """

    def receive(self, events: List[DetectionEvent]) -> None:
        """
        Keep what the monitor just detected as one tick.

        :param events: The newly detected events.
        """
        self.observer.tick(self.observer.elapsed_seconds, events)


# %% the hook a plan is given


@dataclass
class ObserverMotionListener:
    """
    What an executable tells the chart it ran to, so each becomes a motion of the
    observer spanning the moments it ran between.
    """

    observer: EpisodeObserver
    """
    The observer the motions go to.
    """

    def receive(self, motion_state_chart: MotionStatechart, duration: float) -> None:
        """
        Keep the chart that has just run, placing it on the trial's own clock.

        :param motion_state_chart: The chart that ran.
        :param duration: How long it ran, in seconds.
        """
        end_moment = self.observer.elapsed_seconds
        self.observer.ran_the_motion(
            motion_state_chart, end_moment - duration, end_moment
        )
