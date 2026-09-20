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
`Narration.report()` prints where each line falls and the silence after it. Where a
scene has steps that should come as the narration reaches them -- the views of the
look, the steps of the taxonomy slide, the questions over the grid -- the assembly
measures the lines with the voice (`starts_of`) and times the scene to them, so the
picture and the speech cannot drift apart.

The narration goes into the mp4 as AAC. The subtitles are burned into the picture by
default (`Subtitled`, drawn into the band every scene leaves clear at the bottom,
`Resolution.stage_height`); `--subtitles soft` puts them in as a text track the
viewer can switch off (on by default) plus the same cues as a SubRip file next to the
mp4 instead. Either way the cues are cut from the written lines at clause ends where
possible, one row of at most 42 characters each.

### The robot's camera

Every picture of the robot's camera is shown through a `Framing` from `footage.py`:
`TABLE_FRAMING` cuts the floor and the stand off the full HD recording and keeps the
table alone at sixteen by nine, for the grid and the attribution trials; the film of
the robot carrying the plan out keeps `ACTING_FRAMING`, which trims less so the arm
stays in. A framing is applied to the drawn picture, after any findings are drawn on
it, so nothing in the camera's pixel coordinates has to move.

Where someone filmed the framework demo by hand from beside the table, the film is
kept among the run's files as `hand_held_camera.mp4` (`HandHeldFilm.beside` finds it),
and `SideBySide` plays it next to the robot's own camera in step, both at one speed
from one moment of the run: `HAND_HELD_OFFSET` in `icra_video.py` says how long after
the robot's recording the hand-held one started, read off the moment the gripper is
lowered into the hole in both. Without such a film the robot's camera plays alone.

### Reading the plan

The figure's typst source states, with its geometry, where each open slot of the plan
and each of its two actions lie, and where each answer is written into the resolved
plan. `Magnified` grows such a stretch out of the figure to where it can be read,
holds it and shrinks it back: each backend's sub-query is magnified before its
close-up, and its answer in the resolved plan after. `Scrolled` grows the whole plan
out to a window it is read through and scrolls it down at `ReadingStop`s the assembly
times to the lines about the plan: the plan rests at its top while the line introduces
it, and has scrolled to its end once the insertion has been named.

The queries put to long-term memory over the grid are written in the match syntax,
`a(Type)` for each class with the event named where it is matched
(`pickup := a(PickUpEvent)`); the second question marks what changed from the first
(`changed_spans` in `canvas.py`), so the one variable that differs is seen at a glance.

## How it is built

- `timeline.py` -- a `Scene` says how long it lasts and what it shows at any moment;
  a `Timeline` lays scenes end to end, dissolving each into the next, and reads them
  out as frames at one rate.
- `encoding.py` -- `H264Encoder` writes a timeline to an mp4 no larger than a byte
  budget, in two passes; `Muxer` joins the narration (and a subtitle track, where
  they are not burned in) to it; `SubmissionLimits` checks the file the way the call
  for papers states the limits.
- `narration.py` -- a `Line` as written and as spoken, a `Voice` that says it,
  `Storyboard` pairing scenes with the lines that start with them, `Narration`,
  every line placed in time, checked, laid on a soundtrack and cut into subtitles,
  and `Subtitled`, a timeline with those subtitles drawn in.
- `slides.py` and `taxonomy.py` -- the title, text and closing slides, and the slide
  that shows an example query, the tree of backend kinds under it and the choice
  between them, building up as the narration reaches each.
- `canvas.py` -- where things go and how they are drawn and written; `CodeTypesetting`
  writes a line of Python coloured piece by piece as an editor would, with any stretch
  marked behind as a highlighter would.
- `figure.py` and `stages.py` -- the paper's framework figure, compiled from its own
  typst source with a `video` input that says how many backends have answered and
  which slot is being answered now, and what the panels are titled where the video
  calls the backends by their class names; `Spotlight` grows a backend's work out of
  its panel of the figure, names the backend on a tab over it, and shrinks it back
  once answered; `Magnified` does the same for a stretch of the figure itself, and
  `Scrolled` for one too tall to read at once.
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
  a time-lapse, beside a hand-held film of the same run where there is one, and as a
  grid of the perturbation episodes with the look's
  findings drawn while the robot stands still. Each tile stands on its last frame once
  its recording has ended; long-term memory is asked over the grid which episodes the
  cube moved in and which the robot picked it up in, as the narration reaches the
  questions and while the recordings still play: the questions are put to the results
  database through the query language when the scene is built, and the tiles each
  answer names are lit.
- `icra_video.py` -- the scenes in order with their lines, and the command line.
