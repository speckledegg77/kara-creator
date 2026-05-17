# Alignment diagnostics summary

Draft: `C:\Users\mark\kara-creator\outputs\let_it_go-draft-lyrics-aligner-v3.json`
Tool version: `0.1.0`

## Counts

- Total lines: 42
- High severity lines: 5
- Medium severity lines: 2
- Local realignment candidates: 2
- Repeated or held word collapse candidates: 0
- Instrumental placeholder checks: 2
- Pronunciation or tokenisation checks: 4

## Worst lines

- 100 | line-0005 | very_large_internal_word_gap|pronunciation_or_tokenisation_check|draft_builder_rescue_applied|local_realignment_candidate | And it looks like I'm the queen
  - Action: Treat as a likely bad word-anchor section. Consider local realignment rather than manual display-only repair. Check contractions, hyphens, rare words, and custom pronunciations. This line has already been rescued by Kara Creator. Check whether the raw word anchors are still trustworthy. Best next step: local realignment of this phrase window, not another display timing patch.
- 100 | line-0008 | very_large_internal_word_gap|first_word_anchor_suspect|first_gap_outlier|pronunciation_or_tokenisation_check | Don't let them in, don't let them see
  - Action: Treat as a likely bad word-anchor section. Consider local realignment rather than manual display-only repair. Check whether the first word has been placed too early or too late. Compare the first word against the rest of the line. The opening anchor may be unreliable. Check contractions, hyphens, rare words, and custom pronunciations.
- 100 | line-0032 | very_large_internal_word_gap|first_word_anchor_suspect|first_gap_outlier | My power flurries through the air into the ground
  - Action: Treat as a likely bad word-anchor section. Consider local realignment rather than manual display-only repair. Check whether the first word has been placed too early or too late. Compare the first word against the rest of the line. The opening anchor may be unreliable.
- 100 | line-0041 | very_large_internal_word_gap|draft_builder_rescue_applied|local_realignment_candidate | Let the storm rage on
  - Action: Treat as a likely bad word-anchor section. Consider local realignment rather than manual display-only repair. This line has already been rescued by Kara Creator. Check whether the raw word anchors are still trustworthy. Best next step: local realignment of this phrase window, not another display timing patch.
- 85 | line-0035 | very_large_internal_word_gap|pronunciation_or_tokenisation_check | I'm never going back, the past is in the past
  - Action: Treat as a likely bad word-anchor section. Consider local realignment rather than manual display-only repair. Check contractions, hyphens, rare words, and custom pronunciations.
- 65 | line-0034 | large_internal_word_gap|pronunciation_or_tokenisation_check | And one thought crystallises like an icy blast
  - Action: Review word anchors. If the gap is musical rather than real, mark this as a local realignment candidate. Check contractions, hyphens, rare words, and custom pronunciations.
- 45 | line-0030 | large_internal_word_gap | Here I stand and here I stay
  - Action: Review word anchors. If the gap is musical rather than real, mark this as a local realignment candidate.
- 20 | line-0014 | first_gap_outlier | Let it go, let it go
  - Action: Compare the first word against the rest of the line. The opening anchor may be unreliable.
- 20 | line-0018 | first_gap_outlier | The cold never bothered me anyway
  - Action: Compare the first word against the rest of the line. The opening anchor may be unreliable.
- 20 | line-0027 | first_gap_outlier | I am one with the wind and sky
  - Action: Compare the first word against the rest of the line. The opening anchor may be unreliable.
- 20 | line-0031 | long_tail_after_last_word | Let the storm rage on
  - Action: Check whether the line should really remain visible this long after the final word start.
- 10 | line-0001 | instrumental_placeholder | . . .
  - Action: Check only if the visual instrumental gap feels wrong in the editor.
