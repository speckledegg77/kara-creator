# Authoring Workflow

This explains how the tool should work from the user's point of view.

## One song workflow

## Step 1: Prepare the files

Create or obtain:

- isolated vocal audio file
- exact lyrics for the same version
- optional backing track for preview

Use clean lyric text.

Do not include scraped website clutter, song suggestions, annotations, or unrelated text.

## Step 2: Create a project

The tool asks for:

- title
- show key or show name
- version label
- notes

Example:

```text
Title: I Miss the Mountains
Show key: next_to_normal
Version label: isolated vocal test
```

## Step 3: Add source files

Add:

```text
vocals.mp3
lyrics.txt
```

Optional:

```text
backing-track.mp3
```

## Step 4: Review lyric phrases before generation

The tool should show the lyric lines and let the user:

- keep a line
- split a line
- merge two lines
- add a section break
- rename a section

This matters because printed lyric lines are not always sung phrases.

## Step 5: Generate draft timing

The user presses:

```text
Generate draft
```

The backend creates:

```text
working/karaoke.draft.json
```

## Step 6: Review confidence flags

The editor should show:

- high-confidence phrases
- medium-confidence phrases
- low-confidence phrases
- overlap warnings
- repeated-line warnings

The user should not have to listen to every phrase in order.

The editor should guide them to the weak parts first.

## Step 7: Correct timing

The main correction actions are:

- anchor phrase start to playhead
- anchor phrase end to playhead
- shift phrase
- ripple forward
- rescale section
- split phrase
- merge phrase
- mark reviewed

## Step 8: Export final JSON

When reviewed, export:

```text
exports/karaoke.final.json
```

Optional:

```text
exports/karaoke.final.lrc
```

## Draft quality judgement

A draft is good if most correction is section-level or small line-level tweaking.

A draft is poor if the user has to manually sync most lines from scratch.

## Recommended first test song

Use one known test song with:

- clean isolated vocal
- clean exact lyrics
- known earlier timing problems

This lets the team compare new output against earlier rough attempts.

## When to reject a song for MVP

A song may be poor for the first version if it has:

- heavy overlapping vocals
- spoken dialogue mixed with singing
- unclear or missing lyric text
- lots of ad libs
- live recording noise
- very free rubato timing
- long sections with no clear vocal gaps

Do not force poor candidates through the MVP.
