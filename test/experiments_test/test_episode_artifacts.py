"""
Tests for what an episode keeps outside the database.

The rows say what happened; these are what a reader can look at, so what is asserted
here is that an episode's video, its own files and its transcript go somewhere addressed
by its identifier and come back from it.
"""

from __future__ import annotations

from pathlib import Path

import numpy
import pytest
import trimesh
from semantic_digital_twin.adapters.mujoco_video_recording import RecordedVideo
from semantic_digital_twin.world_description.mesh_file_storage import MeshFileStorage

from experiments.episodes.artifacts import (
    ARTIFACT_DIRECTORY_ENVIRONMENT_VARIABLE,
    MESH_DIRECTORY_NAME,
    ArtifactDirectory,
    ArtifactNotKept,
    EpisodeArtifact,
    Transcript,
    configured_artifact_directory,
    configured_mesh_directory,
    keep_mesh,
)
from experiments.episodes.episode import Episode, RecordedQuery, RecordedTrial
from experiments.questions.working_memory import ObjectColours, ObjectsSeen
from experiments.scenarios.trial import TrialOutcome

from .test_episode_recording import sorting_episode

# %% what the tests record

FRAME_SIDE = 16
"""
Pixel width and height of the frames the test videos are made of, kept small because
what is asserted is that the file was written rather than what it shows.
"""


def coloured_frames(count: int) -> list[numpy.ndarray]:
    """
    A run of frames that differ from one another, so an encoder has something to encode.

    :param count: How many frames to make.
    """
    return [
        numpy.full((FRAME_SIDE, FRAME_SIDE, 3), index * 10, dtype=numpy.uint8)
        for index in range(count)
    ]


def answered_trial(episode: Episode, queries: list[RecordedQuery]) -> RecordedTrial:
    """
    One finished trial of the given episode that was asked the given questions.

    :param episode: The episode the trial belongs to.
    :param queries: The questions asked while the trial ran.
    """
    return RecordedTrial(
        episode=episode,
        outcome=TrialOutcome.SUCCEEDED,
        duration=2.0,
        queries=queries,
    )


def two_answered_trials(episode: Episode) -> list[RecordedTrial]:
    """
    The two trials of one run, each asked a question of its own.

    :param episode: The episode both trials belong to.
    """
    return [
        answered_trial(
            episode,
            [
                RecordedQuery(
                    role_taker=ObjectsSeen(),
                    answer="The cube.",
                    latency=0.02,
                    moment=1.5,
                )
            ],
        ),
        answered_trial(
            episode,
            [
                RecordedQuery(
                    role_taker=ObjectColours(),
                    answer="The square one.",
                    latency=0.03,
                    moment=1.75,
                )
            ],
        ),
    ]


# %% where an episode's artifacts are kept


def test_an_episode_keeps_its_artifacts_under_its_own_identifier(tmp_path):
    """
    A row references its artifacts by carrying the identifier, so the identifier has to
    be what addresses them.
    """
    episode = sorting_episode()

    artifacts = ArtifactDirectory(path=tmp_path).open_for(episode)

    assert artifacts.directory == tmp_path / episode.identifier


def test_two_episodes_keep_their_artifacts_apart(tmp_path):
    directory = ArtifactDirectory(path=tmp_path)

    first = directory.open_for(sorting_episode())
    second = directory.open_for(sorting_episode())

    assert first.directory != second.directory


def test_the_directory_artifacts_are_kept_in_is_read_from_the_environment(
    monkeypatch, tmp_path
):
    """
    A corpus run records somewhere other than a developer's home directory, and is
    pointed there the way the results database is.
    """
    monkeypatch.setenv(ARTIFACT_DIRECTORY_ENVIRONMENT_VARIABLE, str(tmp_path))

    assert configured_artifact_directory() == tmp_path


# %% the meshes a recorded world refers to


def test_a_kept_mesh_is_written_beside_the_artifacts(monkeypatch, tmp_path):
    """
    A recorded world refers to its meshes by path and is read back by a later process,
    so a kept mesh cannot live in the directory this process removes when it exits.
    """
    monkeypatch.setenv(ARTIFACT_DIRECTORY_ENVIRONMENT_VARIABLE, str(tmp_path))

    mesh = keep_mesh(trimesh.creation.box((0.1, 0.1, 0.1)))

    written_to = Path(mesh.filename)
    assert written_to.is_file()
    assert written_to.is_relative_to(configured_mesh_directory())
    assert configured_mesh_directory() == tmp_path / MESH_DIRECTORY_NAME
    assert not written_to.is_relative_to(MeshFileStorage().root)


# %% the video


def test_a_video_is_read_back_from_the_episode_that_kept_it(tmp_path):
    episode = sorting_episode()
    artifacts = ArtifactDirectory(path=tmp_path).open_for(episode)

    artifacts.keep_video(RecordedVideo(frames=coloured_frames(5), frames_per_second=30))

    assert artifacts.video == artifacts.directory / EpisodeArtifact.VIDEO
    assert artifacts.video.stat().st_size > 0


def test_an_episode_that_kept_no_video_says_which_episode_is_missing_one(tmp_path):
    episode = sorting_episode()
    artifacts = ArtifactDirectory(path=tmp_path).open_for(episode)

    with pytest.raises(ArtifactNotKept) as raised:
        artifacts.video

    assert raised.value.episode_identifier == episode.identifier
    assert raised.value.artifact is EpisodeArtifact.VIDEO


# %% the run's own files


def test_the_runs_own_files_are_read_back_from_the_episode(tmp_path):
    """
    The world a run built and the scene it wrote are files it produced, and the episode
    is what they are found through afterwards.
    """
    scene = tmp_path / "scene.xml"
    scene.write_text("<mujoco/>")
    artifacts = ArtifactDirectory(path=tmp_path / "artifacts").open_for(
        sorting_episode()
    )

    artifacts.keep_file(scene)

    assert [kept.name for kept in artifacts.run_files] == ["scene.xml"]
    assert artifacts.run_files[0].read_text() == scene.read_text()


def test_a_kept_file_survives_its_original_being_removed(tmp_path):
    """
    A run's own files live wherever the run put them; keeping one has to copy it, or the
    episode holds a reference to something already deleted.
    """
    scene = tmp_path / "scene.xml"
    scene.write_text("<mujoco/>")
    artifacts = ArtifactDirectory(path=tmp_path / "artifacts").open_for(
        sorting_episode()
    )

    artifacts.keep_file(scene)
    scene.unlink()

    assert artifacts.run_files[0].read_text() == "<mujoco/>"


def test_an_episode_that_kept_no_files_reports_none(tmp_path):
    """
    Unlike the video and the transcript, the run's files are a collection, and a run
    that produced none is not a run missing something.
    """
    artifacts = ArtifactDirectory(path=tmp_path).open_for(sorting_episode())

    assert artifacts.run_files == []


# %% the transcript


def test_the_transcript_carries_every_question_of_every_trial_with_its_answer():
    episode = sorting_episode()
    trials = two_answered_trials(episode)

    rendered = Transcript(episode=episode, trials=trials).render()

    for trial in trials:
        for query in trial.queries:
            assert query.text in rendered
            assert query.answer in rendered


def test_the_transcript_names_the_episode_it_transcribes():
    """
    A transcript is read on its own, away from the row it belongs to, so it has to say
    which run it is of.
    """
    episode = sorting_episode()

    rendered = Transcript(episode=episode, trials=[]).render()

    assert episode.identifier in rendered
    assert episode.scenario_name in rendered


def test_the_transcript_is_read_back_from_the_episode_that_kept_it(tmp_path):
    episode = sorting_episode()
    artifacts = ArtifactDirectory(path=tmp_path).open_for(episode)
    transcript = Transcript(episode=episode, trials=two_answered_trials(episode))

    artifacts.keep_transcript(transcript)

    assert artifacts.transcript == artifacts.directory / EpisodeArtifact.TRANSCRIPT
    assert artifacts.transcript.read_text() == transcript.render()


def test_an_episode_that_kept_no_transcript_says_which_episode_is_missing_one(tmp_path):
    episode = sorting_episode()
    artifacts = ArtifactDirectory(path=tmp_path).open_for(episode)

    with pytest.raises(ArtifactNotKept) as raised:
        artifacts.transcript

    assert raised.value.artifact is EpisodeArtifact.TRANSCRIPT


# %% all three of one run


def test_a_two_trial_episode_keeps_its_video_its_files_and_its_transcript(tmp_path):
    """
    The three together are what a reader - or a vision-language model - is given of one
    run, so one run has to be able to keep all three at once.
    """
    episode = sorting_episode()
    trials = two_answered_trials(episode)
    scene = tmp_path / "scene.xml"
    scene.write_text("<mujoco/>")
    artifacts = ArtifactDirectory(path=tmp_path / "artifacts").open_for(episode)

    artifacts.keep_video(RecordedVideo(frames=coloured_frames(4), frames_per_second=30))
    artifacts.keep_file(scene)
    artifacts.keep_transcript(Transcript(episode=episode, trials=trials))

    assert artifacts.video.stat().st_size > 0
    assert [kept.name for kept in artifacts.run_files] == ["scene.xml"]
    assert trials[1].queries[0].answer in artifacts.transcript.read_text()


def test_a_directory_the_run_produced_is_kept_whole(tmp_path):
    """
    A bag is a directory of files rather than one file, and is kept as one run file with
    everything in it.
    """
    bag = tmp_path / "run_20260911_120000"
    bag.mkdir()
    (bag / "metadata.yaml").write_text("rosbag2_bagfile_information: {}")
    (bag / "run_0.mcap").write_bytes(b"mcap")
    artifacts = ArtifactDirectory(path=tmp_path / "artifacts").open_for(
        sorting_episode()
    )

    kept = artifacts.keep_directory(bag)

    assert [kept.name for kept in artifacts.run_files] == [bag.name]
    assert sorted(path.name for path in kept.iterdir()) == [
        "metadata.yaml",
        "run_0.mcap",
    ]
    assert (kept / "run_0.mcap").read_bytes() == b"mcap"
