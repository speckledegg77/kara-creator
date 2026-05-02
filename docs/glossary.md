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

## Confidence score

A number that estimates how reliable a generated timing is.

Low confidence means the editor should ask the user to review it.

## Drift

A timing problem where early lines are correct but later lines gradually move out of sync.

The fix is usually section-based alignment or section rescaling.

## Forced alignment

A process where known text and audio are matched to create timestamps.

This is the core idea behind the project.

## Isolated vocal

An audio file that contains mostly the sung vocal without the full backing track.

This gives clearer timing information than a full mix.

## JSON

A structured data format used by apps.

This project uses JSON as the main karaoke timing format.

## LRC

A simpler lyric timing format often used for karaoke-style lyrics.

It is useful for export, but it is not expressive enough to be the main project format.

## Phrase

A sung unit of lyric timing.

A phrase may be the same as a printed lyric line, but not always.

## Ripple edit

A timing edit where changing one phrase moves later phrases too, so the timeline does not overlap.

## Section

A larger part of a song, such as verse, chorus, bridge, or final chorus.

Sections help prevent timing drift.

## Vocal activity detection

A process that finds parts of the audio where voice is present.
