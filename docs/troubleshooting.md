# Troubleshooting

Use this when something goes wrong.

## PowerShell says Python is not recognised

Try:

```powershell
py --version
```

If that works, use `py` instead of `python`.

If neither works, reinstall Python and make sure `Add python.exe to PATH` is ticked.

## The wrong Python environment is active

The pipeline currently needs the conda environment:

```powershell
conda activate aligner-win
```

Check where Python is coming from:

```powershell
where python
python --version
```

If you see both `(.venv)` and `(aligner-win)` in your prompt, deactivate the project venv:

```powershell
deactivate
conda activate aligner-win
```

## lyrics-aligner says a word list file already exists

Example error:

```text
AssertionError: file files/kara_new_song_test_word_list.txt exists already
```

Cause:

- a previous failed run left aligner files behind

Fix:

- the updated pipeline should clean these files automatically
- if needed, clean manually:

```powershell
cd C:\Users\mark\kara-creator

Remove-Item ".\alignment_lab\singing-aligners\lyrics-aligner\files\kara_new_song_test*" -Force -ErrorAction SilentlyContinue
Remove-Item ".\alignment_lab\singing-aligners\lyrics-aligner\outputs\kara_new_song_test" -Recurse -Force -ErrorAction SilentlyContinue
```

## The pipeline reports missing pronunciations

Example:

```text
3 words are missing pronunciations
```

Cause:

- the word is not in the pronunciation dictionary
- common examples are names, compound words, unusual spellings, or musical theatre terms

Fix:

1. Open the missing words file shown in the error.
2. Add pronunciations to:

```text
config/custom_pronunciations.json
```

Example:

```json
{
  "lovestruck": "L AH V S T R AH K",
  "unplayed": "AH N P L EY D",
  "wideeyed": "W AY D AY D"
}
```

Then rerun the pipeline.

## Word review JSON has many word-mapping warnings

Cause:

- line-map tokens do not match aligner tokens
- a common cause is hyphenated words, such as `wide-eyed` being treated as `wide` and `eyed` in one place but `wideeyed` in another

Fix:

- make sure the pipeline tokenisation merges hyphenated words for alignment
- rerun the pipeline from the original lyrics

Do not edit the word review JSON by hand to fix this. Fix the parser.

## Instrumental placeholder is sent to the aligner

Cause:

- `. . .`, `...`, or `…` was treated as lyric text

Fix:

- parser should detect placeholder lines before building aligner lyrics
- placeholder lines should become `display_type: "instrumental"`
- placeholder lines should have `words: []`

## PowerShell says FFmpeg is not recognised

FFmpeg is either not installed or not added to PATH.

Check:

```powershell
ffmpeg -version
```

If PowerShell says `ffmpeg is not recognised`, fix the FFmpeg install or PATH.

## The generated timing starts correctly and then drifts

Possible causes:

- lyrics do not match the exact recording
- printed lyric lines do not match sung phrasing
- repeated lines confused the alignment
- long held notes are affecting line ends

Fix:

- check exact lyrics against the recording
- split long printed lines if needed
- use the editor to anchor trusted lines
- use ripple corrections
- add `. . .` placeholders for long non-lyric gaps if useful

## The draft has overlapping lines

Likely cause:

- edits were applied to one line only
- ripple behaviour was not used
- generated timings were too close together

Fix:

- use ripple edit
- anchor or lock trusted lines
- check JSON for start/end errors

## The tool struggles with repeated lines

Repeated lyrics are hard because the same text appears more than once.

Fix:

- keep repeated lines as separate IDs
- use line order, not text, as the source of truth
- add manual anchors around repeated sections
- check flagged repeated areas first

## The vocal file sounds clean but timing is still poor

Possible causes:

- lyrics do not match that exact recording
- lyric lines do not match sung phrases
- there are long held notes or delayed consonants
- there are harmony layers or backing vocals
- there are ad libs not present in the lyric file

Fix:

- check the lyric file line by line
- split phrases more carefully
- use `. . .` for instrumental gaps
- test whether the song is too free or too noisy for the MVP

## The editor works but the exported JSON will not load

Check:

- JSON has no trailing commas
- every object has required fields
- timings are numbers, not strings
- section and line arrays are not empty
- instrumental lines have empty `words` arrays

## Git tries to add audio files

Do not commit audio files.

Run:

```powershell
git status
```

If you see MP3, WAV, source folders, or generated lyric JSON listed, fix `.gitignore` before committing.

If a file was accidentally staged, unstage it:

```powershell
git restore --staged path\to\file.mp3
```
