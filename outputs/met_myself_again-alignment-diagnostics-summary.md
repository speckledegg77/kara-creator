# Alignment diagnostics summary

Draft: `C:\Users\mark\kara-creator\outputs\met_myself_again-draft-alignment-confidence-boundary.json`
Tool version: `0.1.0`

## Counts

- Total lines: 36
- High severity lines: 4
- Medium severity lines: 0
- Local realignment candidates: 1
- Repeated or held word collapse candidates: 0
- Instrumental placeholder checks: 4
- Pronunciation or tokenisation checks: 2

## Worst lines

- 100 | line-0003 | large_internal_word_gap|first_word_anchor_suspect|first_gap_outlier|pronunciation_or_tokenisation_check | Would I tell that simple wide-eyed girl the truth
  - Action: Review word anchors. If the gap is musical rather than real, mark this as a local realignment candidate. Check whether the first word has been placed too early or too late. Compare the first word against the rest of the line. The opening anchor may be unreliable. Check contractions, hyphens, rare words, and custom pronunciations.
- 100 | line-0010 | large_internal_word_gap|first_word_anchor_suspect|first_gap_outlier | If I met myself again
  - Action: Review word anchors. If the gap is musical rather than real, mark this as a local realignment candidate. Check whether the first word has been placed too early or too late. Compare the first word against the rest of the line. The opening anchor may be unreliable.
- 100 | line-0012 | very_large_internal_word_gap|first_word_anchor_suspect|first_gap_outlier|post_instrumental_reentry_suspect|pronunciation_or_tokenisation_check|draft_builder_rescue_applied|local_realignment_candidate | If I met myself again I wonder what she'd say
  - Action: Treat as a likely bad word-anchor section. Consider local realignment rather than manual display-only repair. Check whether the first word has been placed too early or too late. Compare the first word against the rest of the line. The opening anchor may be unreliable. Check the first vocal entry after . . . . The next lyric may start later than the aligner thinks. Check contractions, hyphens, rare words, and custom pronunciations. This line has already been rescued by Kara Creator. Check whether the raw word anchors are still trustworthy. Best next step: local realignment of this phrase window, not another display timing patch.
- 100 | line-0033 | very_large_internal_word_gap|first_word_anchor_suspect|first_gap_outlier | If I met myself again
  - Action: Treat as a likely bad word-anchor section. Consider local realignment rather than manual display-only repair. Check whether the first word has been placed too early or too late. Compare the first word against the rest of the line. The opening anchor may be unreliable.
- 20 | line-0022 | long_tail_after_last_word | And go and do it all again
  - Action: Check whether the line should really remain visible this long after the final word start.
- 10 | line-0001 | instrumental_placeholder | . . .
  - Action: Check only if the visual instrumental gap feels wrong in the editor.
- 10 | line-0011 | instrumental_placeholder | . . .
  - Action: Check only if the visual instrumental gap feels wrong in the editor.
- 10 | line-0024 | draft_builder_rescue_applied | If I met that girl again I'd tell her sink or swim
  - Action: This line has already been rescued by Kara Creator. Check whether the raw word anchors are still trustworthy.
- 10 | line-0034 | draft_builder_rescue_applied | If I met myself again
  - Action: This line has already been rescued by Kara Creator. Check whether the raw word anchors are still trustworthy.
- 10 | line-0035 | instrumental_placeholder | . . .
  - Action: Check only if the visual instrumental gap feels wrong in the editor.
- 10 | line-0036 | draft_builder_rescue_applied | If I met myself again
  - Action: This line has already been rescued by Kara Creator. Check whether the raw word anchors are still trustworthy.
- 0 | line-0002 | ok | If I met myself back then I wonder what I'd say
  - Action: No obvious diagnostic issue detected.
