## Next
Nothing outstanding in this session: PR #221 is open as a draft with its description matching
the work. CI has not been read yet.

## The two things the plan had not found
The item's note says "invisible twice over"; it is four. The restructure fixes two.

- The lid wears a piece colour (wood hue 19, amber prisms 21, tolerance 4), so one mask over
  all piece colours merged a piece on the lid into the lid.
- The edge fit ran Canny over brightness, where a cyan piece is **one** grey level from the
  lid and **34** from the bare table -- no edge to fit.

Both fixed inside the one detector, so `choose-detection-method` still owns choosing between
detectors. **But its "the lid selects the colour blob" rule loses its motivation**: the edge
fit now fits a cube on the lid at 0.93. Recorded on #201 and in the roadmap.
