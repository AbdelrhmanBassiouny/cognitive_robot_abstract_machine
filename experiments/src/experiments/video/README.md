# The supplementary video

`experiments.video` cuts the paper's supplementary video from what the robot recorded:
the framework demo episode and the six perturbation episodes, read back from the
results database and the episode artifacts, and writes it out as an mp4 within the
conference's limits.

## Rendering it

```bash
export MONTESSORI_SORTING_DATABASE_URI=postgresql+psycopg://semantic_digital_twin:montessori@localhost:5432/montessori_sorting_results
export EPISODE_ARTIFACTS_DIRECTORY=/path/to/reproduction_package/episode-artifacts
python -m experiments.video.icra_video --output video.mp4
```

`--preview` renders a shorter, rougher version for looking at. Everything that takes a
while -- the look run over the recordings' frames, the pictures of the twin, the
decoded camera streams -- is kept under `EXPERIMENTS_VIDEO_CACHE`
(`~/.cache/experiments/video` by default), so a second render is mostly encoding.

The words the slides carry -- the paper's title and submission number, and what the
robot is called on screen -- are `VideoScript` in `script.py`; `--paper-id` overrides
the number. What the narrator says is `NarrationLines` in the same file.

### The narration

The lines are spoken by the Kokoro speech model, run on this machine (`kokoro-onnx`;
the model and its voices lie under `~/.cache/experiments/video/voice/`, downloaded
once from the model's release files). `--voice` picks any of its voices (`af_heart` by
default) and `--speech-speed` its pace; a different synthesizer is anything with a
`speaks(text)` method given to `VideoAssembly` as its `voice`. Every line said is
kept under the cache, so a video is rebuilt with the very same speech.

A line belongs to the scene it starts with and may run on into the scenes that follow.
A slide grows to hold its line; a close-up keeps the length of what it shows, and a
line that is still being said when the next begins is refused (`NarrationOverrun`),
so the scene lengths in `icra_video.py` are tuned to the lines.
`Narration.report()` prints where each line falls and the silence after it.

The narration goes into the mp4 as AAC, and the subtitles as a text track the viewer
can switch off (on by default), plus the same cues as a SubRip file next to the mp4.
The cues are cut from the written lines at clause ends where possible, one row of at
most 42 characters each, since players differ in how large they draw them. Every
scene leaves the bottom 12 % of the frame clear (`Resolution.stage_height`), which is
where players draw subtitles, so nothing is covered.

### The robot's camera

Every picture of the robot's camera is shown through `TABLE_FRAMING` in
`footage.py`, which cuts the floor and the stand off the full HD recording and keeps
the table alone at sixteen by nine. It is applied to the drawn picture, after any
findings are drawn on it, so nothing in the camera's pixel coordinates has to move.

## How it is built

- `timeline.py` -- a `Scene` says how long it lasts and what it shows at any moment;
  a `Timeline` lays scenes end to end, dissolving each into the next, and reads them
  out as frames at one rate.
- `encoding.py` -- `H264Encoder` writes a timeline to an mp4 no larger than a byte
  budget, in two passes; `Muxer` joins the narration and the subtitles to it;
  `SubmissionLimits` checks the file the way the call for papers states the limits.
- `narration.py` -- a `Line` as written and as spoken, a `Voice` that says it,
  `Storyboard` pairing scenes with the lines that start with them, and `Narration`,
  every line placed in time, checked, laid on a soundtrack and cut into subtitles.
- `figure.py` and `stages.py` -- the paper's framework figure, compiled from its own
  typst source with a `video` input that says how many backends have answered and
  which slot is being answered now, and what the panels are titled where the video
  calls the backends by their class names; `Spotlight` grows a backend's work out of
  its panel of the figure, names the backend on a tab over it, and shrinks it back
  once answered.
- `perception.py`, `twin.py`, `grasp.py`, `rules.py` -- one scene per backend, each
  driving the backend's own code on the recorded run: the narrowing, the predicate's
  boxes, the model's samples, the rule tree's trace. The twin is drawn dressed as
  itself -- the board from its own mesh with its holes cut through the lid, in its
  wood, and the table in its metal -- while the relation is still read off the plain
  box the look spawned. The grasp scene samples under an
  `ApproachPrior`, a model registry that favours the direction the run took (the run
  itself sampled under the backend's uniform default); the rule tree is drawn as
  ripple-down rules, each node its condition over its conclusion, an `else` branch
  down to the next rule and an `except` branch off the side where a correction would
  hang.
- `attribution.py` -- the robot's camera beside the two timelines of a trial, the
  events the monitor reported over the actions the plan ran, growing together until
  the recorded questions "Which objects recently moved?" and "Did you move them?"
  take the screen and are answered off the events, checked against the recorded
  answers.
- `footage.py`, `perturbations.py` and `long_term.py` -- the robot's camera played as
  a time-lapse, alone and as a grid of the perturbation episodes with the look's
  findings drawn while the robot stands still. Each tile stands on its last frame once
  its recording has ended, and once every one has, long-term memory is asked over the
  grid which episodes the cube moved in and which the robot picked it up in: the
  questions are put to the results database through the query language when the scene
  is built, and the tiles each answer names are lit.
- `icra_video.py` -- the scenes in order with their lines, and the command line.
