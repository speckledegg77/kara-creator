# Alignment diagnostics summary

Draft: `C:\Users\mark\kara-creator\outputs\miss_the_mountains-draft-alignment-confidence-boundary.json`
Tool version: `0.1.0`

## Counts

- Total lines: 41
- High severity lines: 7
- Medium severity lines: 2
- Local realignment candidates: 2
- Repeated or held word collapse candidates: 0
- Instrumental placeholder checks: 0
- Pronunciation or tokenisation checks: 0

## Worst lines

- 100 | line-0003 | very_large_internal_word_gap|first_word_anchor_suspect|first_gap_outlier | Would be me
  - Action: Treat as a likely bad word-anchor section. Consider local realignment rather than manual display-only repair. Check whether the first word has been placed too early or too late. Compare the first word against the rest of the line. The opening anchor may be unreliable.
- 100 | line-0009 | very_large_internal_word_gap|draft_builder_rescue_applied|local_realignment_candidate | And while she runs free and fast
  - Action: Treat as a likely bad word-anchor section. Consider local realignment rather than manual display-only repair. This line has already been rescued by Kara Creator. Check whether the raw word anchors are still trustworthy. Best next step: local realignment of this phrase window, not another display timing patch.
- 100 | line-0011 | very_large_internal_word_gap|first_word_anchor_suspect|first_gap_outlier | But I miss the mountains
  - Action: Treat as a likely bad word-anchor section. Consider local realignment rather than manual display-only repair. Check whether the first word has been placed too early or too late. Compare the first word against the rest of the line. The opening anchor may be unreliable.
- 100 | line-0029 | large_internal_word_gap|first_word_anchor_suspect|first_gap_outlier|long_tail_after_last_word | Everything is perfect
  - Action: Review word anchors. If the gap is musical rather than real, mark this as a local realignment candidate. Check whether the first word has been placed too early or too late. Compare the first word against the rest of the line. The opening anchor may be unreliable. Check whether the line should really remain visible this long after the final word start.
- 100 | line-0040 | very_large_internal_word_gap|first_word_anchor_suspect|draft_builder_rescue_applied|local_realignment_candidate | I miss my life
  - Action: Treat as a likely bad word-anchor section. Consider local realignment rather than manual display-only repair. Check whether the first word has been placed too early or too late. This line has already been rescued by Kara Creator. Check whether the raw word anchors are still trustworthy. Best next step: local realignment of this phrase window, not another display timing patch.
- 90 | line-0039 | large_internal_word_gap|first_word_anchor_suspect|draft_builder_rescue_applied | I miss the mountains
  - Action: Review word anchors. If the gap is musical rather than real, mark this as a local realignment candidate. Check whether the first word has been placed too early or too late. This line has already been rescued by Kara Creator. Check whether the raw word anchors are still trustworthy.
- 85 | line-0010 | large_internal_word_gap|long_tail_after_last_word|draft_builder_rescue_applied|alignment_confidence_boundary_used | Seems my wild days are past
  - Action: Review word anchors. If the gap is musical rather than real, mark this as a local realignment candidate. Check whether the line should really remain visible this long after the final word start. This line has already been rescued by Kara Creator. Check whether the raw word anchors are still trustworthy. Audio phrase-boundary rescue was used. Check that the display looks right, but treat word timings with caution.
- 55 | line-0007 | large_internal_word_gap|draft_builder_rescue_applied | All these blank and tranquil years
  - Action: Review word anchors. If the gap is musical rather than real, mark this as a local realignment candidate. This line has already been rescued by Kara Creator. Check whether the raw word anchors are still trustworthy.
- 45 | line-0032 | large_internal_word_gap | And I miss the mountains
  - Action: Review word anchors. If the gap is musical rather than real, mark this as a local realignment candidate.
- 30 | line-0006 | short_display_duration | I'm nowhere
  - Action: Check readability and timing. The display duration is short.
- 30 | line-0031 | long_tail_after_last_word|draft_builder_rescue_applied | Nothing's real
  - Action: Check whether the line should really remain visible this long after the final word start. This line has already been rescued by Kara Creator. Check whether the raw word anchors are still trustworthy.
- 20 | line-0021 | first_gap_outlier | I miss the mountains
  - Action: Compare the first word against the rest of the line. The opening anchor may be unreliable.
