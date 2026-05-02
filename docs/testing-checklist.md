# Testing Checklist

Use this checklist after any change to the timing pipeline, JSON schema, editor, or export logic.

## Source file checks

Test with:

- isolated vocal MP3
- isolated vocal WAV
- lyrics with blank lines between sections
- lyrics with repeated lines
- lyrics with contractions such as `I'm`, `you're`, `don't`
- lyrics with punctuation-heavy lines
- lyrics with a long title or unusual word

## Audio preparation checks

Check that:

- audio loads without crashing
- duration is detected correctly
- prepared WAV is created
- leading silence is handled
- the original source file is preserved
- no audio files are accidentally committed to Git

## Lyric processing checks

Check that:

- clean lyric lines stay in the right order
- blank lines can create section hints
- unwanted empty lines are ignored
- display text keeps apostrophes and punctuation
- alignment text can be normalised separately
- repeated lines remain separate phrase IDs

## Draft JSON checks

Check that:

- JSON is valid
- every phrase has an ID
- every phrase has text
- every phrase has start and end times
- no phrase has a negative time
- phrase end is after phrase start
- phrases do not overlap unless intentionally flagged
- section start and end times contain their phrases
- confidence values are present
- low-confidence phrases are flagged

## Editor checks

Check that:

- audio plays
- waveform displays
- active phrase highlights at the right time
- clicking a phrase jumps to it
- loop current phrase works
- loop current section works
- start anchor to playhead works
- end anchor to playhead works
- ripple forward prevents overlaps
- section shift moves all section phrases together
- section rescale keeps order
- split phrase works
- merge phrase works
- edited JSON downloads correctly

## Export checks

Check that:

- final JSON exports
- exported JSON can be reloaded
- optional LRC exports
- LRC line times match JSON phrase starts
- manual edits are preserved

## Quality checks

For each test song, record:

- number of phrases
- number of low-confidence phrases
- number of manual edits needed
- time taken to correct the draft
- whether the song is MVP suitable

## Acceptance test for a song

A song is acceptable for the MVP workflow if:

- most phrases are roughly aligned
- drift can be fixed by section anchors or rescaling
- only a small number of individual phrases need manual repair
- the final review takes minutes, not a full manual syncing session

## Regression warning signs

Stop and investigate if:

- first lines are correct but the rest drifts badly
- repeated phrases are assigned to the wrong place
- corrections create overlaps
- section edits damage earlier sections
- exported JSON cannot be loaded again
