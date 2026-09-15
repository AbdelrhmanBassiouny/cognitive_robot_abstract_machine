// Framework figure: an underspecified plan resolved by four backends, in Tracy's head.
//
// Reads left to right: the plan with its open slots, the backend that closes each slot,
// the plan with the slots filled. Below it, in one row, the robot thinking and the robot acting.
// Everything a reader sees is data in the CONFIG section: the two plans as nested
// trees, colours, sizes, the look's pictures, the bars, the rules, the image slots.
// The DRAWING section below it only lays that data out.
//
// Build:  python build.py
//         (or, from the repository root: typst compile --root . experiments/doc/figures/framework/framework.typ)
// Paper:  #figure(image("framework.pdf", width: 100%), caption: [...])

// %% CONFIG: sizes ------------------------------------------------------------------

#let W = 18cm                       // total width (IEEE figure*: 17.8 cm text width)
#let font-size = 6.6pt
#let code-size = 6pt
#let label-size = 6pt
#let stroke-width = 0.5pt
#let line-height = 0.3cm            // one line of plan code
#let inset = 0.09cm                 // padding inside a slot box
#let block-gap = 0.06cm             // air above and below a slot box

// %% CONFIG: colours ----------------------------------------------------------------

#let ink = rgb("#1f2328")
#let muted = rgb("#6b7280")
#let hairline = rgb("#cfd4dc")
#let bubble-fill = rgb("#f6f7f9")
#let card-fill = white

// one hue per open slot and the backend that closes it
#let hues = (
  perception: (stroke: rgb("#0f766e"), fill: rgb("#d9f0ec")),
  simulation: (stroke: rgb("#1d4ed8"), fill: rgb("#dbe7fb")),
  probabilistic: (stroke: rgb("#b45309"), fill: rgb("#fdebd0")),
  rules: (stroke: rgb("#6d28d9"), fill: rgb("#ebe4fb")),
)
#let perception = hues.perception
#let simulation = hues.simulation
#let probabilistic = hues.probabilistic
#let rules = hues.rules

// %% CONFIG: fonts ------------------------------------------------------------------

#let text-font = ("Liberation Sans", "Arial", "Helvetica")
#let mono-font = ("Liberation Mono", "DejaVu Sans Mono", "Menlo")

// %% CONFIG: the plans ----------------------------------------------------------------
// A plan is a list of entries, top to bottom. A plain entry is one line of code. A slot
// entry is a box in its backend's hue, indented by `indent` characters, holding `lines`
// and optionally one `nested` slot at its end. `...` is how coraplex leaves a field open.
// A name a later line reuses (`shape`, `grasp`) is whatever the slot above it stood for:
// the plan states the one description in both actions, so both act on the one answer.

#let open-plan = (
  (text: "sequential(["),
  (text: "  a(PickUpAction)("),
  (text: "    arm=LEFT,"),
  (text: "    object_designator="),
  (
    slot: "perception", indent: 6,
    lines: ("a(DetectedMontessoriShape)(", "  category=CUBE)", ".where(", "  Colored(shape, CYAN),"),
    nested: (slot: "simulation", indent: 2, lines: ("SupportedBy(shape, lid)),",)),
  ),
  (text: "    grasp_description="),
  (
    slot: "probabilistic", indent: 6,
    lines: ("a(GraspDescription)(", "  approach_direction=...,", "  vertical_alignment=TOP,", "  end_effector=LEFT_HAND)"),
  ),
  (text: "  ),"),
  (text: "  an(InsertionAction)("),
  (text: "    arm=LEFT,"),
  (text: "    object_designator=shape,"),
  (text: "    grasp_description=grasp,"),
  (text: "    target="),
  (
    slot: "rules", indent: 6,
    lines: ("a(ShapeSortingHole)(", "  shape_category=...)", ".from_(board.apertures)"),
  ),
  (text: "  )"),
  (text: "])"),
)

#let resolved-plan = (
  (text: "sequential(["),
  (text: "  PickUpAction("),
  (text: "    arm=LEFT,"),
  (text: "    object_designator="),
  (
    slot: "perception", indent: 6,
    // where tracy/render_tracy.py stands the cube, in Tracy's own frame: on the board's
    // lid, on the stretch of it furthest from the square hole, as the sorting demo starts it
    lines: ("cube_1  # CYAN, CUBE", "  at (0.72, 0.13, 0.10) m,"),
    nested: (slot: "simulation", indent: 2, lines: ("SupportedBy(cube_1, lid) ✓",)),
  ),
  (text: "    grasp_description="),
  (
    slot: "probabilistic", indent: 6,
    lines: ("grasp_1 = GraspDescription(", "  FRONT, TOP,", "  LEFT_HAND)"),
  ),
  (text: "  ),"),
  (text: "  InsertionAction("),
  (text: "    arm=LEFT,"),
  (text: "    object_designator=cube_1,"),
  (text: "    grasp_description=grasp_1,"),
  (text: "    target="),
  (
    slot: "rules", indent: 6,
    lines: ("ShapeSortingHole(", "  shape_category=CUBE)"),
  ),
  (text: "  )"),
  (text: "])"),
)

// %% CONFIG: panel 1, the look --------------------------------------------------------

// The plan's own statement about the cube, read one stated condition at a time over a
// frame Tracy's camera took: what each condition left to read, then the cube it ended in.
// A run of the framework demo keeps these under trials/<n>/narrowing of its episode, and
// `python -m experiments.tracy_experiments.bag_frames <bag> --narrowing <that directory>`
// puts them here. The names are experiments.montessori.perception.step_by_step.NarrowingPictures'.

#let stages = (                                     // one tile each, read row by row
  (label: "current view", picture: "narrowing/0_rectified.png"),
  (label: "cyan", picture: "narrowing/1_rectified.png"),
  (label: "on the lid", picture: "narrowing/2_rectified.png"),
  (label: "cube", picture: "narrowing/answer.png"),
)
#let stage-columns = 2
#let tile-aspect = 3 / 2                            // width over height of every tile
#let tile-gap = 0.12cm                              // between two tiles
#let stage-label-h = 0.24cm                         // room above a tile for its name

// %% CONFIG: panel 2, the imagined world ----------------------------------------------
// The look's finding is spawned into a copy of the twin; the relation is then read off
// the copy's geometry. SupportedBy reads the vertical overlap of the two bounding boxes.

#let world-title = "imagined world"
#let spawn-label = "spawn"
#let support-reading = "overlap 3 mm ≤ 0.1 m"
#let support-verdict = "SupportedBy(cube_1, lid) → True"
#let board-color = rgb("#e9dcbd")
#let cube-color = rgb("#bfe6ea")

// %% CONFIG: panel 3, the grasp -------------------------------------------------------
// Placeholder values until the model is read from the recorded trials.

#let grasp-title = "P(grasp | success)"
#let grasps = (
  (approach: "FRONT", alignment: "TOP", p: 0.58),
  (approach: "LEFT", alignment: "TOP", p: 0.24),
  (approach: "RIGHT", alignment: "TOP", p: 0.13),
  (approach: "BACK", alignment: "TOP", p: 0.05),
)

// %% CONFIG: panel 4, the rules -------------------------------------------------------
// A ripple-down tree: a rule, its exception and its alternative below it.

#let rule-root = (condition: "shape.category == CUBE", conclusion: "hole.shape_category = CUBE", fired: true)
#let rule-except = (condition: "occupied(hole)", conclusion: "next free one", fired: false)
#let rule-else = (condition: "no rule fires", conclusion: "NoHoleFits", fired: false)

// %% CONFIG: labels -------------------------------------------------------------------

#let title-open = "Underspecified plan"
#let title-backends = "Resolved by"
#let title-resolved = "Resolved plan"
#let panel-titles = (perception: "PerceptionBackend", simulation: "Working memory backend", probabilistic: "ProbabilisticBackend", rules: "Ripple-down rules")
#let panel-order = ("perception", "simulation", "probabilistic", "rules")
#let robot-name = "Robot"                     // named generically for double anonymous review
#let execute-label = "executes the resolved plan"

// %% CONFIG: image slots ----------------------------------------------------------------
// Set to a file name to show it; leave `none` for a dashed placeholder.

// The pictures of Tracy are cut from a recording of the framework demo on the robot by
// `python -m experiments.tracy_experiments.bag_frames <bag>`.

#let robot-image = "tracy_idle.png"           // before it acts
#let execution-images = (                     // acting, one above the other
  (picture: "tracy_picking_up.png", placeholder: "picking up the cube"),
  (picture: "tracy_inserting.png", placeholder: "inserting the cube"),
)
#let robot-size = (5.8cm, 3.2cm)
#let execution-size = (7.2cm, 4.3cm)          // the space all of them share
#let execution-gap = 0.1cm                    // between two of them
#let camera-aspect = 16 / 9                   // width over height of the robot's camera

// %% DRAWING: helpers -------------------------------------------------------------------

#set page(width: W, height: auto, margin: 0pt)
#set text(font: text-font, size: font-size, fill: ink)

#let char-width = 0.6 * code-size   // the mono font's advance
#let mono(body, size: code-size) = text(font: mono-font, size: size, body)
#let small(body) = text(size: label-size, fill: muted, body)
#let caption(body) = text(size: label-size, fill: muted, tracking: 0.04em, upper(body))

// a straight arrow from `from` to `to`, each an (x, y) pair
#let arrow(from, to, stroke: ink, head: 0.14cm) = {
  let (x1, y1) = from
  let (x2, y2) = to
  let dx = x2 - x1
  let dy = y2 - y1
  let len = calc.sqrt((dx / 1cm) * (dx / 1cm) + (dy / 1cm) * (dy / 1cm)) * 1cm
  let ux = dx / len
  let uy = dy / len
  place(line(start: from, end: (x2 - ux * head * 0.8, y2 - uy * head * 0.8), stroke: stroke-width + stroke))
  place(polygon(
    fill: stroke,
    (x2, y2),
    (x2 - ux * head - uy * head * 0.42, y2 - uy * head + ux * head * 0.42),
    (x2 - ux * head + uy * head * 0.42, y2 - uy * head - ux * head * 0.42),
  ))
}

#let segment(from, to, stroke: ink, dash: none) = place(line(start: from, end: to, stroke: (paint: stroke, thickness: stroke-width, dash: dash)))

// an arrow that leaves horizontally, turns at `turn-x`, and arrives horizontally
#let elbow(from, to, turn-x, stroke: ink) = {
  segment(from, (turn-x, from.at(1)), stroke: stroke)
  segment((turn-x, from.at(1)), (turn-x, to.at(1)), stroke: stroke)
  arrow((turn-x, to.at(1)), to, stroke: stroke)
}

// a rounded card
#let card(x, y, w, h, fill: card-fill, stroke: hairline, radius: 0.12cm, dash: none, body) = place(
  dx: x, dy: y,
  box(width: w, height: h, fill: fill, stroke: (paint: stroke, thickness: stroke-width, dash: dash), radius: radius, body),
)

// %% DRAWING: a plan as a column of code with its slots boxed ---------------------------

// Where every entry of a plan lands, and where each slot's box is, for arrows to aim at.
#let lay-out-plan(entries, x, y0, width) = {
  let y = y0
  let rows = ()
  let slots = (:)
  for entry in entries {
    if "slot" in entry {
      let box-x = x + entry.indent * char-width
      let box-w = width - entry.indent * char-width
      let lines-h = entry.lines.len() * line-height
      let nested = entry.at("nested", default: none)
      let nested-h = if nested == none { 0cm } else { block-gap + 2 * inset + nested.lines.len() * line-height }
      let h = 2 * inset + lines-h + nested-h
      let top = y + block-gap
      rows.push((entry: entry, x: box-x, y: top, w: box-w, h: h))
      slots.insert(entry.slot, (left: box-x, right: box-x + box-w, top: top, mid: top + inset + lines-h / 2, bottom: top + h))
      if nested != none {
        let nested-x = box-x + inset + nested.indent * char-width
        let nested-y = top + inset + lines-h + block-gap
        let nested-w = box-w - 2 * inset - nested.indent * char-width
        slots.insert(nested.slot, (left: nested-x, right: nested-x + nested-w, top: nested-y, mid: nested-y + inset + nested.lines.len() * line-height / 2, bottom: nested-y + nested-h - block-gap))
      }
      y = top + h + block-gap
    } else {
      rows.push((entry: entry, x: x, y: y, w: width, h: line-height))
      y += line-height
    }
  }
  (rows: rows, slots: slots, bottom: y)
}

#let slot-box(x, y, w, h, hue, lines) = {
  place(dx: x, dy: y, box(width: w, height: h, fill: hue.fill, stroke: stroke-width + hue.stroke, radius: 0.08cm))
  for (i, line) in lines.enumerate() {
    place(dx: x + inset, dy: y + inset + i * line-height, mono(line))
  }
}

#let draw-plan(laid-out) = {
  for row in laid-out.rows {
    let entry = row.entry
    if "slot" in entry {
      slot-box(row.x, row.y, row.w, row.h, hues.at(entry.slot), entry.lines)
      let nested = entry.at("nested", default: none)
      if nested != none {
        let where = laid-out.slots.at(nested.slot)
        slot-box(where.left, where.top, where.right - where.left, where.bottom - where.top, hues.at(nested.slot), nested.lines)
      }
    } else {
      place(dx: row.x, dy: row.y, mono(entry.text))
    }
  }
}

// %% DRAWING: panel 1, detection stages ---------------------------------------------------

#let tile(w, h, stage) = box(width: w, height: h, clip: true, radius: 0.08cm, stroke: stroke-width + hairline, fill: ink,
  image(stage.picture, width: w, height: h, fit: "contain"))

// the tiles in a grid, each with its name above it
#let detection-panel(x, y, w, h) = {
  let rows = calc.ceil(stages.len() / stage-columns)
  let top = y + 0.36cm
  let cell-w = (w - 0.3cm - (stage-columns - 1) * tile-gap) / stage-columns
  let cell-h = (y + h - 0.1cm - top - (rows - 1) * tile-gap) / rows
  let tile-h = calc.min(cell-h - stage-label-h, cell-w / tile-aspect)
  let tile-w = tile-h * tile-aspect
  let left = x + (w - stage-columns * tile-w - (stage-columns - 1) * tile-gap) / 2
  for (i, stage) in stages.enumerate() {
    let tile-x = left + calc.rem(i, stage-columns) * (tile-w + tile-gap)
    let tile-y = top + calc.quo(i, stage-columns) * (stage-label-h + tile-h + tile-gap)
    place(dx: tile-x, dy: tile-y, text(size: 5pt, fill: ink, stage.label))
    place(dx: tile-x, dy: tile-y + stage-label-h, tile(tile-w, tile-h, stage))
  }
}

// %% DRAWING: panel 2, the imagined world -------------------------------------------------

#let world-panel(x, y, w, h) = {
  // a dashed frame: the copy of the twin the finding was spawned into
  let fx = x + 0.2cm
  let fy = y + 0.42cm
  let fw = w - 0.4cm
  let fh = h - 0.95cm
  card(fx, fy, fw, fh, fill: white, stroke: simulation.stroke, dash: "dashed", radius: 0.08cm, none)
  place(dx: fx + 0.1cm, dy: fy + 0.05cm, text(size: 5pt, fill: simulation.stroke, world-title))
  // side view: the board on the table, the spawned cube resting on its lid
  let ground = fy + fh - 0.42cm
  let board-w = fw * 0.6
  let board-h = 0.36cm
  let board-x = fx + (fw - board-w) / 2
  let board-y = ground - board-h
  let cube-s = 0.32cm
  let cube-x = board-x + board-w * 0.6
  let cube-y = board-y - cube-s + 0.02cm          // the overlap the reading measures
  segment((fx + 0.15cm, ground), (fx + fw - 0.15cm, ground), stroke: hairline)
  place(dx: board-x, dy: board-y, rect(width: board-w, height: board-h, fill: board-color, stroke: stroke-width + rgb("#c9b98f"), radius: 0.03cm))
  place(dx: board-x + board-w * 0.18, dy: board-y, rect(width: 0.24cm, height: board-h * 0.55, fill: white, stroke: stroke-width + rgb("#c9b98f")))
  place(dx: cube-x, dy: cube-y, rect(width: cube-s, height: cube-s, fill: cube-color, stroke: stroke-width + perception.stroke, radius: 0.02cm))
  place(dx: cube-x + cube-s + 0.06cm, dy: cube-y + 0.02cm, mono(size: 4.8pt, "cube_1"))   // beside the cube, clear of the panel title
  // the two bounding boxes and the band where they overlap
  place(dx: cube-x - 0.06cm, dy: cube-y - 0.06cm, rect(width: cube-s + 0.12cm, height: cube-s + 0.12cm, stroke: (paint: simulation.stroke, thickness: 0.4pt, dash: "dotted")))
  place(dx: board-x - 0.06cm, dy: board-y - 0.06cm, rect(width: board-w + 0.12cm, height: board-h + 0.12cm, stroke: (paint: simulation.stroke, thickness: 0.4pt, dash: "dotted")))
  place(dx: cube-x - 0.06cm, dy: board-y - 0.06cm, rect(width: cube-s + 0.12cm, height: 0.14cm, fill: simulation.stroke.transparentize(60%)))
  place(dx: fx, dy: fy + fh - 0.3cm, box(width: fw, align(center, text(size: 4.8pt, fill: simulation.stroke, support-reading))))
  // what the copy answers
  place(dx: x, dy: y + h - 0.42cm, box(width: w, align(center, mono(size: 5.2pt, text(fill: simulation.stroke, support-verdict)))))
}

// %% DRAWING: panel 3, the grasp distribution ---------------------------------------------

#let grasp-panel(x, y, w, h) = {
  let chart-x = x + 0.3cm
  let chart-w = w - 0.6cm
  let base = y + h - 0.62cm
  let top = y + 0.66cm
  let n = grasps.len()
  let slot-w = chart-w / n
  let bar-w = slot-w * 0.52
  let pmax = calc.max(..grasps.map(g => g.p))
  place(dx: x, dy: y + 0.3cm, box(width: w - 0.15cm, align(right, mono(size: 5.2pt, grasp-title))))
  place(dx: chart-x, dy: base, line(length: chart-w, stroke: stroke-width + hairline))
  for (i, g) in grasps.enumerate() {
    let bar-h = (base - top) * g.p / pmax
    let bx = chart-x + i * slot-w + (slot-w - bar-w) / 2
    let best = g.p == pmax
    place(dx: bx, dy: base - bar-h, rect(width: bar-w, height: bar-h, radius: (top: 0.04cm),
      fill: if best { probabilistic.stroke } else { probabilistic.fill },
      stroke: if best { none } else { 0.4pt + probabilistic.stroke }))
    place(dx: bx - 0.2cm, dy: base - bar-h - 0.27cm, box(width: bar-w + 0.4cm,
      align(center, text(size: 5pt, fill: if best { ink } else { muted }, str(g.p)))))
    place(dx: chart-x + i * slot-w, dy: base + 0.05cm, box(width: slot-w,
      align(center, mono(size: 4.6pt, g.approach + linebreak() + g.alignment))))
  }
}

// %% DRAWING: panel 4, the ripple-down tree -----------------------------------------------

#let rule-node(x, y, w, rule) = {
  let hue = if rule.fired { rules.stroke } else { hairline }
  place(dx: x, dy: y, box(width: w, fill: if rule.fired { rules.fill } else { white },
    stroke: stroke-width + hue, radius: 0.08cm, inset: (x: 0.09cm, y: 0.06cm), {
      set par(leading: 0.25em)
      mono(size: 4.9pt, rule.condition)
      linebreak()
      text(size: 4.9pt, fill: if rule.fired { rules.stroke } else { muted }, sym.arrow.r + " ")
      mono(size: 4.9pt, rule.conclusion)
    }))
}

#let rules-panel(x, y, w, h) = {
  let inner-w = w - 0.4cm
  let root-w = inner-w * 0.72
  let leaf-w = (inner-w - 0.25cm) / 2
  let node-h = 0.56cm
  let root = (x: x + 0.2cm + (inner-w - root-w) / 2, y: y + 0.42cm)
  let leaf-y = root.y + node-h + 0.5cm
  let except = (x: x + 0.2cm, y: leaf-y)
  let else-node = (x: x + 0.2cm + leaf-w + 0.25cm, y: leaf-y)
  rule-node(root.x, root.y, root-w, rule-root)
  rule-node(except.x, except.y, leaf-w, rule-except)
  rule-node(else-node.x, else-node.y, leaf-w, rule-else)
  let root-bottom = root.y + node-h
  arrow((root.x + root-w * 0.25, root-bottom), (except.x + leaf-w / 2, except.y), stroke: muted)
  arrow((root.x + root-w * 0.75, root-bottom), (else-node.x + leaf-w / 2, else-node.y), stroke: muted)
  // each label beside its arrow, on the side the arrow leans away from, so no stroke runs through it
  let label-w = 1.2cm
  let label-gap = 0.12cm
  let label-y = root-bottom + 0.1cm
  let except-mid = (root.x + root-w * 0.25 + except.x + leaf-w / 2) / 2
  let else-mid = (root.x + root-w * 0.75 + else-node.x + leaf-w / 2) / 2
  place(dx: except-mid - label-gap - label-w, dy: label-y, box(width: label-w, align(right, small("except"))))
  place(dx: else-mid + label-gap, dy: label-y, box(width: label-w, align(left, small("else"))))
}

#let panel-drawers = (perception: detection-panel, simulation: world-panel, probabilistic: grasp-panel, rules: rules-panel)

// %% DRAWING: geometry ---------------------------------------------------------------------

#let bubble-x = 0.15cm
#let bubble-w = W - 0.3cm
#let margin = 0.35cm                 // inside the bubble
#let gap = 0.7cm                     // between a column and the next, where the arrows turn
#let plan-w = 5.4cm
#let panel-w = 5.0cm
#let panel-heights = (perception: 3.24cm, simulation: 2.0cm, probabilistic: 1.73cm, rules: 1.93cm)
#let panel-gap = 0.18cm
#let plan-x = bubble-x + margin
#let panel-x = plan-x + plan-w + gap
#let resolved-x = panel-x + panel-w + gap
#let resolved-w = bubble-x + bubble-w - margin - resolved-x

#let bubble-y = 0.2cm
#let columns-y = bubble-y + 0.75cm
#let panels-h = panel-heights.values().sum() + (panel-order.len() - 1) * panel-gap
#let bubble-h = 0.75cm + panels-h + margin
#let floor-y = bubble-y + bubble-h + 0.75cm          // the row with both robot images
#let floor-h = calc.max(robot-size.at(1), execution-size.at(1))
#let H = floor-y + floor-h + 0.45cm

#let panel-y(i) = columns-y + panel-order.slice(0, i).map(name => panel-heights.at(name)).sum(default: 0cm) + i * panel-gap

// %% DRAWING: the page ---------------------------------------------------------------------

#box(width: W, height: H, {
  // the thought bubble
  card(bubble-x, bubble-y, bubble-w, bubble-h, fill: bubble-fill, stroke: hairline, radius: 0.45cm, none)
  place(dx: plan-x, dy: columns-y - 0.32cm, caption(title-open))
  place(dx: panel-x, dy: columns-y - 0.32cm, caption(title-backends))
  place(dx: resolved-x, dy: columns-y - 0.32cm, caption(title-resolved))

  // the plan with its open slots, and the plan with them filled
  let open = lay-out-plan(open-plan, plan-x + 0.15cm, columns-y + 0.15cm, plan-w - 0.3cm)
  let resolved = lay-out-plan(resolved-plan, resolved-x + 0.15cm, columns-y + 0.15cm, resolved-w - 0.3cm)
  card(plan-x, columns-y, plan-w, panels-h, none)
  card(resolved-x, columns-y, resolved-w, panels-h, none)
  draw-plan(open)
  draw-plan(resolved)

  // the backends, one per slot, and the arrows in and out of them
  for (i, name) in panel-order.enumerate() {
    let hue = hues.at(name)
    let y = panel-y(i)
    let h = panel-heights.at(name)
    card(panel-x, y, panel-w, h, none)
    place(dx: panel-x + 0.15cm, dy: y + 0.1cm, text(size: label-size, fill: hue.stroke, weight: "bold", panel-titles.at(name)))
    (panel-drawers.at(name))(panel-x, y, panel-w, h)
    let turn = 0.2cm + i * 0.12cm
    let from = open.slots.at(name)
    elbow((from.right, from.mid), (panel-x, y + h / 2), plan-x + plan-w + turn, stroke: hue.stroke)
    let to = resolved.slots.at(name)
    elbow((panel-x + panel-w, y + h / 2), (to.left, to.mid), panel-x + panel-w + gap - turn, stroke: hue.stroke)
  }
  // the look's finding is spawned into the imagined world before the relation is read
  let spawn-x = panel-x + panel-w * 0.5
  let look-bottom = panel-y(0) + panel-heights.at(panel-order.at(0))
  arrow((spawn-x, look-bottom), (spawn-x, panel-y(1)), stroke: simulation.stroke, head: 0.12cm)
  place(dx: spawn-x + 0.12cm, dy: look-bottom + 0.01cm, text(size: 4.8pt, fill: simulation.stroke, spawn-label))

  // the robot, thinking: the bubble above is its thought
  let robot-x = 0.35cm
  let robot-y = floor-y + (floor-h - robot-size.at(1)) / 2
  if robot-image != none {
    place(dx: robot-x, dy: robot-y, box(width: robot-size.at(0), height: robot-size.at(1), image(robot-image, width: robot-size.at(0), height: robot-size.at(1), fit: "contain")))
  } else {
    card(robot-x, robot-y, robot-size.at(0), robot-size.at(1), fill: white, stroke: muted, dash: "dashed", align(center + horizon, small(robot-name)))
  }
  place(dx: robot-x, dy: robot-y + robot-size.at(1) + 0.02cm, box(width: robot-size.at(0), align(center, small(robot-name))))

  // the robot, acting: one picture above the next, in the space they share
  let n = execution-images.len()
  let acting-h = (execution-size.at(1) - (n - 1) * execution-gap) / n
  let acting-w = calc.min(execution-size.at(0), acting-h * camera-aspect)
  let execution-x = W - 0.35cm - acting-w
  let execution-y = floor-y + (floor-h - execution-size.at(1)) / 2
  for (i, acting) in execution-images.enumerate() {
    let acting-y = execution-y + i * (acting-h + execution-gap)
    if acting.picture != none {
      place(dx: execution-x, dy: acting-y, box(width: acting-w, height: acting-h, clip: true, radius: 0.1cm,
        image(acting.picture, width: acting-w, height: acting-h, fit: "cover")))
    } else {
      card(execution-x, acting-y, acting-w, acting-h, fill: white, stroke: muted, dash: "dashed",
        align(center + horizon, small("photo: " + robot-name + " " + acting.placeholder)))
    }
  }
  let arrow-y = floor-y + floor-h / 2
  let arrow-from = robot-x + robot-size.at(0) + 0.4cm
  let arrow-to = execution-x - 0.3cm
  arrow((arrow-from, arrow-y), (arrow-to, arrow-y))
  place(dx: arrow-from, dy: arrow-y - 0.36cm, box(width: arrow-to - arrow-from, align(center, small(execute-label))))
})
