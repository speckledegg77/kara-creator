# Authoring Workflow

This explains how Kara Creator should work from the user's point of view.

## One song workflow

## Step 1: Prepare the files

Create or obtain:

- isolated vocal audio file
- exact lyrics for the same version
- optional backing track for preview later

Use clean lyric text.

Do not include scraped website clutter, song suggestions, annotations, or unrelated text.

## Step 2: Prepare the lyrics

Exact lyric line breaks matter.

Manual section headings are optional.

The tool should support these lyric formats.

### Option A: Explicit section headings

```text
[OPENING]
First lyric line
Second lyric line

[VERSE]
Third lyric line
Fourth lyric line
```

### Option B: Blank-line groups

```text
First lyric line
Second lyric line

Third lyric line
Fourth lyric line

Fifth lyric line
Sixth lyric line
```

Each blank-line group becomes an automatic section.

### Option C: Continuous lyrics

```text
First lyric line
Second lyric line
Third lyric line
Fourth lyric line
```

The tool should split continuous lyrics into automatic sections of about 8 lines.

## Step 3: Add instrumental placeholders if needed

Use this on a line by itself when you want the karaoke display to show an instrumental gap:

```text
. . .
```

The parser should also accept:

```text
...
…
```

and normalise them to:

```text
. . .
```

This line should appear in the editor and final JSON, but it should not be sent to the aligner.

Example:

```text
I had a dream my life would be
So different from this hell I'm living

. . .

So different now from what it seemed
```

## Step 4: Run the pipeline

Current command-line workflow:

```powershell
conda activate aligner-win
cd C:\Users\mark\kara-creator

python .\tools\run_lyrics_aligner_pipeline.py `
  --audio ".\incoming\new-song-test\vocals.mp3" `
  --lyrics ".\incoming\new-song-test\lyrics.txt" `
  --name "new_song_test"
```

Expected outputs:

```text
outputs\new_song_test-word-review-lyrics-aligner.json
outputs\new_song_test-draft-lyrics-aligner-v3.json
alignment_lab\runs\new_song_test\new_song_test-run-manifest.json
```

## Step 5: Open the draft editor

Open:

```text
tools/edit_karaoke_draft.html
```

Load:

```text
alignment_lab\runs\<song>\audio\<song>.mp3
outputs\<song>-draft-lyrics-aligner-v3.json
```

## Step 6: Review the draft

Use Follow playback to watch the active line move through the song.

Check:

- line starts
- line ends
- repeated lyric phrases
- long held notes
- flagged lines
- `. . .` instrumental placeholders

The editor should guide attention to likely weak lines.

## Step 7: Correct timing

Main correction actions:

- jump to line
- play line
- set line start to playhead
- set line end to playhead
- ripple forward
- anchor trusted lines
- lock lines to stop ripple

Future correction actions:

- shift whole section
- rescale section
- mark line reviewed
- loop current line
- loop current section

## Step 8: Export edited JSON

When reviewed, export edited JSON from the editor.

Store the edited file in `outputs/` if you want to keep it locally.

Be careful before committing edited files, because they may contain full copyrighted lyrics.

## Draft quality judgement

A draft is good if most correction is small line-level tweaking.

A draft is poor if the user has to manually sync most lines from scratch.

## When to reject a song for MVP

A song may be poor for the first version if it has:

- heavy overlapping vocals
- spoken dialogue mixed with singing
- unclear or missing lyric text
- lots of ad libs
- live recording noise
- very free rubato timing
- long sections where the sung lyrics do not match the supplied text

Do not force poor candidates through the MVP.
