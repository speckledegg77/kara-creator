# Testing Checklist

Use this checklist after any change to the timing pipeline, JSON schema, editor, launcher, or export logic.

## Source file checks

Test with:

- isolated vocal MP3
- isolated vocal WAV if supported
- lyrics with explicit `[SECTION]` headings
- lyrics with blank lines between lyric groups
- lyrics with no headings and no blank-line groups
- lyrics with `. . .` instrumental placeholders
- lyrics with `...` and `…` placeholders
- lyrics with repeated lines
- lyrics with contractions such as `I'm`, `you're`, `don't`, `I'd`
- lyrics with punctuation-heavy lines
- lyrics with hyphenated words such as `wide-eyed` and `love-struck`
- lyrics with unusual words that need custom pronunciations

## Pipeline checks

Check that:

- the pipeline starts in `aligner-win`
- the audio file is copied into the run folder
- the clean lyrics file is created
- the line map is created
- stale `kara_<song>*` aligner files are cleaned before rerun
- missing pronunciation errors are readable
- custom pronunciations are loaded
- generated word review JSON has zero word-mapping warnings
- draft JSON is created
- run manifest is created

## Lyric processing checks

Check that:

- clean lyric lines stay in the right order
- explicit section headings become section labels
- blank-line groups become automatic sections
- continuous lyrics are auto-split into sensible sections
- display text keeps apostrophes and punctuation
- alignment text can be normalised separately
- repeated lines remain separate line IDs
- hyphenated words do not cause word-index drift
- `. . .` lines are kept as instrumental placeholders
- instrumental placeholders are not sent to `lyrics-aligner`

## Draft JSON checks

Check that:

- JSON is valid
- every section has an ID and label
- every line has an ID
- every line has text
- every line has start and end times
- no line has a negative time
- line end is after line start
- lines do not overlap unless intentionally flagged
- section start and end times contain their lines
- review flags are present where needed
- instrumental lines have `display_type: "instrumental"`
- instrumental lines have an empty `words` array
- lyric lines have `display_type: "lyric"` or a clear equivalent

## Editor checks

Check that:

- audio plays
- JSON loads
- line cards appear
- selected line follows playback
- clicking a line selects it
- jump works
- play line works
- set start to playhead works
- set end to playhead works
- ripple forward behaves as expected
- anchors stop or guide ripple as intended
- locks stop ripple as intended
- edited JSON downloads correctly
- exported JSON can be reloaded
- instrumental placeholder lines can be selected and edited

## Launcher checks

Check that:

- launcher starts from PowerShell
- browser opens at the local address
- audio upload works
- lyrics upload works
- song name is slugified safely
- pipeline errors are displayed clearly
- missing pronunciation words are shown clearly
- success page shows the generated audio and draft JSON paths
- editor opens from the launcher page

## Export checks

Check that:

- edited JSON exports
- exported JSON can be reloaded
- manual edits are preserved
- anchors and locks are preserved
- optional LRC export later matches JSON line starts

## Quality checks

For each test song, record:

- number of lines
- number of sections
- number of review flags
- number of manual edits needed
- time taken to correct the draft
- whether repeated phrases stayed in the right place
- whether the song is MVP suitable

## Acceptance test for a song

A song is acceptable for the MVP workflow if:

- most lines are roughly aligned
- only a small number of individual lines need manual repair
- repeated phrases can be corrected without redoing the whole song
- instrumental gaps can be represented when needed
- final review takes minutes, not a full manual syncing session

## Regression warning signs

Stop and investigate if:

- word review JSON has word-mapping warnings
- first lines are correct but the rest drifts badly
- repeated phrases are assigned to the wrong place
- hyphenated words shift all later lines
- corrections create overlaps
- section edits damage earlier sections
- exported JSON cannot be loaded again
