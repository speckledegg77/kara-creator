# Karaoke JSON Schema

This document describes the current working draft schema and the intended final export direction.

The current working file is `karaoke-draft-v3`. It is an authoring draft format, not necessarily the final quiz app format.

## Current draft principles

- JSON is the source of truth during authoring.
- Store sections as first-class objects.
- Store timed lines inside sections.
- Preserve display text.
- Store word starts where available for diagnostics.
- Store review flags.
- Store manual edit markers.
- Support future instrumental display lines.

## Current timing unit

The current `karaoke-draft-v3` files use seconds as numbers:

```json
"start": 12.81,
"end": 17.584
```

A future final export for the quiz app may convert timings to milliseconds. Do not mix units inside one file.

## Current top-level shape

```json
{
  "schema_version": "karaoke-draft-v3",
  "created_by": "kara-creator lyrics-aligner draft builder",
  "source": {
    "word_review_json": "outputs/song-word-review-lyrics-aligner.json",
    "audio_file": "incoming/song/vocals.mp3",
    "lyrics_file": "incoming/song/lyrics.txt",
    "audio_duration_seconds": 203.888
  },
  "alignment": {
    "mode": "singing-specific-word-starts-to-line-draft",
    "status": "draft",
    "primary_aligner": "lyrics-aligner",
    "line_count": 34,
    "section_count": 6,
    "settings": {},
    "review_flag_count": 4,
    "review_flags": []
  },
  "sections": [],
  "editor_notes": []
}
```

## Section shape

```json
{
  "id": "verse-one-002",
  "label": "VERSE ONE",
  "start": 38.778,
  "end": 69.36,
  "lines": []
}
```

Section labels may come from:

- explicit `[SECTION]` headings
- blank-line lyric groups
- automatic grouping when no headings or blank groups exist

## Lyric line shape

```json
{
  "id": "line-0005",
  "display_type": "lyric",
  "text": "I'd tell her only fools rush in and think the heart can lead",
  "start": 38.778,
  "end": 45.472,
  "word_start": 38.928,
  "last_word_start": 43.488,
  "confidence": "draft",
  "locked": false,
  "anchor": false,
  "timing_source": "lyrics-aligner-word-starts",
  "review_flags": [],
  "words": [],
  "edited_manually": false
}
```

## Instrumental placeholder line shape

A lyric input line containing only `. . .`, `...`, or `…` should become:

```json
{
  "id": "line-0012",
  "display_type": "instrumental",
  "text": ". . .",
  "start": 72.5,
  "end": 84.2,
  "confidence": "draft",
  "locked": false,
  "anchor": false,
  "timing_source": "instrumental-placeholder-inferred",
  "review_flags": ["instrumental_timing_needs_review"],
  "words": [],
  "edited_manually": false
}
```

Rules:

- It should display as `. . .`.
- It should not be sent to `lyrics-aligner`.
- It should not require a pronunciation.
- It should have an empty `words` array.
- It should be editable in the same editor as lyric lines.

## Word shape

The current draft can store words from `lyrics-aligner`:

```json
{
  "id": "word-0001",
  "text": "if",
  "start": 12.96,
  "end": 13.152,
  "source": "lyrics-aligner-word-start"
}
```

Important:

- Word starts are useful.
- Word ends are inferred for display and review.
- Do not treat inferred word ends as final sung word endings.

## Review flags

Examples:

- `long_tail_after_last_word_needs_review`
- `very_short_display_duration_needs_review`
- `instrumental_timing_needs_review`
- `instrumental_at_start_needs_review`
- `instrumental_at_end_needs_review`
- `manual_edit`
- `overlap`
- `too_short`
- `too_long`
- `repeated_phrase`
- `needs_review`

## Future final export direction

The final quiz app format may be cleaner than the draft format.

A final export may:

- convert seconds to milliseconds
- remove diagnostic word timing if not needed
- keep only reviewed line timings
- keep `display_type`
- keep section structure
- keep enough source metadata for traceability

## LRC export rule

LRC should be generated from the JSON, not edited as the source of truth.

The JSON remains canonical.
