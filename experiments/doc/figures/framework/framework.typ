// Framework figure: an underspecified plan resolved by four backends, in Tracy's head.
//
// Reads left to right: the plan with its open slots, the backend that closes each slot,
// the plan with the slots filled. Below it, in one row, the robot thinking and the robot acting.
// Everything a reader sees is data in the CONFIG section: the two plans as nested
// trees, colours, sizes, the camera crop, the bars, the rules, the image slots.
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

#let open-plan = (
  (text: "underspecified(sequential(["),
  (text: "  a(PickUpAction)("),
  (text: "    arm=LEFT,"),
  (text: "    object_designator="),
  (
    slot: "perception", indent: 6,
    lines: ("a(DetectedMontessoriShape)(", "  category=CUBE)", ".where(", "  Colored(shape, LIGHT_BLUE),"),
    nested: (slot: "simulation", indent: 2, lines: ("SupportedBy(shape, board)),",)),
  ),
  (text: "    grasp_description="),
  (
    slot: "probabilistic", indent: 6,
    lines: ("a(GraspDescription)(", "  approach_direction=...,", "  vertical_alignment=...)"),
  ),
  (text: "  ),"),
  (text: "  a(PlaceAction)("),
  (text: "    object_designator=shape,"),
  (text: "    target_location="),
  (
    slot: "rules", indent: 6,
    lines: ("a(ShapeSortingHole)(", "  shape=..., on=board)"),
  ),
  (text: "  )"),
  (text: "]))"),
)

#let resolved-plan = (
  (text: "sequential(["),
  (text: "  PickUpAction("),
  (text: "    arm=LEFT,"),
  (text: "    object_designator="),
  (
    slot: "perception", indent: 6,
    lines: ("cube_1  # LIGHT_BLUE, CUBE", "  at (0.61, 0.24, 0.79) m,"),
    nested: (slot: "simulation", indent: 2, lines: ("SupportedBy(cube_1, board) ✓",)),
  ),
  (text: "    grasp_description="),
  (
    slot: "probabilistic", indent: 6,
    lines: ("GraspDescription(", "  FRONT, TOP)"),
  ),
  (text: "  ),"),
  (text: "  PlaceAction("),
  (text: "    object_designator=cube_1,"),
  (text: "    target_location="),
  (
    slot: "rules", indent: 6,
    lines: ("ShapeSortingHole(", "  shape=SQUARE, on=board)"),
  ),
  (text: "  )"),
  (text: "])"),
)

// %% CONFIG: panel 1, the look --------------------------------------------------------

// the repository's own camera frame of the board, 1920 x 1080; the build root is the repository root
#let capture = "../../../src/experiments/montessori/resources/captures/objects_on_montessori_color.jpg"
#let capture-size = (1920, 1080)
#let crop = (x: 570, y: 172, w: 360, h: 200)        // pixels of the frame shown per tile
#let cube-box = (x: 772, y: 191, w: 50, h: 56)      // the cube, in frame pixels
#let stages = ("colour", "shape", "cube found")     // one tile each, back to front
#let stage-offset = (0.75cm, 0.32cm)                // how far each tile steps forward

// %% CONFIG: panel 2, the imagined world ----------------------------------------------
// The look's finding is spawned into a copy of the twin; the relation is then read off
// the copy's geometry. SupportedBy reads the vertical overlap of the two bounding boxes.

#let world-title = "imagined world"
#let spawn-label = "spawn"
#let support-reading = "overlap 3 mm ≤ 0.1 m"
#let support-verdict = "SupportedBy(cube_1, board) → True"
#let board-color = rgb("#e9dcbd")
#let cube-color = rgb("#bfe6ea")

// %% CONFIG: panel 3, the grasp -------------------------------------------------------
// Placeholder values until the model is read from the recorded trials.

#let grasp-title = "P(grasp | success)"
#let grasps = (
  (approach: "FRONT", alignment: "TOP", p: 0.58),
  (approach: "LEFT", alignment: "TOP", p: 0.24),
  (approach: "RIGHT", alignment: "TOP", p: 0.13),
  (approach: "FRONT", alignment: "NONE", p: 0.05),
)

// %% CONFIG: panel 4, the rules -------------------------------------------------------
// A ripple-down tree: a rule, its exception and its alternative below it.

#let rule-root = (condition: "shape.category == CUBE", conclusion: "hole.shape = SQUARE", fired: true)
#let rule-except = (condition: "occupied(hole)", conclusion: "next free one", fired: false)
#let rule-else = (condition: "no rule fires", conclusion: "NoHoleFits", fired: false)

// %% CONFIG: labels -------------------------------------------------------------------

#let title-open = "Underspecified plan"
#let title-backends = "Resolved by"
#let title-resolved = "Resolved plan"
#let panel-titles = (perception: "PerceptionBackend", simulation: "Simulation backend", probabilistic: "ProbabilisticBackend", rules: "Ripple-down rules")
#let panel-order = ("perception", "simulation", "probabilistic", "rules")
#let robot-name = "Tracy"
#let execute-label = "executes the resolved plan"

// %% CONFIG: image slots ----------------------------------------------------------------
// Set to a file name to show it; leave `none` for a dashed placeholder.

#let robot-image = "tracy_idle.png"           // rendered by tracy/render_tracy.py idle
#let execution-image = "tracy_inserting.png"  // rendered by tracy/render_tracy.py inserting
#let robot-size = (5.8cm, 3.2cm)
#let execution-size = (6.2cm, 3.5cm)

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

#let tile(stage-index, w, h, label) = {
  let scale = w / (crop.w * 1pt)
  let frame-w = capture-size.at(0) * 1pt * scale
  let frame-h = capture-size.at(1) * 1pt * scale
  let frame = image(capture, width: frame-w, height: frame-h)
  let cube = (
    x: (cube-box.x - crop.x) * 1pt * scale,
    y: (cube-box.y - crop.y) * 1pt * scale,
    w: cube-box.w * 1pt * scale,
    h: cube-box.h * 1pt * scale,
  )
  box(width: w, height: h, clip: true, radius: 0.08cm, stroke: stroke-width + hairline, {
    place(dx: -crop.x * 1pt * scale, dy: -crop.y * 1pt * scale, frame)
    if stage-index >= 0 {
      // colour: everything that is not the colour asked for falls back
      place(rect(width: w, height: h, fill: white.transparentize(45%)))
      place(dx: cube.x, dy: cube.y, box(width: cube.w, height: cube.h, clip: true,
        place(dx: -cube.x - crop.x * 1pt * scale, dy: -cube.y - crop.y * 1pt * scale, frame)))
    }
    if stage-index >= 1 {
      // shape: the fitted outline
      place(dx: cube.x - 0.04cm, dy: cube.y - 0.04cm,
        rect(width: cube.w + 0.08cm, height: cube.h + 0.08cm, stroke: 0.7pt + perception.stroke, radius: 0.03cm))
    }
    if stage-index >= 2 {
      // found: its place
      let cx = cube.x + cube.w / 2
      let cy = cube.y + cube.h / 2
      place(dx: cx - 0.06cm, dy: cy - 0.06cm, circle(radius: 0.06cm, fill: perception.stroke, stroke: 0.6pt + white))
      // the tag is worth its space only on a tile wide enough to hold it
      let tag = box(fill: perception.stroke, radius: 0.04cm, inset: (x: 0.07cm, y: 0.03cm), text(size: 5pt, fill: white, font: mono-font, "cube_1"))
      if w > 2.6cm { place(dx: cx + 0.14cm, dy: cy - 0.16cm, tag) }
    }
    place(dx: 0.08cm, dy: 0.07cm, box(fill: white.transparentize(10%), radius: 0.04cm, inset: (x: 0.07cm, y: 0.03cm),
      text(size: 5pt, fill: ink, label)))
  })
}

#let detection-panel(x, y, w, h) = {
  let n = stages.len() - 1
  let top = y + 0.45cm
  let tile-h = calc.min((h - 0.6cm) - n * stage-offset.at(1), (w - 0.2cm - n * stage-offset.at(0)) * crop.h / crop.w)
  let tile-w = tile-h * crop.w / crop.h
  for (i, label) in stages.enumerate() {
    place(dx: x + 0.1cm + i * stage-offset.at(0), dy: top + i * stage-offset.at(1), tile(i, tile-w, tile-h, label))
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
  place(dx: cube-x + 0.02cm, dy: cube-y - 0.28cm, mono(size: 4.8pt, "cube_1"))
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
  let top = y + 0.8cm
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
  place(dx: except.x, dy: root-bottom + 0.1cm, box(width: leaf-w, align(center, small("except"))))
  place(dx: else-node.x, dy: root-bottom + 0.1cm, box(width: leaf-w, align(center, small("else"))))
}

#let panel-drawers = (perception: detection-panel, simulation: world-panel, probabilistic: grasp-panel, rules: rules-panel)

// %% DRAWING: geometry ---------------------------------------------------------------------

#let bubble-x = 0.15cm
#let bubble-w = W - 0.3cm
#let margin = 0.35cm                 // inside the bubble
#let gap = 0.7cm                     // between a column and the next, where the arrows turn
#let plan-w = 5.4cm
#let panel-w = 5.0cm
#let panel-h = 2.15cm
#let panel-gap = 0.28cm
#let plan-x = bubble-x + margin
#let panel-x = plan-x + plan-w + gap
#let resolved-x = panel-x + panel-w + gap
#let resolved-w = bubble-x + bubble-w - margin - resolved-x

#let bubble-y = 0.2cm
#let columns-y = bubble-y + 0.75cm
#let panels-h = panel-order.len() * panel-h + (panel-order.len() - 1) * panel-gap
#let bubble-h = 0.75cm + panels-h + margin
#let floor-y = bubble-y + bubble-h + 0.75cm          // the row with both robot images
#let floor-h = calc.max(robot-size.at(1), execution-size.at(1))
#let H = floor-y + floor-h + 0.45cm

#let panel-y(i) = columns-y + i * (panel-h + panel-gap)

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
    card(panel-x, y, panel-w, panel-h, none)
    place(dx: panel-x + 0.15cm, dy: y + 0.1cm, text(size: label-size, fill: hue.stroke, weight: "bold", panel-titles.at(name)))
    (panel-drawers.at(name))(panel-x, y, panel-w, panel-h)
    let turn = 0.2cm + i * 0.12cm
    let from = open.slots.at(name)
    elbow((from.right, from.mid), (panel-x, y + panel-h / 2), plan-x + plan-w + turn, stroke: hue.stroke)
    let to = resolved.slots.at(name)
    elbow((panel-x + panel-w, y + panel-h / 2), (to.left, to.mid), panel-x + panel-w + gap - turn, stroke: hue.stroke)
  }
  // the look's finding is spawned into the imagined world before the relation is read
  let spawn-x = panel-x + panel-w * 0.5
  arrow((spawn-x, panel-y(0) + panel-h), (spawn-x, panel-y(1)), stroke: simulation.stroke, head: 0.12cm)
  place(dx: spawn-x + 0.12cm, dy: panel-y(0) + panel-h + 0.02cm, text(size: 4.8pt, fill: simulation.stroke, spawn-label))

  // the robot, thinking: the bubble above is its thought
  let robot-x = 0.35cm
  let robot-y = floor-y + (floor-h - robot-size.at(1)) / 2
  if robot-image != none {
    place(dx: robot-x, dy: robot-y, box(width: robot-size.at(0), height: robot-size.at(1), image(robot-image, width: robot-size.at(0), height: robot-size.at(1), fit: "contain")))
  } else {
    card(robot-x, robot-y, robot-size.at(0), robot-size.at(1), fill: white, stroke: muted, dash: "dashed", align(center + horizon, small(robot-name)))
  }
  place(dx: robot-x, dy: robot-y + robot-size.at(1) + 0.02cm, box(width: robot-size.at(0), align(center, small(robot-name))))
  for (i, r) in ((0.12cm, 0.0cm), (0.09cm, 0.26cm), (0.06cm, 0.47cm)).enumerate() {
    place(dx: robot-x + robot-size.at(0) * 0.55 - i * 0.2cm - r.at(0), dy: bubble-y + bubble-h + 0.06cm + r.at(1) - r.at(0),
      circle(radius: r.at(0), fill: bubble-fill, stroke: stroke-width + hairline))
  }

  // the robot, acting
  let execution-x = W - 0.35cm - execution-size.at(0)
  let execution-y = floor-y + (floor-h - execution-size.at(1)) / 2
  if execution-image != none {
    place(dx: execution-x, dy: execution-y, box(width: execution-size.at(0), height: execution-size.at(1), clip: true, radius: 0.1cm,
      image(execution-image, width: execution-size.at(0), height: execution-size.at(1), fit: "cover")))
  } else {
    card(execution-x, execution-y, execution-size.at(0), execution-size.at(1), fill: white, stroke: muted, dash: "dashed",
      align(center + horizon, small("photo: " + robot-name + " inserting the cube")))
  }
  let arrow-y = floor-y + floor-h / 2
  let arrow-from = robot-x + robot-size.at(0) + 0.4cm
  let arrow-to = execution-x - 0.3cm
  arrow((arrow-from, arrow-y), (arrow-to, arrow-y))
  place(dx: arrow-from, dy: arrow-y - 0.36cm, box(width: arrow-to - arrow-from, align(center, small(execute-label))))
})
