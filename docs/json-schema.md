# Karaoke JSON Schema

This document defines the proposed canonical JSON shape for exported karaoke timing files.

The schema may change during development, but changes should be deliberate.

## Core principles

- Use milliseconds for all timings.
- Store sections as first-class objects.
- Store phrases inside sections.
- Keep display text separate from alignment data if needed.
- Include confidence and flags.
- Support future word timing without requiring it in MVP.

## Example JSON

```json
{
  "version": 1,
  "title": "I Miss the Mountains",
  "showKey": "next_to_normal",
  "versionLabel": "isolated vocal test",
  "sourceType": "isolated_vocal",
  "timingMode": "phrase",
  "generatedBy": "karaoke-authoring-tool-mvp",
  "audioReference": {
    "authoringSource": "source/vocals.wav",
    "playbackSource": null,
    "durationMs": 244793
  },
  "sections": [
    {
      "id": "s001",
      "label": "Verse 1",
      "startMs": 8200,
      "endMs": 39200,
      "confidence": 0.86,
      "phrases": [
        {
          "id": "p001",
          "text": "There was a time when I flew higher",
          "startMs": 8420,
          "endMs": 12560,
          "confidence": 0.91,
          "words": [],
          "flags": []
        },
        {
          "id": "p002",
          "text": "Was a time the wild girl running free",
          "startMs": 15240,
          "endMs": 18810,
          "confidence": 0.78,
          "words": [],
          "flags": ["low_confidence"]
        }
      ]
    }
  ]
}
```

## Top-level fields

### `version`

Schema version number.

Start with `1`.

### `title`

Song title shown to the author and later to the quiz app if needed.

### `showKey`

Optional show key.

For musical theatre content, this should later match the quiz app's show key convention where possible.

### `versionLabel`

Optional label for the recording or source.

Examples:

- `Original Broadway Cast`
- `London revival`
- `isolated vocal test`

### `sourceType`

Expected values:

- `isolated_vocal`
- `full_mix`
- `manual`
- `unknown`

MVP should prefer `isolated_vocal`.

### `timingMode`

Expected values:

- `phrase`
- `line`
- `word`

MVP should use `phrase` or `line`.

### `generatedBy`

Tool or pipeline name.

Useful for later debugging.

### `audioReference`

Information about source audio.

Do not assume these paths are valid inside the quiz app.

They are authoring references.

## Section fields

### `id`

Stable section ID.

Example: `s001`.

### `label`

Human-readable section name.

Examples:

- `Verse 1`
- `Chorus 1`
- `Bridge`
- `Final chorus`

### `startMs`

Section start time.

### `endMs`

Section end time.

### `confidence`

Overall confidence for the section.

This can be the average or weighted average of phrase confidence values.

### `phrases`

Timed lyric phrases in that section.

## Phrase fields

### `id`

Stable phrase ID.

Example: `p001`.

### `text`

Display text for the lyric phrase.

### `startMs`

Phrase start time.

### `endMs`

Phrase end time.

### `confidence`

Number from `0` to `1`.

High confidence does not mean perfect. It means the tool thinks the timing is likely usable.

### `words`

Optional word timing array.

MVP can leave this empty.

Example future shape:

```json
[
  { "text": "There", "startMs": 8420, "endMs": 8780 },
  { "text": "was", "startMs": 8790, "endMs": 9060 }
]
```

### `flags`

List of review flags.

Examples:

- `low_confidence`
- `overlap`
- `too_short`
- `too_long`
- `repeated_phrase`
- `needs_review`
- `manual_edit`

## Editing metadata

Later versions may add:

```json
"review": {
  "status": "draft",
  "reviewedAt": null,
  "reviewedBy": null
}
```

Do not add this until the editor needs it.

## LRC export rule

LRC should be generated from the JSON, not edited as the source of truth.

The JSON remains canonical.
