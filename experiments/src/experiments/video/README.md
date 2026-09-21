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

The words the slides carry -- the paper's title, the three chapters' claims, the hero
frame's principle, the results table, the one line over the grid, the footnote on the
resolved plan and what the robot is called on screen -- are `VideoScript` in
`script.py`. What the narrator says is `NarrationLines` in the same file.

The video runs in three chapters, one per contribution of the paper (`chapters.py`):
each opens with its claim large over its first shot, which then shrinks into a pill in
the top left corner that stays for the chapter, with a dot per chapter marking how far
along the video is. Every frame keeps the same zones: the pill top left, the speed
badge top right on footage, the caption on a fixed baseline at the bottom -- dark on
the page, white on a band shaded towards black wherever footage fills the frame. Three
letter sizes (`canvas.py`): 40 px for claims and the hero text, 28 px for captions,
body and table cells, 20 px for labels. The backends' colours are used for backends
alone; one accent (the figure's answer magenta) marks answers and what to look at, and
the rest is greyscale.

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
look, the parts of the query slide, the questions over the grid -- the assembly
measures the lines with the voice (`starts_of`) and times the scene to them, so the
picture and the speech cannot drift apart. Where a part must come up at a word inside
a line (the example's lines as each is named, its `...` at "three dots"), the moment
is measured on the spoken line once and kept as a constant beside the scene.

The narration goes into the mp4 as AAC. The subtitles are burned into the picture by
default (`Subtitled`, drawn into the band every scene leaves clear at the bottom,
`Resolution.stage_height`); `--subtitles soft` puts them in as a text track the
viewer can switch off (on by default) plus the same cues as a SubRip file next to the
mp4 instead. Either way the cues are cut from the written lines at clause ends where
possible; burned in, a cue takes two rows of the band (`BURNED_IN_ROOM`, up to 58
characters a row, the letters' size being the video's own), so a whole clause is read
at a time; in the soft track, whose text size is the player's, one row of at most 42
characters.

### The robot's camera

Every picture of the robot's camera is shown through a `Framing` from `footage.py`:
`TABLE_FRAMING` cuts the floor and the stand off the full HD recording and keeps the
table alone at sixteen by nine, for the grid, the attribution trials and the inset. A
framing is applied to the drawn picture, after any findings are drawn on it, so
nothing in the camera's pixel coordinates has to move.

Someone filmed the framework demo by hand from beside the table; the film is kept
among the run's files as `hand_held_camera.mp4` (`HandHeldFilm.beside` finds it). It
stands upright, and `FULL_BLEED_FRAMING` keeps the widest sixteen-by-nine window of
it, over the gripper, the pieces and the board, so that `FullBleedFootage` fills the
whole frame with it, the robot's own camera small in the bottom right corner in step
(`HAND_HELD_OFFSET` in `icra_video.py` says how long after the robot's recording the
hand-held one started, read off the moment the gripper is lowered into the hole in
both) and the speed-up badged top right. The inset first holds what the look found on
the robot's picture, since the look ran before the hand-held film starts. The title
stands over the same film, where the cube goes through the hole (`TitleOverFootage`).

### Reading the plan

The plan is written out twice (`plan.py`, `PlanOverview` in `stages.py`): as stated,
in two columns so that it reads at the video's size, with everything but its three
open parts dimmed once the line names them; and resolved with what the run read, with
the footnote that the paper's figure shows stand-ins. Between the two, each backend
works in one fixed layout (`BackendAtWork`): the sub-query in a box on the left
(`statements.py`, the plan's sub-queries as stated and as answered), the backend's
panel on the right with its title bar in the backend's colour and its one visual, and,
once the backend has answered, its answer on a chip that moves into the open slot of
the sub-query, which then reads answered -- the same motion for all four. A backend's
scene cuts in rather than dissolving, since the box would otherwise crossfade two
different texts.

The query put to long term memory over the grid is written in the match syntax,
`a(Type)` for each class with the event named where it is matched
(`pickup := a(PickUpEvent)`), and is answered by running it over the results database
when the scene is built, kept to the seven episodes the paper's results are over
(`PAPER_EPISODES`), which is what running it over a memory holding those alone would
give.

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
- `chapters.py` -- `ChapterMark` draws a chapter's claim large and its pill;
  `InChapter` wraps a scene with them.
- `slides.py` and `query_slide.py` -- the results table and the end card, and the
  introduction in three beats on one slide: the plan's grasp query with its `...`
  marked and what it says in words; the query shrunk to the top with the backends by
  kind under it and the choice among them; the hero frame, the query above a divider
  and the paper's principle under it in large type.
- `canvas.py` -- where things go and how they are drawn and written, the three letter
  sizes and the margin; `CodeTypesetting` writes a line of Python coloured piece by
  piece as an editor would, with any stretch marked behind as a highlighter would.
- `plan.py`, `statements.py` and `stages.py` -- the plan's lines as stated and as
  resolved, the four sub-queries as stated and as answered, and the scenes that show
  them: `PlanOverview` and `BackendAtWork`. `figure.py` compiles the paper's framework
  figure from its own typst source and states what the run read (`RunReadings`), from
  which the resolved lines are taken.
- `perception.py`, `twin.py`, `grasp.py`, `rules.py` -- one visual per backend, each
  driving the backend's own code on the recorded run: the narrowing as a row of four
  pictures, the predicate's boxes on the twin drawn close over the cube, the model's
  bars and samples under the registry the run used (every direction as likely as the
  next), and the rule tree elided to the rule that fired and the last rule with the
  concluded hole ringed on the board.
- `attribution.py` -- the robot's camera filling the frame with the trial's timeline
  on a panel over it: the rows the questions are about (the motions, the pick-ups and
  placings) and one strip for everything the robot ran; the recorded questions "Which
  objects recently moved?" and "Did you move them?" take a card over the footage and
  are answered off the events, checked against the recorded answers, the asking ruled
  onto the timeline at its recorded moment.
- `footage.py`, `perturbations.py` and `long_term.py` -- the robot's camera and the
  hand-held film played faster with the speed-up badged, and the grid of the
  perturbation episodes (`GridSequence`) with the look's findings drawn while the
  robot stands still and each tile badged with its phase -- a person perturbing the
  scene (from the trial telling them to until the film shows the scene still again),
  the robot perceiving, or the robot executing; two tiles are brought to the front in
  turn and replayed slower from just before the person moves, the rest paused and
  dimmed; then long term memory is asked which episodes the robot picked the cube up
  in, and the tiles its answer names are outlined.
- `icra_video.py` -- the scenes in order with their lines, in three chapters, and the
  command line.
