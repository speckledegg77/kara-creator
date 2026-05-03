# Glossary

## Alignment

Matching known lyric text to moments in an audio file.

This is different from transcription.

## Authoring source

The audio used to create timings.

For this project, the best authoring source is usually an isolated vocal.

## Backing track

The audio that may be used for karaoke playback.

This may be different from the isolated vocal used for authoring.

## Blank-line section

An automatic section created from a group of lyric lines separated by blank lines.

This reduces the need to type headings like `[VERSE]` manually.

## Confidence score

A number or label that estimates how reliable a generated timing is.

Low confidence means the editor should ask the user to review it.

## Custom pronunciation

A manually supplied phoneme spelling for a word the pronunciation dictionary does not know.

Example:

```json
"wideeyed": "W AY D AY D"
```

## Drift

A timing problem where early lines are correct but later lines gradually move out of sync.

The fix may involve anchors, ripple edits, section tools, or a better alignment method.

## Forced alignment

A process where known text and audio are matched to create timestamps.

This is the core idea behind the project.

## Instrumental placeholder

A non-lyric line used to show that there is an instrumental or non-vocal gap.

Accepted input forms:

```text
. . .
...
…
```

Canonical display form:

```text
. . .
```

Instrumental placeholders should appear in the editor and final JSON, but should not be sent to the aligner.

## Isolated vocal

An audio file that contains mostly the sung vocal without the full backing track.

This gives clearer timing information than a full mix.

## JSON

A structured data format used by apps.

This project uses JSON as the main karaoke timing format.

## Karaoke-draft-v3

The current working draft JSON format created by Kara Creator.

It stores sections, timed lines, review flags, manual edit markers, anchors, locks, and word timing diagnostics.

## Line map

A JSON file that maps lyric lines to word indexes.

It lets the converter rebuild line timings from word-onset output.

## LRC

A simpler lyric timing format often used for karaoke-style lyrics.

It is useful for export, but it is not expressive enough to be the main project format.

## lyrics-aligner

The current default singing-specific alignment engine used by Kara Creator.

It produces word onset timings from an audio file and known lyrics.

## MFA

Montreal Forced Aligner.

It was tested earlier, but it struggled with sung vocals and held notes in this project.

## Phrase

A sung unit of lyric timing.

In the current MVP, a phrase is usually the same as a lyric line.

## Ripple edit

A timing edit where changing one line moves later lines too, so the timeline does not overlap.

## Section

A larger part of a song.

Sections may come from explicit headings, blank-line groups, or automatic grouping.

They help editor navigation and future section tools.

## Vocal activity detection

A process that finds parts of the audio where voice is present.

It may be useful later for confidence checks or instrumental gap detection.

## Word onset

The start time of a word.

The current singing aligner is strongest at word starts. Word endings are less reliable and may be inferred for display.

## Word review JSON

A diagnostic JSON file used to inspect word and line starts before building or reviewing the draft karaoke JSON.
