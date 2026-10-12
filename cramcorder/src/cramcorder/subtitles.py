"""
Subtitles: a line cut into pieces that each fit the room a player gives them, and the
SubRip file they are written to.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta
from itertools import product

from typing_extensions import Iterator, Sequence

# %% a subtitle


@dataclass(frozen=True)
class SubtitleCue:
    """
    One subtitle: a piece of a line, shown for a while.
    """

    start: timedelta
    """
    When it appears, from the video's start.
    """

    end: timedelta
    """
    When it goes.
    """

    text: str
    """
    What it shows.
    """

    def rows(self, room: SubtitleRoom) -> list[str]:
        """
        :param room: How much text one subtitle may show.
        :return: The text on one row where it fits, else on two as even as the words
            allow.
        """
        if len(self.text) <= room.characters_per_row:
            return [self.text]
        words = self.text.split()
        for cuts in room.even_cuts(words, 2):
            halves = cuts.parts(words)
            if all(len(half) <= room.characters_per_row for half in halves):
                return halves
        return SubtitleRoom.packed(words, room.characters_per_row)

    @property
    def timestamps(self) -> str:
        """
        The moments it appears and goes as SubRip writes them: ``HH:MM:SS,mmm``.
        """
        return f"{self._timestamp(self.start)} --> {self._timestamp(self.end)}"

    @staticmethod
    def _timestamp(moment: timedelta) -> str:
        """
        :param moment: A moment of the video.
        :return: It as SubRip writes it, ``HH:MM:SS,mmm``.
        """
        milliseconds = round(moment.total_seconds() * 1000)
        hours, rest = divmod(milliseconds, 3_600_000)
        minutes, rest = divmod(rest, 60_000)
        whole, milliseconds = divmod(rest, 1000)
        return f"{hours:02d}:{minutes:02d}:{whole:02d},{milliseconds:03d}"


# %% where words are cut


@dataclass(frozen=True)
class WordCuts:
    """
    Where a run of words is cut into parts.
    """

    last_words: tuple[int, ...]
    """
    The index of the word each part but the last ends with, in order.
    """

    def parts(self, words: Sequence[str]) -> list[str]:
        """
        :param words: Words, in order.
        :return: The parts they are cut into.
        """
        parts: list[str] = []
        begin = 0
        for last_word in self.last_words:
            parts.append(" ".join(words[begin : last_word + 1]))
            begin = last_word + 1
        parts.append(" ".join(words[begin:]))
        return parts


# %% the room a subtitle has


@dataclass(frozen=True)
class SubtitleRoom:
    """
    How much text one subtitle may show: so many rows of so many characters.
    """

    characters_per_row: int
    """
    The most characters a player shows on one row.
    """

    rows: int
    """
    How many rows a subtitle may take.
    """

    cuts_tried: int = 3
    """
    How many places near each even cut are tried, nearest first, before one more part.
    """

    clause_end_pattern: re.Pattern[str] = re.compile(r"[.;:?!,—]$")
    """
    A word a subtitle had better end after: one that ends a clause with its punctuation.
    """

    sentence_break_pattern: re.Pattern[str] = re.compile(r"(?<=[.?!])\s+")
    """
    Where a written line falls into sentences.
    """

    @classmethod
    def of_player(cls) -> SubtitleRoom:
        """
        :return: What a player's own text shows at a glance: one row of 42 characters,
            so that its text size, which differs from player to player, stays inside the
            band the scenes leave clear.
        """
        return cls(characters_per_row=42, rows=1)

    @classmethod
    def burned_in(cls) -> SubtitleRoom:
        """
        :return: What a subtitle burned into the picture shows: two rows of the band the
            scenes keep clear, so that a whole clause is read at a time rather than
            pieces that switch faster than they are read; the rows are as wide as the
            longest sentence said whole needs.
        """
        return cls(characters_per_row=72, rows=2)

    def holds(self, text: str) -> bool:
        """
        :param text: A piece of text.
        :return: Whether it fits in the rows, broken between words.
        """
        return len(self.packed(text.split(), self.characters_per_row)) <= self.rows

    def evenly(self, text: str) -> list[str]:
        """
        :param text: A piece of text.
        :return: It, as it is if it fits, else cut between words into the fewest parts
            that each fit, as even in length as the words allow, each cut moved to a
            clause end where one lies near.
        """
        words = text.split()
        if self.holds(text):
            return [text]
        for parts in range(2, len(words) + 1):
            for cuts in self.even_cuts(words, parts):
                cut = cuts.parts(words)
                if all(self.holds(part) for part in cut):
                    return cut
        return words

    def pieces(self, written: str) -> list[str]:
        """
        :param written: A written line.
        :return: It cut into pieces that each fit the room: sentence by sentence, each
            cut into the fewest even parts that fit, at clause ends where one lies near
            enough, and short sentences joined where they fit together.
        """
        pieces: list[str] = []
        for sentence in self.sentence_break_pattern.split(written):
            for part in self.evenly(sentence):
                if pieces and self.holds(pieces[-1] + " " + part):
                    pieces[-1] += " " + part
                else:
                    pieces.append(part)
        return pieces

    def even_cuts(self, words: Sequence[str], parts: int) -> Iterator[WordCuts]:
        """
        :param words: Words, in order.
        :param parts: How many parts to cut them into.
        :return: The places the words may be cut, likeliest first; a cut after a word
            that ends a clause within a fifth of a part's length of where the cut would
            fall comes before any other.
        """
        ends = [
            sum(len(word) + 1 for word in words[: index + 1])
            for index in range(len(words))
        ]
        share = ends[-1] / parts
        choices: list[list[int]] = []
        for number in range(1, parts):
            target = share * number
            candidates = sorted(
                range(number - 1, len(words) - (parts - number)),
                key=lambda index: (
                    not (
                        self.ends_a_clause(words[index])
                        and abs(ends[index] - target) <= share / 5
                    ),
                    abs(ends[index] - target),
                ),
            )
            choices.append(candidates[: self.cuts_tried])
        for cuts in product(*choices):
            if all(earlier < later for earlier, later in zip(cuts, cuts[1:])):
                yield WordCuts(cuts)

    def ends_a_clause(self, word: str) -> bool:
        """
        :param word: A word.
        :return: Whether a subtitle had better end after it.
        """
        return bool(self.clause_end_pattern.search(word))

    @staticmethod
    def packed(words: Sequence[str], longest: int) -> list[str]:
        """
        :param words: Words, in order.
        :param longest: The most characters a piece takes.
        :return: The words packed into pieces no longer than that, in order.
        """
        pieces: list[str] = []
        for word in words:
            if pieces and len(pieces[-1]) + 1 + len(word) <= longest:
                pieces[-1] += " " + word
            else:
                pieces.append(word)
        return pieces


# %% the file they are written to


@dataclass(frozen=True)
class SubRipFile:
    """
    Subtitles in the SubRip format every player reads.
    """

    cues: Sequence[SubtitleCue]
    """
    The subtitles, in order.
    """

    room: SubtitleRoom
    """
    How the rows of each are broken.
    """

    @property
    def text(self) -> str:
        """
        The file's contents.
        """
        return "".join(
            f"{number}\n{cue.timestamps}\n" + "\n".join(cue.rows(self.room)) + "\n\n"
            for number, cue in enumerate(self.cues, start=1)
        )
