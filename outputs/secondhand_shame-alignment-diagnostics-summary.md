# Alignment diagnostics summary

Draft: `C:\Users\mark\kara-creator\outputs\secondhand_shame-draft-alignment-confidence-boundary.json`
Tool version: `0.1.0`

## Counts

- Total lines: 60
- High severity lines: 2
- Medium severity lines: 3
- Local realignment candidates: 2
- Repeated or held word collapse candidates: 3
- Instrumental placeholder checks: 1
- Pronunciation or tokenisation checks: 1

## Worst lines

- 100 | line-0057 | very_large_internal_word_gap|first_word_anchor_suspect|draft_builder_rescue_applied|local_realignment_candidate | Clear the past away
  - Action: Treat as a likely bad word-anchor section. Consider local realignment rather than manual display-only repair. Check whether the first word has been placed too early or too late. This line has already been rescued by Kara Creator. Check whether the raw word anchors are still trustworthy. Best next step: local realignment of this phrase window, not another display timing patch.
- 100 | line-0058 | very_large_internal_word_gap|first_word_anchor_suspect|repeated_word_or_held_word_collapse|draft_builder_rescue_applied|local_realignment_candidate|alignment_confidence_boundary_used | Then the future can begin today
  - Action: Treat as a likely bad word-anchor section. Consider local realignment rather than manual display-only repair. Check whether the first word has been placed too early or too late. Check repeated-word timing. If word anchors are collapsed, a local realignment or repeated-word recovery is needed. This line has already been rescued by Kara Creator. Check whether the raw word anchors are still trustworthy. Best next step: local realignment of this phrase window, not another display timing patch. Audio phrase-boundary rescue was used. Check that the display looks right, but treat word timings with caution.
- 65 | line-0047 | large_internal_word_gap|pronunciation_or_tokenisation_check | And you can't say I'm running away from myself
  - Action: Review word anchors. If the gap is musical rather than real, mark this as a local realignment candidate. Check contractions, hyphens, rare words, and custom pronunciations.
- 45 | line-0059 | repeated_word_or_held_word_collapse|draft_builder_rescue_applied | Today
  - Action: Check repeated-word timing. If word anchors are collapsed, a local realignment or repeated-word recovery is needed. This line has already been rescued by Kara Creator. Check whether the raw word anchors are still trustworthy.
- 45 | line-0060 | repeated_word_or_held_word_collapse|draft_builder_rescue_applied | Today
  - Action: Check repeated-word timing. If word anchors are collapsed, a local realignment or repeated-word recovery is needed. This line has already been rescued by Kara Creator. Check whether the raw word anchors are still trustworthy.
- 20 | line-0025 | long_tail_after_last_word | Just for one day?
  - Action: Check whether the line should really remain visible this long after the final word start.
- 10 | line-0001 | instrumental_placeholder | . . .
  - Action: Check only if the visual instrumental gap feels wrong in the editor.
- 0 | line-0002 | ok | Can't I have one day?
  - Action: No obvious diagnostic issue detected.
- 0 | line-0003 | ok | Without you breathing in my ear
  - Action: No obvious diagnostic issue detected.
- 0 | line-0004 | ok | Without your voice inside my head
  - Action: No obvious diagnostic issue detected.
- 0 | line-0005 | ok | With words of caution, guilt and fear
  - Action: No obvious diagnostic issue detected.
- 0 | line-0006 | ok | Just one day
  - Action: No obvious diagnostic issue detected.
